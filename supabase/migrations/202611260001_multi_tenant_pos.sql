begin;

-- Multiempresa v1. Todos los cambios son aditivos para conservar el comercio actual.
alter table organizations add column if not exists slug text;
alter table organizations add column if not exists status text not null default 'active';
alter table organizations add column if not exists created_by uuid references auth.users(id);

create table if not exists platform_admins (
    auth_user_id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists organization_memberships (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    auth_user_id uuid references auth.users(id) on delete cascade,
    email text not null,
    username text not null default '',
    role text not null check (role in ('store_admin', 'cashier')),
    status text not null default 'active' check (status in ('invited','active','disabled')),
    created_at timestamptz not null default now(),
    unique (organization_id, email),
    unique (organization_id, auth_user_id)
);
create index if not exists memberships_auth_idx on organization_memberships(auth_user_id) where status='active';

create table if not exists organization_invitations (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    email text not null,
    role text not null check (role in ('store_admin', 'cashier')),
    token_hash text not null unique,
    status text not null default 'pending' check (status in ('pending','accepted','revoked','expired')),
    delivery_status text not null default 'queued',
    delivery_attempts integer not null default 0,
    invited_by uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null default now() + interval '48 hours',
    accepted_at timestamptz
);
create unique index if not exists one_pending_invitation
on organization_invitations(organization_id, email, role) where status='pending';

create table if not exists sale_operations (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id),
    request_id text not null,
    factura bigint not null,
    caja_id bigint not null references caja(id),
    customer_id bigint references clientes(id),
    total numeric(14,2) not null,
    payment_method text not null,
    created_by uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    unique (organization_id, request_id),
    unique (organization_id, factura)
);
alter table ventas add column if not exists operation_id uuid references sale_operations(id);
alter table ventas add column if not exists product_id bigint references inventario(id);

-- La ficha es exactamente una por comercio. Los nombres pueden repetirse.
update empresa set nombre='Mi negocio' where nombre is null or btrim(nombre)='';
create unique index if not exists one_company_profile_per_org on empresa(organization_id);

-- Migra perfiles existentes sin cambiar sus identificadores ni datos comerciales.
insert into organization_memberships(organization_id, auth_user_id, email, username, role, status)
select organization_id, auth_user_id, lower(coalesce(email, username || '@local.invalid')),
       username,
       case when lower(rol) in ('administrador','admin') then 'store_admin' else 'cashier' end,
       case when activo then 'active' else 'disabled' end
from usuarios
on conflict (organization_id, email) do update
set auth_user_id=coalesce(organization_memberships.auth_user_id, excluded.auth_user_id),
    username=excluded.username, role=excluded.role, status=excluded.status;

-- RLS para el rol DATABASE_URL. Nunca usar postgres/service_role como DATABASE_URL.
create or replace function private.request_organization_id() returns uuid
language sql stable as $$
  select nullif(current_setting('app.organization_id', true), '')::uuid
$$;
create or replace function private.request_auth_user_id() returns uuid
language sql stable as $$
  select nullif(current_setting('app.auth_user_id', true), '')::uuid
$$;
create or replace function private.request_is_platform_admin() returns boolean
language sql stable as $$
  select coalesce(nullif(current_setting('app.is_platform_admin', true), '')::boolean, false)
$$;
create or replace function private.can_access_organization(target uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select private.request_is_platform_admin()
      or (target=private.request_organization_id() and exists (
          select 1 from public.organization_memberships m
          where m.organization_id=target
            and m.auth_user_id=private.request_auth_user_id()
            and m.status='active'))
$$;

create or replace function private.accept_organization_invitation(
  requested_token_hash text, requested_auth_user_id uuid, requested_email text
) returns uuid
language plpgsql security definer set search_path='' as $$
declare invitation public.organization_invitations%rowtype;
begin
  if requested_auth_user_id is distinct from private.request_auth_user_id() then
    raise exception 'Identidad de invitación inválida';
  end if;
  select * into invitation from public.organization_invitations
  where token_hash=requested_token_hash and status='pending' and expires_at>now()
  for update;
  if invitation.id is null or lower(invitation.email)<>lower(btrim(requested_email)) then
    raise exception 'Invitación inválida o expirada';
  end if;
  insert into public.organization_memberships
    (organization_id, auth_user_id, email, username, role, status)
  values (invitation.organization_id, requested_auth_user_id, lower(btrim(requested_email)),
          split_part(requested_email, '@', 1), invitation.role, 'active')
  on conflict (organization_id, email) do update
  set auth_user_id=excluded.auth_user_id, role=excluded.role, status='active';
  update public.organization_invitations set status='accepted', accepted_at=now()
  where id=invitation.id;
  return invitation.organization_id;
end $$;

-- NOLOGIN evita guardar una contraseña en Git. Producción crea pos_app_login y le otorga este rol.
do $$ begin
  if not exists (select 1 from pg_roles where rolname='pos_app') then
    create role pos_app nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;

do $$
declare table_name text;
begin
  foreach table_name in array array[
    'empresa','usuarios','roles','moneda','categorias','sucursal','impuestos','clientes',
    'proveedores','inventario','caja','ventas','cotizaciones','pedidos','gastos',
    'organization_memberships','organization_invitations','sale_operations'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('alter table public.%I force row level security', table_name);
    execute format('drop policy if exists app_tenant_access on public.%I', table_name);
    execute format(
      'create policy app_tenant_access on public.%I for all to pos_app using (private.can_access_organization(organization_id)) with check (private.can_access_organization(organization_id))',
      table_name);
  end loop;
end $$;

-- El login todavía no conoce la empresa: solo puede descubrir su propia membresía.
drop policy if exists app_tenant_access on organization_memberships;
create policy app_tenant_access on organization_memberships for all to pos_app
using (
  private.request_is_platform_admin()
  or auth_user_id=private.request_auth_user_id()
  or private.can_access_organization(organization_id)
)
with check (
  private.request_is_platform_admin()
  or auth_user_id=private.request_auth_user_id()
  or private.can_access_organization(organization_id)
);

grant usage on schema public, private to pos_app;
grant select, insert, update, delete on all tables in schema public to pos_app;
grant usage, select on all sequences in schema public to pos_app;
grant execute on function private.request_organization_id() to pos_app;
grant execute on function private.request_auth_user_id() to pos_app;
grant execute on function private.request_is_platform_admin() to pos_app;
grant execute on function private.can_access_organization(uuid) to pos_app;
grant execute on function private.accept_organization_invitation(text, uuid, text) to pos_app;

-- Registros huérfanos: la migración se detiene para evitar asignarlos a ciegas.
do $$
declare table_name text; orphan_count bigint;
begin
  foreach table_name in array array['empresa','usuarios','inventario','caja','ventas','clientes','proveedores','pedidos','gastos','cotizaciones'] loop
    execute format('select count(*) from public.%I where organization_id is null', table_name) into orphan_count;
    if orphan_count > 0 then
      raise exception 'Tabla % contiene % registros sin empresa; revisar antes de desplegar', table_name, orphan_count;
    end if;
  end loop;
end $$;

commit;

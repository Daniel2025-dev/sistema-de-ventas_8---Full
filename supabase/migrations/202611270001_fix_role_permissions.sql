begin;

-- Los permisos son un catálogo global y deben ser legibles por el rol servidor.
drop policy if exists permisos_app_read on public.permisos;
create policy permisos_app_read on public.permisos
for select to pos_app using (true);

-- Cada asignación pertenece indirectamente a una empresa a través de roles.
drop policy if exists permisos_rol_app_access on public.permisos_rol;
create policy permisos_rol_app_access on public.permisos_rol
for all to pos_app
using (
  exists (
    select 1 from public.roles r
    where r.id=permisos_rol.id_rol
      and private.can_access_organization(r.organization_id)
  )
)
with check (
  exists (
    select 1 from public.roles r
    where r.id=permisos_rol.id_rol
      and private.can_access_organization(r.organization_id)
  )
);

-- Repara almacenes existentes sin borrar personalizaciones: solo completa los
-- permisos operativos que permiten trabajar a Supervisor y Vendedor.
insert into public.permisos_rol(id_rol, id_permiso)
select r.id, p.id
from public.roles r
join public.permisos p on (
  lower(r.nombre)='administrador'
  or (
    lower(r.nombre) in ('supervisor','vendedor')
    and p.modulo in (
      'ventas','cotizaciones','inventario','clientes','proveedor','pedidos',
      'reportes','gastos','informacion'
    )
  )
)
where lower(r.nombre) in ('administrador','supervisor','vendedor')
on conflict do nothing;

commit;

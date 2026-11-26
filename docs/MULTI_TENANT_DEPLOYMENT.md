# POS multiempresa: preparación y despliegue

Este cambio se entrega en local. No ejecuta migraciones ni modifica Render o Supabase de producción.

## Respaldo obligatorio

En Supabase, copie la cadena directa de base de datos (no la del pooler) y ejecute:

```bash
mkdir -p respaldos
pg_dump --format=custom --no-owner --file="respaldos/antes_multiempresa_$(date +%F_%H%M).dump" "$DATABASE_URL_DIRECT"
pg_dump --schema-only --no-owner --file="respaldos/esquema_antes_multiempresa_$(date +%F_%H%M).sql" "$DATABASE_URL_DIRECT"
```

Registre antes y después los totales por tabla y empresa:

```sql
select organization_id, count(*) from usuarios group by 1;
select organization_id, count(*), coalesce(sum(stock),0) from inventario group by 1;
select organization_id, count(*), coalesce(sum(total),0) from ventas group by 1;
select organization_id, count(*), coalesce(sum(total_en_caja),0) from caja group by 1;
select organization_id, count(*) from empresa group by 1;
```

La migración se detiene si encuentra `organization_id is null`. No asigne esos registros sin revisar a qué comercio pertenecen.

## Ensayo y migración

```bash
cd "/home/daniel/Documentos/Proyectos/Administración sistema de ventas almacenes/sistema de ventas_8 - Full"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
psql "$DATABASE_URL_PRUEBA" -v ON_ERROR_STOP=1 -f supabase/migrations/202611150001_initial_sales_system.sql
psql "$DATABASE_URL_PRUEBA" -v ON_ERROR_STOP=1 -f supabase/migrations/202611150002_public_company_logos.sql
psql "$DATABASE_URL_PRUEBA" -v ON_ERROR_STOP=1 -f supabase/migrations/202611260001_multi_tenant_pos.sql
```

Para recuperar el respaldo en una base vacía:

```bash
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL_DIRECT" respaldos/antes_multiempresa_FECHA_HORA.dump
```

## Rol seguro para `DATABASE_URL`

No use `postgres`, `service_role` ni un rol con `BYPASSRLS`. Después de aplicar la migración, cree una contraseña fuera de Git:

```sql
create role pos_app_login login password 'CONTRASENA_ALEATORIA_LARGA' nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
grant pos_app to pos_app_login;
```

Use la URL de `pos_app_login` como `DATABASE_URL` de Render. El pool reutilizado recibe variables `SET LOCAL` en cada transacción, por lo que una sesión no hereda el comercio anterior.

## Administrador inicial

1. Cree su cuenta normalmente en Supabase Auth.
2. Copie su UUID desde Authentication > Users.
3. En SQL Editor ejecute una sola vez:

```sql
insert into platform_admins(auth_user_id) values ('SU_UUID_DE_AUTH') on conflict do nothing;
```

La cuenta Google usada para administrar Render no participa en el login del POS.

## Flujo desde el POS

1. **Alta de almacén:** inicie con el administrador de plataforma, complete correo y nombre opcional y pulse **Crear almacén e invitación**. Sin nombre se crea como `Mi negocio`.
2. **Invitar dueña:** el paso anterior crea una invitación `store_admin` ligada al correo y UUID del comercio. En prueba local copie el enlace mostrado. En producción debe configurarse el envío de Supabase Auth.
3. **Invitar cajero:** la dueña entra a **Usuarios**, escribe correo, usuario y rol `Vendedor`, y pulsa **Guardar**. Se crea una invitación `cashier`, no una contraseña visible o compartida.

## Pendiente antes de producción

- Supabase Auth: URL pública y redirects de invitación/recuperación; plantilla SMTP si se supera el correo gratuito; validación manual de aceptación desde el enlace.
- Render: reemplazar `DATABASE_URL` por el usuario `pos_app_login`; definir `INVITE_DELIVERY_MODE=supabase`; conservar `SUPABASE_SECRET_KEY` solo en variables secretas del servidor.
- Validar en dos navegadores el logo, cierre de sesión, comprobante PDF y recuperación de contraseña.

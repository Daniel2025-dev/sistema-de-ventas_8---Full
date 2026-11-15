# Sistema de ventas web

Punto de venta responsivo desarrollado con Python y Flet. Puede ejecutarse localmente con SQLite o publicarse como aplicación web privada con Supabase Auth y PostgreSQL.

## Modulos principales

- Ventas y caja
- Cotizaciones
- Inventario
- Clientes
- Proveedores
- Pedidos
- Reportes
- Configuracion
- Usuarios

## Arquitectura de producción

- Flet dinámico alojado en un servidor con soporte WebSocket.
- Supabase Auth para credenciales y sesiones.
- Supabase PostgreSQL como base central compartida.
- Acceso a datos únicamente desde el servidor Flet; las claves secretas nunca llegan al navegador.
- Esquema con organizaciones, roles, RLS y operaciones críticas transaccionales.

## Instalación local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Ejecucion

```bash
python3 index.py
```

La ejecución local conserva `database.db` y sirve para desarrollo. Para probar la versión web:

```bash
flet run --web --host 0.0.0.0 --port 8000 index.py
```

Desde otro dispositivo de la misma red se accede mediante `http://IP-DEL-PC:8000`.

## Configuración de Supabase

1. Crear un proyecto en Supabase.
2. Ejecutar `supabase/migrations/202611150001_initial_sales_system.sql` en el SQL Editor o mediante Supabase CLI.
3. Copiar `.env.example` a `.env` y completar las cuatro variables de Supabase/PostgreSQL.
4. Crear el administrador inicial:

```bash
BOOTSTRAP_ADMIN_PASSWORD='CONTRASEÑA-SEGURA' \
python scripts/bootstrap_admin.py --email admin@empresa.cl --username administrador
```

5. Migrar la base SQLite existente:

```bash
python scripts/migrate_sqlite_to_supabase.py
```

El migrador no copia contraseñas antiguas en texto plano. Los usuarios deben crearse o vincularse con Supabase Auth.

## Despliegue con Docker

El `Dockerfile` inicia la aplicación web en `0.0.0.0` y utiliza la variable `PORT` del proveedor de alojamiento. El servicio debe admitir conexiones WebSocket persistentes. Configure allí las variables de `.env`; no suba el archivo al repositorio.

```bash
docker build -t sistema-ventas .
docker run --env-file .env -p 8000:8000 sistema-ventas
```

## Notas

La base local, `.env`, el entorno virtual y los PDF generados no se versionan. En producción, las imágenes y comprobantes deberían almacenarse en Supabase Storage en lugar del disco efímero del servidor.

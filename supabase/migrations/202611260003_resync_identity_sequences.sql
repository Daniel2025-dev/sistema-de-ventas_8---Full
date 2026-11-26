begin;

-- Los datos iniciales se cargaron con IDs explícitos. Sincroniza todas las
-- identidades para que el siguiente INSERT nunca reutilice un ID existente.
do $$
declare
  table_name text;
  sequence_name text;
  next_id bigint;
begin
  foreach table_name in array array[
    'empresa', 'usuarios', 'roles', 'permisos', 'moneda', 'categorias',
    'sucursal', 'impuestos', 'clientes', 'proveedores', 'inventario',
    'caja', 'ventas', 'cotizaciones', 'pedidos', 'gastos'
  ] loop
    sequence_name := pg_get_serial_sequence('public.' || table_name, 'id');
    if sequence_name is not null then
      execute format('select coalesce(max(id), 0) + 1 from public.%I', table_name)
        into next_id;
      perform setval(sequence_name, next_id, false);
    end if;
  end loop;
end $$;

commit;

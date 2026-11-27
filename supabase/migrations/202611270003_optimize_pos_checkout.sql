-- Indices for the POS hot path. Every key starts with organization_id so
-- lookups remain isolated and efficient as more stores are added.
create index if not exists inventario_org_nombre_idx
on public.inventario (organization_id, nombre);

create index if not exists ventas_org_factura_desc_idx
on public.ventas (organization_id, factura desc)
include (cliente, total, fecha, hora, cajero);

create index if not exists clientes_org_nombre_idx
on public.clientes (organization_id, nombre);

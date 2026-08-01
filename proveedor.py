import flet as ft

from flet_utils import DOCUMENT_TYPES, FieldSpec, SimpleCrudModule


class Proveedor(SimpleCrudModule):
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.user = user
        super().__init__(
            page=page,
            title="Proveedor",
            subtitle="Gestiona la información de tus proveedores de manera eficiente.",
            table_name="proveedores",
            search_field="nombre",
            fields=[
                FieldSpec("nombre", "Nombre"),
                FieldSpec("tipo_id", "Tipo de ID", kind="dropdown", options=DOCUMENT_TYPES),
                FieldSpec("identificacion", "Numero de ID"),
                FieldSpec("celular", "Celular"),
                FieldSpec("direccion", "Direccion"),
                FieldSpec("correo", "Correo"),
            ],
        )

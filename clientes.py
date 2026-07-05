import flet as ft

from flet_utils import DOCUMENT_TYPES, FieldSpec, SimpleCrudModule


class Clientes(SimpleCrudModule):
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.user = user
        super().__init__(
            page=page,
            title="Clientes",
            subtitle="Administra la base de clientes con una vista mas limpia y directa.",
            table_name="clientes",
            search_field="nombre",
            delete_pin="1234567890",
            fields=[
                FieldSpec("nombre", "Nombre"),
                FieldSpec("tipo_id", "Tipo de ID", kind="dropdown", options=DOCUMENT_TYPES),
                FieldSpec("cedula", "Numero de ID"),
                FieldSpec("celular", "Celular"),
                FieldSpec("direccion", "Direccion"),
                FieldSpec("correo", "Correo"),
            ],
        )

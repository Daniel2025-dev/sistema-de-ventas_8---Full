import datetime

import flet as ft

from flet_utils import FieldSpec, SimpleCrudModule


class Gastos(SimpleCrudModule):
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.user = user
        super().__init__(
            page=page,
            title="Gastos",
            subtitle="Registro simple de egresos con fecha y valor en la misma base existente.",
            table_name="gastos",
            search_field="concepto",
            id_field="ID",
            fields=[
                FieldSpec("concepto", "Concepto"),
                FieldSpec("valor", "Valor"),
                FieldSpec("entidad", "Entidad"),
                FieldSpec("fecha", "Fecha"),
            ],
        )
        fecha_control = self.form_controls["fecha"]
        if isinstance(fecha_control, ft.TextField):
            fecha_control.value = datetime.datetime.now().strftime("%d-%m-%Y")

import flet as ft

from flet_utils import DEFAULT_COMPANY_LOGO, PALETTE, get_company_info, image_base64, page_title, shell_card


class Informacion:
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.page = page
        self.user = user
        self.company = get_company_info()

    def build(self) -> ft.Control:
        company_logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)
        brand_logo = image_base64(DEFAULT_COMPANY_LOGO)
        return ft.Column(
            [
                page_title(
                    "About Us",
                    "Informacion institucional presentada con un estilo claro y contemporaneo.",
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "lg": 5},
                            content=shell_card(
                                ft.Column(
                                    [
                                        ft.Container(
                                            height=260,
                                            alignment=ft.Alignment(0, 0),
                                            content=ft.Image(
                                                src=company_logo,
                                                height=260,
                                                fit="contain",
                                            )
                                            if company_logo
                                            else ft.Icon(ft.Icons.STOREFRONT, size=80),
                                        ),
                                        ft.Text(
                                            self.company["nombre"],
                                            size=24,
                                            weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        ft.Text(
                                            self.company["direccion"],
                                            color=PALETTE["muted"],
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        ft.Text(
                                            self.company["telefono"],
                                            color=PALETTE["muted"],
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        ft.Text(
                                            self.company["email"],
                                            color=PALETTE["muted"],
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=12,
                                ),
                                expand=True,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "lg": 7},
                            content=shell_card(
                                ft.Column(
                                    [
                                        ft.Text(
                                            "Nuestra propuesta",
                                            size=22,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            "La aplicacion fue reorganizada hacia Flet para ofrecer una experiencia mas moderna, "
                                            "limpia y coherente con un punto de venta actual, manteniendo la base de datos, "
                                            "las imagenes y el flujo funcional del proyecto.",
                                            color=PALETTE["text"],
                                        ),
                                        ft.Container(
                                            height=160,
                                            alignment=ft.Alignment(-1, 0),
                                            content=ft.Image(
                                                src=brand_logo,
                                                height=160,
                                                fit="contain",
                                            )
                                            if brand_logo
                                            else ft.Icon(ft.Icons.AUTO_AWESOME, size=64),
                                        ),
                                        ft.Text(
                                            "Software creado por Daniel Flores @ 2026",
                                            color=PALETTE["muted"],
                                        ),
                                    ],
                                    spacing=18,
                                ),
                                expand=True,
                            ),
                        ),
                    ]
                ),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
        )

import unittest

import flet as ft

from flet_utils import PALETTE, apply_visual_theme


class ButtonFeedbackTests(unittest.TestCase):
    def test_save_action_uses_success_states(self):
        button = ft.ElevatedButton("Guardar")

        apply_visual_theme(button)

        self.assertEqual(button.style.bgcolor[ft.ControlState.DEFAULT], PALETTE["success"])
        self.assertEqual(button.style.bgcolor[ft.ControlState.HOVERED], PALETTE["success_hover"])
        self.assertEqual(button.style.bgcolor[ft.ControlState.PRESSED], PALETTE["success_pressed"])
        self.assertTrue(button.style.enable_feedback)

    def test_delete_action_uses_danger_states(self):
        button = ft.OutlinedButton("Eliminar")

        apply_visual_theme(button)

        self.assertEqual(button.style.color[ft.ControlState.DEFAULT], PALETTE["danger"])
        self.assertEqual(button.style.bgcolor[ft.ControlState.HOVERED], PALETTE["danger_soft"])
        self.assertEqual(button.style.bgcolor[ft.ControlState.PRESSED], PALETTE["danger"])

    def test_neutral_action_uses_primary_states(self):
        button = ft.OutlinedButton("Siguiente")

        apply_visual_theme(button)

        self.assertEqual(button.style.color[ft.ControlState.DEFAULT], PALETTE["primary"])
        self.assertEqual(button.style.bgcolor[ft.ControlState.PRESSED], PALETTE["primary"])
        self.assertEqual(button.style.animation_duration, 110)

    def test_icon_action_stays_compact(self):
        button = ft.IconButton(ft.Icons.REFRESH_ROUNDED)

        apply_visual_theme(button)

        self.assertEqual(button.width, 52)
        self.assertEqual(button.height, 52)
        self.assertEqual(button.style.padding, 8)

    def test_dropdown_keeps_fluid_width_and_matching_menu(self):
        dropdown = ft.Dropdown(
            label="Producto",
            options=[ft.dropdown.Option("Arroz 1 kg")],
        )

        apply_visual_theme(dropdown)

        self.assertIsNone(dropdown.width)
        self.assertIsNone(dropdown.menu_width)


if __name__ == "__main__":
    unittest.main()

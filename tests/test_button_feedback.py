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


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import Mock, patch

import supabase_service


class PasswordRecoveryTests(unittest.TestCase):
    def test_render_url_is_used_as_recovery_redirect(self):
        client = Mock()
        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_PUBLISHABLE_KEY": "public-key",
                    "RENDER_EXTERNAL_URL": "https://pos.example.com",
                },
                clear=False,
            ),
            patch.object(supabase_service, "_client", return_value=client),
            patch.dict(os.environ, {"PUBLIC_APP_URL": ""}),
        ):
            supabase_service.request_password_recovery(" User@Example.com ")

        client.auth.reset_password_for_email.assert_called_once_with(
            "User@Example.com",
            options={"redirect_to": "https://pos.example.com"},
        )


if __name__ == "__main__":
    unittest.main()

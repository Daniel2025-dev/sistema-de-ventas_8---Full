from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from supabase_service import admin_create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea el administrador inicial")
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if len(password) < 8:
        sys.exit("Defina BOOTSTRAP_ADMIN_PASSWORD con al menos 8 caracteres")
    user_id = admin_create_user(args.email, password, args.username, "Administrador")
    print(f"Administrador creado correctamente: {user_id}")


if __name__ == "__main__":
    main()

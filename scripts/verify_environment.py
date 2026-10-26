#!/usr/bin/env python3
"""Validate required runtime configuration without exposing secret values."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_VARIABLES = (
    "POSTGRES_ADMIN_USER",
    "POSTGRES_ADMIN_PASSWORD",
    "LANGFLOW_DB_NAME",
    "LANGFLOW_DB_USER",
    "LANGFLOW_DB_PASSWORD",
    "LANGFLOW_DATABASE_URL",
    "SUPPORT_DB_NAME",
    "SUPPORT_DB_USER",
    "SUPPORT_DB_PASSWORD",
    "SUPPORT_DATABASE_URL",
    "LANGFLOW_SUPERUSER",
    "LANGFLOW_SUPERUSER_PASSWORD",
    "LANGFLOW_SECRET_KEY",
    "LANGFLOW_CONFIG_DIR",
    "GEMINI_API_KEY",
    "COMPOSIO_API_KEY",
)

PLACEHOLDERS = {
    "change-me",
    "changeme",
    "placeholder",
    "replace-me",
    "replace-with-random-secret",
    "your-api-key",
    "your-password",
}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read environment file: {path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"invalid environment entry on line {line_number}")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name] = value
    return values


def validate_database_url(
    variable_name: str,
    value: str,
    expected_user: str,
    expected_password: str,
    expected_database: str,
) -> list[str]:
    errors: list[str] = []
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return [f"{variable_name} is not a valid URL"]

    if parsed.scheme not in {"postgresql", "postgres"}:
        errors.append(f"{variable_name} must use the postgresql scheme")
    if unquote(parsed.username or "") != expected_user:
        errors.append(f"{variable_name} username does not match its user variable")
    if unquote(parsed.password or "") != expected_password:
        errors.append(f"{variable_name} password does not match its password variable")
    if parsed.hostname != "postgres":
        errors.append(f"{variable_name} host must be postgres inside Docker")
    if port != 5432:
        errors.append(f"{variable_name} port must be 5432")
    if parsed.path.lstrip("/") != expected_database:
        errors.append(f"{variable_name} database does not match its database variable")
    return errors


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or normalized in PLACEHOLDERS or normalized.startswith("replace-")


def valid_fernet_key(value: str) -> bool:
    try:
        decoded = base64.b64decode(value, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        return False
    return len(decoded) == 32


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Read values from this file before process environment values")
    args = parser.parse_args()

    values: dict[str, str] = {}
    if args.env_file:
        try:
            values.update(load_env_file(args.env_file))
        except ValueError as exc:
            print(f"Environment configuration: invalid ({exc})", file=sys.stderr)
            return 1
    values.update(os.environ)

    missing = [name for name in REQUIRED_VARIABLES if name not in values]
    placeholders = [name for name in REQUIRED_VARIABLES if name in values and is_placeholder(values[name])]
    errors: list[str] = []

    expected_values = {
        "LANGFLOW_DB_NAME": "langflow_internal",
        "LANGFLOW_DB_USER": "langflow_app",
        "SUPPORT_DB_NAME": "support_demo",
        "SUPPORT_DB_USER": "support_reader",
        "LANGFLOW_CONFIG_DIR": "/app/langflow",
    }
    for name, expected in expected_values.items():
        if name in values and values[name] != expected:
            errors.append(f"{name} must match the repository configuration")

    if (
        "LANGFLOW_SECRET_KEY" in values
        and not is_placeholder(values["LANGFLOW_SECRET_KEY"])
        and not valid_fernet_key(values["LANGFLOW_SECRET_KEY"])
    ):
        errors.append("LANGFLOW_SECRET_KEY must be a valid Fernet key")

    if not missing:
        errors.extend(
            validate_database_url(
                "LANGFLOW_DATABASE_URL",
                values["LANGFLOW_DATABASE_URL"],
                values["LANGFLOW_DB_USER"],
                values["LANGFLOW_DB_PASSWORD"],
                values["LANGFLOW_DB_NAME"],
            )
        )
        errors.extend(
            validate_database_url(
                "SUPPORT_DATABASE_URL",
                values["SUPPORT_DATABASE_URL"],
                values["SUPPORT_DB_USER"],
                values["SUPPORT_DB_PASSWORD"],
                values["SUPPORT_DB_NAME"],
            )
        )

    if missing or placeholders or errors:
        print("Environment configuration: invalid", file=sys.stderr)
        if missing:
            print(f"Missing variables: {', '.join(missing)}", file=sys.stderr)
        if placeholders:
            print(f"Placeholder values: {', '.join(placeholders)}", file=sys.stderr)
        for error in errors:
            print(f"Configuration error: {error}", file=sys.stderr)
        return 1

    print("Environment configuration: valid")
    print(f"Required variables found: {len(REQUIRED_VARIABLES)}")
    print("Placeholder values found: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

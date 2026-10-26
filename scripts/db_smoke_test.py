#!/usr/bin/env python3
"""Validate the support database through its read-only connection."""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import errors


class ValidationError(Exception):
    """Raised when a smoke-test assertion fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def main() -> int:
    database_url = os.environ.get("SUPPORT_DATABASE_URL")
    if not database_url:
        print("Database validation failed: SUPPORT_DATABASE_URL is not set", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(database_url, connect_timeout=10, autocommit=True) as connection:
            print("Database connection: OK")

            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.support_requests')")
                require(cursor.fetchone() == ("support_requests",), "support_requests table is missing")
                print("support_requests table: OK")

                cursor.execute("SELECT COUNT(*) FROM support_requests")
                row_count = cursor.fetchone()[0]
                require(row_count == 5, f"expected 5 initial records, found {row_count}")
                print("Initial records: 5")

                cursor.execute(
                    """
                    SELECT customer_name, email, category, priority, status
                    FROM support_requests
                    WHERE customer_name = %s
                    """,
                    ("John Smith",),
                )
                require(
                    cursor.fetchone()
                    == ("John Smith", "john@example.com", "Login Issue", "High", "Open"),
                    "John Smith record does not match the assignment data",
                )
                print("John Smith lookup: OK")

                cursor.execute(
                    """
                    SELECT customer_name
                    FROM support_requests
                    WHERE priority = %s AND status = %s
                    ORDER BY customer_name
                    """,
                    ("High", "Open"),
                )
                high_priority_names = [row[0] for row in cursor.fetchall()]
                require(
                    high_priority_names == ["Emma Johnson", "John Smith"],
                    "high-priority open request results do not match the assignment data",
                )
                print("High-priority open requests: 2")

                connection.autocommit = False
                try:
                    cursor.execute(
                        """
                        INSERT INTO support_requests
                            (customer_name, email, category, priority, status)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        ("Permission Test", "nobody@example.com", "Test", "Low", "Open"),
                    )
                except (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction):
                    connection.rollback()
                    print("Read-only permissions: OK")
                else:
                    connection.rollback()
                    raise ValidationError("support_reader unexpectedly inserted a record")

    except ValidationError as exc:
        print(f"Database validation failed: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Database validation failed: PostgreSQL operation failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

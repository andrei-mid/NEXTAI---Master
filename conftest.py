"""Session-wide test setup. Owner: @role-2-core.

Tests must never write into the development database: the persistence tests insert rows and
never delete them (audit_decisions is append-only). If TEST_DATABASE_URL is set (environment
or .env), every test uses it as DATABASE_URL. CI gets a throwaway postgres:17, so it doesn't
need it. Locally, point it at a separate database (see .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_test_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(
    Path(__file__).with_name(".env")
).get("TEST_DATABASE_URL")
if _test_url:
    os.environ["DATABASE_URL"] = _test_url

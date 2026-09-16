import os
from unittest.mock import patch

from app.sources.registry import SourceProfile


def test_connection_url_uses_db_name_for_active_source() -> None:
    with patch.dict(
        os.environ,
        {
            "PGHOST": "db.internal",
            "PGPORT": "5432",
            "PGUSER": "viewer",
            "PGPASSWORD": "secret",
            "PGDATABASE": "shared_db",
        },
        clear=False,
    ):
        profile = SourceProfile(
            id="eia",
            name="EIA",
            status="active",
            adapter="eia",
            homepage_url="https://example.com",
            description="",
            db_name="eia_data",
        )

        assert profile.connection_url() == "postgresql://viewer:secret@db.internal:5432/eia_data"

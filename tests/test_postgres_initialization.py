"""Fresh-database regression test; requires a local PostgreSQL admin URL."""

import os
import uuid

import pytest

from kyungdong_agent.data_hub import PostgresRepository


def test_initializes_fresh_database_and_can_reopen():
    admin_url = os.environ.get("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("Set TEST_POSTGRES_ADMIN_URL to test with PostgreSQL + pgvector")

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    database = "kgt_test_" + uuid.uuid4().hex
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            url = make_conninfo(admin_url, dbname=database)
            with psycopg.connect(url) as raw:
                assert raw.execute("SELECT to_regtype('vector')").fetchone()[0] is None

            repo = PostgresRepository(url)
            assert repo.dashboard()["confirmed_avg_lead_days"] == 90
            with repo._connect() as connection:
                assert connection.execute("SELECT '[1,2,3]'::vector").fetchone()[0].tolist() == [1, 2, 3]
                assert connection.execute(
                    "SELECT to_regclass('knowledge_documents_embedding_idx')"
                ).fetchone()[0] is not None
            repo.save_setting("initialization_test", "preserved")
            assert PostgresRepository(url).setting("initialization_test") == "preserved"
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))

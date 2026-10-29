"""Alembic environment: online migrations only, URL from PG_DATABASE_URL."""
from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from policyguard.config import PGSettings
from policyguard.infra.tables import metadata

url = context.config.attributes.get("url") or PGSettings.from_env().database_url
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

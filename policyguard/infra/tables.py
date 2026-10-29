"""PostgreSQL schema (SQLAlchemy Core). Every private table carries tenant_id.

Indexes follow the query list in the brief; see docs/policyguard/QUERY_PLANS.md for EXPLAIN ANALYZE.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_N_name)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"})


def ts(name: str, nullable: bool = True, **kw) -> Column:
    return Column(name, DateTime(timezone=True), nullable=nullable, **kw)


def created() -> Column:
    return ts("created_at", False, server_default=func.now())


ID = String(64)

tenants = Table("tenants", metadata, Column("tenant_id", ID, primary_key=True), Column("name", Text, nullable=False),
                created())

institutions = Table(
    "institutions", metadata,
    Column("institution_id", ID, primary_key=True),
    Column("tenant_id", ID, ForeignKey("tenants.tenant_id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("aliases", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("country_code", String(2)),
    Column("timezone", Text, nullable=False),
    Column("official_contact_url", Text),
    Column("synthetic", Boolean, nullable=False),
    Column("policy_epoch", Integer, nullable=False, server_default="0"),
    created(),
    Index(None, "tenant_id", "name"),
)

authority_grants = Table(
    "authority_grants", metadata,
    Column("grant_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("institution_id", ID, ForeignKey("institutions.institution_id"), nullable=False),
    Column("issuer_id", Text, nullable=False),
    Column("authority_scope", Text, nullable=False),
    Column("verification_method", Text, nullable=False),
    Column("evidence_level", Text, nullable=False),
    ts("valid_from"), ts("valid_to"), ts("recorded_at", False), ts("revoked_at"),
    Index(None, "tenant_id", "institution_id"),
)

source_documents = Table(
    "source_documents", metadata,
    Column("source_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("institution_id", ID, ForeignKey("institutions.institution_id"), nullable=False),
    Column("url", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("issuer_id", Text, nullable=False),
    Column("language", String(16), nullable=False),
    Column("content_hash", Text, nullable=False),
    ts("fetched_at", False),
    Column("object_key", Text),
    Column("etag", Text), Column("last_modified", Text),
    Column("synthetic", Boolean, nullable=False),
    Index(None, "tenant_id", "institution_id"),
)

policy_versions = Table(
    "policy_versions", metadata,
    Column("version_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("institution_id", ID, ForeignKey("institutions.institution_id"), nullable=False),
    Column("policy_id", ID, nullable=False),
    Column("version_label", Text, nullable=False),
    Column("source_id", ID, ForeignKey("source_documents.source_id"), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("source_hash", Text, nullable=False),
    Column("issuer_id", Text, nullable=False),
    Column("authority_scope", Text, nullable=False),
    Column("verification_method", Text, nullable=False),
    Column("evidence_level", Text, nullable=False),
    ts("valid_from"), ts("valid_to"),
    Column("valid_tz", Text, nullable=False),
    ts("recorded_at", False),
    Column("supersedes_version_id", ID),
    ts("revoked_at"), ts("fetched_at"), ts("verified_at"), ts("freshness_deadline"),
    Column("document_object_key", Text),
    Column("extraction_version", Text, nullable=False),
    Column("approval_status", Text, nullable=False),
    Column("discovered_by", Text),
    Column("approved_by", Text), ts("approved_at"),
    Column("payee", JSONB, nullable=False),
    Column("citation", JSONB, nullable=False),
    Column("synthetic", Boolean, nullable=False),
    Column("row_version", Integer, nullable=False, server_default="1"),
    CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_from < valid_to", name="valid_interval"),
    Index(None, "institution_id", "policy_id", "valid_from"),
    Index(None, "tenant_id", "institution_id", "approval_status"),
)

cases = Table(
    "cases", metadata,
    Column("case_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("institution_id", ID, ForeignKey("institutions.institution_id")),
    Column("institution_query", Text),
    Column("instruction_text", Text, nullable=False),
    Column("instruction_sha256", String(64), nullable=False),
    Column("instruction_received_on", Date),
    ts("paid_at"), ts("due_at"),
    Column("payment_tz", Text),
    Column("state", Text, nullable=False),
    Column("user_corrections", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("upload_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("request_hash", String(64), nullable=False),
    Column("synthetic", Boolean, nullable=False, server_default=text("true")),
    Column("row_version", Integer, nullable=False, server_default="1"),
    created(), ts("updated_at", False, server_default=func.now()),
    Index(None, "tenant_id", "created_at", "case_id"),
    Index(None, "tenant_id", "state"),
)

idempotency_requests = Table(
    "idempotency_requests", metadata,
    Column("tenant_id", ID, nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("case_id", ID, ForeignKey("cases.case_id"), nullable=False),
    created(),
    UniqueConstraint("tenant_id", "idempotency_key"),
)

outbox_events = Table(
    "outbox_events", metadata,
    Column("event_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("case_id", ID, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("payload", JSONB, nullable=False),
    ts("occurred_at", False),
    Column("traceparent", Text),
    Column("status", Text, nullable=False, server_default="PENDING"),
    ts("available_at", False, server_default=func.now()),
    Column("attempts", Integer, nullable=False, server_default="0"),
    ts("published_at"),
    Index(None, "status", "available_at"),
)

jobs = Table(
    "jobs", metadata,
    Column("job_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("case_id", ID, ForeignKey("cases.case_id"), nullable=False),
    Column("source_event_id", ID, nullable=False, unique=True),
    Column("state", Text, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False),
    ts("run_after", False, server_default=func.now()),
    ts("deadline_at", False),
    Column("lease_owner", Text), ts("lease_expires_at"),
    Column("last_error", Text),
    Column("traceparent", Text),
    created(), ts("updated_at", False, server_default=func.now()),
    Index(None, "state", "run_after"),
    Index(None, "case_id"),
)

processed_events = Table(
    "processed_events", metadata,
    Column("consumer_name", Text, nullable=False),
    Column("event_id", ID, nullable=False),
    ts("processed_at", False, server_default=func.now()),
    UniqueConstraint("consumer_name", "event_id"),
)

decisions = Table(
    "decisions", metadata,
    Column("decision_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("case_id", ID, ForeignKey("cases.case_id"), nullable=False),
    Column("assessment_kind", Text, nullable=False),
    ts("target_time"),
    Column("policy_decision", Text, nullable=False),
    Column("evidence_level", Text),
    Column("transaction_status", Text, nullable=False),
    Column("next_action", Text, nullable=False),
    Column("findings", JSONB, nullable=False),
    Column("limitations", JSONB, nullable=False),
    Column("applied_version_ids", JSONB, nullable=False),
    Column("considered_version_ids", JSONB, nullable=False),
    Column("claim", JSONB, nullable=False),
    Column("evidence_snapshot", JSONB, nullable=False),
    Column("rule_version", Text, nullable=False),
    Column("model_version", Text, nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("policy_epoch", Integer, nullable=False),
    Column("needs_reevaluation", Boolean, nullable=False, server_default=text("false")),
    created(),
    Index(None, "tenant_id", "case_id"),
)

inference_runs = Table(
    "inference_runs", metadata,
    Column("run_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("case_id", ID, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model_id", Text, nullable=False),
    Column("mode", Text, nullable=False),   # live | replay | mock | rules
    ts("started_at", False),
    Column("latency_ms", Integer),
    Column("prompt_tokens", Integer), Column("completion_tokens", Integer),
    Column("est_cost_usd", Numeric(12, 6)),
    Column("outcome", Text, nullable=False),
    Column("error_code", Text),
    Column("attempt", Integer, nullable=False),
    Index(None, "tenant_id", "case_id"),
)

reviews = Table(
    "reviews", metadata,
    Column("review_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("case_id", ID, ForeignKey("cases.case_id"), nullable=False),
    Column("reviewer_id", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("case_row_version", Integer, nullable=False),
    created(),
    Index(None, "tenant_id", "case_id"),
)

experience_records = Table(
    "experience_records", metadata,
    Column("record_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("case_id", ID, nullable=False),
    Column("review_id", ID, ForeignKey("reviews.review_id"), nullable=False),
    Column("institution_id", ID, nullable=False),
    Column("version_ids", JSONB, nullable=False),
    Column("lesson", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="ACTIVE"),
    created(),
    Index(None, "tenant_id", "institution_id", "status"),
)

audit_entries = Table(
    "audit_entries", metadata,
    Column("entry_id", BigInteger, primary_key=True, autoincrement=True),
    Column("tenant_id", ID, nullable=False),
    Column("actor", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("target", Text, nullable=False),
    Column("details", JSONB, nullable=False),
    ts("at", False, server_default=func.now()),
    Column("prev_hash", String(64), nullable=False),
    Column("entry_hash", String(64), nullable=False),
    Index(None, "tenant_id", "entry_id"),
)

budget_ledger = Table(
    "budget_ledger", metadata,
    Column("scope", Text, primary_key=True),          # e.g. "global:2026-10"
    Column("limit_usd", Numeric(12, 6), nullable=False),
    Column("max_calls", Integer, nullable=False),
    Column("reserved_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("spent_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("calls", Integer, nullable=False, server_default="0"),
    CheckConstraint("reserved_usd + spent_usd <= limit_usd", name="within_limit"),
    CheckConstraint("calls <= max_calls", name="within_calls"),
)

uploads = Table(
    "uploads", metadata,
    Column("upload_id", ID, primary_key=True),
    Column("tenant_id", ID, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("object_key", Text, nullable=False),
    Column("filename", Text, nullable=False),
    Column("content_type", Text, nullable=False),
    Column("declared_size", Integer, nullable=False),
    Column("size", Integer), Column("sha256", String(64)),
    Column("status", Text, nullable=False),     # PENDING | QUARANTINED | CLEAN | REJECTED
    Column("reject_reason", Text),
    ts("expires_at", False),
    created(),
    Index(None, "tenant_id", "created_at"),
)

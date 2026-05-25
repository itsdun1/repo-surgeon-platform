"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("installation_id", sa.BigInteger, unique=True, nullable=True),
        sa.Column("account_login", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(16), nullable=False, server_default="User"),
        sa.Column("agent_repo", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Seed the local tenant
    op.execute(
        "INSERT INTO tenants (id, account_login, account_type) VALUES ('local', 'local', 'User')"
    )

    op.create_table(
        "repos",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False, server_default="local"),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("default_branch", sa.String(60), nullable=False, server_default="main"),
        sa.Column("language", sa.String(40), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("rules", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "full_name"),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False, server_default="local"),
        sa.Column("repo_id", sa.String(64), sa.ForeignKey("repos.id"), nullable=True),
        sa.Column("repo_full_name", sa.String(200), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("trigger", sa.String(60), nullable=False),
        sa.Column("trigger_payload", sa.JSON, nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("prompt", sa.Text, nullable=True),
        sa.Column("session_branch", sa.String(120), nullable=True),
        sa.Column("issue_number", sa.Integer, nullable=True),
        sa.Column("pr_url", sa.String(300), nullable=True),
        sa.Column("pr_number", sa.Integer, nullable=True),
        sa.Column("log_path", sa.String(300), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("tool_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("runs_repo_started_idx", "runs", [sa.text("repo_full_name"), sa.text("started_at DESC")])
    op.create_index("runs_status_idx", "runs", ["status"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="local"),
        sa.Column("delivery_id", sa.String(80), unique=True, nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("action", sa.String(60), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=True),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="local"),
        sa.Column("fixture_id", sa.String(120), nullable=False),
        sa.Column("suite", sa.String(60), nullable=False),
        sa.Column("runtime", sa.String(80), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("assertions", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("trace_path", sa.String(300), nullable=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "memory_audits",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="local"),
        sa.Column("repo", sa.String(120), nullable=False),
        sa.Column("file_path", sa.String(300), nullable=False),
        sa.Column("before_blob", sa.Text, nullable=True),
        sa.Column("after_blob", sa.Text, nullable=False),
        sa.Column("edited_by", sa.String(120), nullable=False),
        sa.Column("pr_url", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("memory_audits")
    op.drop_table("eval_runs")
    op.drop_table("webhook_events")
    op.drop_index("runs_status_idx", table_name="runs")
    op.drop_index("runs_repo_started_idx", table_name="runs")
    op.drop_table("runs")
    op.drop_table("repos")
    op.drop_table("tenants")

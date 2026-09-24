"""Persist abstention separately from four-level risk predictions."""
from __future__ import annotations

import json
import math

from alembic import op
import sqlalchemy as sa


revision = "0012_detection_assessment"
down_revision = "0011_system_log_audit_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("detection_records") as batch:
        batch.alter_column("final_score", existing_type=sa.Numeric(5, 2), nullable=True)
        batch.add_column(sa.Column("assessment_status", sa.String(32), nullable=False, server_default="legacy"))
    connection = op.get_bind()
    detections = sa.table("detection_records", sa.column("id", sa.BigInteger()),
        sa.column("analysis_payload", sa.Text()), sa.column("assessment_status", sa.String(32)),
        sa.column("final_score", sa.Numeric(5, 2)), sa.column("risk_level", sa.String(30)),
        sa.column("judgement_result", sa.String(100)), sa.column("is_high_risk", sa.Boolean()),
        sa.column("is_public", sa.Boolean()))
    evidence = sa.table("evidence_matches", sa.column("detection_id", sa.BigInteger()))
    last_id = 0
    while True:
        rows = connection.execute(sa.select(detections.c.id, detections.c.analysis_payload)
            .where(detections.c.id > last_id).order_by(detections.c.id).limit(500)).all()
        if not rows:
            break
        for record_id, raw in rows:
            last_id = record_id
            try:
                payload = json.loads(raw or "{}")
            except (ValueError, TypeError):
                continue
            if not isinstance(payload, dict) or not payload.get("arbitration_status"):
                continue
            arbitration = payload["arbitration_status"]
            status = "degraded"
            if arbitration == "no_evidence":
                status = "insufficient_evidence"
            elif arbitration == "ok" and payload.get("quality_status") == "ok":
                has_evidence = connection.scalar(sa.select(sa.func.count()).select_from(evidence)
                    .where(evidence.c.detection_id == record_id))
                quality = payload.get("evidence_quality")
                coverage = quality.get("coverage") if isinstance(quality, dict) else None
                if not has_evidence:
                    status = "insufficient_evidence"
                elif isinstance(coverage, (int, float)) and not isinstance(coverage, bool) and math.isfinite(coverage) and 0 <= coverage <= 100:
                    status = "completed" if coverage > 0 else "insufficient_evidence"
                else:
                    # Missing historical diagnostics cannot prove successful validation.
                    status = "legacy" if coverage is None else "degraded"
            values = {"assessment_status": status}
            payload["assessment_status"] = status
            if status not in {"completed", "legacy"}:
                reason = "有效证据不足，暂时无法判断。" if status == "insufficient_evidence" else "分析未完整成功，暂时无法判断。"
                payload["assessment_reason"] = reason
                values.update(final_score=None, risk_level="无法判断", judgement_result=reason,
                              is_high_risk=False, is_public=False)
            values["analysis_payload"] = json.dumps(payload, ensure_ascii=False)
            connection.execute(detections.update().where(detections.c.id == record_id).values(**values))


def downgrade() -> None:
    # Never invent a score for an abstention when reverting a NOT NULL column.
    connection = op.get_bind()
    count = connection.scalar(sa.text("SELECT COUNT(*) FROM detection_records WHERE final_score IS NULL"))
    if count:
        raise RuntimeError("Cannot downgrade assessment schema while unscored records exist; export/reconcile them first.")
    with op.batch_alter_table("detection_records") as batch:
        batch.drop_column("assessment_status")
        batch.alter_column("final_score", existing_type=sa.Numeric(5, 2), nullable=False)

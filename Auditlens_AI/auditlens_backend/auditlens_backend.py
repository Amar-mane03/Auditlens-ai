"""Single-file AuditLens API, database models, audit, feedback, and ML backend.

Install the requirements once, configure DATABASE_URL/API_TOKENS_JSON, then:
    python auditlens_backend.py --init-db
    python auditlens_backend.py --serve
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import joblib
import numpy as np
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("auditlens")


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parent.parent / 'auditlens_fraud.db'}",
    )
    artifact_dir: Path = Path(
        os.getenv(
            "ARTIFACT_DIR",
            str(Path(__file__).resolve().parent.parent / "artifacts"),
        )
    )
    api_tokens_json: str = os.getenv(
        "API_TOKENS_JSON",
        json.dumps({
            "dev-token": {"identity": "admin@auditlens.ai", "role": "admin"},
            "analyst-token": {"identity": "analyst@auditlens.ai", "role": "analyst"},
            "reviewer-token": {"identity": "reviewer@auditlens.ai", "role": "reviewer"},
        }),
    )
    model_min_precision: float = Field(default=0.50, ge=0, le=1)
    model_min_recall: float = Field(default=0.50, ge=0, le=1)
    model_min_pr_auc: float = Field(default=0.50, ge=0, le=1)
    model_min_precision_delta: float = Field(default=-0.02, ge=-1, le=1)
    model_min_recall_delta: float = Field(default=-0.02, ge=-1, le=1)
    model_min_pr_auc_delta: float = Field(default=-0.02, ge=-1, le=1)
    app_env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _engine_options(url: str) -> dict[str, object]:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, **_engine_options(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_transaction_amount_nonnegative"),
        CheckConstraint(
            "fraud_score IS NULL OR (fraud_score >= 0 AND fraud_score <= 1)",
            name="ck_transaction_fraud_score",
        ),
        CheckConstraint("status IN ('successful', 'failed', 'blocked', 'pending')", name="ck_transaction_status"),
        CheckConstraint(
            "fraud_status IN ('unknown', 'suspected', 'confirmed', 'legitimate')",
            name="ck_transaction_fraud_status",
        ),
        CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="ck_transaction_risk_level"),
        Index("ix_transaction_timestamp_status", "occurred_at", "status"),
        Index("ix_transaction_sender_timestamp", "sender_account_id", "occurred_at"),
        Index("ix_transaction_receiver_timestamp", "receiver_account_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sender_account_id: Mapped[str | None] = mapped_column(String(128), index=True)
    receiver_account_id: Mapped[str | None] = mapped_column(String(128), index=True)
    device_id: Mapped[str | None] = mapped_column(String(128), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fraud_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low", index=True)
    fraud_score: Mapped[float | None] = mapped_column()
    prediction_label: Mapped[str | None] = mapped_column(String(32))
    model_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    case_links: Mapped[list[CaseTransaction]] = relationship(back_populates="transaction")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="transaction")


class FraudCase(Base):
    __tablename__ = "fraud_cases"
    __table_args__ = (
        CheckConstraint("suspected_amount >= 0", name="ck_case_suspected_nonnegative"),
        CheckConstraint("confirmed_amount >= 0", name="ck_case_confirmed_nonnegative"),
        CheckConstraint("recovered_amount >= 0", name="ck_case_recovered_nonnegative"),
        CheckConstraint("recovered_amount <= confirmed_amount", name="ck_case_recovered_lte_confirmed"),
        CheckConstraint(
            "status IN ('open', 'under_review', 'confirmed_fraud', 'legitimate', 'unresolved')",
            name="ck_case_status",
        ),
        Index("ix_fraud_case_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    suspected_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    confirmed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    recovered_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    assigned_reviewer: Mapped[str | None] = mapped_column(String(128))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    evidence_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transactions: Mapped[list[CaseTransaction]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseTransaction(Base):
    __tablename__ = "case_transactions"
    __table_args__ = (
        UniqueConstraint("case_id", "transaction_id", name="uq_case_transaction"),
        UniqueConstraint("transaction_id", name="uq_transaction_case"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("fraud_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    case: Mapped[FraudCase] = relationship(back_populates="transactions")
    transaction: Mapped[Transaction] = relationship(back_populates="case_links")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_transaction_timestamp", "transaction_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[str | None] = mapped_column(ForeignKey("fraud_cases.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("original_fraud_score >= 0 AND original_fraud_score <= 1", name="ck_feedback_score"),
        CheckConstraint(
            "verified_outcome IN ('confirmed_fraud', 'legitimate', 'inconclusive')",
            name="ck_feedback_outcome",
        ),
        Index("ix_feedback_eligible_reviewed", "training_eligible", "reviewed_at"),
        Index(
            "uq_feedback_eligible_transaction",
            "transaction_id",
            unique=True,
            postgresql_where=text("training_eligible IS TRUE"),
            sqlite_where=text("training_eligible IS 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_prediction: Mapped[str] = mapped_column(String(32), nullable=False)
    original_fraud_score: Mapped[float] = mapped_column(nullable=False)
    verified_outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="verified")
    reason_code: Mapped[str | None] = mapped_column(String(64))
    reviewer_identity: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    original_model_version: Mapped[str | None] = mapped_column(String(64))
    training_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedback.id", ondelete="RESTRICT"), index=True
    )
    transaction: Mapped[Transaction] = relationship(back_populates="feedback")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint("status IN ('champion', 'challenger', 'retired')", name="ck_model_version_status"),
        Index(
            "uq_model_champion",
            "status",
            unique=True,
            postgresql_where=text("status = 'champion'"),
            sqlite_where=text("status = 'champion'"),
        ),
    )

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_training_job_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    candidate_version: Mapped[str | None] = mapped_column(
        ForeignKey("model_versions.version", ondelete="RESTRICT")
    )
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransactionCreate(BaseModel):
    sender_account_id: str | None = None
    receiver_account_id: str | None = None
    device_id: str | None = None
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    occurred_at: datetime
    status: Literal["successful", "failed", "blocked", "pending"]

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class ResolveCaseRequest(BaseModel):
    status: Literal["confirmed_fraud", "legitimate", "unresolved"]
    confirmed_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    recovered_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    reason_code: str = Field(min_length=1, max_length=64, pattern="^[A-Za-z0-9_.:-]+$")

    @model_validator(mode="after")
    def validate_amounts(self) -> ResolveCaseRequest:
        if self.recovered_amount > self.confirmed_amount:
            raise ValueError("recovered_amount cannot exceed confirmed_amount")
        if self.status != "confirmed_fraud" and (self.confirmed_amount or self.recovered_amount):
            raise ValueError("confirmed and recovered amounts are only valid for confirmed fraud")
        return self


class FeedbackCreate(BaseModel):
    transaction_id: str
    verified_outcome: Literal["confirmed_fraud", "legitimate", "inconclusive"]
    reason_code: str = Field(min_length=1, max_length=64, pattern="^[A-Za-z0-9_.:-]+$")
    supersedes_id: str | None = None


def current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
) -> tuple[str, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        tokens = json.loads(settings.api_tokens_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="API token configuration is invalid") from exc
    if not isinstance(tokens, dict):
        raise HTTPException(status_code=500, detail="API token configuration must be a JSON object")
    value = tokens.get(credentials.credentials)
    if not isinstance(value, dict) or not isinstance(value.get("role"), str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return str(value.get("identity", "configured-service")), value["role"]


def require_roles(*roles: str):
    def dependency(identity: Annotated[tuple[str, str], Depends(current_identity)]) -> str:
        actor, role = identity
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return actor

    return dependency


def append_event(
    db: Session,
    *,
    action: str,
    actor: str,
    transaction_id: str | None = None,
    case_id: str | None = None,
    reason: str | None = None,
    model_version: str | None = None,
    details: dict[str, object] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        actor=actor,
        transaction_id=transaction_id,
        case_id=case_id,
        reason=reason,
        model_version=model_version,
        details=details or {},
    )
    db.add(event)
    return event


def record_feedback(
    db: Session,
    *,
    transaction_id: str,
    verified_outcome: str,
    reason_code: str,
    reviewer: str,
    supersedes_id: str | None = None,
) -> Feedback:
    transaction = db.scalar(select(Transaction).where(Transaction.id == transaction_id).with_for_update())
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.fraud_score is None or transaction.prediction_label is None:
        raise HTTPException(status_code=409, detail="Transaction has no stored model prediction")
    prior = db.scalars(
        select(Feedback)
        .where(Feedback.transaction_id == transaction_id)
        .order_by(Feedback.reviewed_at.desc(), Feedback.id.desc())
    ).first()
    if prior:
        if supersedes_id != prior.id:
            raise HTTPException(status_code=409, detail="Existing feedback must be explicitly superseded")
        prior.training_eligible = False
    elif supersedes_id is not None:
        raise HTTPException(status_code=409, detail="Feedback to supersede was not found")
    eligible = verified_outcome in {"confirmed_fraud", "legitimate"}
    if verified_outcome == "unresolved":
        verified_outcome = "inconclusive"
    feedback = Feedback(
        transaction_id=transaction_id,
        original_prediction=transaction.prediction_label,
        original_fraud_score=transaction.fraud_score,
        verified_outcome=verified_outcome,
        review_status="verified",
        reason_code=reason_code,
        reviewer_identity=reviewer,
        original_model_version=transaction.model_version,
        training_eligible=eligible,
        supersedes_id=supersedes_id,
    )
    db.add(feedback)
    append_event(
        db,
        action="feedback_verified",
        actor=reviewer,
        transaction_id=transaction_id,
        reason=reason_code,
        model_version=transaction.model_version,
        details={"feedback_id": feedback.id, "outcome": verified_outcome, "training_eligible": eligible},
    )
    return feedback


def eligible_feedback(db: Session) -> list[tuple[Feedback, Transaction]]:
    rows = db.execute(
        select(Feedback, Transaction)
        .join(Transaction, Feedback.transaction_id == Transaction.id)
        .where(Feedback.training_eligible.is_(True), Feedback.review_status == "verified")
        .order_by(Feedback.reviewed_at, Feedback.id)
    ).all()
    return list(rows)


def feature_vector(transaction: Transaction) -> list[float]:
    return [
        float(transaction.amount),
        float(transaction.occurred_at.hour),
        float(transaction.occurred_at.weekday()),
        float(transaction.device_id is not None),
    ]


def metric_report(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    amounts: np.ndarray | None = None,
) -> dict[str, object]:
    predictions = (probabilities >= 0.5).astype(int)
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    tn, fp, fn, tp = (int(item) for item in matrix.ravel())
    return {
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "fraud_value_detected": (
            float(amounts[(y_true == 1) & (predictions == 1)].sum()) if amounts is not None else None
        ),
    }


def train_candidate(db: Session, *, actor: str, champion: bool = False) -> ModelVersion:
    rows = eligible_feedback(db)
    if len(rows) < 20:
        raise ValueError(f"At least 20 eligible verified examples are required; found {len(rows)}")
    x = np.asarray([feature_vector(tx) for _, tx in rows], dtype=float)
    y = np.asarray([int(fb.verified_outcome == "confirmed_fraud") for fb, _ in rows], dtype=int)
    amounts = np.asarray([float(tx.amount) for _, tx in rows], dtype=float)
    if len(set(y.tolist())) < 2 or not np.isfinite(x).all():
        raise ValueError("Training data requires both verified classes and finite feature values")
    order = sorted(range(len(rows)), key=lambda i: (rows[i][0].reviewed_at, rows[i][0].id))
    split = max(1, min(len(order) - 1, int(len(order) * 0.8)))
    train_idx, test_idx = order[:split], order[split:]
    if len(set(y[train_idx].tolist())) < 2 or len(set(y[test_idx].tolist())) < 2:
        raise ValueError("Time-based training and validation partitions must each contain both classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
    )
    model.fit(x[train_idx], y[train_idx])
    y_test, test_amounts = y[test_idx], amounts[test_idx]
    probabilities = model.predict_proba(x[test_idx])[:, 1]
    candidate_metrics = metric_report(y_test, probabilities, test_amounts)
    current = db.scalars(select(ModelVersion).where(ModelVersion.status == "champion")).first()
    if current:
        champion_path = Path(current.artifact_path)
        if not champion_path.is_file():
            raise FileNotFoundError(f"Champion artifact is missing: {champion_path}")
        champion_metrics = metric_report(
            y_test,
            joblib.load(champion_path).predict_proba(x[test_idx])[:, 1],
            test_amounts,
        )
    else:
        champion_metrics = None

    feedback_ids = [fb.id for fb, _ in rows]
    lineage = [
        {
            "feedback_id": fb.id,
            "transaction_id": tx.id,
            "outcome": fb.verified_outcome,
            "reviewed_at": fb.reviewed_at.isoformat(),
            "model_version": fb.original_model_version,
            "features": x[i].tolist(),
            "amount": str(tx.amount),
        }
        for i, (fb, tx) in enumerate(rows)
    ]
    digest = hashlib.sha256(json.dumps(lineage, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    version = f"model-{utc_now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    target = settings.artifact_dir.resolve() / f"{version}.joblib"
    temporary = target.with_suffix(".joblib.tmp")
    joblib.dump(model, temporary)
    os.replace(temporary, target)
    version_row = ModelVersion(
        version=version,
        status="champion" if champion else "challenger",
        artifact_path=str(target),
        dataset_version=f"feedback-{digest}",
        feature_schema=["amount", "hour", "weekday", "device_present"],
        configuration={
            "algorithm": "sklearn.LogisticRegression",
            "class_weight": "balanced",
            "random_state": 42,
            "verified_feedback_count": len(feedback_ids),
            "training_feedback_ids": feedback_ids,
            "validation": "chronological 80/20 split by review timestamp",
        },
        metrics={"candidate": candidate_metrics, "champion": champion_metrics},
        created_by=actor,
    )
    db.add(version_row)
    if champion:
        for previous in db.scalars(select(ModelVersion).where(ModelVersion.status == "champion")).all():
            if previous.version != version:
                previous.status = "retired"
    append_event(
        db,
        action="model_trained",
        actor=actor,
        model_version=version,
        reason="Initial champion training" if champion else "Challenger training",
        details={"dataset_version": f"feedback-{digest}", "metrics": candidate_metrics},
    )
    db.flush()
    return version_row


def candidate_passes(version: ModelVersion) -> bool:
    candidate, champion = version.metrics.get("candidate", {}), version.metrics.get("champion")
    minimums_pass = (
        float(candidate.get("precision", 0)) >= settings.model_min_precision
        and float(candidate.get("recall", 0)) >= settings.model_min_recall
        and float(candidate.get("pr_auc", 0)) >= settings.model_min_pr_auc
    )
    if not minimums_pass:
        return False
    if champion is None:
        return True
    return (
        float(candidate["precision"]) - float(champion["precision"]) >= settings.model_min_precision_delta
        and float(candidate["recall"]) - float(champion["recall"]) >= settings.model_min_recall_delta
        and float(candidate["pr_auc"]) - float(champion["pr_auc"]) >= settings.model_min_pr_auc_delta
    )


def promote_model(db: Session, version: ModelVersion, actor: str) -> None:
    if version.status != "challenger" or not candidate_passes(version):
        raise ValueError("Candidate does not satisfy configured promotion criteria")
    if not Path(version.artifact_path).is_file():
        raise FileNotFoundError(f"Candidate artifact is missing: {version.artifact_path}")
    for previous in db.scalars(select(ModelVersion).where(ModelVersion.status == "champion")).all():
        previous.status = "retired"
    db.flush()
    version.status = "champion"
    append_event(db, action="model_promoted", actor=actor, model_version=version.version)


def rollback_model(db: Session, version: ModelVersion, actor: str) -> None:
    if version.status != "retired" or not Path(version.artifact_path).is_file():
        raise ValueError("Rollback target must be a retained model with an available artifact")
    current = db.scalars(select(ModelVersion).where(ModelVersion.status == "champion")).first()
    if current:
        current.status = "retired"
        db.flush()
    version.status = "champion"
    append_event(
        db,
        action="model_rollback",
        actor=actor,
        model_version=version.version,
        details={"replaced_version": current.version if current else None},
    )


def run_training_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(TrainingJob, job_id)
        if job is None:
            raise ValueError(f"Training job not found: {job_id}")
        try:
            job.status = "running"
            db.commit()
            candidate = train_candidate(db, actor=job.requested_by)
            job.candidate_version = candidate.version
            job.status = "succeeded"
            job.completed_at = utc_now()
            db.commit()
        except Exception as exc:
            logger.exception("Training job %s failed", job.id)
            db.rollback()
            failed_job = db.get(TrainingJob, job_id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.error = str(exc)[:1000]
                failed_job.completed_at = utc_now()
                db.commit()
            raise


def timeline(
    db: Session,
    *,
    start: datetime,
    end: datetime,
    transaction_id: str | None = None,
    account_id: str | None = None,
    status_filter: str | None = None,
    fraud_status: str | None = None,
    risk_level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, object]]:
    query = select(Transaction).where(Transaction.occurred_at >= start, Transaction.occurred_at < end)
    if transaction_id:
        query = query.where(Transaction.id == transaction_id)
    if account_id:
        query = query.where(
            (Transaction.sender_account_id == account_id) | (Transaction.receiver_account_id == account_id)
        )
    if status_filter:
        query = query.where(Transaction.status == status_filter)
    if fraud_status:
        query = query.where(Transaction.fraud_status == fraud_status)
    if risk_level:
        query = query.where(Transaction.risk_level == risk_level)
    transactions = db.scalars(
        query.order_by(Transaction.occurred_at, Transaction.id).limit(limit).offset(offset)
    ).all()
    result = []
    for transaction in transactions:
        events = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.transaction_id == transaction.id)
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        ).all()
        relationship_filters = []
        if transaction.sender_account_id:
            relationship_filters.append(Transaction.sender_account_id == transaction.sender_account_id)
        if transaction.receiver_account_id:
            relationship_filters.append(Transaction.receiver_account_id == transaction.receiver_account_id)
        if transaction.device_id:
            relationship_filters.append(Transaction.device_id == transaction.device_id)
        related = (
            db.scalars(
                select(Transaction.id)
                .where(Transaction.id != transaction.id, *relationship_filters)
                .order_by(Transaction.occurred_at, Transaction.id)
                .limit(100)
            ).all()
            if relationship_filters
            else []
        )
        result.append(
            {
                "transaction": transaction,
                "events": events,
                "related_transaction_ids": related,
                "related_transactions": {
                    "account_ids": sorted(
                        {
                            value
                            for value in (transaction.sender_account_id, transaction.receiver_account_id)
                            if value
                        }
                    ),
                    "device_id": transaction.device_id,
                },
            }
        )
    return result


def analytics_summary(db: Session, *, start: datetime, end: datetime) -> dict[str, object]:
    transactions = db.scalars(
        select(Transaction).where(Transaction.occurred_at >= start, Transaction.occurred_at < end)
    ).all()
    cases = db.scalars(select(FraudCase).where(FraudCase.created_at >= start, FraudCase.created_at < end)).all()
    confirmed = sum(
        (case.confirmed_amount for case in cases if case.status == "confirmed_fraud"), Decimal("0")
    )
    recovered = sum((case.recovered_amount for case in cases), Decimal("0"))
    trends: dict[str, dict[str, dict[str, object]]] = {"daily": {}, "weekly": {}, "monthly": {}}
    for transaction in transactions:
        date = transaction.occurred_at.date().isoformat()
        week = transaction.occurred_at.isocalendar()
        keys = (
            ("daily", date),
            ("weekly", f"{week.year}-W{week.week:02d}"),
            ("monthly", transaction.occurred_at.strftime("%Y-%m")),
        )
        for period, key in keys:
            item = trends[period].setdefault(key, {"count": 0, "value": Decimal("0")})
            item["count"] += 1
            item["value"] += transaction.amount
    return {
        "period": {"start": start, "end": end},
        "transaction_volume": len(transactions),
        "transaction_value": sum((tx.amount for tx in transactions), Decimal("0")),
        "successful_count": sum(tx.status == "successful" for tx in transactions),
        "failed_count": sum(tx.status == "failed" for tx in transactions),
        "suspected_fraud_value": sum((case.suspected_amount for case in cases), Decimal("0")),
        "confirmed_fraud_amount": confirmed,
        "recovered_amount": recovered,
        "unresolved_potential_exposure": sum(
            (
                max(Decimal("0"), max(case.confirmed_amount, case.suspected_amount) - case.recovered_amount)
                for case in cases
                if case.status in {"open", "under_review", "unresolved"}
            ),
            Decimal("0"),
        ),
        "blocked_transaction_value": sum(
            (tx.amount for tx in transactions if tx.status == "blocked"), Decimal("0")
        ),
        "fraud_recovery_rate": float(recovered / confirmed) if confirmed > 0 else None,
        "trends": trends,
        "definitions": {
            "transaction_value": "Sum of transaction amounts in the occurrence-time range; not revenue.",
            "suspected_fraud_value": "Sum of suspected case amounts for cases created in-range.",
            "confirmed_fraud_amount": "Sum of confirmed-fraud case amounts created in-range.",
            "recovered_amount": "Sum of case-level recovery amounts created in-range, counted once per case.",
            "unresolved_potential_exposure": "For open, under-review, or unresolved cases: max(suspected, confirmed) less recovered, floored at zero.",
            "blocked_transaction_value": "Sum of transaction amounts whose status is blocked.",
            "fraud_recovery_rate": "Recovered amount divided by confirmed amount; null when confirmed amount is zero.",
        },
    }


app = FastAPI(
    title="AuditLens Fraud Intelligence API",
    version="0.1.0",
    description="Single-file backend: transaction analytics, investigations, audit, and controlled ML.",
)
router = APIRouter(prefix="/api")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Db = Annotated[Session, Depends(get_db)]


def validate_time_window(start: datetime, end: datetime) -> None:
    if start.utcoffset() is None or end.utcoffset() is None:
        raise HTTPException(status_code=422, detail="start and end must include a timezone")
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be later than start")


@router.get("/health")
def health(db: Db) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@router.post("/transactions", status_code=201)
def create_transaction(
    body: TransactionCreate,
    db: Db,
    identity: Annotated[tuple[str, str], Depends(current_identity)],
) -> dict[str, object]:
    transaction = Transaction(**body.model_dump(), fraud_status="unknown", risk_level="low")
    db.add(transaction)
    db.flush()
    append_event(
        db,
        action="transaction_blocked" if transaction.status == "blocked" else "transaction_recorded",
        actor=identity[0],
        transaction_id=transaction.id,
        reason="Transaction recorded as blocked" if transaction.status == "blocked" else "Transaction recorded without a model prediction",
    )
    db.commit()
    return {"transaction_id": transaction.id, "status": transaction.status}


@router.post("/predictions", status_code=201)
def predict(
    body: TransactionCreate,
    db: Db,
    identity: Annotated[tuple[str, str], Depends(current_identity)],
) -> dict[str, object]:
    champion = db.scalars(select(ModelVersion).where(ModelVersion.status == "champion")).first()
    if champion is None:
        raise HTTPException(status_code=503, detail="No approved model is deployed")
    artifact = Path(champion.artifact_path)
    if not artifact.is_file():
        raise HTTPException(status_code=503, detail="Deployed model artifact is unavailable")
    transaction = Transaction(**body.model_dump(), fraud_status="unknown", risk_level="low")
    score = float(joblib.load(artifact).predict_proba([feature_vector(transaction)])[0][1])
    label = "fraud" if score >= 0.5 else "legitimate"
    transaction.fraud_score = score
    transaction.prediction_label = label
    transaction.model_version = champion.version
    transaction.fraud_status = "suspected" if label == "fraud" else "unknown"
    transaction.risk_level = "high" if score >= 0.7 else "medium" if score >= 0.3 else "low"
    db.add(transaction)
    db.flush()
    append_event(
        db,
        action="transaction_flagged" if label == "fraud" else "prediction_recorded",
        actor=identity[0],
        transaction_id=transaction.id,
        model_version=champion.version,
        reason="Model prediction",
        details={"prediction": label, "fraud_score": score},
    )
    if label == "fraud":
        case = FraudCase(status="open", suspected_amount=transaction.amount, reason_code="MODEL_FLAG")
        db.add(case)
        db.flush()
        db.add(CaseTransaction(case_id=case.id, transaction_id=transaction.id))
        append_event(
            db,
            action="case_created",
            actor=identity[0],
            transaction_id=transaction.id,
            case_id=case.id,
            model_version=champion.version,
        )
    db.commit()
    return {
        "transaction_id": transaction.id,
        "fraud_score": score,
        "prediction_label": label,
        "risk_level": transaction.risk_level,
        "model_version": champion.version,
    }


@router.get("/analytics/summary")
def summary(
    start: datetime,
    end: datetime,
    db: Db,
    _: Annotated[str, Depends(require_roles("analyst", "reviewer", "admin"))],
) -> dict[str, object]:
    validate_time_window(start, end)
    return analytics_summary(db, start=start, end=end)


@router.get("/analytics/timeline")
def get_timeline(
    start: datetime,
    end: datetime,
    db: Db,
    transaction_id: str | None = None,
    account_id: str | None = None,
    status_filter: Literal["successful", "failed", "blocked", "pending"] | None = Query(default=None, alias="status"),
    fraud_status: Literal["unknown", "suspected", "confirmed", "legitimate"] | None = None,
    risk_level: Literal["low", "medium", "high"] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: Annotated[str, Depends(require_roles("analyst", "reviewer", "admin"))] = "",
) -> dict[str, object]:
    validate_time_window(start, end)
    return jsonable_encoder(
        {
            "items": timeline(
                db,
                start=start,
                end=end,
                transaction_id=transaction_id,
                account_id=account_id,
                status_filter=status_filter,
                fraud_status=fraud_status,
                risk_level=risk_level,
                limit=limit,
                offset=offset,
            ),
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/transactions/{transaction_id}/history")
def transaction_history(
    transaction_id: str,
    db: Db,
    _: Annotated[str, Depends(require_roles("analyst", "reviewer", "admin"))],
) -> dict[str, object]:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.transaction_id == transaction_id)
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
    ).all()
    cases = db.scalars(
        select(FraudCase)
        .join(CaseTransaction, CaseTransaction.case_id == FraudCase.id)
        .where(CaseTransaction.transaction_id == transaction_id)
    ).all()
    return jsonable_encoder({"transaction": transaction, "events": events, "cases": cases})


@router.post("/fraud-cases", status_code=201)
def create_case(
    transaction_ids: list[str],
    db: Db,
    actor: Annotated[str, Depends(require_roles("reviewer", "admin"))],
) -> dict[str, object]:
    if not transaction_ids or len(set(transaction_ids)) != len(transaction_ids):
        raise HTTPException(status_code=422, detail="Provide unique transaction IDs")
    transactions = db.scalars(select(Transaction).where(Transaction.id.in_(transaction_ids))).all()
    if len(transactions) != len(transaction_ids):
        raise HTTPException(status_code=404, detail="One or more transactions were not found")
    linked = db.scalars(
        select(CaseTransaction.transaction_id).where(CaseTransaction.transaction_id.in_(transaction_ids))
    ).all()
    if linked:
        raise HTTPException(status_code=409, detail="One or more transactions already belong to a fraud case")
    case = FraudCase(
        status="open",
        suspected_amount=sum((tx.amount for tx in transactions), Decimal("0")),
        reason_code="ANALYST_REVIEW",
    )
    db.add(case)
    db.flush()
    for tx in transactions:
        db.add(CaseTransaction(case_id=case.id, transaction_id=tx.id))
        append_event(db, action="sent_for_investigation", actor=actor, transaction_id=tx.id, case_id=case.id)
    db.commit()
    return {"case_id": case.id, "status": case.status, "transaction_ids": transaction_ids}


@router.get("/fraud-cases/{case_id}")
def get_case(
    case_id: str,
    db: Db,
    _: Annotated[str, Depends(require_roles("reviewer", "admin"))],
) -> dict[str, object]:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Fraud case not found")
    return jsonable_encoder({"case": case, "transactions": [link.transaction for link in case.transactions]})


@router.post("/fraud-cases/{case_id}/start-review")
def start_review(
    case_id: str,
    db: Db,
    actor: Annotated[str, Depends(require_roles("reviewer", "admin"))],
) -> dict[str, str]:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Fraud case not found")
    if case.status not in {"open", "under_review"}:
        raise HTTPException(status_code=409, detail="Resolved cases cannot be put under review")
    case.status, case.assigned_reviewer = "under_review", actor
    for link in case.transactions:
        append_event(
            db,
            action="analyst_review_started",
            actor=actor,
            transaction_id=link.transaction_id,
            case_id=case.id,
        )
    append_event(db, action="case_status_changed", actor=actor, case_id=case.id, details={"status": case.status})
    db.commit()
    return {"case_id": case.id, "status": case.status}


@router.post("/fraud-cases/{case_id}/resolve")
def resolve_case(
    case_id: str,
    body: ResolveCaseRequest,
    db: Db,
    actor: Annotated[str, Depends(require_roles("reviewer", "admin"))],
) -> dict[str, object]:
    case = db.get(FraudCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Fraud case not found")
    if case.status in {"confirmed_fraud", "legitimate", "unresolved"}:
        raise HTTPException(status_code=409, detail="Case is already resolved; correct via feedback")
    case.status = body.status
    case.confirmed_amount = body.confirmed_amount if body.status == "confirmed_fraud" else Decimal("0")
    case.recovered_amount = body.recovered_amount if body.status == "confirmed_fraud" else Decimal("0")
    case.reason_code, case.assigned_reviewer, case.resolved_at = body.reason_code, actor, utc_now()
    db.flush()
    outcome = {
        "confirmed_fraud": "confirmed_fraud",
        "legitimate": "legitimate",
        "unresolved": "inconclusive",
    }[body.status]
    for link in case.transactions:
        tx = link.transaction
        tx.fraud_status = "confirmed" if body.status == "confirmed_fraud" else body.status
        if tx.fraud_score is not None and tx.prediction_label is not None:
            record_feedback(
                db,
                transaction_id=tx.id,
                verified_outcome=outcome,
                reason_code=body.reason_code,
                reviewer=actor,
            )
        append_event(
            db,
            action="analyst_decision_recorded",
            actor=actor,
            transaction_id=tx.id,
            case_id=case.id,
            reason=body.reason_code,
        )
    if body.recovered_amount:
        append_event(
            db,
            action="funds_recovered",
            actor=actor,
            case_id=case.id,
            reason=body.reason_code,
            details={"amount": str(body.recovered_amount)},
        )
    append_event(
        db,
        action="case_status_changed",
        actor=actor,
        case_id=case.id,
        reason=body.reason_code,
        details={"status": body.status},
    )
    db.commit()
    return {"case_id": case.id, "status": case.status, "resolved_at": case.resolved_at}


@router.post("/feedback", status_code=201)
def submit_feedback(
    body: FeedbackCreate,
    db: Db,
    actor: Annotated[str, Depends(require_roles("reviewer", "admin"))],
) -> dict[str, object]:
    feedback = record_feedback(
        db,
        transaction_id=body.transaction_id,
        verified_outcome=body.verified_outcome,
        reason_code=body.reason_code,
        reviewer=actor,
        supersedes_id=body.supersedes_id,
    )
    db.commit()
    return {"feedback_id": feedback.id, "training_eligible": feedback.training_eligible}


@router.get("/feedback/pending")
def pending_feedback(
    db: Db,
    _: Annotated[str, Depends(require_roles("reviewer", "admin"))],
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    transactions = db.scalars(
        select(Transaction)
        .where(
            Transaction.fraud_score.is_not(None),
            ~select(Feedback.id).where(Feedback.transaction_id == Transaction.id).exists(),
        )
        .order_by(Transaction.occurred_at)
        .limit(limit)
    ).all()
    return jsonable_encoder({"items": transactions, "count": len(transactions)})


@router.get("/ml/metrics")
def ml_metrics(
    db: Db,
    _: Annotated[str, Depends(require_roles("analyst", "reviewer", "admin", "trainer"))],
) -> dict[str, object]:
    models = db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    jobs = db.scalars(select(TrainingJob).order_by(TrainingJob.created_at.desc()).limit(100)).all()
    distribution = db.execute(
        select(Feedback.review_status, Feedback.verified_outcome, func.count()).group_by(
            Feedback.review_status, Feedback.verified_outcome
        )
    ).all()
    eligible_count = db.scalar(
        select(func.count()).select_from(Feedback).where(Feedback.training_eligible.is_(True))
    )
    return jsonable_encoder(
        {
            "eligible_feedback_count": eligible_count or 0,
            "feedback_distribution": [
                {"review_status": row[0], "outcome": row[1], "count": row[2]} for row in distribution
            ],
            "models": models,
            "training_jobs": jobs,
        }
    )


@router.get("/ml/models", response_model=None)
def list_models(
    db: Db,
    _: Annotated[str, Depends(require_roles("analyst", "reviewer", "admin", "trainer"))],
) -> list[dict[str, object]]:
    return jsonable_encoder(db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all())


@router.post("/ml/training-jobs", status_code=202)
def start_training(
    db: Db,
    actor: Annotated[str, Depends(require_roles("trainer", "admin"))],
) -> dict[str, str]:
    job = TrainingJob(status="queued", requested_by=actor)
    db.add(job)
    db.commit()
    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", job.id], close_fds=True)
    except OSError as exc:
        job.status, job.error, job.completed_at = "failed", str(exc)[:1000], utc_now()
        db.commit()
        raise HTTPException(status_code=500, detail="Could not start training worker") from exc
    return {"job_id": job.id, "status": "queued"}


@router.get("/ml/training-jobs/{job_id}", response_model=None)
def get_training_job(
    job_id: str,
    db: Db,
    _: Annotated[str, Depends(require_roles("trainer", "admin", "analyst"))],
) -> dict[str, object]:
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return jsonable_encoder(job)


@router.post("/ml/models/{model_version}/promote")
def promote_endpoint(
    model_version: str,
    db: Db,
    actor: Annotated[str, Depends(require_roles("admin"))],
) -> dict[str, str]:
    version = db.get(ModelVersion, model_version)
    if version is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    try:
        promote_model(db, version, actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"model_version": version.version, "status": version.status}


@router.post("/ml/models/{model_version}/rollback")
def rollback_endpoint(
    model_version: str,
    db: Db,
    actor: Annotated[str, Depends(require_roles("admin"))],
) -> dict[str, str]:
    version = db.get(ModelVersion, model_version)
    if version is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    try:
        rollback_model(db, version, actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"model_version": version.version, "status": version.status}


app.include_router(router)


def seed_synthetic(count: int) -> None:
    if settings.app_env != "development":
        raise SystemExit("Synthetic seeding is allowed only when APP_ENV=development")
    if count < 20:
        raise ValueError("At least 20 transactions are required")
    from random import Random

    generator = Random(42)
    base_time = utc_now() - timedelta(days=count + 1)
    with SessionLocal() as db:
        if db.scalars(select(ModelVersion).where(ModelVersion.status == "champion")).first():
            raise SystemExit("A champion already exists; refusing synthetic retraining")
        for index in range(count):
            fraud = generator.random() < 0.12
            amount = generator.uniform(350, 2500) if fraud else generator.uniform(5, 250)
            tx = Transaction(
                sender_account_id=f"synthetic-sender-{index % 30}",
                receiver_account_id=f"synthetic-receiver-{index % 25}",
                device_id=None if fraud and index % 2 else f"synthetic-device-{index % 20}",
                amount=Decimal(f"{amount:.2f}"),
                currency="USD",
                occurred_at=base_time + timedelta(minutes=index * 11),
                status="blocked" if fraud and index % 3 == 0 else "successful",
                fraud_status="suspected" if fraud else "legitimate",
                risk_level="high" if fraud else "low",
                fraud_score=0.9 if fraud else 0.08,
                prediction_label="fraud" if fraud else "legitimate",
                model_version="synthetic-seed",
            )
            db.add(tx)
            db.flush()
            db.add(
                Feedback(
                    transaction_id=tx.id,
                    original_prediction=tx.prediction_label,
                    original_fraud_score=tx.fraud_score,
                    verified_outcome="confirmed_fraud" if fraud else "legitimate",
                    review_status="verified",
                    reason_code="SYNTHETIC_LABEL",
                    reviewer_identity="synthetic-seed",
                    original_model_version=tx.model_version,
                    training_eligible=True,
                )
            )
            append_event(
                db,
                action="transaction_flagged" if fraud else "prediction_recorded",
                actor="synthetic-seed",
                transaction_id=tx.id,
                model_version=tx.model_version,
                reason="Synthetic development record",
            )
        db.commit()
        champion = train_candidate(db, actor="synthetic-seed", champion=True)
        db.commit()
        print(f"Seeded {count} synthetic transactions; initialized champion {champion.version}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-file AuditLens Python backend")
    parser.add_argument("--init-db", action="store_true", help="Create database tables from SQLAlchemy metadata")
    parser.add_argument("--seed-synthetic", action="store_true", help="Seed synthetic data and initialize a dev model")
    parser.add_argument("--count", type=int, default=500, help="Synthetic rows for --seed-synthetic")
    parser.add_argument("--worker", metavar="JOB_ID", help=argparse.SUPPRESS)
    parser.add_argument("--serve", action="store_true", help="Run the API with Uvicorn")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.init_db:
        Base.metadata.create_all(engine)
        print("Database schema is ready.")
    elif args.seed_synthetic:
        seed_synthetic(args.count)
    elif args.worker:
        run_training_job(args.worker)
    elif args.serve:
        import uvicorn

        uvicorn.run(app, host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

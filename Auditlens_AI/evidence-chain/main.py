
import os
import json
import hashlib
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "evidence_files"
DB_PATH = BASE_DIR / "evidence.db"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="RevAI Evidence Chain - Trust",
    description="Tamper-evident audit evidence and verification API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout = 10000")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def calculate_event_hash(event: dict) -> str:
    return sha256_bytes(canonical_json(event).encode("utf-8"))


def initialize_database():
    with database() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                transaction_id TEXT,
                filename TEXT,
                evidence_sha256 TEXT,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
        """)


def append_event(
    actor: str,
    event_type: str,
    transaction_id: str | None = None,
    filename: str | None = None,
    evidence_sha256: str | None = None,
    metadata: dict | None = None,
):
    """
    Append an event while holding a SQLite write transaction.
    The hash covers all event fields and the previous event hash.
    """
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")

        previous = conn.execute("""
            SELECT sequence, event_hash
            FROM audit_events
            ORDER BY sequence DESC
            LIMIT 1
        """).fetchone()

        previous_hash = previous["event_hash"] if previous else "GENESIS"

        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "actor": actor,
            "event_type": event_type,
            "transaction_id": transaction_id,
            "filename": filename,
            "evidence_sha256": evidence_sha256,
            "previous_hash": previous_hash,
            "metadata": metadata or {},
        }

        event_hash = calculate_event_hash(event)

        cursor = conn.execute("""
            INSERT INTO audit_events (
                event_id, timestamp, actor, event_type,
                transaction_id, filename, evidence_sha256,
                previous_hash, event_hash, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event["event_id"],
            event["timestamp"],
            event["actor"],
            event["event_type"],
            event["transaction_id"],
            event["filename"],
            event["evidence_sha256"],
            event["previous_hash"],
            event_hash,
            canonical_json(event["metadata"]),
        ))

        event["sequence"] = cursor.lastrowid
        event["event_hash"] = event_hash

        return event


def row_to_event(row):
    return {
        "event_id": row["event_id"],
        "timestamp": row["timestamp"],
        "actor": row["actor"],
        "event_type": row["event_type"],
        "transaction_id": row["transaction_id"],
        "filename": row["filename"],
        "evidence_sha256": row["evidence_sha256"],
        "previous_hash": row["previous_hash"],
        "metadata": json.loads(row["metadata_json"]),
        "sequence": row["sequence"],
        "event_hash": row["event_hash"],
    }


@app.on_event("startup")
def startup():
    initialize_database()


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "RevAI Evidence Chain - Trust",
    }


@app.post("/evidence/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    actor: str = Form(...),
    transaction_id: str = Form(...),
):
    """
    Demo endpoint. In production, derive actor from authenticated
    identity and validate engagement-level permissions.
    """
    actor = actor.strip()
    transaction_id = transaction_id.strip()

    if not actor or not transaction_id:
        raise HTTPException(
            status_code=400,
            detail="Actor and transaction ID are required.",
        )

    original_name = Path(file.filename or "evidence").name

    # Stream to a temporary file while hashing; enforce size limit.
    stored_name = f"{uuid.uuid4().hex}.bin"
    final_path = UPLOAD_DIR / stored_name
    temp_path = UPLOAD_DIR / f"{stored_name}.tmp"
    digest = hashlib.sha256()
    size = 0

    try:
        with temp_path.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break

                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the 10 MB limit.",
                    )

                digest.update(chunk)
                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty files are not allowed.",
            )

        file_hash = digest.hexdigest()
        os.replace(temp_path, final_path)

        try:
            event = append_event(
                actor=actor,
                event_type="EVIDENCE_UPLOADED",
                transaction_id=transaction_id,
                filename=original_name,
                evidence_sha256=file_hash,
                metadata={
                    "stored_file_id": stored_name,
                    "size_bytes": size,
                    "content_type": file.content_type,
                },
            )
        except Exception:
            final_path.unlink(missing_ok=True)
            raise

        return {
            "message": "Evidence stored and audit event recorded.",
            "evidence_sha256": file_hash,
            "size_bytes": size,
            "event": event,
        }

    finally:
        temp_path.unlink(missing_ok=True)
        await file.close()


@app.post("/events")
def create_audit_event(
    actor: str = Form(...),
    event_type: str = Form(...),
    transaction_id: str = Form(""),
    details: str = Form(""),
):
    allowed_types = {
        "AUDIT_TEST_RUN",
        "FINDING_CREATED",
        "FINDING_REVIEWED",
        "EVIDENCE_REVIEWED",
    }

    if event_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Unsupported event type.",
        )

    if not actor.strip():
        raise HTTPException(status_code=400, detail="Actor is required.")

    return append_event(
        actor=actor.strip(),
        event_type=event_type,
        transaction_id=transaction_id.strip() or None,
        metadata={"details": details.strip()},
    )


@app.get("/events")
def list_events(limit: int = 100):
    limit = max(1, min(limit, 500))

    with database() as conn:
        rows = conn.execute("""
            SELECT * FROM audit_events
            ORDER BY sequence DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return {
        "events": [row_to_event(row) for row in rows],
        "count": len(rows),
    }


@app.get("/verify")
def verify_chain():
    with database() as conn:
        rows = conn.execute("""
            SELECT * FROM audit_events ORDER BY sequence ASC
        """).fetchall()

    expected_previous = "GENESIS"
    checked = 0
    errors = []

    for row in rows:
        event = row_to_event(row)

        if event["previous_hash"] != expected_previous:
            errors.append({
                "sequence": event["sequence"],
                "reason": "Previous hash does not match.",
            })

        payload = {
            "event_id": event["event_id"],
            "timestamp": event["timestamp"],
            "actor": event["actor"],
            "event_type": event["event_type"],
            "transaction_id": event["transaction_id"],
            "filename": event["filename"],
            "evidence_sha256": event["evidence_sha256"],
            "previous_hash": event["previous_hash"],
            "metadata": event["metadata"],
        }

        computed = calculate_event_hash(payload)

        if computed != event["event_hash"]:
            errors.append({
                "sequence": event["sequence"],
                "reason": "Event content or event hash was altered.",
            })

        # Check whether uploaded evidence still matches its original hash.
        stored_file_id = event["metadata"].get("stored_file_id")
        original_hash = event["evidence_sha256"]

        if stored_file_id and original_hash:
            evidence_path = UPLOAD_DIR / Path(stored_file_id).name

            if not evidence_path.is_file():
                errors.append({
                    "sequence": event["sequence"],
                    "reason": "Evidence file is missing.",
                })
            else:
                file_digest = hashlib.sha256()
                with evidence_path.open("rb") as evidence_file:
                    for chunk in iter(
                        lambda: evidence_file.read(1024 * 1024), b""
                    ):
                        file_digest.update(chunk)

                if file_digest.hexdigest() != original_hash:
                    errors.append({
                        "sequence": event["sequence"],
                        "reason": "Evidence file hash does not match.",
                    })

        expected_previous = event["event_hash"]
        checked += 1

    return {
        "valid": len(errors) == 0,
        "events_checked": checked,
        "errors": errors,
        "last_verified_hash": expected_previous if rows else "GENESIS",
        "verification_time": utc_now(),
        "note": (
            "This verifies the stored chain and evidence files. "
            "It cannot detect a coordinated rewrite of the entire "
            "database and chain without an independently protected "
            "checkpoint."
        ),
    }

"""Disaster Recovery, Hot Backups, Restore, System Configuration, and LAN Activation API router.

Enforces strict ADMIN authorization for backups, restore, and system config.
Hot backups are non-blocking using SQLite VACUUM INTO / backup API and SHA-256 validation.
Restores use staged integrity checking and automatic pre-restore safety backups.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional
import uuid
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials

from .. import __version__
from ..config import DaemonConfig
from ..printing.service import default_printer_service
from ..security.roles import UserRole
from .dependencies import get_current_user, get_db, require_role, security_bearer
from .schemas import (
    BackupCreateRequest,
    BackupManifestResponse,
    BackupVerifyResponse,
    HardwareTestRequest,
    HardwareTestResponse,
    RestoreExecuteRequest,
    RestoreExecuteResponse,
    RestorePreviewResponse,
    SuccessResponse,
    SystemConfigResponse,
    SystemConfigUpdateRequest,
    SystemDiscoveryResponse,
)

logger = logging.getLogger("pharmacy_daemon.system")

router = APIRouter(prefix="/api/v1/system", tags=["System, Backups & LAN"])
admin_guard = Depends(require_role(UserRole.ADMIN))

# In-memory registry for staged restore sessions: staging_token -> metadata dict
_STAGED_RESTORES: Dict[str, Dict[str, Any]] = {}


def _compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _get_active_app_config(request: Request) -> DaemonConfig:
    """Extract daemon configuration from FastAPI application state."""
    config = getattr(request.app.state, "config", None)
    if not config:
        config = DaemonConfig.load()
    return config


def _get_backups_dir(config: DaemonConfig, db: sqlite3.Connection) -> Path:
    """Resolve backup archive destination directory."""
    cursor = db.cursor()
    cursor.execute("SELECT value FROM system_config WHERE key = 'backup_directory';")
    row = cursor.fetchone()
    cursor.close()

    if row and row["value"] and row["value"].strip():
        custom_dir = Path(row["value"].strip())
        custom_dir.mkdir(parents=True, exist_ok=True)
        return custom_dir

    backups_dir = config.app_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def _collect_db_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Calculate baseline metrics from database tables for manifest verification."""
    cursor = conn.cursor()

    # Schema version
    try:
        cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations;")
        schema_version = cursor.fetchone()[0]
    except Exception:
        schema_version = 0

    # Invoice count and total revenue
    try:
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(grand_total_paise), 0) FROM sale_invoices;")
        inv_row = cursor.fetchone()
        invoice_count = inv_row[0]
        revenue_total_paise = inv_row[1]
    except Exception:
        invoice_count = 0
        revenue_total_paise = 0

    # Medicine count
    try:
        cursor.execute("SELECT COUNT(*) FROM medicines;")
        medicine_count = cursor.fetchone()[0]
    except Exception:
        medicine_count = 0

    # Khata balance
    try:
        cursor.execute("SELECT COALESCE(SUM(current_balance_paise), 0) FROM customers;")
        khata_balance_paise = cursor.fetchone()[0]
    except Exception:
        khata_balance_paise = 0

    cursor.close()
    return {
        "schema_version": schema_version,
        "invoice_count": invoice_count,
        "medicine_count": medicine_count,
        "revenue_total_paise": revenue_total_paise,
        "khata_balance_paise": khata_balance_paise,
    }


def _create_hot_backup_archive(
    db: sqlite3.Connection,
    config: DaemonConfig,
    backup_type: str,
    notes: Optional[str],
    user_id: Optional[int],
) -> BackupManifestResponse:
    """Perform hot SQLite snapshot, calculate SHA-256, package into .pbk archive, and log manifest."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    timestamp_slug = now.strftime("%Y%m%d_%H%M%S")

    backups_dir = _get_backups_dir(config, db)
    temp_dir = Path(tempfile.mkdtemp(prefix="pbk_temp_"))

    try:
        snapshot_db_path = temp_dir / "pharmacy.db"

        # Safe non-blocking snapshot using VACUUM INTO or sqlite3.backup
        try:
            # First try VACUUM INTO
            db.execute("VACUUM INTO ?;", (str(snapshot_db_path),))
        except Exception as e:
            logger.warning("VACUUM INTO failed, falling back to sqlite3.backup: %s", e)
            snapshot_conn = sqlite3.connect(str(snapshot_db_path))
            db.backup(snapshot_conn)
            snapshot_conn.close()

        # Run integrity check on snapshot
        snapshot_conn = sqlite3.connect(str(snapshot_db_path))
        snapshot_conn.row_factory = sqlite3.Row
        int_check = snapshot_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        if int_check.lower() != "ok":
            snapshot_conn.close()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Integrity check failed on snapshot: {int_check}",
            )

        # Collect metadata from snapshot
        stats = _collect_db_stats(snapshot_conn)
        snapshot_conn.close()

        # Compute snapshot database SHA-256
        db_hash = _compute_sha256(snapshot_db_path)

        # Create manifest metadata
        manifest_meta = {
            "version": "1.0",
            "created_at": now_str,
            "backup_type": backup_type,
            "daemon_version": __version__,
            "db_sha256": db_hash,
            "stats": stats,
            "notes": notes,
        }
        manifest_path = temp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_meta, indent=2), encoding="utf-8")

        # Package into compressed .pbk (zip archive)
        pbk_filename = f"backup_{timestamp_slug}_{backup_type.lower()}_{db_hash[:8]}.pbk"
        pbk_path = backups_dir / pbk_filename

        with zipfile.ZipFile(pbk_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot_db_path, arcname="pharmacy.db")
            zf.write(manifest_path, arcname="manifest.json")

        file_size = pbk_path.stat().st_size
        pbk_sha256 = _compute_sha256(pbk_path)

        # Record in backup_manifests ledger
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO backup_manifests (
                filename, filepath, file_size_bytes, sha256_hash, backup_type,
                status, schema_version, invoice_count, medicine_count,
                revenue_total_paise, khata_balance_paise, notes, created_by,
                created_at, verified_at
            ) VALUES (?, ?, ?, ?, ?, 'VALID', ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            pbk_filename,
            str(pbk_path),
            file_size,
            pbk_sha256,
            backup_type,
            stats["schema_version"],
            stats["invoice_count"],
            stats["medicine_count"],
            stats["revenue_total_paise"],
            stats["khata_balance_paise"],
            notes,
            user_id,
            now_str,
            now_str,
        ))
        manifest_id = cursor.lastrowid
        db.commit()

        # Fetch operator username
        creator_name = None
        if user_id:
            cursor.execute("SELECT username FROM users WHERE id = ?;", (user_id,))
            u_row = cursor.fetchone()
            if u_row:
                creator_name = u_row[0]
        cursor.close()

        return BackupManifestResponse(
            id=manifest_id,
            filename=pbk_filename,
            filepath=str(pbk_path),
            file_size_bytes=file_size,
            sha256_hash=pbk_sha256,
            backup_type=backup_type,
            status="VALID",
            schema_version=stats["schema_version"],
            invoice_count=stats["invoice_count"],
            medicine_count=stats["medicine_count"],
            revenue_total_paise=stats["revenue_total_paise"],
            khata_balance_paise=stats["khata_balance_paise"],
            notes=notes,
            created_by=user_id,
            created_by_name=creator_name,
            created_at=now_str,
            verified_at=now_str,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# =========================================================================
# 1. HOT BACKUPS & MANIFESTS
# =========================================================================

@router.post("/backups", response_model=SuccessResponse[BackupManifestResponse], dependencies=[admin_guard])
def create_backup(
    payload: BackupCreateRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create an immediate hot SQLite backup package (.pbk) with SHA-256 verification."""
    config = _get_active_app_config(request)
    manifest = _create_hot_backup_archive(
        db=db,
        config=config,
        backup_type=payload.backup_type,
        notes=payload.notes,
        user_id=current_user["id"],
    )
    return SuccessResponse(data=manifest)


@router.get("/backups", response_model=SuccessResponse[List[BackupManifestResponse]], dependencies=[admin_guard])
def list_backups(
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve audit ledger of backup manifests."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT bm.*, u.username AS created_by_name
        FROM backup_manifests bm
        LEFT JOIN users u ON u.id = bm.created_by
        ORDER BY bm.created_at DESC;
    """)
    rows = cursor.fetchall()
    cursor.close()

    manifests = [
        BackupManifestResponse(
            id=r["id"],
            filename=r["filename"],
            filepath=r["filepath"],
            file_size_bytes=r["file_size_bytes"],
            sha256_hash=r["sha256_hash"],
            backup_type=r["backup_type"],
            status=r["status"],
            schema_version=r["schema_version"],
            invoice_count=r["invoice_count"],
            medicine_count=r["medicine_count"],
            revenue_total_paise=r["revenue_total_paise"],
            khata_balance_paise=r["khata_balance_paise"],
            notes=r["notes"],
            created_by=r["created_by"],
            created_by_name=r["created_by_name"],
            created_at=r["created_at"],
            verified_at=r["verified_at"],
        )
        for r in rows
    ]
    return SuccessResponse(data=manifests)


@router.get("/backups/{backup_id}/verify", response_model=SuccessResponse[BackupVerifyResponse], dependencies=[admin_guard])
def verify_backup(
    backup_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Verify archive integrity, calculate fresh SHA-256 hash, and validate inner SQLite snapshot."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM backup_manifests WHERE id = ?;", (backup_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup manifest #{backup_id} not found.",
        )

    filepath = Path(row["filepath"])
    now_str = datetime.now(timezone.utc).isoformat()

    if not filepath.exists():
        cursor.execute("UPDATE backup_manifests SET status = 'CORRUPT', verified_at = ? WHERE id = ?;", (now_str, backup_id))
        db.commit()
        cursor.close()
        return SuccessResponse(
            data=BackupVerifyResponse(
                id=backup_id,
                filename=row["filename"],
                is_valid=False,
                sha256_hash="",
                integrity_status="FILE_NOT_FOUND",
                message=f"Archive file does not exist at '{filepath}'.",
                verified_at=now_str,
            )
        )

    # 1. Compute SHA-256 of the .pbk archive
    current_hash = _compute_sha256(filepath)
    if current_hash != row["sha256_hash"]:
        cursor.execute("UPDATE backup_manifests SET status = 'CORRUPT', verified_at = ? WHERE id = ?;", (now_str, backup_id))
        db.commit()
        cursor.close()
        return SuccessResponse(
            data=BackupVerifyResponse(
                id=backup_id,
                filename=row["filename"],
                is_valid=False,
                sha256_hash=current_hash,
                integrity_status="HASH_MISMATCH",
                message=f"Calculated SHA-256 does not match recorded manifest hash.",
                verified_at=now_str,
            )
        )

    # 2. Inspect inner zip contents and SQLite integrity
    temp_dir = Path(tempfile.mkdtemp(prefix="pbk_verify_"))
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            namelist = zf.namelist()
            if "pharmacy.db" not in namelist or "manifest.json" not in namelist:
                cursor.execute("UPDATE backup_manifests SET status = 'CORRUPT', verified_at = ? WHERE id = ?;", (now_str, backup_id))
                db.commit()
                cursor.close()
                return SuccessResponse(
                    data=BackupVerifyResponse(
                        id=backup_id,
                        filename=row["filename"],
                        is_valid=False,
                        sha256_hash=current_hash,
                        integrity_status="INVALID_ARCHIVE_STRUCTURE",
                        message="Archive missing required pharmacy.db or manifest.json files.",
                        verified_at=now_str,
                    )
                )
            zf.extract("pharmacy.db", temp_dir)

        inner_db = temp_dir / "pharmacy.db"
        inner_conn = sqlite3.connect(str(inner_db))
        check_res = inner_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        inner_conn.close()

        if check_res.lower() != "ok":
            cursor.execute("UPDATE backup_manifests SET status = 'CORRUPT', verified_at = ? WHERE id = ?;", (now_str, backup_id))
            db.commit()
            cursor.close()
            return SuccessResponse(
                data=BackupVerifyResponse(
                    id=backup_id,
                    filename=row["filename"],
                    is_valid=False,
                    sha256_hash=current_hash,
                    integrity_status="SQLITE_CORRUPTION",
                    message=f"PRAGMA integrity_check failed: {check_res}",
                    verified_at=now_str,
                )
            )

        cursor.execute("UPDATE backup_manifests SET status = 'VALID', verified_at = ? WHERE id = ?;", (now_str, backup_id))
        db.commit()
        cursor.close()

        return SuccessResponse(
            data=BackupVerifyResponse(
                id=backup_id,
                filename=row["filename"],
                is_valid=True,
                sha256_hash=current_hash,
                integrity_status="HEALTHY",
                message="Archive SHA-256 hash verified and SQLite database integrity check passed.",
                verified_at=now_str,
            )
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/backups/{backup_id}/download", dependencies=[admin_guard])
def download_backup(
    backup_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Download the compressed backup (.pbk) archive."""
    cursor = db.cursor()
    cursor.execute("SELECT filepath, filename FROM backup_manifests WHERE id = ?;", (backup_id,))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup manifest #{backup_id} not found.",
        )

    filepath = Path(row["filepath"])
    if not filepath.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup archive file not found on disk at '{filepath}'.",
        )

    return FileResponse(
        path=str(filepath),
        media_type="application/octet-stream",
        filename=row["filename"],
    )


# =========================================================================
# 2. DISASTER RECOVERY & SAFE RESTORE
# =========================================================================

@router.post("/restore/preview", response_model=SuccessResponse[RestorePreviewResponse], dependencies=[admin_guard])
async def preview_restore(
    request: Request,
    backup_id: Optional[int] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: sqlite3.Connection = Depends(get_db),
):
    """Inspect and validate a backup archive in a temporary staging area prior to execution."""
    config = _get_active_app_config(request)
    staging_token = str(uuid.uuid4())
    staging_dir = config.app_dir / "staging" / staging_token
    staging_dir.mkdir(parents=True, exist_ok=True)

    archive_path = staging_dir / "backup.pbk"
    archive_filename = "uploaded_backup.pbk"

    if file and file.filename:
        archive_filename = file.filename
        content = await file.read()
        archive_path.write_bytes(content)
    elif backup_id:
        cursor = db.cursor()
        cursor.execute("SELECT filepath, filename FROM backup_manifests WHERE id = ?;", (backup_id,))
        b_row = cursor.fetchone()
        cursor.close()
        if not b_row:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup manifest #{backup_id} not found.",
            )
        source_path = Path(b_row["filepath"])
        if not source_path.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup archive file missing at '{source_path}'.",
            )
        archive_filename = b_row["filename"]
        shutil.copy2(source_path, archive_path)
    else:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a backup_id or an uploaded .pbk file must be provided.",
        )

    # Validate archive format and unpack to staging
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            namelist = zf.namelist()
            if "pharmacy.db" not in namelist or "manifest.json" not in namelist:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid backup package: missing pharmacy.db or manifest.json.",
                )
            zf.extract("pharmacy.db", staging_dir)
            zf.extract("manifest.json", staging_dir)

        staged_db_path = staging_dir / "pharmacy.db"
        staged_manifest_path = staging_dir / "manifest.json"

        # Integrity check on staged DB
        staged_conn = sqlite3.connect(str(staged_db_path))
        staged_conn.row_factory = sqlite3.Row
        int_res = staged_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        if int_res.lower() != "ok":
            staged_conn.close()
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity check failed for staged backup: {int_res}",
            )

        # Parse stats
        staged_stats = _collect_db_stats(staged_conn)
        staged_conn.close()

        manifest_data = {}
        try:
            manifest_data = json.loads(staged_manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        # Check compatibility: staged schema version must be compatible with current engine
        active_stats = _collect_db_stats(db)
        is_compatible = staged_stats["schema_version"] <= active_stats["schema_version"]

        msg = (
            "Backup package is valid and ready for restoration."
            if is_compatible
            else f"Schema version mismatch: Backup is at v{staged_stats['schema_version']}, current engine is at v{active_stats['schema_version']}."
        )

        sha256_hash = _compute_sha256(archive_path)

        # Register in staged cache
        _STAGED_RESTORES[staging_token] = {
            "staging_dir": str(staging_dir),
            "staged_db_path": str(staged_db_path),
            "schema_version": staged_stats["schema_version"],
            "sha256_hash": sha256_hash,
            "filename": archive_filename,
            "created_at": manifest_data.get("created_at", datetime.now(timezone.utc).isoformat()),
        }

        return SuccessResponse(
            data=RestorePreviewResponse(
                staging_token=staging_token,
                filename=archive_filename,
                created_at=manifest_data.get("created_at", datetime.now(timezone.utc).isoformat()),
                schema_version=staged_stats["schema_version"],
                invoice_count=staged_stats["invoice_count"],
                medicine_count=staged_stats["medicine_count"],
                revenue_total_paise=staged_stats["revenue_total_paise"],
                khata_balance_paise=staged_stats["khata_balance_paise"],
                sha256_hash=sha256_hash,
                integrity_status="HEALTHY",
                is_compatible=is_compatible,
                message=msg,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to inspect backup package: {str(exc)}",
        )


@router.post("/restore/execute", response_model=SuccessResponse[RestoreExecuteResponse], dependencies=[admin_guard])
def execute_restore(
    payload: RestoreExecuteRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Safely restore database from a verified staging session with automatic pre-restore safety snapshot."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation flag must be set to true to execute database restoration.",
        )

    staged_info = _STAGED_RESTORES.get(payload.staging_token)
    if not staged_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staging session expired or not found. Please preview the backup package again.",
        )

    staged_db_path = Path(staged_info["staged_db_path"])
    staging_dir = Path(staged_info["staging_dir"])

    if not staged_db_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staged database file no longer exists.",
        )

    config = _get_active_app_config(request)

    # 1. Automatic Pre-Restore Safety Backup
    logger.info("Generating automatic pre-restore safety backup prior to swap...")
    safety_manifest = _create_hot_backup_archive(
        db=db,
        config=config,
        backup_type="PRE_RESTORE_SAFETY",
        notes=f"Automatic safety snapshot before restoring from '{staged_info['filename']}'",
        user_id=current_user["id"],
    )

    # 2. Perform safe transactional database restore using sqlite3.backup
    # This avoids file locking and access denied errors on Windows NTFS
    try:
        staged_conn = sqlite3.connect(str(staged_db_path))
        staged_conn.backup(db)
        staged_conn.close()

        # Checkpoint WAL pages into main database
        db.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        now_str = datetime.now(timezone.utc).isoformat()

        # Cleanup staging session
        _STAGED_RESTORES.pop(payload.staging_token, None)
        shutil.rmtree(staging_dir, ignore_errors=True)

        return SuccessResponse(
            data=RestoreExecuteResponse(
                success=True,
                message="Database successfully restored from backup package.",
                safety_backup_filename=safety_manifest.filename,
                restored_schema_version=staged_info["schema_version"],
                restored_at=now_str,
            )
        )
    except Exception as exc:
        logger.error("Restore failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database restore failed: {str(exc)}",
        )


# =========================================================================
# 3. SYSTEM CONFIGURATION & STORE SETTINGS
# =========================================================================

@router.get("/config", response_model=SuccessResponse[SystemConfigResponse], dependencies=[admin_guard])
def get_system_config(
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve operational settings and store configuration."""
    cursor = db.cursor()
    cursor.execute("SELECT key, value FROM system_config;")
    rows = cursor.fetchall()
    cursor.close()

    configs = {r["key"]: r["value"] for r in rows}
    return SuccessResponse(data=SystemConfigResponse(configs=configs))


@router.put("/config", response_model=SuccessResponse[SystemConfigResponse], dependencies=[admin_guard])
def update_system_config(
    payload: SystemConfigUpdateRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update system settings and store credentials."""
    now_str = datetime.now(timezone.utc).isoformat()
    cursor = db.cursor()

    for key, value in payload.configs.items():
        cursor.execute("""
            INSERT INTO system_config (key, value, updated_by, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at;
        """, (key, str(value), current_user["id"], now_str))

    db.commit()

    # Re-fetch all configs
    cursor.execute("SELECT key, value FROM system_config;")
    rows = cursor.fetchall()
    cursor.close()

    configs = {r["key"]: r["value"] for r in rows}
    return SuccessResponse(data=SystemConfigResponse(configs=configs))


# =========================================================================
# 4. LAN ACTIVATION & SERVER TELEMETRY
# =========================================================================

def _get_local_ip_addresses() -> List[str]:
    """Discover all reachable local IPv4 addresses on active network interfaces."""
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    # Fallback to UDP socket trick if hostname resolution yields only loopback
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            sock_ip = s.getsockname()[0]
            s.close()
            if sock_ip and not sock_ip.startswith("127."):
                ips.append(sock_ip)
        except Exception:
            pass

    return ips or ["127.0.0.1"]


@router.get("/info", response_model=SuccessResponse[SystemDiscoveryResponse])
@router.get("/discovery", response_model=SuccessResponse[SystemDiscoveryResponse])
def get_system_discovery_info(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve server status, active host bindings, and LAN discovery IPs."""
    config = _get_active_app_config(request)
    cursor = db.cursor()
    cursor.execute("SELECT key, value FROM system_config WHERE key IN ('server_mode', 'store_name', 'lan_port');")
    cfg_rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    cursor.close()

    server_mode = cfg_rows.get("server_mode", "STANDALONE")
    store_name = cfg_rows.get("store_name", "Apex Health Pharmacy")
    lan_ips = _get_local_ip_addresses()

    # Calculate active db size
    db_size_kb = 0.0
    if config.db_path and config.db_path.exists():
        db_size_kb = round(config.db_path.stat().st_size / 1024.0, 2)

    uptime = round(getattr(request.app.state, "start_time", 0), 2)
    uptime_sec = round(datetime.now(timezone.utc).timestamp() - uptime, 2) if uptime else 0.0

    return SuccessResponse(
        data=SystemDiscoveryResponse(
            server_name=store_name,
            version=__version__,
            server_mode=server_mode,
            host=config.host,
            port=config.port,
            lan_ips=lan_ips,
            database_status="HEALTHY",
            database_size_kb=db_size_kb,
            uptime_seconds=max(0.0, uptime_sec),
            platform=os.name,
            mdns_enabled=False,  # Unblocking fallback: zero-conf optional
        )
    )


# =========================================================================
# 5. HARDWARE VALIDATION & PRINTER DIAGNOSTICS
# =========================================================================

@router.post("/hardware/test-printer", response_model=SuccessResponse[HardwareTestResponse], dependencies=[admin_guard])
def test_hardware_printer(
    payload: HardwareTestRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Execute a real or simulated hardware print test (USB ESC/POS, TCP Network, or Laser)."""
    cursor = db.cursor()
    cursor.execute("SELECT key, value FROM system_config WHERE key = 'store_name';")
    row = cursor.fetchone()
    store_name = row["value"] if row else "APEX HEALTH PHARMACY"
    cursor.close()

    store_info = {"store_name": store_name}
    service = default_printer_service
    is_sim = payload.simulation_mode

    # Cash Drawer kick test
    if payload.test_type == "drawer_kick":
        pulse = service.generate_drawer_pulse_bytes()
        service.log_simulation(pulse, "Drawer Kick Test Pulse")
        hex_s = pulse.hex()
        return SuccessResponse(
            data=HardwareTestResponse(
                success=True,
                printer_type="thermal",
                target=payload.target or "Local Spooler / Drawer Pin 2",
                bytes_generated=len(pulse),
                message="Cash drawer pulse generated (b'\\x1bp\\x00\\x19\\xfa')",
                is_simulated=is_sim or service.mock_mode,
                hex_sample=hex_s,
                ascii_preview="<ESC>p<0><25><250>",
            )
        )

    # A4/A5 Laser Invoice test
    if payload.test_type == "invoice" or payload.printer_type == "laser":
        sample_inv = {
            "invoice_no": "TEST-INV-001",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "customer_name": "Test Diagnostics",
            "payment_mode": "CASH",
            "items": [],
            "subtotal_taxable_paise": 10000,
            "total_cgst_paise": 600,
            "total_sgst_paise": 600,
            "grand_total_paise": 11200,
        }
        html_doc = service.generate_invoice_html(sample_inv, store_info)
        return SuccessResponse(
            data=HardwareTestResponse(
                success=True,
                printer_type="laser",
                target=payload.target or "Default Laser Spooler",
                bytes_generated=len(html_doc.encode("utf-8")),
                message="A4 Laser tax invoice template rendered successfully.",
                is_simulated=True,
                hex_sample=html_doc[:64].encode("utf-8").hex(),
                ascii_preview=html_doc[:250],
            )
        )

    # Standard 80mm ESC/POS Test Receipt
    test_bytes = service.generate_test_receipt_bytes(store_info)
    hex_sample = test_bytes[:64].hex()
    ascii_prev = test_bytes.decode("ascii", errors="replace")[:250].replace("\x1b", "<ESC>").replace("\x1d", "<GS>")

    if is_sim:
        service.log_simulation(test_bytes, "Diagnostic Self-Test Receipt (Simulated)")
        return SuccessResponse(
            data=HardwareTestResponse(
                success=True,
                printer_type=payload.printer_type,
                target=payload.target or "Simulation Buffer",
                bytes_generated=len(test_bytes),
                message=f"Simulated ESC/POS test receipt ({len(test_bytes)} bytes) logged to spooler_simulation.log",
                is_simulated=True,
                hex_sample=hex_sample,
                ascii_preview=ascii_prev,
            )
        )

    # Network thermal printer via TCP socket (host:port)
    if payload.printer_type == "network" or (payload.target and ":" in payload.target):
        target = payload.target or "127.0.0.1:9100"
        host, port_str = target.split(":", 1) if ":" in target else (target, "9100")
        res = service.send_network_raw_bytes(host, int(port_str), test_bytes)
        return SuccessResponse(
            data=HardwareTestResponse(
                success=res.success,
                printer_type="network",
                target=f"{host}:{port_str}",
                bytes_generated=res.bytes_generated,
                message=res.message,
                is_simulated=res.is_mock,
                hex_sample=res.hex_sample,
                ascii_preview=res.ascii_preview,
            )
        )

    # Local USB / Win32 Spooler
    sample_inv = {
        "invoice_no": "TEST-TICKET",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
        "grand_total_paise": 0,
    }
    res = service.print_invoice(sample_inv, printer_type="thermal", printer_name=payload.target, store_info=store_info)
    return SuccessResponse(
        data=HardwareTestResponse(
            success=res.success,
            printer_type="thermal",
            target=payload.target or "Default Windows Spooler",
            bytes_generated=res.bytes_generated,
            message=res.message,
            is_simulated=res.is_mock,
            hex_sample=res.hex_sample,
            ascii_preview=res.ascii_preview,
        )
    )


# =============================================================================
# OFFLINE CLIENT LICENSING
# =============================================================================

@router.get("/license", tags=["Licensing"])
def get_license_status(request: Request):
    """Retrieve active offline client license status and terminal entitlements."""
    from dataclasses import asdict
    from ..security.license import LicenseManager

    config = _get_active_app_config(request)
    mgr = LicenseManager(config.app_dir / "license.json")
    lic_status = mgr.get_status()
    return SuccessResponse(data=asdict(lic_status))


@router.post("/license", tags=["Licensing"])
def apply_license(
    payload: Dict[str, Any],
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
):
    """Import and activate a cryptographically signed client license.

    Allows unauthenticated calls during first-run setup (when no admin user exists yet).
    Requires active admin authentication once system has been initialized.
    """
    from dataclasses import asdict
    from ..security.license import LicenseManager, evaluate_license

    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users';")
    users_exists = cursor.fetchone() is not None
    admin_count = 0
    if users_exists:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_active = 1;")
        admin_count = cursor.fetchone()[0]
    cursor.close()

    if admin_count > 0:
        # Require admin credentials
        config = _get_active_app_config(request)
        current_user = get_current_user(credentials=credentials, db=db, config=config)
        if current_user.get("role") != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can apply license updates.",
            )

    lic_status = evaluate_license(payload)
    if not lic_status.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid license: {lic_status.message}",
        )
    config = _get_active_app_config(request)
    mgr = LicenseManager(config.app_dir / "license.json")
    mgr.save_license(payload)
    return SuccessResponse(data=asdict(lic_status))



"""
Database backup job.
"""

import base64
import hashlib
import os
import subprocess
import structlog
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pytz

from app.config import settings, get_google_credentials

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)

# Backup directory
BACKUP_DIR = Path("/app/backups")

# Google Drive scopes
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """Get Google Drive service."""
    try:
        credentials = get_google_credentials(DRIVE_SCOPES)
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        logger.error("Failed to initialize Google Drive service", error=str(e))
        return None


def _get_backup_fernet() -> Fernet:
    """Derive a Fernet key from SECRET_KEY for backup encryption."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        settings.secret_key.encode(),
        b"agencybot-backup-encryption",  # static salt (distinct from Redis salt)
        iterations=100_000,
    )
    fernet_key = base64.urlsafe_b64encode(dk)
    return Fernet(fernet_key)


def _encrypt_file(src_path: Path, dest_path: Path) -> None:
    """Read *src_path*, encrypt its contents with Fernet, and write to *dest_path*."""
    fernet = _get_backup_fernet()
    plaintext = src_path.read_bytes()
    ciphertext = fernet.encrypt(plaintext)
    dest_path.write_bytes(ciphertext)


async def backup_database() -> None:
    """
    Create a backup of the PostgreSQL database and upload to Google Drive.

    This job:
    1. Creates a pg_dump of the database
    2. Uploads the backup file to Google Drive
    3. Cleans up old local backups (keeps last 7 days)
    """
    logger.info("Starting database backup job")

    try:
        # Ensure backup directory exists
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{settings.app_name}_backup_{timestamp}.sql"
        backup_path = BACKUP_DIR / backup_filename

        # Parse database URL for pg_dump
        # Expected format: postgresql+asyncpg://user:pass@host:port/dbname
        db_url = settings.database_url
        # Remove the async driver prefix
        db_url = db_url.replace("+asyncpg", "")

        # Extract connection details
        # Format: postgresql://user:pass@host:port/dbname
        from urllib.parse import urlparse

        parsed = urlparse(db_url)

        pg_host = parsed.hostname or "localhost"
        pg_port = parsed.port or 5432
        pg_user = parsed.username
        pg_password = parsed.password
        pg_database = parsed.path.lstrip("/")

        # Set environment variable for password
        env = os.environ.copy()
        env["PGPASSWORD"] = pg_password

        # Run pg_dump
        cmd = [
            "pg_dump",
            "-h", pg_host,
            "-p", str(pg_port),
            "-U", pg_user,
            "-d", pg_database,
            "-f", str(backup_path),
            "--no-owner",
            "--no-acl",
        ]

        logger.info("Running pg_dump", host=pg_host, database=pg_database)

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error(
                "pg_dump failed",
                stderr=result.stderr,
                returncode=result.returncode,
            )
            from app.services.telegram_notifier import notify_error
            await notify_error(
                "backup",
                f"pg_dump failed with code {result.returncode}: {result.stderr[:300]}",
            )
            return

        # Check backup file size
        backup_size = backup_path.stat().st_size
        logger.info(
            "Backup created (unencrypted)",
            filename=backup_filename,
            size_bytes=backup_size,
        )

        # Encrypt the backup before storing or transmitting
        encrypted_filename = f"{backup_filename}.enc"
        encrypted_path = BACKUP_DIR / encrypted_filename
        _encrypt_file(backup_path, encrypted_path)
        encrypted_size = encrypted_path.stat().st_size
        logger.info(
            "Backup encrypted",
            filename=encrypted_filename,
            size_bytes=encrypted_size,
        )

        # Delete the plain-text SQL dump immediately
        backup_path.unlink()

        # Send encrypted backup to Telegram
        if settings.telegram_notifications_enabled:
            from app.services.telegram_notifier import telegram_notifier
            import pytz

            tz = pytz.timezone(settings.calendar_timezone)
            now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            size_kb = round(encrypted_size / 1024, 1)
            caption = (
                f"\U0001f4be <b>Backup diario (cifrado)</b>\n\n"
                f"<b>App:</b> {settings.app_name}\n"
                f"<b>Fecha:</b> {now}\n"
                f"<b>Tama\u00f1o:</b> {size_kb} KB\n"
                f"<b>Cifrado:</b> Fernet (AES-128-CBC)"
            )
            await telegram_notifier.send_document(str(encrypted_path), caption)
        else:
            logger.info("Telegram not configured, encrypted backup saved locally only")

        # Upload encrypted backup to Google Drive (if configured)
        if settings.google_drive_folder_id:
            uploaded = await upload_to_drive(encrypted_path, encrypted_filename)
            if uploaded:
                await cleanup_old_drive_backups(days_to_keep=settings.backup_retention_days)

        # Clean up old local backups (keep last 7 days)
        await cleanup_old_backups(days_to_keep=7)

        logger.info("Database backup job completed successfully")

    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out")
        from app.services.telegram_notifier import notify_error
        await notify_error("backup", "pg_dump timed out (300s limit)")
    except Exception as e:
        logger.error("Error in database backup job", error=str(e))
        import traceback
        from app.services.telegram_notifier import notify_error
        await notify_error(
            "backup",
            f"Database backup failed: {str(e)}",
            traceback_str=traceback.format_exc(),
        )


async def upload_to_drive(file_path: Path, filename: str) -> bool:
    """
    Upload a file to Google Drive.

    Args:
        file_path: Path to the local file
        filename: Name for the file in Drive

    Returns:
        True if successful, False otherwise
    """
    try:
        service = get_drive_service()
        if not service:
            return False

        file_metadata = {
            "name": filename,
            "parents": [settings.google_drive_folder_id],
        }

        mimetype = "application/octet-stream" if filename.endswith(".enc") else "application/sql"
        media = MediaFileUpload(
            str(file_path),
            mimetype=mimetype,
            resumable=True,
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()

        logger.info(
            "Backup uploaded to Google Drive",
            filename=filename,
            file_id=file.get("id"),
        )

        return True

    except Exception as e:
        logger.error("Failed to upload backup to Google Drive", error=str(e))
        return False


async def cleanup_old_drive_backups(days_to_keep: int = 30) -> None:
    """
    Remove old backup files from Google Drive.

    Lists all files in the backup folder whose name matches the backup pattern
    and whose createdTime is older than the retention window, then deletes them.

    Args:
        days_to_keep: Number of days to keep backups in Drive
    """
    try:
        service = get_drive_service()
        if not service:
            return

        cutoff = datetime.now(TZ) - timedelta(days=days_to_keep)
        cutoff_rfc3339 = cutoff.strftime("%Y-%m-%dT%H:%M:%S%z")
        # Insert colon in timezone offset for RFC 3339 (e.g., +0000 -> +00:00)
        if cutoff_rfc3339[-5] in ('+', '-') and ':' not in cutoff_rfc3339[-5:]:
            cutoff_rfc3339 = cutoff_rfc3339[:-2] + ":" + cutoff_rfc3339[-2:]

        query = (
            f"'{settings.google_drive_folder_id}' in parents"
            f" and name contains '_backup_'"
            f" and createdTime < '{cutoff_rfc3339}'"
            f" and trashed = false"
        )

        result = service.files().list(
            q=query,
            fields="files(id, name, createdTime)",
            pageSize=100,
        ).execute()

        files = result.get("files", [])
        if not files:
            logger.info("No old Drive backups to clean up")
            return

        deleted = 0
        for file in files:
            try:
                service.files().delete(fileId=file["id"]).execute()
                deleted += 1
                logger.info(
                    "Deleted old Drive backup",
                    filename=file["name"],
                    created=file["createdTime"],
                )
            except Exception as e:
                logger.error(
                    "Failed to delete Drive backup",
                    filename=file["name"],
                    error=str(e),
                )

        logger.info("Drive backup cleanup completed", deleted=deleted)

    except Exception as e:
        logger.error("Error cleaning up old Drive backups", error=str(e))


async def cleanup_old_backups(days_to_keep: int = 7) -> None:
    """
    Remove local backup files older than specified days.

    Args:
        days_to_keep: Number of days to keep backups
    """
    try:
        now = datetime.now()
        cutoff = now.timestamp() - (days_to_keep * 24 * 60 * 60)

        for pattern in [f"{settings.app_name}_backup_*.sql", f"{settings.app_name}_backup_*.sql.enc"]:
            for backup_file in BACKUP_DIR.glob(pattern):
                if backup_file.stat().st_mtime < cutoff:
                    backup_file.unlink()
                    logger.info("Removed old backup", filename=backup_file.name)

    except Exception as e:
        logger.error("Error cleaning up old backups", error=str(e))

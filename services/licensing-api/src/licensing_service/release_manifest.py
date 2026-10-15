"""Official Production Release Manifest and Asset Streaming for MediHisaab Windows Installers."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

from fastapi import status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

logger = logging.getLogger("licensing_service.release_manifest")

REPO_ROOT = Path(__file__).resolve().parents[4]
DIST_RELEASE_DIR = REPO_ROOT / "dist-release"

# Official published releases
OFFICIAL_RELEASES: Dict[str, Dict[str, Any]] = {
    "1.0.8": {
        "id": "installer-windows",
        "title": "MediHisaab Windows Installer (v1.0.8)",
        "version": "1.0.8",
        "filename": "MediHisaab-Setup-1.0.8.exe",
        "file_size": "122.5 MB (128,500,444 bytes)",
        "file_size_bytes": 128500444,
        "sha256": "79e0284d8e4fd9b6600796b952aeff3fed74516e4fd0a28d560e40cb093da0d4d",
        "release_date": "October 2026",
        "os": "Windows 10 / 11 (64-bit)",
        "download_url": "/api/v1/client/downloads/installer-windows/file",
        "direct_download_url": "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.8/MediHisaab-Setup-1.0.8.exe",
        "is_installer": True,
        "description": "MediHisaab desktop installer with reliable CSV/Excel sample downloads and visible download error feedback.",
    },
    "1.0.7": {
        "id": "installer-windows",
        "title": "MediHisaab Windows Installer (v1.0.7)",
        "version": "1.0.7",
        "filename": "MediHisaab-Setup-1.0.7.exe",
        "file_size": "122.5 MB (128,500,842 bytes)",
        "file_size_bytes": 128500842,
        "sha256": "ba77b55611a575bec3d4acad5ff4a4a9d30661630875075d0f7ec81585e2293b",
        "release_date": "October 2026",
        "os": "Windows 10 / 11 (64-bit)",
        "download_url": "/api/v1/client/downloads/installer-windows/file",
        "direct_download_url": "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.7/MediHisaab-Setup-1.0.7.exe",
        "is_installer": True,
        "description": "MediHisaab desktop installer with CSV/Excel import sample files and improved opening-stock expiry header handling.",
    },
    "1.0.6": {
        "id": "installer-windows",
        "title": "MediHisaab Windows Installer (v1.0.6)",
        "version": "1.0.6",
        "filename": "MediHisaab-Setup-1.0.6.exe",
        "file_size": "121.0 MB (126,833,835 bytes)",
        "file_size_bytes": 126833835,
        "sha256": "f9729901c59d88a0ff39333b1541771f9098da84d0db11198409926ed1b0b0c7",
        "release_date": "October 2026",
        "os": "Windows 10 / 11 (64-bit)",
        "download_url": "/api/v1/client/downloads/installer-windows/file",
        "direct_download_url": "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.6/MediHisaab-Setup-1.0.6.exe",
        "is_installer": True,
        "description": "MediHisaab desktop installer with the updated profile menu overlay and current offline-first POS bundle.",
    },
    "1.0.3": {
        "id": "installer-windows",
        "title": "MediHisaab Windows Installer (v1.0.3)",
        "version": "1.0.3",
        "filename": "MediHisaab-Setup-1.0.3.exe",
        "file_size": "91.0 MB (95,453,540 bytes)",
        "file_size_bytes": 95453540,
        "sha256": "e16d1742f00a7f9e4dea9010c01849d8ec43243cdf2d03ad3aa047cb36cfe583",
        "release_date": "October 2026",
        "os": "Windows 10 / 11 (64-bit)",
        "download_url": "/api/v1/client/downloads/installer-windows/file",
        "direct_download_url": "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.3/MediHisaab-Setup-1.0.3.exe",
        "is_installer": True,
        "description": "Standalone offline-first MediHisaab installer with embedded Python daemon, SQLite WAL engine, ESC/POS printing, and LAN multi-counter support.",
    },
    "1.0.0": {
        "id": "installer-windows-1.0.0",
        "title": "MediHisaab Windows Installer (v1.0.0)",
        "version": "1.0.0",
        "filename": "MediHisaab-Setup-1.0.0.exe",
        "file_size": "91.0 MB (95,442,984 bytes)",
        "file_size_bytes": 95442984,
        "sha256": "2e323e4b90768f866699b24c2aad6ba36f201e092acd65ba8cf6010b0f91c02f",
        "release_date": "October 2026",
        "os": "Windows 10 / 11 (64-bit)",
        "download_url": "/MediHisaab-Setup-1.0.0.exe",
        "direct_download_url": "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.3/MediHisaab-Setup-1.0.0.exe",
        "is_installer": True,
        "description": "Initial release of MediHisaab Windows installer.",
    },
}

LATEST_RELEASE = OFFICIAL_RELEASES["1.0.8"]


def get_latest_release_metadata() -> Dict[str, Any]:
    """Return the official latest release metadata."""
    return dict(LATEST_RELEASE)


def get_release_by_filename_or_version(target: str) -> Optional[Dict[str, Any]]:
    """Lookup release metadata by version number or setup filename."""
    clean = target.strip().lower()
    if clean in OFFICIAL_RELEASES:
        return OFFICIAL_RELEASES[clean]
    for rel in OFFICIAL_RELEASES.values():
        if rel["filename"].lower() == clean or f"medihisaab-setup-{rel['version']}.exe".lower() == clean:
            return rel
    return None


def serve_release_installer(requested_file: Optional[str] = None):
    """Serve the Windows installer binary.
    
    1. If present on the local filesystem (e.g. dist-release/), serves via FileResponse.
    2. Else streams verified bytes directly from the persistent GitHub Release asset with
       proper Content-Type, Content-Disposition, and Content-Length.
    3. If unavailable, returns HTTP 404 JSON with clear diagnostic status.
    """
    rel = get_release_by_filename_or_version(requested_file) if requested_file else LATEST_RELEASE
    if not rel:
        rel = LATEST_RELEASE

    filename = rel["filename"]
    file_size_bytes = rel["file_size_bytes"]
    remote_url = rel["direct_download_url"]

    # 1. Check local filesystem in dist-release
    local_path = DIST_RELEASE_DIR / filename
    if local_path.is_file() and local_path.stat().st_size > 0:
        logger.info("Serving installer %s directly from local filesystem (%s bytes)", filename, local_path.stat().st_size)
        return FileResponse(
            str(local_path),
            filename=filename,
            media_type="application/vnd.microsoft.portable-executable",
        )

    # Also check if another installer version exists locally as fallback
    if not requested_file:
        for candidate in (DIST_RELEASE_DIR / LATEST_RELEASE["filename"], DIST_RELEASE_DIR / "MediHisaab-Setup-1.0.0.exe"):
            if candidate.is_file() and candidate.stat().st_size > 0:
                logger.info("Serving fallback installer from local file: %s", candidate)
                return FileResponse(
                    str(candidate),
                    filename=candidate.name,
                    media_type="application/vnd.microsoft.portable-executable",
                )

    # 2. Stream from verified public persistent release asset
    try:
        req = urllib.request.Request(
            remote_url,
            headers={
                "User-Agent": "MediHisaab-Licensing-Service",
                "Accept": "*/*",
            },
        )
        resp = urllib.request.urlopen(req, timeout=15)
    except Exception as exc:
        logger.error("Failed to connect to remote release asset %s: %s", remote_url, exc)
        return JSONResponse(
            {
                "status": "UNAVAILABLE",
                "message": "The Windows installer binary is currently being packaged or unavailable on this server instance.",
                "file": filename,
                "version": rel["version"],
                "support": "support@apexhealth.com",
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )

    def iter_remote_chunks():
        try:
            with resp:
                while chunk := resp.read(65536):
                    yield chunk
        except Exception as read_exc:
            logger.error("Error streaming release asset chunks: %s", read_exc)

    logger.info("Streaming installer %s from persistent remote asset: %s", filename, remote_url)
    return StreamingResponse(
        iter_remote_chunks(),
        media_type="application/vnd.microsoft.portable-executable",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_size_bytes),
        },
    )

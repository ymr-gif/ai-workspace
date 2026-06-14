import time
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import decrypt_token, encrypt_token
from llm import client as llm_client
from models import ExternalSource
from services.integrations.google_drive import GoogleDriveConnector

logger = logging.getLogger("tools.drive")

DRIVE_API = "https://www.googleapis.com/drive/v3"

_READABLE_MIME_PREFIXES = ("application/vnd.google-apps", "text/")
_READABLE_MIME_EXACT = {"application/json", "application/xml", "application/javascript"}


def _is_readable(mime_type: str) -> bool:
    return any(mime_type.startswith(p) for p in _READABLE_MIME_PREFIXES) or mime_type in _READABLE_MIME_EXACT


async def _load_credentials(db: AsyncSession, user_id: int) -> tuple[ExternalSource | None, dict | None]:
    src = await db.scalar(
        select(ExternalSource).where(
            ExternalSource.user_id == user_id,
            ExternalSource.connector_type == "google_drive",
            ExternalSource.status == "active",
        )
    )
    if not src or not src.credentials:
        return None, None

    creds = {
        "access_token": decrypt_token(src.credentials["access_token"]),
        "refresh_token": decrypt_token(src.credentials["refresh_token"]) if src.credentials.get("refresh_token") else None,
        "expires_at": src.credentials.get("expires_at"),
    }

    if creds.get("expires_at") and creds["expires_at"] < int(time.time()):
        if not creds.get("refresh_token"):
            src.status = "needs_reauth"
            await db.commit()
            return src, None
        creds = await GoogleDriveConnector.refresh_tokens(creds)
        src.credentials = {
            "access_token": encrypt_token(creds["access_token"]),
            "expires_at": creds.get("expires_at"),
        }
        if creds.get("refresh_token"):
            src.credentials["refresh_token"] = encrypt_token(creds["refresh_token"])
        await db.commit()

    return src, creds


async def _drive_list_files(db: AsyncSession, user_id: int, query: str | None = None) -> str:
    src, creds = await _load_credentials(db, user_id)
    if not src:
        return "Google Drive not connected. Please connect via the Integrations panel."
    if not creds:
        return "Google Drive access expired. Please reconnect via the Integrations panel."

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    params = {
        "fields": "nextPageToken,files(id,name,mimeType,modifiedTime)",
        "pageSize": 100,
        "orderBy": "modifiedTime desc",
    }
    if query:
        params["q"] = query

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.get(f"{DRIVE_API}/files", headers=headers, params=params)
    if resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Google Drive access expired. Please reconnect via the Integrations panel."
    resp.raise_for_status()

    data = resp.json()
    files = data.get("files", [])
    if not files:
        return "No files found."

    lines = []
    for f in files:
        readable = _is_readable(f["mimeType"])
        tag = "" if readable else " [unreadable — binary format]"
        lines.append(f"- {f['name']}{tag} (id={f['id']}, type={f['mimeType']}, modified={f.get('modifiedTime', '?')})")

    if data.get("nextPageToken"):
        lines.append(f"\n[Showing first {len(files)} files — more exist. Use drive_search to find specific files by content or name. Do not call drive_list_files again. Only call drive_read_file for files directly relevant to the user's request.]")
    else:
        lines.append(f"\n[{len(files)} file(s) total. This listing is complete — do not call drive_list_files again. Only call drive_read_file for files directly relevant to the user's request.]")
    return "\n".join(lines)


async def _drive_read_file(db: AsyncSession, user_id: int, file_id: str, max_chars: int = 12000) -> str:
    src, creds = await _load_credentials(db, user_id)
    if not src:
        return "Google Drive not connected. Please connect via the Integrations panel."
    if not creds:
        return "Google Drive access expired. Please reconnect via the Integrations panel."

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    meta_resp = await client.get(f"{DRIVE_API}/files/{file_id}?fields=mimeType,name", headers=headers)
    if meta_resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Google Drive access expired. Please reconnect via the Integrations panel."
    meta_resp.raise_for_status()
    meta = meta_resp.json()
    mime_type = meta.get("mimeType", "")
    name = meta.get("name", file_id)

    if mime_type == "application/vnd.google-apps.spreadsheet":
        export_url = f"{DRIVE_API}/files/{file_id}/export?mimeType=text/csv"
        content_resp = await client.get(export_url, headers=headers)
    elif mime_type.startswith("application/vnd.google-apps"):
        export_url = f"{DRIVE_API}/files/{file_id}/export?mimeType=text/plain"
        content_resp = await client.get(export_url, headers=headers)
    elif mime_type.startswith("text/") or mime_type in ("application/json", "application/xml", "application/javascript"):
        download_url = f"{DRIVE_API}/files/{file_id}?alt=media"
        content_resp = await client.get(download_url, headers=headers)
    else:
        return f"Cannot read '{name}': binary format ({mime_type}). Only Google Docs and plain-text files are supported."

    if content_resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Google Drive access expired. Please reconnect via the Integrations panel."
    content_resp.raise_for_status()

    content = content_resp.text
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n[Content truncated at {max_chars} chars]"

    return f"--- {name} ---\n{content}"


async def _drive_search(db: AsyncSession, user_id: int, query: str) -> str:
    src, creds = await _load_credentials(db, user_id)
    if not src:
        return "Google Drive not connected. Please connect via the Integrations panel."
    if not creds:
        return "Google Drive access expired. Please reconnect via the Integrations panel."

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    q_escaped = query.replace("'", "\\'")
    params = {"q": f"fullText contains '{q_escaped}'", "fields": "nextPageToken,files(id,name,mimeType,modifiedTime)", "pageSize": 100}

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.get(f"{DRIVE_API}/files", headers=headers, params=params)
    if resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Google Drive access expired. Please reconnect via the Integrations panel."
    resp.raise_for_status()

    data = resp.json()
    files = data.get("files", [])
    if not files:
        return "No files found matching that query."

    lines = []
    for f in files:
        lines.append(f"- {f['name']} (id={f['id']}, type={f['mimeType']}, modified={f.get('modifiedTime', '?')})")

    if data.get("nextPageToken"):
        lines.append(f"\n[Showing first {len(files)} matches — more exist. Refine your query to narrow results. Do not repeat this search. Only call drive_read_file for files directly relevant to the user's request.]")
    else:
        lines.append(f"\n[{len(files)} file(s) matched. Search complete — do not call drive_search again with the same query. Only call drive_read_file for files directly relevant to the user's request.]")
    return "\n".join(lines)

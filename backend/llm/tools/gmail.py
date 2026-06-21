import base64
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from llm import client as llm_client
from models import ExternalSource
from services.integrations.gmail import GmailConnector
from ._google_creds import load_google_credentials

logger = logging.getLogger("tools.gmail")

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


async def _load_credentials(db: AsyncSession, user_id: int) -> tuple[ExternalSource | None, dict | None]:
    return await load_google_credentials(db, user_id, "gmail", GmailConnector)


def _extract_body(payload: dict) -> str:
    parts = []
    if payload.get("body", {}).get("data"):
        try:
            decoded = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            parts.append(decoded)
        except Exception:
            pass
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _format_message(msg: dict) -> str:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "(no subject)")
    sender = headers.get("from", "(unknown)")
    date = headers.get("date", "(unknown date)")
    body = _extract_body(msg.get("payload", {}))
    snippet = msg.get("snippet", "")
    return f"From: {sender}\nSubject: {subject}\nDate: {date}\n\n{body or snippet}"


def _format_message_preview(msg: dict) -> str:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "(no subject)")
    sender = headers.get("from", "(unknown)")
    date = headers.get("date", "(unknown)")
    snippet = msg.get("snippet", "")
    return f"- {subject} (from={sender}, date={date}, id={msg['id']})\n  {snippet[:200]}"


async def _gmail_list_messages(db: AsyncSession, user_id: int, max_results: int = 20) -> str:
    src, creds = await _load_credentials(db, user_id)
    if not src:
        return "Gmail not connected. Please connect via the Integrations panel."
    if not creds:
        return "Gmail access expired. Please reconnect via the Integrations panel."

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    params = {"maxResults": max_results, "labelIds": "INBOX"}

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    list_resp = await client.get(f"{GMAIL_API}/users/me/messages", headers=headers, params=params)
    if list_resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Gmail access expired. Please reconnect via the Integrations panel."
    list_resp.raise_for_status()

    data = list_resp.json()
    messages = data.get("messages", [])
    if not messages:
        return "No messages found."

    result_parts = []
    for m in messages[:max_results]:
        detail_resp = await client.get(
            f"{GMAIL_API}/users/me/messages/{m['id']}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": "From,Subject,Date"},
        )
        if detail_resp.status_code == 401:
            break
        detail = detail_resp.json()
        result_parts.append(_format_message_preview(detail))

    return "\n".join(result_parts) + "\n\nTo read a specific message, call gmail_get_message with its ID."


async def _gmail_get_message(db: AsyncSession, user_id: int, message_id: str, max_chars: int = 12000) -> str:
    src, creds = await _load_credentials(db, user_id)
    if not src:
        return "Gmail not connected. Please connect via the Integrations panel."
    if not creds:
        return "Gmail access expired. Please reconnect via the Integrations panel."

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.get(
        f"{GMAIL_API}/users/me/messages/{message_id}",
        headers=headers,
        params={"format": "full"},
    )
    if resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Gmail access expired. Please reconnect via the Integrations panel."
    if resp.status_code == 404:
        return f"Message {message_id} not found."
    resp.raise_for_status()

    msg = resp.json()
    formatted = _format_message(msg)
    if len(formatted) > max_chars:
        formatted = formatted[:max_chars] + f"\n\n[Content truncated at {max_chars} chars]"
    return formatted


async def _gmail_search_messages(db: AsyncSession, user_id: int, query: str, max_results: int = 10) -> str:
    src, creds = await _load_credentials(db, user_id)
    if not src:
        return "Gmail not connected. Please connect via the Integrations panel."
    if not creds:
        return "Gmail access expired. Please reconnect via the Integrations panel."

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    q_escaped = query.replace("'", "\\'")
    params = {"q": q_escaped, "maxResults": max_results}

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    list_resp = await client.get(f"{GMAIL_API}/users/me/messages", headers=headers, params=params)
    if list_resp.status_code == 401:
        src.status = "needs_reauth"
        await db.commit()
        return "Gmail access expired. Please reconnect via the Integrations panel."
    list_resp.raise_for_status()

    data = list_resp.json()
    messages = data.get("messages", [])
    if not messages:
        return "No messages found matching that query."

    result_parts = []
    for m in messages[:max_results]:
        detail_resp = await client.get(
            f"{GMAIL_API}/users/me/messages/{m['id']}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": "From,Subject,Date"},
        )
        if detail_resp.status_code == 401:
            break
        detail = detail_resp.json()
        result_parts.append(_format_message_preview(detail))

    lines = "\n".join(result_parts)
    return f"{lines}\n\n[Search complete — {len(messages)} message(s) matched. To read a specific message, call gmail_get_message with its ID.]"

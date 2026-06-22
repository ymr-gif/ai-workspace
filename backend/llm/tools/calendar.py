import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from llm import client as llm_client
from models import ExternalSource
from services.integrations.google_calendar import GoogleCalendarConnector
from ._google_creds import load_google_credentials

logger = logging.getLogger("tools.calendar")

CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def _not_connected() -> str:
    return "Google Calendar not connected. Please connect via the Integrations panel."


def _expired() -> str:
    return "Google Calendar access expired. Please reconnect via the Integrations panel."


def _forbidden() -> str:
    return (
        "Google Calendar denied access (403). The Calendar API may not be enabled for this "
        "project, or the calendar.events scope wasn't granted. Enable the Google Calendar API "
        "in Google Cloud, then reconnect Google Calendar in the Integrations panel."
    )


async def _mark_reauth(db: AsyncSession, src: ExternalSource) -> None:
    src.status = "needs_reauth"
    await db.commit()


async def _load_calendar_creds(db: AsyncSession, user_id: int) -> tuple[ExternalSource | None, dict | None]:
    return await load_google_credentials(db, user_id, "google_calendar", GoogleCalendarConnector)


async def _calendar_list_events(
    db: AsyncSession,
    user_id: int,
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 20,
) -> str:
    src, creds = await _load_calendar_creds(db, user_id)
    if not src:
        return _not_connected()
    if not creds:
        return _expired()

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    params = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": str(max_results),
    }
    if time_min:
        params["timeMin"] = time_min
    else:
        params["timeMin"] = datetime.now(timezone.utc).isoformat()
    if time_max:
        params["timeMax"] = time_max

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.get(f"{CALENDAR_API}/calendars/primary/events", headers=headers, params=params)
    if resp.status_code == 401:
        await _mark_reauth(db, src)
        return _expired()
    if resp.status_code == 403:
        # 403 = authenticated but not authorized (Calendar API disabled or scope
        # missing). Keep the connector active so the tool stays offered and the
        # model can relay the actionable message — do NOT flip to needs_reauth
        # (that would hide the tool and leave the user with "no calendar access").
        return _forbidden()
    resp.raise_for_status()

    data = resp.json()
    items = data.get("items", [])
    if not items:
        return "No upcoming events found."

    lines = []
    for ev in items:
        start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
        end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date", "?"))
        location = ev.get("location", "")
        loc_str = f", {location}" if location else ""
        lines.append(f"{ev.get('summary', '(no title)')} | {start}–{end}{loc_str} (id={ev['id']})")

    return "\n".join(lines)


async def _calendar_get_event(
    db: AsyncSession,
    user_id: int,
    event_id: str,
) -> str:
    src, creds = await _load_calendar_creds(db, user_id)
    if not src:
        return _not_connected()
    if not creds:
        return _expired()

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.get(f"{CALENDAR_API}/calendars/primary/events/{event_id}", headers=headers)
    if resp.status_code == 401:
        await _mark_reauth(db, src)
        return _expired()
    if resp.status_code == 403:
        # 403 = authenticated but not authorized (Calendar API disabled or scope
        # missing). Keep the connector active so the tool stays offered and the
        # model can relay the actionable message — do NOT flip to needs_reauth
        # (that would hide the tool and leave the user with "no calendar access").
        return _forbidden()
    if resp.status_code == 404:
        return f"Event not found: {event_id}"
    resp.raise_for_status()

    ev = resp.json()
    start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
    end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date", "?"))
    location = ev.get("location", "")
    loc_str = f", {location}" if location else ""
    desc = ev.get("description", "")
    desc_str = f"\nDescription: {desc}" if desc else ""
    return f"{ev.get('summary', '(no title)')} | {start}–{end}{loc_str}{desc_str} (id={ev['id']})"


async def _calendar_search_events(
    db: AsyncSession,
    user_id: int,
    query: str,
) -> str:
    src, creds = await _load_calendar_creds(db, user_id)
    if not src:
        return _not_connected()
    if not creds:
        return _expired()

    headers = {"Authorization": f"Bearer {creds['access_token']}"}
    params = {
        "q": query,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "20",
    }

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.get(f"{CALENDAR_API}/calendars/primary/events", headers=headers, params=params)
    if resp.status_code == 401:
        await _mark_reauth(db, src)
        return _expired()
    if resp.status_code == 403:
        # 403 = authenticated but not authorized (Calendar API disabled or scope
        # missing). Keep the connector active so the tool stays offered and the
        # model can relay the actionable message — do NOT flip to needs_reauth
        # (that would hide the tool and leave the user with "no calendar access").
        return _forbidden()
    resp.raise_for_status()

    data = resp.json()
    items = data.get("items", [])
    if not items:
        return "No events found matching that query."

    lines = []
    for ev in items:
        start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
        end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date", "?"))
        location = ev.get("location", "")
        loc_str = f", {location}" if location else ""
        lines.append(f"{ev.get('summary', '(no title)')} | {start}–{end}{loc_str} (id={ev['id']})")

    return "\n".join(lines)


async def _calendar_create_event(
    db: AsyncSession,
    user_id: int,
    summary: str,
    start: str,
    end: str,
    description: str | None = None,
    location: str | None = None,
) -> str:
    src, creds = await _load_calendar_creds(db, user_id)
    if not src:
        return _not_connected()
    if not creds:
        return _expired()

    headers = {
        "Authorization": f"Bearer {creds['access_token']}",
        "Content-Type": "application/json",
    }
    body = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.post(f"{CALENDAR_API}/calendars/primary/events", headers=headers, json=body)
    if resp.status_code == 401:
        await _mark_reauth(db, src)
        return _expired()
    if resp.status_code == 403:
        # 403 = authenticated but not authorized (Calendar API disabled or scope
        # missing). Keep the connector active so the tool stays offered and the
        # model can relay the actionable message — do NOT flip to needs_reauth
        # (that would hide the tool and leave the user with "no calendar access").
        return _forbidden()
    resp.raise_for_status()

    ev = resp.json()
    return f"Created event: {ev.get('summary')} (id={ev['id']})"


async def _calendar_update_event(
    db: AsyncSession,
    user_id: int,
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> str:
    src, creds = await _load_calendar_creds(db, user_id)
    if not src:
        return _not_connected()
    if not creds:
        return _expired()

    headers = {
        "Authorization": f"Bearer {creds['access_token']}",
        "Content-Type": "application/json",
    }
    body: dict = {}
    if summary is not None:
        body["summary"] = summary
    if start is not None:
        body["start"] = {"dateTime": start}
    if end is not None:
        body["end"] = {"dateTime": end}
    if description is not None:
        body["description"] = description
    if location is not None:
        body["location"] = location

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.patch(f"{CALENDAR_API}/calendars/primary/events/{event_id}", headers=headers, json=body)
    if resp.status_code == 401:
        await _mark_reauth(db, src)
        return _expired()
    if resp.status_code == 403:
        # 403 = authenticated but not authorized (Calendar API disabled or scope
        # missing). Keep the connector active so the tool stays offered and the
        # model can relay the actionable message — do NOT flip to needs_reauth
        # (that would hide the tool and leave the user with "no calendar access").
        return _forbidden()
    if resp.status_code == 404:
        return f"Event not found: {event_id}"
    resp.raise_for_status()

    ev = resp.json()
    return f"Updated event: {ev.get('summary')} (id={ev['id']})"


async def _calendar_delete_event(
    db: AsyncSession,
    user_id: int,
    event_id: str,
) -> str:
    src, creds = await _load_calendar_creds(db, user_id)
    if not src:
        return _not_connected()
    if not creds:
        return _expired()

    headers = {"Authorization": f"Bearer {creds['access_token']}"}

    client = llm_client.client
    if not client:
        return "Internal error: HTTP client unavailable."

    resp = await client.delete(f"{CALENDAR_API}/calendars/primary/events/{event_id}", headers=headers)
    if resp.status_code == 401:
        await _mark_reauth(db, src)
        return _expired()
    if resp.status_code == 403:
        # 403 = authenticated but not authorized (Calendar API disabled or scope
        # missing). Keep the connector active so the tool stays offered and the
        # model can relay the actionable message — do NOT flip to needs_reauth
        # (that would hide the tool and leave the user with "no calendar access").
        return _forbidden()
    if resp.status_code == 404:
        return f"Event not found: {event_id}"
    resp.raise_for_status()

    return f"Deleted event: {event_id}"

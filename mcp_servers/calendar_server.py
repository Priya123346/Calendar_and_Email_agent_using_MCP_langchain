from datetime import datetime
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP
from auth import get_calendar_creds

mcp = FastMCP("calendar-tools", host="0.0.0.0", port=9002)

@mcp.tool()
def create_event(title: str, start: str, end: str, timezone: str = "UTC"):
    """Create a Google Calendar event.

    Args:
        title: Event title.
        start: Start time in "YYYY-MM-DD HH:MM" format.
        end: End time in "YYYY-MM-DD HH:MM" format.
        timezone: IANA time zone, e.g., "Asia/Kolkata".
    """
    creds = get_calendar_creds()
    service = build("calendar", "v3", credentials=creds)

    start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M")

    event = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return f"Event '{title}' created: {created.get('htmlLink')}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")

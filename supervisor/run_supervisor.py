import asyncio
import os
import re
from datetime import datetime, timedelta
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from mcp_loader import load_mcp_tools
from .agent import build_supervisor
load_dotenv()
async def main():
    async with AsyncExitStack() as stack:
        gmail_url = os.getenv("GMAIL_MCP_URL", "http://127.0.0.1:9001/mcp")
        calendar_url = os.getenv("CALENDAR_MCP_URL", "http://127.0.0.1:9002/mcp")
        tools = await load_mcp_tools([gmail_url, calendar_url], stack)
        print("Loaded MCP tools:", [t.name for t in tools])

        agent = build_supervisor(tools)
        tool_map = {t.name: t for t in tools}
        chat_history = []
        pending_email = None
        last_email_from_user = None
        last_assistant_text = None
        pending_event = None
        
        def normalize_content(content) -> str:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if hasattr(item, "text"):
                        parts.append(item.text)
                    elif isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            return str(content)

        def is_negative_email(text: str) -> bool:
            normalized = text.strip().lower()
            return any(
                phrase in normalized
                for phrase in (
                    "dont send",
                    "don't send",
                    "do not send",
                    "no email",
                    "skip email",
                )
            )

        def extract_email_details(text: str):
            # Structured format with labels.
            to_match = re.search(
                r"^[\s>*-]*To:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
            )
            subject_match = re.search(
                r"^[\s>*-]*Subject:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
            )
            body_match = re.search(
                r"^[\s>*-]*Body:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
            )
            if to_match and subject_match and body_match:
                to_raw = to_match.group(1).strip()
                to_list = [
                    addr.strip() for addr in re.split(r"[;,]\s*", to_raw) if addr
                ]
                return {
                    "to": to_list,
                    "subject": subject_match.group(1).strip(),
                    "body": body_match.group(1).strip(),
                }

            # Narrative summary with quotes.
            narrative = re.search(
                r"send an email to\s+([^\s]+)\s+with the subject\s+\"([^\"]+)\"\s+and the body\s+\"([^\"]+)\"",
                text,
                re.IGNORECASE,
            )
            if narrative:
                return {
                    "to": [narrative.group(1).strip()],
                    "subject": narrative.group(2).strip(),
                    "body": narrative.group(3).strip(),
                }

            # More flexible narrative parsing without quotes.
            to_match = re.search(
                r"\bto\s+([^\s]+@[^\s]+)", text, re.IGNORECASE
            )
            subject_match = re.search(
                r"\bsubject(?: line)?\s+(?:is\s+)?\"?([^\".]+)\"?",
                text,
                re.IGNORECASE,
            )
            body_match = re.search(
                r"\bbody\s+(?:is\s+)?\"?(.+?)\"?(?:\.$|\n|$)",
                text,
                re.IGNORECASE,
            )
            if to_match and subject_match and body_match:
                return {
                    "to": [to_match.group(1).strip()],
                    "subject": subject_match.group(1).strip(),
                    "body": body_match.group(1).strip(),
                }

            return None

        def extract_event_details(text: str):
            # Example: "Schedule an event named \"catch up meet\" starting at 2pm today, lasting 1 hour."
            title_match = re.search(
                r"(?:event named|titled)\s+\"?([^\".]+)\"?",
                text,
                re.IGNORECASE,
            )
            time_match = re.search(
                r"\b(at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
                text,
                re.IGNORECASE,
            )
            duration_match = re.search(
                r"\b(lasting|duration)\s+(\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)\b",
                text,
                re.IGNORECASE,
            )
            date_match = re.search(
                r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)\s+(\d{4})\b",
                text,
                re.IGNORECASE,
            )
            date_is_today = bool(re.search(r"\btoday\b", text, re.IGNORECASE))

            if not (title_match and time_match and duration_match and (date_is_today or date_match)):
                return None

            if date_is_today:
                event_date = datetime(2026, 2, 23)
            else:
                day = int(date_match.group(1))
                month_str = date_match.group(2).lower()
                year = int(date_match.group(3))
                month_map = {
                    "jan": 1, "january": 1,
                    "feb": 2, "february": 2,
                    "mar": 3, "march": 3,
                    "apr": 4, "april": 4,
                    "may": 5,
                    "jun": 6, "june": 6,
                    "jul": 7, "july": 7,
                    "aug": 8, "august": 8,
                    "sep": 9, "sept": 9, "september": 9,
                    "oct": 10, "october": 10,
                    "nov": 11, "november": 11,
                    "dec": 12, "december": 12,
                }
                month = month_map.get(month_str[:3], None)
                if not month:
                    return None
                event_date = datetime(year, month, day)

            hour = int(time_match.group(2))
            minute = int(time_match.group(3) or 0)
            ampm = time_match.group(4).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            start_dt = event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            dur_value = int(duration_match.group(2))
            dur_unit = duration_match.group(3).lower()
            if dur_unit.startswith("hour") or dur_unit.startswith("hr"):
                delta = timedelta(hours=dur_value)
            else:
                delta = timedelta(minutes=dur_value)
            end_dt = start_dt + delta

            tz_match = re.search(
                r"\b([a-z]+)\s+([a-z]+)\s+timezone\b",
                text,
                re.IGNORECASE,
            )
            tz_raw = None
            if tz_match:
                tz_raw = f"{tz_match.group(1)} {tz_match.group(2)}"
            else:
                tz_name = re.search(r"\b([A-Za-z_]+\/[A-Za-z_]+)\b", text)
                tz_raw = tz_name.group(1) if tz_name else None

            tz_map = {
                "asia calcutta": "Asia/Kolkata",
                "asia kolkata": "Asia/Kolkata",
                "ist": "Asia/Kolkata",
            }
            timezone = tz_map.get(tz_raw.lower(), tz_raw) if tz_raw else "UTC"

            return {
                "title": title_match.group(1).strip(),
                "start": start_dt.strftime("%Y-%m-%d %H:%M"),
                "end": end_dt.strftime("%Y-%m-%d %H:%M"),
                "timezone": timezone,
            }

        def is_confirmation(text: str) -> bool:
            normalized = text.strip().lower()
            if normalized in {
                "yes",
                "yes send it",
                "send it",
                "confirm",
                "please send",
                "send",
            }:
                return True
            return bool(re.search(r"\b(yes|confirm|send)\b", normalized))

        while True:
            try:
                query = input("You: ")
            except (EOFError, KeyboardInterrupt):
                print("Exiting.")
                break

            # Try to extract directly from user input.
            user_extracted = extract_email_details(query)
            if user_extracted:
                last_email_from_user = user_extracted

            # Respect explicit "don't send email" instructions.
            if is_negative_email(query):
                pending_email = None
                last_email_from_user = None

            # Try to extract event details from user input or last assistant summary.
            pending_event = extract_event_details(query) or pending_event

            if is_confirmation(query):
                email_payload = (
                    pending_email
                    or last_email_from_user
                    or (
                        extract_email_details(last_assistant_text)
                        if last_assistant_text
                        else None
                    )
                )
                event_payload = (
                    pending_event
                    or (
                        extract_event_details(last_assistant_text)
                        if last_assistant_text
                        else None
                    )
                )

                # If user negated email, skip email even if present.
                if not is_negative_email(query) and email_payload and all(
                    k in email_payload for k in ("to", "subject", "body")
                ):
                    try:
                        result = await tool_map["send_email"].ainvoke(email_payload)
                        print("Assistant:", result)
                        pending_email = None
                        last_email_from_user = None
                        last_assistant_text = None
                        continue
                    except Exception as exc:
                        print(f"Error: {exc}")
                        continue

                if event_payload and all(
                    k in event_payload for k in ("title", "start", "end")
                ):
                    try:
                        result = await tool_map["create_event"].ainvoke(event_payload)
                        print("Assistant:", result)
                        pending_event = None
                        last_assistant_text = None
                        continue
                    except Exception as exc:
                        print(f"Error: {exc}")
                        continue

            chat_history.append({"role": "user", "content": query})

            try:
                response = await agent.ainvoke({"messages": chat_history})
            except Exception as exc:
                print(f"Error: {exc}")
                continue

            assistant_msg = response["messages"][-1].content
            assistant_text = normalize_content(assistant_msg).strip()
            last_assistant_text = assistant_text
            print("Assistant:", assistant_text)
            chat_history.append({"role": "assistant", "content": assistant_text})
            pending_email = extract_email_details(assistant_text)
            pending_event = extract_event_details(assistant_text) or pending_event


if __name__ == "__main__":
    asyncio.run(main())

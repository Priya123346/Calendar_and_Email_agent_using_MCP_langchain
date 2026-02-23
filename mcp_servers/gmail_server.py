from mcp.server.fastmcp import FastMCP
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from auth import get_gmail_creds

mcp = FastMCP("gmail-tools", host="0.0.0.0", port=9001)

@mcp.tool()
def ping() -> str:
    """Health check for the MCP server."""
    print("ping tool called")
    return "ok"

@mcp.tool()
def send_email(to: list[str], subject: str, body: str) -> str:
    """Send email via Gmail."""

    print(f"send_email called: to={to}, subject={subject}")
    creds = get_gmail_creds()
    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(body)
    message["to"] = ", ".join(to)
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()

    return f"Email sent to {', '.join(to)}"


if __name__ == "__main__":
    print("Starting gmail-tools MCP server...")
    mcp.run(transport="streamable-http")

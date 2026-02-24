import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

BASE_DIR = os.path.dirname(__file__)
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CALENDAR_TOKEN_PATH = os.path.join(BASE_DIR, "token_calendar.json")
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")

def _get_creds(scopes, token_path):
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    f"Missing credentials.json at {CREDS_PATH}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_PATH, scopes
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
    return creds


def get_gmail_creds():
    return _get_creds(GMAIL_SCOPES, TOKEN_PATH)


def get_calendar_creds():
    return _get_creds(CALENDAR_SCOPES, CALENDAR_TOKEN_PATH)

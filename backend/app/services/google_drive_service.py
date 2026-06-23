import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Token stored relative to project root (.run/google_token.json)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
TOKEN_PATH = _PROJECT_ROOT / ".run" / "google_token.json"


def _get_credentials() -> Credentials:
    settings = get_settings()
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
        return creds

    # First-time browser auth
    client_config = {
        "installed": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    logger.info("google_oauth_token_saved", path=str(TOKEN_PATH))
    return creds


class GoogleDriveService:
    def __init__(self):
        settings = get_settings()
        self.root_folder_id = settings.google_drive_folder_id
        self._service = None

        if settings.google_oauth_client_id and settings.google_oauth_client_secret:
            creds = _get_credentials()
            self._service = build("drive", "v3", credentials=creds)

    def _ensure_service(self):
        if not self._service:
            raise RuntimeError(
                "Google Drive not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
            )

    def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        self._ensure_service()
        query = (
            f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
            f" and '{parent_id}' in parents and trashed=false"
        )
        results = self._service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        folder = self._service.files().create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            },
            fields="id",
        ).execute()
        return folder["id"]

    def get_or_create_session_folder(
        self, character_name: str, date_str: str, session_id: str
    ) -> str:
        char_id = self._get_or_create_folder(character_name, self.root_folder_id)
        date_id = self._get_or_create_folder(date_str, char_id)
        session_folder_id = self._get_or_create_folder(session_id[:12], date_id)
        return session_folder_id

    def upload_image(self, local_path: str, filename: str, folder_id: str) -> dict:
        self._ensure_service()
        media = MediaFileUpload(local_path, mimetype="image/jpeg", resumable=True)
        file = self._service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        self._service.permissions().create(
            fileId=file["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        logger.info("image_uploaded", file_id=file["id"], filename=filename)
        return {"fileId": file["id"], "url": file.get("webViewLink", "")}

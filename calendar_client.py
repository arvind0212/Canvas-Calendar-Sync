import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config

logger = logging.getLogger(__name__)

class CalendarClient:
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self):
        self.service = None
        self.calendar_id = Config.GOOGLE_CALENDAR_ID
        self._authenticate()

    def _authenticate(self):
        creds = None

        # Check if service account credentials exist
        if os.path.exists(Config.GOOGLE_SERVICE_ACCOUNT_FILE):
            logger.info("Using service account authentication")
            creds = service_account.Credentials.from_service_account_file(
                Config.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=self.SCOPES
            )
        # Fall back to OAuth flow
        elif os.path.exists(Config.GOOGLE_CREDENTIALS_FILE):
            logger.info("Using OAuth authentication")
            from google.auth.exceptions import RefreshError

            if os.path.exists(Config.GOOGLE_TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(Config.GOOGLE_TOKEN_FILE, self.SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except RefreshError as e:
                        logger.warning(f"Token refresh failed: {e}")
                        logger.warning("Token has expired or been revoked. Re-authentication required.")
                        # In CI/CD environment, we can't run interactive auth
                        if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
                            raise RuntimeError(
                                "Google OAuth token has expired or been revoked. "
                                "Please regenerate token.json locally and update the GOOGLE_TOKEN GitHub secret."
                            ) from e
                        # For local environment, proceed to interactive auth
                        creds = None

                if not creds:
                    flow = InstalledAppFlow.from_client_secrets_file(Config.GOOGLE_CREDENTIALS_FILE, self.SCOPES)
                    creds = flow.run_local_server(port=0)

                with open(Config.GOOGLE_TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
        else:
            raise FileNotFoundError(
                f"No authentication credentials found. Please provide either:\n"
                f"- Service account: {Config.GOOGLE_SERVICE_ACCOUNT_FILE}\n"
                f"- OAuth credentials: {Config.GOOGLE_CREDENTIALS_FILE}"
            )

        self.service = build('calendar', 'v3', credentials=creds)
        logger.info("Google Calendar authentication successful")

    def _clean_html(self, html_text: str) -> str:
        if not html_text:
            return ""

        # Handle HTML entities first to convert &lt; to < and &gt; to >
        clean_text = html_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')

        # Extract and format complete links: <a ...href="url"...>text</a> -> text (url)
        def replace_complete_link(match):
            href = match.group(1)
            text = match.group(2).strip() if match.group(2).strip() else "Link"
            return f"{text} ({href})"

        # Handle complete links with closing tags
        clean_text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', replace_complete_link, clean_text)

        # Handle broken/incomplete links - extract just the URL and add context
        def replace_broken_link(match):
            href = match.group(1)
            # Try to extract a meaningful name from the URL
            filename = href.split('/')[-1].split('?')[0] if '/' in href else href
            return f"Link: {href}"

        # Handle broken links (missing closing tag or cut off)
        clean_text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*(?:>.*?$|$)', replace_broken_link, clean_text, flags=re.MULTILINE | re.DOTALL)

        # Remove any remaining HTML tags
        clean_text = re.sub(r'<[^>]*>', '', clean_text)

        # Clean up whitespace and line breaks
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text

    def _format_assignment_id(self, assignment: Dict[str, Any]) -> str:
        return f"canvas_{assignment['university']}_{assignment['id']}"

    def _create_event_body(self, assignment: Dict[str, Any]) -> Dict[str, Any]:
        due_date = datetime.fromisoformat(assignment['due_at'].replace('Z', '+00:00'))

        start_time = due_date - timedelta(minutes=30)
        end_time = due_date

        title = f"[{assignment['university_name']}] {assignment['course_name']}: {assignment['name']}"

        description_parts = []
        if assignment.get('description'):
            # Clean HTML first, then limit length to avoid cutting URLs mid-way
            clean_desc = self._clean_html(assignment['description'])
            if len(clean_desc) > 400:
                clean_desc = clean_desc[:400] + "..."
            description_parts.append(clean_desc)

        if assignment.get('html_url'):
            description_parts.append(f"\nAssignment Link: {assignment['html_url']}")

        description_parts.append(f"\nCourse: {assignment['course_name']}")
        if assignment.get('course_code'):
            description_parts.append(f"Course Code: {assignment['course_code']}")

        return {
            'summary': title,
            'description': '\n'.join(description_parts),
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'extendedProperties': {
                'private': {
                    'canvas_assignment_id': self._format_assignment_id(assignment),
                    'canvas_university': assignment['university'],
                    'canvas_course_id': str(assignment.get('course_id', '')),
                    'canvas_due_at': assignment['due_at']
                }
            }
        }

    def get_existing_canvas_events(self) -> Dict[str, Dict[str, Any]]:
        logger.info("Fetching existing Canvas events from Google Calendar")

        try:
            time_min = datetime.now().isoformat() + 'Z'
            time_max = (datetime.now() + timedelta(weeks=Config.SYNC_WEEKS_AHEAD)).isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                maxResults=2500
            ).execute()

            events = events_result.get('items', [])

            canvas_events = {}
            for event in events:
                extended_props = event.get('extendedProperties', {}).get('private', {})
                canvas_id = extended_props.get('canvas_assignment_id')

                if canvas_id:
                    canvas_events[canvas_id] = event

            logger.info(f"Found {len(canvas_events)} existing Canvas events")
            return canvas_events

        except HttpError as e:
            logger.error(f"Failed to fetch existing events: {e}")
            raise

    def create_event(self, assignment: Dict[str, Any]) -> Optional[str]:
        try:
            event_body = self._create_event_body(assignment)

            event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event_body
            ).execute()

            logger.info(f"Created event for assignment: {assignment['name']} ({assignment['university_name']})")
            return event.get('id')

        except HttpError as e:
            logger.error(f"Failed to create event for assignment {assignment['name']}: {e}")
            return None

    def update_event(self, event_id: str, assignment: Dict[str, Any]) -> bool:
        try:
            event_body = self._create_event_body(assignment)

            self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event_body
            ).execute()

            logger.info(f"Updated event for assignment: {assignment['name']} ({assignment['university_name']})")
            return True

        except HttpError as e:
            logger.error(f"Failed to update event for assignment {assignment['name']}: {e}")
            return False

    def delete_event(self, event_id: str) -> bool:
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()

            logger.info(f"Deleted event: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to delete event {event_id}: {e}")
            return False
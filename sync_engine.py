import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime

from canvas_client import CanvasClient
from calendar_client import CalendarClient

logger = logging.getLogger(__name__)

class SyncEngine:
    def __init__(self):
        self.canvas_clients = {
            'kth': CanvasClient('kth'),
            'ki': CanvasClient('ki')
        }
        self.calendar_client = CalendarClient()

    def _has_assignment_changed(self, assignment: Dict[str, Any], existing_event: Dict[str, Any]) -> bool:
        extended_props = existing_event.get('extendedProperties', {}).get('private', {})

        # Check if due date changed
        if extended_props.get('canvas_due_at') != assignment['due_at']:
            return True

        # Check if title changed
        expected_title = f"[{assignment['university_name']}] {assignment['course_name']}: {assignment['name']}"
        if existing_event.get('summary') != expected_title:
            return True

        # Check if description contains HTML or HTML entities (indicating it needs cleaning)
        existing_description = existing_event.get('description', '')
        has_html_tags = '<' in existing_description and '>' in existing_description
        has_html_entities = '&lt;' in existing_description or '&gt;' in existing_description
        has_broken_links = 'href=' in existing_description

        if has_html_tags or has_html_entities or has_broken_links:
            return True

        return False

    def _collect_all_assignments(self) -> List[Dict[str, Any]]:
        logger.info("Collecting assignments from all Canvas instances")

        all_assignments = []
        for university, client in self.canvas_clients.items():
            try:
                assignments = client.get_all_assignments()
                all_assignments.extend(assignments)
                logger.info(f"Collected {len(assignments)} assignments from {university.upper()}")
            except Exception as e:
                logger.error(f"Failed to collect assignments from {university.upper()}: {e}")

        logger.info(f"Total assignments collected: {len(all_assignments)}")
        return all_assignments

    def _process_sync_operations(self, assignments: List[Dict[str, Any]],
                               existing_events: Dict[str, Dict[str, Any]]) -> Tuple[int, int, int]:
        created_count = 0
        updated_count = 0
        error_count = 0

        for assignment in assignments:
            assignment_id = self.calendar_client._format_assignment_id(assignment)

            try:
                if assignment_id in existing_events:
                    existing_event = existing_events[assignment_id]

                    if self._has_assignment_changed(assignment, existing_event):
                        success = self.calendar_client.update_event(existing_event['id'], assignment)
                        if success:
                            updated_count += 1
                        else:
                            error_count += 1
                    else:
                        logger.debug(f"No changes for assignment: {assignment['name']}")

                else:
                    event_id = self.calendar_client.create_event(assignment)
                    if event_id:
                        created_count += 1
                    else:
                        error_count += 1

            except Exception as e:
                logger.error(f"Error processing assignment {assignment['name']}: {e}")
                error_count += 1

        return created_count, updated_count, error_count


    def sync(self) -> Dict[str, int]:
        logger.info("Starting Canvas to Google Calendar sync")

        try:
            assignments = self._collect_all_assignments()

            if not assignments:
                logger.warning("No assignments found to sync")
                return {'created': 0, 'updated': 0, 'errors': 0}

            existing_events = self.calendar_client.get_existing_canvas_events()

            created_count, updated_count, error_count = self._process_sync_operations(
                assignments, existing_events
            )

            result = {
                'created': created_count,
                'updated': updated_count,
                'errors': error_count
            }

            logger.info(f"Sync completed: {created_count} created, {updated_count} updated, {error_count} errors")
            return result

        except Exception as e:
            logger.error(f"Sync failed with error: {e}")
            raise
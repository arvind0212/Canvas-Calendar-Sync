import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

class CanvasClient:
    def __init__(self, university: str):
        self.config = Config.get_canvas_config(university)
        self.university = university
        self.base_url = self.config['base_url']
        self.headers = {
            'Authorization': f"Bearer {self.config['access_token']}",
            'Content-Type': 'application/json'
        }

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1{endpoint}"
        params = params or {}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            results = response.json()

            while 'next' in response.links:
                logger.debug(f"Fetching next page for {endpoint}")
                response = requests.get(response.links['next']['url'], headers=self.headers, timeout=30)
                response.raise_for_status()
                results.extend(response.json())

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Canvas API request failed for {self.university}: {e}")
            raise

    def get_courses(self) -> List[Dict[str, Any]]:
        logger.info(f"Fetching courses for {self.university}")

        params = {
            'enrollment_state': 'active',
            'state[]': ['available', 'completed'],
            'per_page': 100
        }

        courses = self._make_request('/courses', params)
        logger.info(f"Found {len(courses)} courses for {self.university}")

        return courses

    def get_assignments(self, course_id: int) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching assignments for course {course_id} at {self.university}")

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = today + timedelta(weeks=Config.SYNC_WEEKS_AHEAD)

        params = {
            'per_page': 100,
            'order_by': 'due_at'
        }

        endpoint = f"/courses/{course_id}/assignments"
        assignments = self._make_request(endpoint, params)

        filtered_assignments = []
        for assignment in assignments:
            if not assignment.get('due_at'):
                continue

            try:
                due_date = datetime.fromisoformat(assignment['due_at'].replace('Z', '+00:00'))
                due_date_local = due_date.replace(tzinfo=None)

                # Only include assignments from today onwards and within the sync window
                if today <= due_date_local <= cutoff_date:
                    assignment['university'] = self.university
                    assignment['university_name'] = self.config['name']
                    filtered_assignments.append(assignment)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid due date for assignment {assignment.get('id')}: {e}")

        logger.debug(f"Found {len(filtered_assignments)} assignments with valid due dates for course {course_id}")
        return filtered_assignments

    def get_all_assignments(self) -> List[Dict[str, Any]]:
        logger.info(f"Fetching all assignments for {self.university}")

        courses = self.get_courses()
        all_assignments = []

        for course in courses:
            try:
                course_assignments = self.get_assignments(course['id'])
                for assignment in course_assignments:
                    assignment['course_name'] = course.get('name', 'Unknown Course')
                    assignment['course_code'] = course.get('course_code', '')
                all_assignments.extend(course_assignments)
            except Exception as e:
                logger.error(f"Failed to fetch assignments for course {course.get('id')}: {e}")

        logger.info(f"Total assignments found for {self.university}: {len(all_assignments)}")
        return all_assignments
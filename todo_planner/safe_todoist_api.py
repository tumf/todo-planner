import time
import requests  # Added this line

from todoist_api_python.api import TodoistAPI


class SafeTodoistAPI(TodoistAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _safe_api_call(self, method, **kwargs):
        max_retries = 5
        backoff_factor = 2
        for attempt in range(max_retries):
            try:
                response = method(**kwargs)
                if isinstance(response, list) or isinstance(response, dict):
                    return response
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    wait_time = backoff_factor ** (attempt + 4)
                    print(
                        f"Rate limit exceeded. Waiting for {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                else:
                    raise e
            finally:
                # Ensure a delay of at least 2 seconds between requests
                time.sleep(2)
        raise Exception("Max retries exceeded for API call.")

    def get_tasks(self, **kwargs):
        return self._safe_api_call(super().get_tasks, **kwargs)

    def update_task(self, **kwargs):
        return self._safe_api_call(super().update_task, **kwargs)

    # Add other methods as needed that make API calls and need the retry mechanism

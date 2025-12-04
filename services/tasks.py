import logging
from typing import Optional

import config
from services.auth import auth

logger = logging.getLogger(__name__)


class TSUTasks:
    BASE_URL = config.API_URL

    @staticmethod
    async def create_task(
        telegram_id: int,
        title: str,
        description: str = "",
        deadline: Optional[str] = None,
        assignee_id: Optional[int] = None,
        reminders: Optional[list] = None
    ) -> dict | None:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        payload = {
            "title": title,
            "description": description,
        }

        if deadline:
            payload["deadline"] = deadline

        if assignee_id:
            payload["assignee_id"] = assignee_id

        if reminders is not None:
            payload["reminders"] = reminders

        try:
            response = await auth.api_request("POST", "todo/", json=payload)
            logger.info(f"Task created successfully: {response.get('id')}")
            return response
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None

    @staticmethod
    async def get_tasks(
        telegram_id: int,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None
    ) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status

        try:
            response = await auth.api_request("GET", "todo/all/", params=params)
            results = response.get("results", [])
            total_pages = response.get("total_pages", 1)
            current_page = response.get("current_page", page)
            return {
                "results": results,
                "current_page": current_page,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"Error fetching tasks page {page}: {e}")
            return {
                "results": [],
                "current_page": page,
                "total_pages": 1
            }

    @staticmethod
    async def get_task_details(telegram_id: int, task_id: int) -> dict | None:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            response = await auth.api_request("GET", f"todo/{task_id}/")
            return response
        except Exception as e:
            logger.error(f"Error fetching task {task_id}: {e}")
            return None

    @staticmethod
    async def update_task(
        telegram_id: int,
        task_id: int,
        **kwargs
    ) -> dict | None:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            response = await auth.api_request("PATCH", f"todo/{task_id}/", json=kwargs)
            logger.info(f"Task {task_id} updated successfully")
            return response
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            return None

    @staticmethod
    async def delete_task(telegram_id: int, task_id: int) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            await auth.api_request("DELETE", f"todo/{task_id}/")
            logger.info(f"Task {task_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False


tasks_service = TSUTasks()


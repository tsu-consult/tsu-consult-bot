import logging

import config
from services.auth import auth

logger = logging.getLogger(__name__)


class TSUTeachers:
    BASE_URL = config.API_URL

    @staticmethod
    async def get_teachers_page(telegram_id: int, page: int = 0, page_size: int = 10) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        params = {"page": page + 1, "page_size": page_size}
        try:
            response = await auth.api_request("GET", "teachers/", params=params)
            results = response.get("results", [])
            total_pages = response.get("total_pages", 1)
            current_page = response.get("current_page", 1) - 1
            return {
                "results": results,
                "current_page": current_page,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"Error fetching teachers page {page}: {e}")
            return {
                "results": [],
                "current_page": page,
                "total_pages": 1
            }

    @staticmethod
    async def get_teacher_schedule(telegram_id: int, teacher_id: int, page: int = 0, page_size: int = 10) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        params = {"page": page + 1, "page_size": page_size}
        endpoint = f"teachers/{teacher_id}/consultations/"
        try:
            response = await auth.api_request("GET", endpoint, params=params)
            results = response.get("results", [])
            total_pages = response.get("total_pages", 1)
            current_page = response.get("current_page", 1) - 1
            return {
                "results": results,
                "current_page": current_page,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"Error fetching schedule for teacher {teacher_id}, page {page}: {e}")
            return {
                "results": [],
                "current_page": page,
                "total_pages": 1
            }

    @staticmethod
    async def subscribe_teacher(telegram_id: int, teacher_id: int) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            await auth.api_request("POST", f"teachers/{teacher_id}/subscribe/")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to teacher {teacher_id}: {e}")
            return False

    @staticmethod
    async def unsubscribe_teacher(telegram_id: int, teacher_id: int) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            await auth.api_request("DELETE", f"teachers/{teacher_id}/unsubscribe/")
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing from teacher_id={teacher_id}: {e}")
            return False

    @staticmethod
    async def get_subscribed_teachers(telegram_id: int) -> list:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            response = await auth.api_request("GET", "teachers/subscribed/")
            return response.get("results", []) if response else []
        except Exception as e:
            logger.error(f"Error fetching subscribed teachers: {e}")
            return []


teachers = TSUTeachers()

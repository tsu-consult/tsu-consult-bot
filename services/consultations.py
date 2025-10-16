import logging
import aiohttp
import config
from services.auth import auth

logger = logging.getLogger(__name__)


class TSUConsultations:
    BASE_URL = config.API_URL

    @staticmethod
    async def book_consultation(telegram_id: int, consultation_id: int, request_text: str) -> str:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            payload = {"message": request_text}
            status, data = await auth.api_request_with_status(
                "POST",
                f"consultations/{consultation_id}/book/",
                json=payload
            )
            if status in (200, 201):
                return "success"
            if status == 409:
                return "conflict"
            logger.error(f"Error booking consultation {consultation_id}: HTTP {status} - {data}")
            return "error"
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error booking consultation {consultation_id}: {e}")
            return "error"
        except Exception as e:
            logger.error(f"Unexpected error booking consultation {consultation_id}: {e}")
            return "error"

    @staticmethod
    async def get_consultations(telegram_id: int, page: int = 1, page_size: int = 10, is_closed: bool | None = None) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            params = {"page": str(page), "page_size": str(page_size)}
            if is_closed is not None:
                params["is_closed"] = "true" if is_closed else "false"
            status, data = await auth.api_request_with_status(
                "GET",
                "consultations/my/",
                params=params
            )
            if status == 200 and isinstance(data, dict):
                return {
                    "count": data.get("count", 0),
                    "total_pages": data.get("total_pages", 0),
                    "current_page": data.get("current_page", 0),
                    "next": data.get("next"),
                    "previous": data.get("previous"),
                    "results": data.get("results", [])
                }
            logger.error(f"Error getting consultations: HTTP {status} - {data}")
            return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None, "results": []}
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting consultations: {e}")
            return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None, "results": []}
        except Exception as e:
            logger.error(f"Unexpected error getting consultations: {e}")
            return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None, "results": []}

    async def cancel_booking(self, telegram_id: int, consultation_id: int) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            status, _ = await auth.api_request_with_status(
                "DELETE",
                f"consultations/{consultation_id}/cancel/"
            )
            return status == 204
        except Exception as e:
            logger.error(f"Error cancelling consultation {consultation_id}: {e}")
            return False

    @staticmethod
    async def create_request(telegram_id: int, title: str, description: str) -> dict | None:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        payload = {
            "title": title,
            "description": description
        }

        try:
            status, data = await auth.api_request_with_status(
                "POST",
                "consultations/request/",
                json=payload
            )
            if status in (200, 201) and isinstance(data, dict):
                return data
            logger.error(f"Error creating consultation request: HTTP {status} - {data}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error creating consultation request: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating consultation request: {e}")
            return None

    @staticmethod
    async def get_requests(telegram_id: int, page: int = 1, page_size: int = 10) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            params = {"page": page, "page_size": page_size}
            status, data = await auth.api_request_with_status(
                "GET",
                "consultations/requests/",
                params=params
            )
            if status == 200 and isinstance(data, dict):
                return {
                    "count": data.get("count", 0),
                    "total_pages": data.get("total_pages", 0),
                    "current_page": data.get("current_page", 0),
                    "next": data.get("next"),
                    "previous": data.get("previous"),
                    "results": data.get("results", [])
                }
            logger.error(f"Error getting consultation requests: HTTP {status} - {data}")
            return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None, "results": []}
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting consultation requests: {e}")
            return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None, "results": []}
        except Exception as e:
            logger.error(f"Unexpected error getting consultation requests: {e}")
            return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None, "results": []}

    @staticmethod
    async def subscribe_request(telegram_id: int, request_id: int) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            status, _ = await auth.api_request_with_status(
                "POST",
                f"consultations/requests/{request_id}/subscribe/"
            )
            return status in (200, 201)
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error subscribing to request {request_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error subscribing to request {request_id}: {e}")
            return False

    @staticmethod
    async def unsubscribe_request(telegram_id: int, request_id: int) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        try:
            status, _ = await auth.api_request_with_status(
                "DELETE",
                f"consultations/requests/{request_id}/unsubscribe/"
            )
            return status in (200, 204)
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error unsubscribing from request {request_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error unsubscribing from request {request_id}: {e}")
            return False

    @staticmethod
    async def create_consultation(
        telegram_id: int,
        title: str,
        date: str,
        start_time: str,
        end_time: str,
        max_students: int
    ) -> dict | None:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        payload = {
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "max_students": max_students
        }

        try:
            status, data = await auth.api_request_with_status(
                "POST",
                "consultations/",
                json=payload
            )
            if status in (200, 201) and isinstance(data, dict):
                return data
            logger.error(f"Error creating consultation: HTTP {status} - {data}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error creating consultation: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating consultation: {e}")
            return None

    @staticmethod
    async def create_consultation_from_request(
            telegram_id: int,
            request_id: int,
            title: str,
            date: str,
            start_time: str,
            end_time: str,
            max_students: int
    ) -> dict | None:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()

        payload = {
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "max_students": max_students,
            "source_request_id": request_id
        }

        try:
            status, data = await auth.api_request_with_status(
                "POST",
                f"consultations/from/{request_id}/",
                json=payload
            )
            if status in (200, 201) and isinstance(data, dict):
                return data
            logger.error(f"Error creating consultation from request {request_id}: HTTP {status} - {data}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error creating consultation from request {request_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating consultation from request {request_id}: {e}")
            return None

    @staticmethod
    async def cancel_consultation(telegram_id: int, consultation_id: int) -> str:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()
        try:
            status, data = await auth.api_request_with_status(
                "DELETE",
                f"consultations/{consultation_id}/delete/"
            )
            if status in (200, 204):
                return "success"
            logger.error(f"Error cancelling consultation {consultation_id}: HTTP {status} - {data}")
            return "error"
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error cancelling consultation {consultation_id}: {e}")
            return "error"
        except Exception as e:
            logger.error(f"Unexpected error cancelling consultation {consultation_id}: {e}")
            return "error"

    @staticmethod
    async def close_consultation(telegram_id: int, consultation_id: int) -> str:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()
        try:
            status, data = await auth.api_request_with_status(
                "POST",
                f"consultations/{consultation_id}/close/"
            )
            if status in (200, 204):
                return "success"
            logger.error(f"Error closing consultation {consultation_id}: HTTP {status} - {data}")
            return "error"
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error closing consultation {consultation_id}: {e}")
            return "error"
        except Exception as e:
            logger.error(f"Unexpected error closing consultation {consultation_id}: {e}")
            return "error"

    @staticmethod
    async def get_consultation_students(telegram_id: int, consultation_id: int) -> list[dict]:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        await auth.load_tokens_if_needed()
        try:
            status, data = await auth.api_request_with_status(
                "GET",
                f"consultations/{consultation_id}/students/"
            )
            if status == 200:
                if isinstance(data, dict):
                    return data.get("results", [])
                return data or []
            logger.error(f"Error getting consultation students {consultation_id}: HTTP {status} - {data}")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting consultation students {consultation_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting consultation students {consultation_id}: {e}")
            return []


consultations = TSUConsultations()
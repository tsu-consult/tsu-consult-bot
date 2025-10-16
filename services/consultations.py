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
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            payload = {"message": request_text}
            async with auth.session.post(
                    f"{TSUConsultations.BASE_URL}consultations/{consultation_id}/book/",
                    json=payload,
                    headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as resp:
                if resp.status == 201:
                    return "success"
                elif resp.status == 409:
                    return "conflict"
                else:
                    logger.error(
                        f"Error booking consultation {consultation_id}: "
                        f"HTTP {resp.status} - {await resp.text()}"
                    )
                    return "error"

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error booking consultation {consultation_id}: {e}")
            return "error"
        except Exception as e:
            logger.error(f"Unexpected error booking consultation {consultation_id}: {e}")
            return "error"

    @staticmethod
    async def get_consultations(telegram_id: int, page: int = 1, page_size: int = 10) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            params = {"page": page, "page_size": page_size}
            async with auth.session.get(
                    f"{TSUConsultations.BASE_URL}consultations/my/",
                    params=params,
                    headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "count": data.get("count", 0),
                        "total_pages": data.get("total_pages", 0),
                        "current_page": data.get("current_page", 0),
                        "next": data.get("next"),
                        "previous": data.get("previous"),
                        "results": data.get("results", [])
                    }
                else:
                    logger.error(f"Error getting consultations: HTTP {resp.status} - {await resp.text()}")
                    return {"count": 0, "total_pages": 0, "current_page": 0, "next": None, "previous": None,
                            "results": []}

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
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            async with auth.session.delete(
                    f"{self.BASE_URL}consultations/{consultation_id}/cancel/",
                    headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as resp:
                var = True if resp.status == 204 else False
                return var
        except Exception as e:
            logger.error(f"Error cancelling consultation {consultation_id}: {e}")
            return False

    @staticmethod
    async def create_request(telegram_id: int, title: str, description: str) -> str:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        payload = {
            "title": title,
            "description": description
        }

        try:
            async with auth.session.post(
                    f"{TSUConsultations.BASE_URL}consultations/request/",
                    json=payload,
                    headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as resp:
                if resp.status == 201:
                    return "success"
                else:
                    logger.error(
                        f"Error creating consultation request: HTTP {resp.status} - {await resp.text()}"
                    )
                    return "error"
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error creating consultation request: {e}")
            return "error"
        except Exception as e:
            logger.error(f"Unexpected error creating consultation request: {e}")
            return "error"

    @staticmethod
    async def get_requests(telegram_id: int, role: str, page: int = 1, page_size: int = 10) -> dict:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            params = {"page": page, "page_size": page_size}
            if role == "student":
                params["student_id"] = telegram_id
            elif role == "teacher":
                params["teacher_id"] = telegram_id

            async with auth.session.get(
                    f"{TSUConsultations.BASE_URL}consultations/requests/",
                    params=params,
                    headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "count": data.get("count", 0),
                        "total_pages": data.get("total_pages", 0),
                        "current_page": data.get("current_page", 0),
                        "next": data.get("next"),
                        "previous": data.get("previous"),
                        "results": data.get("results", [])
                    }
                else:
                    logger.error(f"Error getting consultation requests: HTTP {resp.status} - {await resp.text()}")
                    return {"count": 0, "total_pages": 0, "current_page": 0,
                            "next": None, "previous": None, "results": []}

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting consultation requests: {e}")
            return {"count": 0, "total_pages": 0, "current_page": 0,
                    "next": None, "previous": None, "results": []}
        except Exception as e:
            logger.error(f"Unexpected error getting consultation requests: {e}")
            return {"count": 0, "total_pages": 0, "current_page": 0,
                    "next": None, "previous": None, "results": []}


consultations = TSUConsultations()

import logging

import config
from services.auth import auth

logger = logging.getLogger(__name__)


class TSUTeachers:
    BASE_URL = config.API_URL

    @staticmethod
    async def get_teachers_page(page: int = 0, page_size: int = 10) -> dict:
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


teachers = TSUTeachers()

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


consultations = TSUConsultations()

import logging

import config
from services.auth import auth

logger = logging.getLogger(__name__)


class TSUConsultations:
    BASE_URL = config.API_URL

    @staticmethod
    async def book_consultation(telegram_id: int, consultation_id: int, request_text: str) -> bool:
        auth.telegram_id = telegram_id
        await auth.init_redis()
        await auth.init_session()
        if not (auth.access_token and auth.refresh_token):
            await auth.load_tokens_if_needed()

        try:
            payload = {"message": request_text}
            response = await auth.api_request("POST", f"consultations/{consultation_id}/book/", json=payload)
            print(response)
            return True
        except Exception as e:
            logger.error(f"Error booking consultation {consultation_id}: {e}")
            return False


consultations = TSUConsultations()

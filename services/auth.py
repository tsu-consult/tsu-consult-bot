import json
import logging
import requests
import redis
from typing import Optional
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TSUAuth:
    BASE_URL = config.API_URL

    def __init__(self):
        self.redis = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True
        )
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.telegram_id: Optional[int] = None

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _save_tokens(self):
        if self.telegram_id and self.access_token and self.refresh_token:
            try:
                data = json.dumps({
                    "access": self.access_token,
                    "refresh": self.refresh_token
                })
                self.redis.set(f"tsu_tokens:{self.telegram_id}", data)
                logger.info(f"Tokens saved for telegram_id={self.telegram_id}")
            except redis.RedisError as e:
                logger.error(f"Redis error (save): {e}")

    def _load_tokens(self):
        if not self.telegram_id:
            return False
        try:
            data = self.redis.get(f"tsu_tokens:{self.telegram_id}")
            if data:
                tokens = json.loads(data)
                self.access_token = tokens.get("access")
                self.refresh_token = tokens.get("refresh")
                logger.info(f"Tokens loaded for telegram_id={self.telegram_id}")
                return True
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Redis error (load): {e}")
        return False

    def is_registered(self, telegram_id: int) -> bool:
        self.telegram_id = telegram_id
        return self._load_tokens()

    def register(
        self,
        telegram_id: int,
        username: str,
        first_name: str = "",
        last_name: str = "",
        phone_number: str = "",
        role: str = "student"
    ):
        self.telegram_id = telegram_id

        payload = {
            "username": username,
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "role": role
        }

        logger.info("Sending register request: %s", payload)

        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/register/",
                json=payload,
                timeout=10
            )
            logger.info("Register response: %s | %s", response.status_code, response.text)

            if response.status_code not in (200, 201):
                logger.error("Register failed: %s", response.text)
                raise ValueError("Ошибка регистрации. Попробуйте снова.")

            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            self._save_tokens()
            return data
        except requests.exceptions.RequestException as e:
            logger.error("Network error during register: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Некорректный ответ от сервера.")

    def login(self, telegram_id: int):
        self.telegram_id = telegram_id

        if self._load_tokens():
            logger.info("Tokens found in Redis for telegram_id=%s", telegram_id)
            return {"access": self.access_token, "refresh": self.refresh_token}

        logger.info("Sending login request for telegram_id=%s", telegram_id)
        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/login/",
                json={"telegram_id": telegram_id},
                timeout=10
            )
            logger.info("Login response: %s | %s", response.status_code, response.text)

            if response.status_code != 200:
                logger.error("Login failed: %s", response.text)
                raise ValueError("Ошибка авторизации. Попробуйте снова.")

            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            self._save_tokens()
            return data
        except requests.exceptions.RequestException as e:
            logger.error("Network error during login: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Некорректный ответ от сервера.")

    def refresh(self):
        if not self.refresh_token:
            raise ValueError("Нет refresh_token для обновления")

        logger.info("Sending refresh request for telegram_id=%s", self.telegram_id)
        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/refresh/",
                json={"refresh": self.refresh_token},
                timeout=10
            )
            logger.info("Refresh response: %s | %s", response.status_code, response.text)

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                self._save_tokens()
                logger.info("Access token refreshed successfully")
                return True
            else:
                logger.error("Refresh failed: %s", response.text)
                if self.telegram_id:
                    self.redis.delete(f"tsu_tokens:{self.telegram_id}")
                self.access_token = None
                self.refresh_token = None
                raise ValueError("Ошибка обновления токена. Авторизуйтесь снова.")

        except requests.exceptions.RequestException as e:
            logger.error("Network error during refresh: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Некорректный ответ от сервера.")

    def logout(self):
        if not self.refresh_token:
            return

        logger.info("Sending logout request for telegram_id=%s", self.telegram_id)
        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/logout/",
                json={"refresh": self.refresh_token},
                timeout=10
            )
            logger.info("Logout response: %s | %s", response.status_code, response.text)

            if response.status_code == 200 and self.telegram_id:
                self.redis.delete(f"tsu_tokens:{self.telegram_id}")
                logger.info("Tokens deleted from Redis for telegram_id=%s", self.telegram_id)
            else:
                logger.error("Logout failed: %s", response.text)
                raise ValueError("Ошибка при выходе из системы.")

        except requests.exceptions.RequestException as e:
            logger.error("Network error during logout: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        finally:
            self.access_token = None
            self.refresh_token = None

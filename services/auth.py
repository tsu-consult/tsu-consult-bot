import json
import requests
import redis
from typing import Optional
import config


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
            except redis.RedisError as e:
                print(f"[RedisError] Не удалось сохранить токены: {e}")

    def _load_tokens(self):
        if not self.telegram_id:
            return False
        try:
            data = self.redis.get(f"tsu_tokens:{self.telegram_id}")
            if data:
                tokens = json.loads(data)
                self.access_token = tokens.get("access")
                self.refresh_token = tokens.get("refresh")
                return True
        except (redis.RedisError, json.JSONDecodeError) as e:
            print(f"[RedisError] Ошибка при загрузке токенов: {e}")
        return False

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
            "telegram_id": self.telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "role": role
        }

        try:
            response = requests.post(f"{self.BASE_URL}/auth/register/", json=payload, timeout=10)
            if response.status_code != 201:
                print(f"[RegisterError] Ошибка регистрации ({response.status_code}): {response.text}")
                return None
            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            self._save_tokens()
            return data
        except requests.exceptions.RequestException as e:
            print(f"[RegisterError] Сетевая ошибка: {e}")
        except json.JSONDecodeError:
            print("[RegisterError] Ошибка парсинга ответа сервера")
        return None

    def login(self, telegram_id: int):
        self.telegram_id = telegram_id

        if self._load_tokens():
            return {"access": self.access_token, "refresh": self.refresh_token}

        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/login/",
                json={"telegram_id": telegram_id},
                timeout=10
            )
            if response.status_code != 200:
                print(f"[LoginError] Ошибка логина ({response.status_code}): {response.text}")
                return None

            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            self._save_tokens()
            return data
        except requests.exceptions.RequestException as e:
            print(f"[LoginError] Сетевая ошибка: {e}")
        except json.JSONDecodeError:
            print("[LoginError] Ошибка парсинга ответа сервера")
        return None

    def refresh(self):
        if not self.refresh_token:
            raise ValueError("No refresh_token for updating")

        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/refresh/",
                json={"refresh": self.refresh_token},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                self._save_tokens()
                return True
            else:
                print(f"[RefreshError] Ошибка обновления ({response.status_code}): {response.text}")
                if self.telegram_id:
                    self.redis.delete(f"tsu_tokens:{self.telegram_id}")
                self.access_token = None
                self.refresh_token = None
                return False

        except requests.exceptions.RequestException as e:
            print(f"[RefreshError] Сетевая ошибка: {e}")
        except json.JSONDecodeError:
            print("[RefreshError] Ошибка парсинга ответа сервера")
        return False

    def logout(self):
        if not self.refresh_token:
            return

        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/logout/",
                json={"refresh": self.refresh_token},
                timeout=10
            )
            if response.status_code == 200 and self.telegram_id:
                self.redis.delete(f"tsu_tokens:{self.telegram_id}")
            else:
                print(f"[LogoutError] Ошибка логаута ({response.status_code}): {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[LogoutError] Сетевая ошибка: {e}")
        finally:
            self.access_token = None
            self.refresh_token = None

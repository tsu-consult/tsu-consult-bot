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
            data = json.dumps({"access": self.access_token, "refresh": self.refresh_token})
            self.redis.set(f"tsu_tokens:{self.telegram_id}", data)

    def _load_tokens(self):
        if not self.telegram_id:
            return False
        data = self.redis.get(f"tsu_tokens:{self.telegram_id}")
        if data:
            tokens = json.loads(data)
            self.access_token = tokens.get("access")
            self.refresh_token = tokens.get("refresh")
            return True
        return False

    def register(
            self,
            username: str,
            first_name: str = "",
            last_name: str = "",
            phone_number: str = "",
            role: str = "student"
    ):
        payload = {
            "username": username,
            "telegram_id": self.telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "role": role
        }
        response = requests.post(f"{self.BASE_URL}/auth/register/", json=payload)
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access"]
        self.refresh_token = data["refresh"]
        self._save_tokens()
        return data

    def login(self, telegram_id: int):
        self.telegram_id = telegram_id

        if self._load_tokens():
            return {"access": self.access_token, "refresh": self.refresh_token}

        response = requests.post(
            f"{self.BASE_URL}/auth/login/",
            json={"telegram_id": telegram_id}
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access"]
        self.refresh_token = data["refresh"]
        self._save_tokens()
        return data

    def refresh(self):
        if not self.refresh_token:
            raise ValueError("No refresh_token for updating")
        response = requests.post(
            f"{self.BASE_URL}/auth/refresh/",
            json={"refresh": self.refresh_token}
        )
        if response.status_code == 200:
            self.access_token = response.json()['access']
            self._save_tokens()
        else:
            if self.telegram_id:
                self.redis.delete(f"tsu_tokens:{self.telegram_id}")
            self.access_token = None
            self.refresh_token = None
            raise ValueError("Refresh token is invalid")

    def logout(self):
        if not self.refresh_token:
            return
        response = requests.post(
            f"{self.BASE_URL}/auth/logout/",
            json={"refresh": self.refresh_token}
        )
        if response.status_code == 200 and self.telegram_id:
            self.redis.delete(f"tsu_tokens:{self.telegram_id}")
        self.access_token = None
        self.refresh_token = None

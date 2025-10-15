import logging
import aiohttp
import config
from typing import Optional, Tuple
from redis import asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TSUAuth:
    BASE_URL = config.API_URL

    def __init__(self):
        self.redis_tokens: Optional[aioredis.Redis] = None
        self.redis_flags: Optional[aioredis.Redis] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.telegram_id: Optional[int] = None

        self.access_ttl = getattr(config, "ACCESS_EXPIRES_IN", 300)
        self.refresh_ttl = getattr(config, "REFRESH_EXPIRES_IN", 86400)

    async def init_redis(self):
        if self.redis_tokens is None:
            self.redis_tokens = aioredis.from_url(
                f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/{config.REDIS_DB}",
                decode_responses=True
            )
        if self.redis_flags is None:
            self.redis_flags = aioredis.from_url(
                f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/{config.REDIS_DB + 1}",
                decode_responses=True
            )

    async def init_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _save_tokens(self):
        if not self.redis_tokens or not self.telegram_id or not self.access_token or not self.refresh_token:
            return
        try:
            await self.redis_tokens.setex(f"tsu_access:{self.telegram_id}", self.access_ttl, self.access_token)
            await self.redis_tokens.setex(f"tsu_refresh:{self.telegram_id}", self.refresh_ttl, self.refresh_token)
            logger.info(f"Tokens saved for telegram_id={self.telegram_id}")
            await self.set_login_flag(self.telegram_id, True)
        except Exception as e:
            logger.error(f"Redis error (_save_tokens): {e}")

    async def _load_tokens(self) -> bool:
        if not self.redis_tokens or not self.telegram_id:
            return False
        try:
            access_token = await self.redis_tokens.get(f"tsu_access:{self.telegram_id}")
            refresh_token = await self.redis_tokens.get(f"tsu_refresh:{self.telegram_id}")
            if access_token and refresh_token:
                self.access_token = access_token
                self.refresh_token = refresh_token
                logger.info(f"Tokens loaded for telegram_id={self.telegram_id}")
                await self.set_login_flag(self.telegram_id, True)
                return True
        except Exception as e:
            logger.error(f"Redis error (_load_tokens): {e}")
        return False

    async def _delete_tokens(self):
        if self.redis_tokens and self.telegram_id:
            try:
                await self.redis_tokens.delete(f"tsu_access:{self.telegram_id}")
                await self.redis_tokens.delete(f"tsu_refresh:{self.telegram_id}")
                logger.info(f"Tokens deleted from Redis for telegram_id={self.telegram_id}")
                await self.clear_login_flag(self.telegram_id)
            except Exception as e:
                logger.error(f"Redis error (_delete_tokens): {e}")
        self.access_token = None
        self.refresh_token = None

    async def set_login_flag(self, telegram_id: int, value: bool):
        await self.init_redis()
        try:
            if value:
                await self.redis_flags.set(f"logged_in:{telegram_id}", "1")
            else:
                await self.redis_flags.set(f"logged_in:{telegram_id}", "0")
        except Exception as e:
            logger.error(f"Redis error (set_login_flag): {e}")

    async def clear_login_flag(self, telegram_id: int):
        await self.set_login_flag(telegram_id, False)

    async def get_role(self, telegram_id: int) -> Optional[str]:
        self.telegram_id = telegram_id
        await self.init_redis()
        await self.init_session()

        if not (self.access_token and self.refresh_token):
            await self._load_tokens()

        try:
            response = await self.api_request("GET", "profile/")
            role = response.get("role")
            if role in ("student", "teacher"):
                return role
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                await self._delete_tokens()
        except Exception as e:
            logger.warning(f"Failed to get role for {telegram_id}: {e}")
        return None

    async def get_user_name(self, telegram_id: int) -> Tuple[str, str]:
        self.telegram_id = telegram_id
        await self.init_redis()
        await self.init_session()

        if not (self.access_token and self.refresh_token):
            await self._load_tokens()

        try:
            response = await self.api_request("GET", "profile/")
            first_name = response.get("first_name", "")
            last_name = response.get("last_name", "")
            return first_name, last_name
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                await self._delete_tokens()
            logger.warning(f"Failed to get user name for {telegram_id}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error while getting user name for {telegram_id}: {e}")

        return "", ""

    async def get_teacher_status(self, telegram_id: int) -> str | None:
        self.telegram_id = telegram_id
        await self.init_redis()
        await self.init_session()

        if not (self.access_token and self.refresh_token):
            await self._load_tokens()

        try:
            profile = await self.api_request("GET", "profile/")
            if profile.get("role") == "teacher":
                return profile.get("status")
        except Exception as e:
            logger.warning(f"Failed to get teacher status for {telegram_id}: {e}")

        return None



    async def api_request(self, method: str, endpoint: str, **kwargs):
        await self._auto_refresh()
        await self.init_session()

        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._headers())

        async with self.session.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status == 401 and self.refresh_token:
                await self.refresh()
                headers = self._headers()
                async with self.session.request(method, url, headers=headers, **kwargs) as retry_resp:
                    return await retry_resp.json()
            return await resp.json()

    async def login(self, telegram_id: int):
        self.telegram_id = telegram_id
        await self.init_redis()
        await self.init_session()

        async with self.session.post(f"{self.BASE_URL}auth/login/", json={"telegram_id": telegram_id}) as resp:
            if resp.status == 404:
                await self._delete_tokens()
                raise ValueError("User not registered")
            data = await resp.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            await self._save_tokens()
            return data

    async def _auto_refresh(self):
        if self.access_token or not self.refresh_token:
            return
        logger.info(f"Access token missing or expired, refreshing for telegram_id={self.telegram_id}")
        await self.refresh()

    async def refresh(self):
        if not self.refresh_token:
            raise ValueError("No refresh_token for refresh")
        await self.init_session()
        async with self.session.post(f"{self.BASE_URL}auth/refresh/", json={"refresh": self.refresh_token}) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.access_token = data.get("access")
                await self._save_tokens()
            elif resp.status in (400, 404):
                await self.login(self.telegram_id)
            else:
                raise ValueError(f"Error updating token: {resp.status}")

    async def register(self, telegram_id: int, username: str, first_name: str = "",
                       last_name: str = "", phone_number: str = "", role: str = "student"):
        self.telegram_id = telegram_id
        await self.init_redis()
        await self.init_session()

        payload = {
            "username": username,
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "role": role
        }

        async with self.session.post(f"{self.BASE_URL}auth/register/", json=payload) as resp:
            if resp.status not in (200, 201):
                data = await resp.text()
                raise ValueError(f"Registration error: {data}")
            data = await resp.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            await self._save_tokens()
            return data

    async def logout(self, telegram_id: int | None = None):
        if telegram_id:
            self.telegram_id = telegram_id

        if not self.refresh_token:
            return
        await self.init_session()
        async with self.session.post(f"{self.BASE_URL}auth/logout/", json={"refresh": self.refresh_token}):
            pass
        await self._delete_tokens()

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
        self._token_owner_id: Optional[int] = None

        self.access_ttl = getattr(config, "ACCESS_EXPIRES_IN", 300)
        self.refresh_ttl = getattr(config, "REFRESH_EXPIRES_IN", 86400)

    async def init_redis(self):
        if self.redis_tokens is None:
            self.redis_tokens = aioredis.from_url(
                f"redis://:{config.REDIS_PASSWORD}@{config.REDIS_HOST}:{config.REDIS_PORT}/{config.REDIS_DB}",
                decode_responses=True
            )
        if self.redis_flags is None:
            self.redis_flags = aioredis.from_url(
                f"redis://:{config.REDIS_PASSWORD}@{config.REDIS_HOST}:{config.REDIS_PORT}/{config.REDIS_DB + 1}",
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

    async def _save_tokens_for(self, owner_id: int, access_token: Optional[str], refresh_token: Optional[str] = None):
        if not self.redis_tokens or not owner_id or not access_token:
            return
        try:
            await self.redis_tokens.setex(f"tsu_access:{owner_id}", self.access_ttl, access_token)
            if refresh_token:
                await self.redis_tokens.setex(f"tsu_refresh:{owner_id}", self.refresh_ttl, refresh_token)
            logger.info(f"Tokens saved for telegram_id={owner_id}")
            self.access_token = access_token
            if refresh_token:
                self.refresh_token = refresh_token
            self._token_owner_id = owner_id
            await self.set_login_flag(owner_id, True)
        except Exception as e:
            logger.error(f"Redis error (_save_tokens_for): {e}")

    async def _save_tokens(self):
        if not self.redis_tokens or not self.telegram_id or not self.access_token or not self.refresh_token:
            return
        await self._save_tokens_for(self.telegram_id, self.access_token, self.refresh_token)

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
                self._token_owner_id = self.telegram_id
                await self.set_login_flag(self.telegram_id, True)
                return True
            else:
                self.access_token = None
                self.refresh_token = None
                self._token_owner_id = None
        except Exception as e:
            logger.error(f"Redis error (_load_tokens): {e}")
        return False

    async def load_tokens_if_needed(self) -> bool:
        if self.access_token and self.refresh_token and self._token_owner_id == self.telegram_id:
            return True
        return await self._load_tokens()

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
        self._token_owner_id = None

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

    async def api_request(self, method: str, endpoint: str, **kwargs):
        await self.load_tokens_if_needed()
        await self.init_session()

        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        local_access = self.access_token
        local_refresh = self.refresh_token
        local_owner = self._token_owner_id
        if local_access:
            headers.update({"Authorization": f"Bearer {local_access}"})
        headers.setdefault("Content-Type", "application/json")

        async with self.session.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status == 204:
                return {}
            if resp.status in (200, 201):
                try:
                    return await resp.json()
                except Exception:
                    return {}
            if resp.status == 401 and local_refresh:
                try:
                    await self.refresh(local_refresh, owner_id=local_owner)
                except Exception:
                    pass
                retry_headers = {"Content-Type": "application/json"}
                if self.access_token:
                    retry_headers["Authorization"] = f"Bearer {self.access_token}"
                async with self.session.request(method, url, headers=retry_headers, **kwargs) as retry_resp:
                    if retry_resp.status == 204:
                        return {}
                    if retry_resp.status in (200, 201):
                        try:
                            return await retry_resp.json()
                        except Exception:
                            return {}
                    try:
                        return await retry_resp.json()
                    except Exception:
                        return {}
            try:
                return await resp.json()
            except Exception:
                return {}

    async def api_request_with_status(self, method: str, endpoint: str, **kwargs) -> tuple[int, dict | list | str | None]:
        await self.load_tokens_if_needed()
        await self.init_session()

        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        local_access = self.access_token
        local_refresh = self.refresh_token
        local_owner = self._token_owner_id
        if local_access:
            headers.update({"Authorization": f"Bearer {local_access}"})
        headers.setdefault("Content-Type", "application/json")

        async with self.session.request(method, url, headers=headers, **kwargs) as resp:
            status = resp.status
            if status == 204:
                return status, {}
            if status in (200, 201):
                try:
                    return status, await resp.json()
                except Exception:
                    return status, None
            if status == 401 and local_refresh:
                try:
                    await self.refresh(local_refresh, owner_id=local_owner)
                except Exception:
                    return status, await resp.text()
                retry_headers = {"Content-Type": "application/json"}
                if self.access_token:
                    retry_headers["Authorization"] = f"Bearer {self.access_token}"
                async with self.session.request(method, url, headers=retry_headers, **kwargs) as retry_resp:
                    retry_status = retry_resp.status
                    if retry_status == 204:
                        return retry_status, {}
                    try:
                        return retry_status, await retry_resp.json()
                    except Exception:
                        return retry_status, await retry_resp.text()
            try:
                return status, await resp.json()
            except Exception:
                return status, await resp.text()

    async def login(self, telegram_id: int):
        self.telegram_id = telegram_id
        await self.init_redis()
        await self.init_session()

        async with self.session.post(f"{self.BASE_URL}auth/login/", json={"telegram_id": telegram_id}) as resp:
            if resp.status == 404:
                await self._delete_tokens()
                raise ValueError("User not registered")
            data = await resp.json()
            access = data.get("access")
            refresh = data.get("refresh")
            await self._save_tokens_for(self.telegram_id, access, refresh)
            return data

    async def _auto_refresh(self):
        if self.access_token or not self.refresh_token:
            return
        logger.info(f"Access token missing or expired, refreshing for telegram_id={self.telegram_id}")
        await self.refresh(self.refresh_token, owner_id=self._token_owner_id)

    async def refresh(self, refresh_token: Optional[str] = None, owner_id: Optional[int] = None):
        token_to_use = refresh_token or self.refresh_token
        if not token_to_use:
            raise ValueError("No refresh_token for refresh")
        await self.init_session()
        async with self.session.post(f"{self.BASE_URL}auth/refresh/", json={"refresh": token_to_use}) as resp:
            if resp.status == 200:
                data = await resp.json()
                new_access = data.get("access")
                await self._save_tokens_for(owner_id or self.telegram_id, new_access)
            elif resp.status in (400, 404):
                await self.login(owner_id or self.telegram_id)
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
            access = data.get("access")
            refresh = data.get("refresh")
            await self._save_tokens_for(self.telegram_id, access, refresh)
            return data

    async def logout(self, telegram_id: int | None = None):
        if telegram_id:
            self.telegram_id = telegram_id

        await self.load_tokens_if_needed()

        if not self.refresh_token:
            return
        await self.init_session()
        async with self.session.post(f"{self.BASE_URL}auth/logout/", json={"refresh": self.refresh_token}):
            pass
        await self._delete_tokens()


auth = TSUAuth()

async def shutdown():
    await auth.close_session()

import logging
from typing import Optional

import aiohttp
from redis import asyncio as aioredis

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TSUAuth:
    BASE_URL = config.API_URL

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.telegram_id: Optional[int] = None

        self.access_ttl = getattr(config, "ACCESS_EXPIRES_IN", 300)
        self.refresh_ttl = getattr(config, "REFRESH_EXPIRES_IN", 86400)
        self.role_ttl = 60

    async def init_redis(self):
        if self.redis is None:
            self.redis = aioredis.from_url(
                f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/{config.REDIS_DB}",
                decode_responses=True
            )

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _save_tokens(self):
        if not self.redis or not self.telegram_id or not self.access_token or not self.refresh_token:
            return
        try:
            await self.redis.setex(f"tsu_access:{self.telegram_id}", self.access_ttl, self.access_token)
            await self.redis.setex(f"tsu_refresh:{self.telegram_id}", self.refresh_ttl, self.refresh_token)
            logger.info(f"Tokens saved for telegram_id={self.telegram_id}")
        except Exception as e:
            logger.error(f"Redis error (_save_tokens): {e}")

    async def _load_tokens(self):
        if not self.redis or not self.telegram_id:
            return False
        try:
            access_token = await self.redis.get(f"tsu_access:{self.telegram_id}")
            refresh_token = await self.redis.get(f"tsu_refresh:{self.telegram_id}")
            if access_token and refresh_token:
                self.access_token = access_token
                self.refresh_token = refresh_token
                logger.info(f"Tokens loaded for telegram_id={self.telegram_id}")
                return True
        except Exception as e:
            logger.error(f"Redis error (_load_tokens): {e}")
        return False

    async def _delete_tokens(self):
        if self.redis and self.telegram_id:
            try:
                await self.redis.delete(f"tsu_access:{self.telegram_id}")
                await self.redis.delete(f"tsu_refresh:{self.telegram_id}")
                await self.redis.delete(f"tsu_role:{self.telegram_id}")
                logger.info(f"Tokens deleted from Redis for telegram_id={self.telegram_id}")
            except Exception as e:
                logger.error(f"Redis error (_delete_tokens): {e}")
        self.access_token = None
        self.refresh_token = None

    async def is_registered(self, telegram_id: int) -> bool:
        self.telegram_id = telegram_id
        await self.init_redis()

        refresh_token = await self.redis.get(f"tsu_refresh:{self.telegram_id}")
        access_token = await self.redis.get(f"tsu_access:{self.telegram_id}")

        self.refresh_token = refresh_token
        self.access_token = access_token

        if not self.refresh_token:
            try:
                login_data = await self.login(telegram_id)
                return bool(login_data)
            except (aiohttp.ClientError, ValueError, aioredis.RedisError) as e:
                logger.warning(f"Login failed for {telegram_id}: {e}")
                return False

        if not self.access_token:
            try:
                await self._auto_refresh()
            except (aiohttp.ClientError, ValueError, aioredis.RedisError) as e:
                logger.warning(f"Auto-refresh failed for {telegram_id}: {e}")
                try:
                    login_data = await self.login(telegram_id)
                    return bool(login_data)
                except (aiohttp.ClientError, ValueError, aioredis.RedisError) as e2:
                    logger.warning(f"Re-login failed for {telegram_id}: {e2}")
                    return False
        return True

    async def _auto_refresh(self):
        if self.access_token or not self.refresh_token:
            return
        logger.info(f"Access token missing or expired, refreshing for telegram_id={self.telegram_id}")
        await self.refresh()

    async def get_role(self, telegram_id: int) -> Optional[str]:
        self.telegram_id = telegram_id
        await self.init_redis()

        try:
            role = await self.redis.get(f"tsu_role:{self.telegram_id}")
            if role:
                return role
        except aioredis.RedisError as e:
            logger.warning(f"Redis error while getting role for {telegram_id}: {e}")

        try:
            tokens = await self._load_tokens()
            if not tokens:
                await self.login(telegram_id)
        except (aiohttp.ClientError, ValueError, aioredis.RedisError) as e:
            logger.warning(f"Token loading or login failed for {telegram_id}: {e}")
            return None

        try:
            response = await self.api_request("GET", "profile/")
            role = response.get("role")
        except (aiohttp.ClientError, ValueError) as e:
            logger.warning(f"Failed to get role for {telegram_id}: {e}")
            return None

        if role in ("student", "teacher"):
            try:
                await self.redis.setex(f"tsu_role:{self.telegram_id}", self.role_ttl, role)
            except aioredis.RedisError as e:
                logger.warning(f"Redis error while saving role for {telegram_id}: {e}")
            return role
        return None

    async def api_request(self, method: str, endpoint: str, **kwargs):
        await self._auto_refresh()
        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._headers())

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status == 401 and self.refresh_token:
                    await self.refresh()
                    headers = self._headers()
                    async with session.request(method, url, headers=headers, **kwargs) as retry_resp:
                        return await retry_resp.json()
                return await resp.json()

    async def login(self, telegram_id: int):
        self.telegram_id = telegram_id
        await self.init_redis()

        if await self._load_tokens():
            return {"access": self.access_token, "refresh": self.refresh_token}

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.BASE_URL}auth/login/", json={"telegram_id": telegram_id}) as resp:
                if resp.status == 404:
                    await self._delete_tokens()
                    raise ValueError("Пользователь не найден. Нужно зарегистрироваться.")
                data = await resp.json()
                self.access_token = data.get("access")
                self.refresh_token = data.get("refresh")
                await self._save_tokens()
                return data

    async def register(self, telegram_id: int, username: str, first_name: str = "",
                       last_name: str = "", phone_number: str = "", role: str = "student"):
        self.telegram_id = telegram_id
        await self.init_redis()

        payload = {
            "username": username,
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "role": role
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.BASE_URL}auth/register/", json=payload) as resp:
                if resp.status not in (200, 201):
                    data = await resp.text()
                    raise ValueError(f"Ошибка регистрации: {data}")
                data = await resp.json()
                self.access_token = data.get("access")
                self.refresh_token = data.get("refresh")
                await self._save_tokens()
                return data

    async def refresh(self):
        if not self.refresh_token:
            raise ValueError("Нет refresh_token для обновления")

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.BASE_URL}auth/refresh/", json={"refresh": self.refresh_token}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.access_token = data.get("access")
                    await self._save_tokens()
                    return True
                elif resp.status in (400, 403):
                    await self.login(self.telegram_id)
                    return True
                else:
                    raise ValueError(f"Ошибка при обновлении токена: {resp.status}")

    async def logout(self):
        if not self.refresh_token:
            return
        async with aiohttp.ClientSession() as session:
            await session.post(f"{self.BASE_URL}auth/logout/", json={"refresh": self.refresh_token})
        await self._delete_tokens()

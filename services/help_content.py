import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any


class HelpContent:
    def __init__(self, file_path: str | None = None, ttl: float = 2.0):
        root = Path(__file__).resolve().parents[1]
        self.file_path = Path(file_path) if file_path else root / "data" / "help_content.json"
        self._ttl = float(ttl)
        self._cache: Dict[str, Any] | None = None
        self._cache_time: float = 0.0
        self._lock = asyncio.Lock()
        self._last_good: Dict[str, Any] | None = None

    def _read_file(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {"sections": [], "content": {}}
        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    async def _load_and_cache(self) -> Dict[str, Any]:
        try:
            data = await asyncio.to_thread(self._read_file)
            self._cache = data
            self._cache_time = time.time()
            self._last_good = data
            return data
        except Exception as e:
            print(f"[HelpContent] failed to load json: {e}")
            if self._last_good is not None:
                self._cache = self._last_good
                self._cache_time = time.time()
                return self._last_good
            return {"sections": [], "content": {}}

    async def get_raw(self) -> Dict[str, Any]:
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < self._ttl:
            return self._cache
        
        async with self._lock:
            now = time.time()
            if self._cache is not None and (now - self._cache_time) < self._ttl:
                return self._cache
            return await self._load_and_cache()

    async def get_sections(self, role: str | None, teacher_status: str | None = None) -> List[Tuple[str, str]]:
        raw = await self.get_raw()
        sections: List[Tuple[str, str]] = []
        for sec in raw.get("sections", []):
            key = sec.get("key")
            title = sec.get("title", key)
            visibility = sec.get("visible", ["all"]) or ["all"]
            if self._is_visible(visibility, role, teacher_status):
                sections.append((key, title))
        return sections

    def _is_visible(self, visibility: List[str], role: str | None, teacher_status: str | None) -> bool:
        for token in visibility:
            if token == "all":
                return True
            if token == "guest" and role is None:
                return True
            if token == "student" and role == "student":
                return True
            if token == "teacher" and role == "teacher":
                return True
            if token == "teacher_active" and role == "teacher" and teacher_status == "active":
                return True
            if token == "non_teacher" and role is not None and role != "teacher":
                return True
        return False

    async def get_section_text(self, key: str) -> str:
        raw = await self.get_raw()
        return raw.get("content", {}).get(key, "")


help_content = HelpContent()

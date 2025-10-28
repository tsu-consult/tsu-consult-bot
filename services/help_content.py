import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import asyncio
from functools import partial


class HelpContent:
    def __init__(self, file_path: str | None = None):
        root = Path(__file__).resolve().parents[1]
        default = root / "data" / "help_content.json"
        self.file_path = Path(file_path) if file_path else default
        self._data: Dict[str, Any] | None = None
        self._mtime: float | None = None
        self._lock = asyncio.Lock()

    def _read_file(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {"sections": [], "content": {}}
        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    async def _ensure_loaded(self):
        async with self._lock:
            try:
                mtime = self.file_path.stat().st_mtime if self.file_path.exists() else None
            except Exception:
                mtime = None

            if self._data is None or mtime != self._mtime:
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(None, self._read_file)
                self._data = data
                self._mtime = mtime

    async def get_raw(self) -> Dict[str, Any]:
        await self._ensure_loaded()
        return self._data or {"sections": [], "content": {}}

    async def get_sections(self, role: str | None, teacher_status: str | None = None) -> List[Tuple[str, str]]:
        raw = await self.get_raw()
        sections = []
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
            if token == "teacher_active" and role == "teacher" and teacher_status == "active":
                return True
            if token == "non_teacher" and role is not None and role != "teacher":
                return True
        return False

    async def get_section_text(self, key: str) -> str:
        raw = await self.get_raw()
        return raw.get("content", {}).get(key, "")


help_content = HelpContent()

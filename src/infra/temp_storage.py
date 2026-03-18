from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TempFileMeta:
    filename: str
    content_type: Optional[str] = None
    created_at: Optional[float] = None


class TempStorage:
    """Simple temp storage with lightweight metadata support."""

    def __init__(self, namespace: str, base_dir: Optional[Path] = None) -> None:
        base_path = Path(base_dir) if base_dir else Path(tempfile.gettempdir()) / "atri_temp"
        self.base_dir = base_path / namespace
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, key: str) -> Path:
        return self.base_dir / f"{key}.json"

    def write_bytes(
        self,
        key: str,
        data: bytes,
        *,
        suffix: str,
        content_type: Optional[str] = None,
    ) -> Path:
        filename = f"{key}{suffix}"
        path = self.base_dir / filename
        path.write_bytes(data)
        meta = {
            "filename": filename,
            "content_type": content_type or "",
            "created_at": time.time(),
        }
        self._meta_path(key).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def read_meta(self, key: str) -> Optional[TempFileMeta]:
        meta_path = self._meta_path(key)
        if not meta_path.exists():
            return None
        try:
            data: Dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        filename = data.get("filename")
        if not isinstance(filename, str) or not filename:
            return None
        return TempFileMeta(
            filename=filename,
            content_type=data.get("content_type") if isinstance(data.get("content_type"), str) else None,
            created_at=data.get("created_at") if isinstance(data.get("created_at"), (int, float)) else None,
        )

    def get_path(self, key: str) -> Optional[Path]:
        meta = self.read_meta(key)
        if meta:
            path = self.base_dir / meta.filename
            if path.exists():
                return path
        # Fallback: try to locate any file with the same prefix
        for item in self.base_dir.glob(f"{key}.*"):
            if item.is_file():
                return item
        return None

    @staticmethod
    def _file_mtime(path: Path) -> Optional[float]:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    @staticmethod
    def _safe_unlink(path: Path) -> int:
        try:
            path.unlink()
            return 1
        except FileNotFoundError:
            return 0
        except OSError:
            return 0

    def cleanup_expired(self, *, max_age_hours: float, now: Optional[float] = None) -> int:
        normalized_hours = max(0.0, float(max_age_hours))
        current_time = time.time() if now is None else float(now)
        cutoff = current_time - normalized_hours * 3600.0
        deleted = 0
        referenced_files: set[str] = set()

        for meta_path in self.base_dir.glob("*.json"):
            meta = self.read_meta(meta_path.stem)
            data_path = self.base_dir / meta.filename if meta else None

            created_at = meta.created_at if meta and meta.created_at is not None else None
            if created_at is None:
                meta_mtime = self._file_mtime(meta_path)
                data_mtime = self._file_mtime(data_path) if data_path else None
                timestamps = [ts for ts in (meta_mtime, data_mtime) if ts is not None]
                created_at = min(timestamps) if timestamps else None

            if created_at is not None and created_at >= cutoff:
                if meta and data_path is not None:
                    referenced_files.add(data_path.name)
                continue

            deleted += self._safe_unlink(meta_path)
            if data_path is not None:
                deleted += self._safe_unlink(data_path)

        for item in self.base_dir.iterdir():
            if not item.is_file() or item.suffix == ".json":
                continue
            if item.name in referenced_files:
                continue
            mtime = self._file_mtime(item)
            if mtime is None or mtime >= cutoff:
                continue
            deleted += self._safe_unlink(item)

        return deleted

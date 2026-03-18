import json
import os
from pathlib import Path

from src.infra.temp_storage import TempStorage


def test_cleanup_expired_removes_old_entry_and_keeps_fresh_entry(tmp_path: Path):
    storage = TempStorage("daily60s", base_dir=tmp_path)
    now = 10_000.0
    old_created_at = now - 49 * 3600
    fresh_created_at = now - 2 * 3600

    old_data = storage.base_dir / "old.png"
    old_meta = storage.base_dir / "old.json"
    old_data.write_bytes(b"old")
    old_meta.write_text(
        json.dumps(
            {
                "filename": old_data.name,
                "content_type": "image/png",
                "created_at": old_created_at,
            }
        ),
        encoding="utf-8",
    )

    fresh_data = storage.base_dir / "fresh.png"
    fresh_meta = storage.base_dir / "fresh.json"
    fresh_data.write_bytes(b"fresh")
    fresh_meta.write_text(
        json.dumps(
            {
                "filename": fresh_data.name,
                "content_type": "image/png",
                "created_at": fresh_created_at,
            }
        ),
        encoding="utf-8",
    )

    deleted = storage.cleanup_expired(max_age_hours=24, now=now)

    assert deleted == 2
    assert not old_data.exists()
    assert not old_meta.exists()
    assert fresh_data.exists()
    assert fresh_meta.exists()


def test_cleanup_expired_removes_old_orphan_file(tmp_path: Path):
    storage = TempStorage("daily60s", base_dir=tmp_path)
    now = 20_000.0
    orphan = storage.base_dir / "orphan.png"
    orphan.write_bytes(b"orphan")

    old_mtime = now - 30 * 3600
    os.utime(orphan, (old_mtime, old_mtime))

    deleted = storage.cleanup_expired(max_age_hours=24, now=now)

    assert deleted == 1
    assert not orphan.exists()

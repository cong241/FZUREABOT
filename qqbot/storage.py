from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from .models import DutyEntry, Settings


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到文件：{path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 JSON 文件：{path}") from exc


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False, dir=path.parent
        ) as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            temp_name = stream.name
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise ValueError(f"无法保存 JSON 文件：{path}") from exc


def load_roster(path: Path) -> list[DutyEntry]:
    raw = _read_json(path)
    if not isinstance(raw, list):
        raise ValueError("无法读取排班：根节点必须是数组")
    entries = [DutyEntry.from_dict(item) for item in raw]
    _validate_unique_dates(entries)
    return sorted(entries, key=lambda entry: entry.duty_date)


def save_roster(path: Path, entries: Iterable[DutyEntry]) -> None:
    values = list(entries)
    _validate_unique_dates(values)
    _atomic_write_json(path, [entry.to_dict() for entry in sorted(values, key=lambda x: x.duty_date)])


def _validate_unique_dates(entries: Iterable[DutyEntry]) -> None:
    seen: set[date] = set()
    for entry in entries:
        if entry.duty_date in seen:
            raise ValueError(f"重复日期：{entry.duty_date.isoformat()}")
        seen.add(entry.duty_date)


def load_settings(path: Path) -> Settings:
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise ValueError("设置文件根节点必须是对象")
    return Settings.from_dict(raw)


def load_sent_dates(path: Path) -> set[str]:
    if not path.exists():
        return set()
    raw = _read_json(path)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("已发送记录必须是日期字符串数组")
    return set(raw)


def save_sent_dates(path: Path, dates: Iterable[str]) -> None:
    _atomic_write_json(path, sorted(set(dates)))


def next_workday(day: date) -> date:
    candidate = day + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate

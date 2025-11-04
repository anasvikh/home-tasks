from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class User:
    telegram_id: int
    name: str


TaskMap = Dict[str, Dict[str, List[str]]]


def load_users(path: Path) -> List[User]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    users: List[User] = []
    for item in raw:
        users.append(User(telegram_id=int(item["id"]), name=item["name"]))
    if not users:
        raise ValueError("Users list cannot be empty")
    return users


def load_tasks(path: Path) -> TaskMap:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):  # pragma: no cover - guard clause
        raise ValueError("tasks.json must contain an object")
    return data

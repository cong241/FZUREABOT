from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests


class NapCatError(RuntimeError):
    """A safe, user-facing NapCat error that never includes credentials."""


@dataclass(frozen=True, slots=True)
class NapCatEndpoint:
    base_url: str
    token: str = field(repr=False)

    @classmethod
    def from_config(cls, path: Path) -> "NapCatEndpoint":
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            servers = raw["network"]["httpServers"]
        except FileNotFoundError as exc:
            raise NapCatError(f"找不到 NapCat 配置：{path}") from exc
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise NapCatError(f"NapCat 配置无法读取：{path}") from exc
        server = next((item for item in servers if item.get("enable")), None)
        if not server:
            raise NapCatError("NapCat 没有已启用的 OneBot HTTP 服务")
        try:
            port = int(server["port"])
            host = str(server.get("host") or "127.0.0.1")
            token = str(server.get("token") or "")
        except (KeyError, TypeError, ValueError) as exc:
            raise NapCatError("NapCat HTTP 服务配置无效") from exc
        if not (1 <= port <= 65535):
            raise NapCatError("NapCat HTTP 端口无效")
        if host in {"0.0.0.0", "::", "[::]"}:
            host = "127.0.0.1"
        return cls(base_url=f"http://{host}:{port}", token=token)


def build_reminder_segments(user_id: int) -> list[dict[str, Any]]:
    return [
        {"type": "at", "data": {"qq": str(user_id)}},
        {
            "type": "text",
            "data": {"text": "，明天轮到你值班，祝你工作顺利"},
        },
    ]


class NapCatClient:
    def __init__(
        self,
        endpoint: NapCatEndpoint,
        *,
        session: Any | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self.session = session or requests.Session()
        self.timeout = timeout

    def _call(self, action: str, *, method: str = "GET", **kwargs: Any) -> Any:
        url = f"{self.endpoint.base_url}/{action}"
        headers = {"Authorization": f"Bearer {self.endpoint.token}"}
        try:
            response = self.session.request(
                method, url, headers=headers, timeout=self.timeout, **kwargs
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, OSError) as exc:
            raise NapCatError(f"无法连接 NapCat：{type(exc).__name__}") from exc
        if not isinstance(payload, dict):
            raise NapCatError("NapCat 返回了无效数据")
        if payload.get("retcode") != 0:
            raise NapCatError(
                f"NapCat 调用失败：retcode={payload.get('retcode')}，"
                f"message={payload.get('message', '')}"
            )
        return payload.get("data")

    def get_login_info(self) -> dict[str, Any]:
        return self._call("get_login_info")

    def get_group_member_info(self, group_id: int, user_id: int) -> dict[str, Any]:
        return self._call(
            "get_group_member_info",
            params={"group_id": group_id, "user_id": user_id, "no_cache": True},
        )

    def send_group_reminder(self, group_id: int, user_id: int) -> dict[str, Any]:
        return self._call(
            "send_group_msg",
            method="POST",
            json={"group_id": group_id, "message": build_reminder_segments(user_id)},
        )

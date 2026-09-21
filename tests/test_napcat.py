import json

import pytest

from qqbot.napcat import (
    NapCatClient,
    NapCatEndpoint,
    NapCatError,
    build_reminder_segments,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse(self.payload)


def test_load_endpoint_uses_enabled_http_server_without_exposing_token(tmp_path):
    path = tmp_path / "onebot.json"
    path.write_text(
        json.dumps(
            {
                "network": {
                    "httpServers": [
                        {"enable": False, "host": "127.0.0.1", "port": 1, "token": "old"},
                        {"enable": True, "host": "0.0.0.0", "port": 3002, "token": "secret"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    endpoint = NapCatEndpoint.from_config(path)
    assert endpoint.base_url == "http://127.0.0.1:3002"
    assert "secret" not in repr(endpoint)


def test_message_has_true_at_segment():
    assert build_reminder_segments(3060569778) == [
        {"type": "at", "data": {"qq": "3060569778"}},
        {"type": "text", "data": {"text": "，明天轮到你值班，祝你工作顺利"}},
    ]


def test_nonzero_retcode_raises_without_token_in_error():
    session = FakeSession({"retcode": 100, "message": "failed"})
    client = NapCatClient(
        NapCatEndpoint("http://127.0.0.1:3002", "secret"), session=session
    )
    with pytest.raises(NapCatError, match="retcode=100") as error:
        client.get_login_info()
    assert "secret" not in str(error.value)


def test_client_sends_authorization_and_group_message():
    session = FakeSession({"retcode": 0, "data": {"message_id": 42}})
    client = NapCatClient(
        NapCatEndpoint("http://127.0.0.1:3002", "secret"), session=session
    )
    result = client.send_group_reminder(1094289617, 3060569778)
    assert result["message_id"] == 42
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith("/send_group_msg")
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["message"][0]["type"] == "at"


def test_missing_enabled_http_server_is_rejected(tmp_path):
    path = tmp_path / "onebot.json"
    path.write_text('{"network":{"httpServers":[]}}', encoding="utf-8")
    with pytest.raises(NapCatError, match="已启用"):
        NapCatEndpoint.from_config(path)

"""텔레그램 Bot API 얇은 클라이언트 — 표준 라이브러리만 사용(외부 의존성 없음)."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from typing import Any

from . import config


def _call(method: str, params: dict[str, Any] | None = None, timeout: float = 60.0) -> dict:
    url = f"{config.API_BASE}/bot{config.bot_token()}/{method}"
    payload = {}
    for k, v in (params or {}).items():
        if v is None:
            continue
        # dict/list 값(reply_markup 등)은 JSON 문자열로 보낸다.
        payload[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method} 실패: {body.get('description')}")
    return body


def send_message(text: str, reply_markup: dict | None = None) -> dict:
    res = _call(
        "sendMessage",
        {"chat_id": config.chat_id(), "text": text, "reply_markup": reply_markup},
    )
    return res["result"]


def edit_message_text(message_id: int, text: str, reply_markup: dict | None = None) -> None:
    try:
        _call(
            "editMessageText",
            {
                "chat_id": config.chat_id(),
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
            },
        )
    except Exception:
        # 편집 실패(메시지 동일/삭제 등)는 흐름을 막지 않는다.
        pass


def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    try:
        _call("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
    except Exception:
        pass


def get_updates(offset: int | None, timeout_sec: int) -> list[dict]:
    """long-poll. urlopen 타임아웃은 텔레그램 timeout 보다 넉넉히 크게 둔다."""
    res = _call(
        "getUpdates",
        {"offset": offset, "timeout": timeout_sec},
        timeout=timeout_sec + 15,
    )
    return res["result"]


def latest_update_id() -> int | None:
    """현재까지 쌓인 마지막 update_id (확정하지 않고 조회만). 질문 이전의 묵은 메시지를 거르는 기준선."""
    res = _call("getUpdates", {"offset": -1, "timeout": 0}, timeout=20)
    ups = res["result"]
    return ups[-1]["update_id"] if ups else None


def get_me() -> dict:
    return _call("getMe", {}, timeout=20)["result"]

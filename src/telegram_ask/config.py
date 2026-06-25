"""설정 — 전부 환경변수로 주입. 비밀(봇 토큰)은 절대 코드/레포에 박지 않는다."""
from __future__ import annotations
import os

API_BASE = "https://api.telegram.org"


def bot_token() -> str:
    """텔레그램 봇 토큰. MCP 클라이언트(~/.claude.json)의 env로만 주입.

    노출 시 봇 탈취 가능 → 레포·문서·로그에 절대 남기지 않는다.
    """
    tok = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not tok:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN 환경변수가 없습니다. MCP 서버 등록 시 env로 주입하세요."
        )
    return tok


def chat_id() -> str:
    """질문을 보낼 대상 chat_id. 개인 식별자라 코드에 기본값을 두지 않는다."""
    cid = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not cid:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID 환경변수가 없습니다. 봇에게 메시지를 보낸 뒤 "
            "getUpdates 의 chat.id 로 확인해 주입하세요."
        )
    return cid


# 전체 대기 한도(초). 이 시간 안에 답이 없으면 timeout 반환 → Claude가 터미널로 폴백.
WAIT_SEC: int = int(os.environ.get("TELEGRAM_ASK_WAIT_SEC", "600"))

# 1회 long-poll 길이(초). 텔레그램 getUpdates 의 timeout 파라미터.
POLL_SEC: int = int(os.environ.get("TELEGRAM_ASK_POLL_SEC", "50"))

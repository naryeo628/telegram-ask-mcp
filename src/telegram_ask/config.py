"""설정 — 전부 환경변수/파일로 주입. 비밀(봇 토큰)은 절대 코드·레포에 박지 않는다.

토큰·chat_id 해석 우선순위 (먼저 잡히는 값 사용):
  1) 리터럴 env            TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
  2) 개별 파일(원문 1줄)   TELEGRAM_BOT_TOKEN_FILE / TELEGRAM_CHAT_ID_FILE
  3) 공유 env 파일         TELEGRAM_ENV_FILE 안의 KEY=VALUE 라인에서 해당 키

→ ~/.claude.json 에 토큰을 직접 적기 싫으면 TELEGRAM_ENV_FILE 만 가리키면 된다.
  예) TELEGRAM_ENV_FILE=~/workspace/oci/launch_a1.sh (기존 토큰 보관처 재사용)
"""
from __future__ import annotations
import os
import re
from pathlib import Path

API_BASE = "https://api.telegram.org"

_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def _read_raw_file(path: str) -> str | None:
    try:
        return Path(path).expanduser().read_text().strip() or None
    except OSError:
        return None


def _parse_env_file(path: str) -> dict[str, str]:
    """KEY=VALUE / export KEY="VALUE" 형식 파일에서 우리가 쓰는 키만 뽑는다(쉘스크립트 호환)."""
    try:
        txt = Path(path).expanduser().read_text()
    except OSError:
        return {}
    out: dict[str, str] = {}
    for key in _KEYS:
        # 따옴표 선택, export 접두 허용, 줄 끝 주석(#) 제거. 텔레그램 토큰/숫자엔 # 없음.
        m = re.search(rf'^\s*(?:export\s+)?{key}\s*=\s*["\']?([^"\'\n#]+)', txt, re.M)
        if m:
            out[key] = m.group(1).strip()
    return out


# 공유 env 파일은 프로세스 동안 1회만 읽는다(폴마다 디스크 접근 방지). 값 바뀌면 서버 재시작.
_ENV_FILE_CACHE: dict[str, str] | None = None


def _env_file_values() -> dict[str, str]:
    global _ENV_FILE_CACHE
    if _ENV_FILE_CACHE is None:
        path = os.environ.get("TELEGRAM_ENV_FILE")
        _ENV_FILE_CACHE = _parse_env_file(path) if path else {}
    return _ENV_FILE_CACHE


def _resolve(name: str) -> str | None:
    # 1) 리터럴 env
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    # 2) 개별 파일(원문 1줄)
    fp = os.environ.get(f"{name}_FILE")
    if fp:
        raw = _read_raw_file(fp)
        if raw:
            return raw
    # 3) 공유 env 파일에서 해당 키
    return _env_file_values().get(name)


def bot_token() -> str:
    """텔레그램 봇 토큰. 노출 시 봇 탈취 가능 → 레포·문서·로그에 절대 남기지 않는다."""
    tok = _resolve("TELEGRAM_BOT_TOKEN")
    if not tok:
        raise RuntimeError(
            "봇 토큰을 찾지 못했습니다. TELEGRAM_BOT_TOKEN(리터럴) 또는 "
            "TELEGRAM_BOT_TOKEN_FILE(원문 파일) 또는 TELEGRAM_ENV_FILE(KEY=VALUE 파일) 중 하나를 주입하세요."
        )
    return tok


def chat_id() -> str:
    """질문을 보낼 대상 chat_id. 개인 식별자라 코드에 기본값을 두지 않는다."""
    cid = _resolve("TELEGRAM_CHAT_ID")
    if not cid:
        raise RuntimeError(
            "chat_id 를 찾지 못했습니다. TELEGRAM_CHAT_ID(리터럴) 또는 "
            "TELEGRAM_CHAT_ID_FILE 또는 TELEGRAM_ENV_FILE 중 하나를 주입하세요. "
            "봇에게 메시지를 보낸 뒤 getUpdates 의 chat.id 로 확인할 수 있습니다."
        )
    return cid


# 전체 대기 한도(초). 이 시간 안에 답이 없으면 timeout 반환 → Claude가 터미널로 폴백.
WAIT_SEC: int = int(os.environ.get("TELEGRAM_ASK_WAIT_SEC", "600"))

# 1회 long-poll 길이(초). 텔레그램 getUpdates 의 timeout 파라미터.
POLL_SEC: int = int(os.environ.get("TELEGRAM_ASK_POLL_SEC", "50"))

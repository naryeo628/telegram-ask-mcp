"""telegram-ask-mcp MCP 서버 (stdio).

Claude가 사용자에게 선택지를 물어야 할 때, 터미널 팝업 대신(또는 함께) 텔레그램으로 질문을
보내고 사용자의 답(버튼 탭 / 번호 / 자유 텍스트)을 받아 반환한다.

도구:
  ask_via_telegram(question, options, allow_free_text)  핵심 — 묻고 답 받을 때까지 long-poll
  notify_telegram(text)                                 단방향 알림만 보낼 때
  check_config()                                        봇/설정 점검(setup 디버그)
"""
from __future__ import annotations
import time
import urllib.error

from mcp.server.fastmcp import FastMCP

from . import config, telegram

mcp = FastMCP("telegram-ask")


def _build_keyboard(options: list[str]) -> dict | None:
    if not options:
        return None
    rows = []
    for i, opt in enumerate(options):
        label = f"{i + 1}. {opt}"
        # 인라인 버튼 텍스트는 길어도 되지만 과하면 잘림 → 표시용만 자른다(반환값은 원문).
        rows.append([{"text": label[:64], "callback_data": f"o{i}"}])
    return {"inline_keyboard": rows}


def _format_question(question: str, options: list[str], allow_free_text: bool) -> str:
    lines = [f"❓ {question}"]
    if options:
        lines.append("")
        for i, opt in enumerate(options):
            lines.append(f"  {i + 1}. {opt}")
        lines.append("")
        hint = "👉 버튼을 누르거나 번호를 보내세요."
        if allow_free_text:
            hint += " 다른 답은 직접 입력해도 됩니다."
        lines.append(hint)
    elif allow_free_text:
        lines.append("")
        lines.append("👉 답변을 입력해 주세요.")
    return "\n".join(lines)


def _from_my_chat(obj: dict) -> bool:
    return str(obj.get("chat", {}).get("id")) == config.chat_id()


@mcp.tool()
def ask_via_telegram(
    question: str,
    options: list[str] | None = None,
    allow_free_text: bool = True,
) -> dict:
    """텔레그램으로 질문을 보내고 사용자의 답을 받을 때까지 기다린다(long-poll).

    사용자가 선택지를 골라야 하는 상황이면 터미널 팝업 대신 이 도구를 쓴다.
    options 를 주면 번호 버튼으로 표시되고, allow_free_text=True 면 버튼 외 자유 입력도 받는다.
    options 가 비어 있으면 순수 주관식 질문이 된다.

    반환:
      답함:    {ok, answered:true, answer, via:"button"|"text",
                option_index: int|None, is_custom: bool}
      시간초과: {ok, answered:false, timeout:true, waited_sec}
      → timeout 이면 Claude 는 평소처럼 터미널에서 다시 물어보면 된다.
    """
    options = options or []

    # 1) 기준선: 질문 이전에 쌓인 묵은 메시지를 무시하기 위해 마지막 update_id 확보
    baseline = telegram.latest_update_id()
    offset = (baseline + 1) if baseline is not None else None

    # 2) 질문 전송
    text = _format_question(question, options, allow_free_text)
    sent = telegram.send_message(text, reply_markup=_build_keyboard(options))
    sent_id = sent["message_id"]

    # 3) 답이 올 때까지 long-poll (전체 WAIT_SEC 한도)
    deadline = time.monotonic() + config.WAIT_SEC
    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        poll = min(config.POLL_SEC, remaining)
        try:
            updates = telegram.get_updates(offset, poll)
        except (urllib.error.URLError, TimeoutError):
            continue  # 폴 타임아웃/일시적 네트워크 → 다음 라운드

        for u in updates:
            offset = u["update_id"] + 1

            # (a) 인라인 버튼 탭
            cq = u.get("callback_query")
            if cq and _from_my_chat(cq.get("message", {})):
                data = cq.get("data", "")
                if data.startswith("o") and data[1:].isdigit():
                    idx = int(data[1:])
                    if 0 <= idx < len(options):
                        ans = options[idx]
                        telegram.answer_callback_query(cq["id"], f"✅ {ans[:180]}")
                        telegram.edit_message_text(sent_id, f"❓ {question}\n\n✅ 선택: {ans}")
                        return {
                            "ok": True, "answered": True, "answer": ans,
                            "via": "button", "option_index": idx, "is_custom": False,
                        }

            # (b) 텍스트 메시지
            msg = u.get("message")
            if allow_free_text and msg and _from_my_chat(msg):
                t = (msg.get("text") or "").strip()
                if not t:
                    continue
                # 번호만 보냈고 그 번호의 선택지가 있으면 선택으로 간주
                if options and t.isdigit() and 1 <= int(t) <= len(options):
                    idx = int(t) - 1
                    ans = options[idx]
                    telegram.edit_message_text(sent_id, f"❓ {question}\n\n✅ 선택: {ans}")
                    return {
                        "ok": True, "answered": True, "answer": ans,
                        "via": "text", "option_index": idx, "is_custom": False,
                    }
                # 그 외엔 자유 답변
                telegram.send_message(f"✅ 답변 받음:\n{t}")
                return {
                    "ok": True, "answered": True, "answer": t,
                    "via": "text", "option_index": None, "is_custom": True,
                }

    # 4) 시간 초과
    telegram.edit_message_text(
        sent_id, f"❓ {question}\n\n⏰ 응답 시간 초과 — 터미널에서 답변하세요."
    )
    return {"ok": True, "answered": False, "timeout": True, "waited_sec": config.WAIT_SEC}


@mcp.tool()
def notify_telegram(text: str) -> dict:
    """답을 기다리지 않고 텔레그램으로 알림만 보낸다(작업 완료/승인요청 안내 등)."""
    sent = telegram.send_message(text)
    return {"ok": True, "message_id": sent["message_id"]}


@mcp.tool()
def check_config() -> dict:
    """설정 점검: 봇 연결(getMe)과 대상 chat_id 를 확인한다(토큰 값은 노출하지 않음)."""
    me = telegram.get_me()
    return {
        "ok": True,
        "bot_username": me.get("username"),
        "bot_id": me.get("id"),
        "chat_id": config.chat_id(),
        "wait_sec": config.WAIT_SEC,
        "poll_sec": config.POLL_SEC,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

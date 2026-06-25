# telegram-ask-mcp

Claude(Claude Code)가 **선택지를 물어야 할 때 터미널 팝업 대신 텔레그램으로 질문을 보내고**,
사용자가 폰에서 누른 버튼·번호·자유 텍스트를 답으로 받아오는 MCP 서버.

> 자리에 없어도 폰으로 Claude의 질문에 답하고 작업을 계속 진행시킬 수 있다.

- 📄 문서/소개: https://naryeo628.github.io/telegram-ask-mcp/
- 🧩 MCP 서버(stdio), Python `FastMCP`, **외부 의존성 없음**(표준 라이브러리 + `mcp`)

## 어떻게 동작하나

1. Claude가 `ask_via_telegram(question, options)` 도구 호출
2. 서버가 텔레그램으로 질문 + **번호 인라인 버튼** 전송
3. 사용자가 **버튼 탭** / **번호 입력** / **자유 텍스트** 중 하나로 응답
4. 서버가 `getUpdates` long-poll 로 응답을 받아 Claude에 반환
5. 약 10분(`TELEGRAM_ASK_WAIT_SEC`) 안에 답이 없으면 `timeout` 반환 → Claude는 평소처럼 터미널에서 다시 질문

> ⚠️ **왜 기존 팝업을 자동으로 못 가로채나**: MCP 서버는 다른 도구(Claude 내장 AskUserQuestion)를
> 후킹할 수 없다. 그래서 "묻기"를 담당하는 **전용 도구**를 만들고, Claude가 질문 상황에서 이 도구를
> 쓰도록 메모리/규칙으로 유도한다.

## 도구

| 도구 | 설명 |
|------|------|
| `ask_via_telegram(question, options=[], allow_free_text=True)` | 질문 전송 후 답 받을 때까지 대기. 반환: `answer`, `via`(button/text), `option_index`, `is_custom`, 또는 `timeout` |
| `notify_telegram(text)` | 답을 기다리지 않는 단방향 알림 |
| `check_config()` | 봇 연결(getMe)·대상 chat_id 점검 (토큰 값은 노출 안 함) |

## 설치

```bash
git clone https://github.com/naryeo628/telegram-ask-mcp
cd telegram-ask-mcp
uv tool install .        # ~/.local/bin/telegram-ask-mcp 생성
```

### Claude Code 등록 (`~/.claude.json`, user 스코프)

```jsonc
{
  "mcpServers": {
    "telegram-ask": {
      "command": "/Users/<you>/.local/bin/telegram-ask-mcp",
      "env": {
        "TELEGRAM_BOT_TOKEN": "<봇 토큰 — 절대 레포에 커밋 금지>",
        "TELEGRAM_CHAT_ID": "<본인 chat_id>"
      }
    }
  }
}
```

등록 후 Claude Code 재시작 → 도구 로드. `check_config()` 로 연결 확인.

### 환경변수

| 변수 | 기본 | 설명 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | (필수) | BotFather 봇 토큰. **비밀** |
| `TELEGRAM_CHAT_ID` | (필수) | 질문 받을 대상 chat_id |
| `TELEGRAM_ASK_WAIT_SEC` | `600` | 전체 응답 대기 한도(초) |
| `TELEGRAM_ASK_POLL_SEC` | `50` | 1회 long-poll 길이(초) |

봇/chat_id 가 없으면: BotFather 로 봇 생성 → 봇에게 아무 메시지 전송 →
`https://api.telegram.org/bot<TOKEN>/getUpdates` 의 `result[].message.chat.id`.

## "항상 텔레그램으로 묻기" 규칙

Claude가 선택지를 물 상황마다 이 도구를 쓰게 하려면, 프로젝트/유저 메모리(또는 `CLAUDE.md`)에
대략 이렇게 적어 둔다:

> 사용자에게 선택지를 물어야 할 때는 터미널 팝업 대신 `telegram-ask` 의
> `ask_via_telegram` 를 먼저 호출한다. `timeout` 이 오면 그때 터미널에서 다시 묻는다.

## 보안

- 봇 토큰은 **MCP 클라이언트 env 로만** 주입. 레포·문서·로그·프론트에 절대 노출 금지.
- 노출 의심 시 BotFather `/revoke` 로 즉시 재발급.
- `getUpdates` 는 한 번에 하나의 소비자만 받을 수 있어, 같은 봇으로 여러 인스턴스를 동시에
  long-poll 하면 서로 업데이트를 가로챌 수 있다(단일 사용자 로컬 환경 기준 설계).

## 라이선스

MIT

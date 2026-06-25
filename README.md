# telegram-ask-mcp

Claude(Claude Code 등)가 **선택지를 물어야 할 때 터미널 팝업 대신 텔레그램으로 질문을 보내고**,
사용자가 폰에서 누른 버튼·번호·자유 텍스트를 답으로 받아오는 MCP 서버.

> 자리에 없어도 폰으로 Claude의 질문에 답하고 작업을 계속 진행시킬 수 있다.

- 📄 소개 페이지: https://naryeo628.github.io/telegram-ask-mcp/
- 🧩 MCP 서버(stdio) · Python `FastMCP` · **외부 의존성 없음**(표준 라이브러리 + `mcp`)

```
┌────────────────────────────────────────┐
│ ❓ 어느 방식으로 배포할까요?            │
│                                        │
│   1. 블루-그린                          │
│   2. 카나리                             │
│   3. 롤링                               │
│                                        │
│ 👉 버튼을 누르거나 번호를 보내세요.     │
│  [ 1. 블루-그린 ]                       │
│  [ 2. 카나리   ]                        │
│  [ 3. 롤링     ]                        │
└────────────────────────────────────────┘
                              나: 2  ↩
```

---

## 목차

1. [동작 방식](#동작-방식)
2. [사전 준비](#사전-준비)
3. [1단계 · 텔레그램 봇 만들기](#1단계--텔레그램-봇-만들기-botfather)
4. [2단계 · 내 chat_id 알아내기](#2단계--내-chat_id-알아내기)
5. [3단계 · 비밀 파일 만들기](#3단계--비밀-파일-만들기)
6. [4단계 · 설치](#4단계--설치)
7. [5단계 · MCP 클라이언트에 등록](#5단계--mcp-클라이언트에-등록)
8. [6단계 · 연결 확인](#6단계--연결-확인)
9. ["항상 텔레그램으로 묻기" 규칙](#항상-텔레그램으로-묻기-규칙)
10. [도구 레퍼런스](#도구-레퍼런스)
11. [환경변수](#환경변수)
12. [문제 해결](#문제-해결)
13. [보안](#보안)
14. [개발 · 재배포](#개발--재배포)

---

## 동작 방식

1. Claude가 `ask_via_telegram(question, options)` 도구를 호출
2. 서버가 텔레그램으로 질문 + **번호 인라인 버튼**을 전송
3. 사용자가 **버튼 탭** / **번호 입력** / **자유 텍스트** 중 하나로 응답
4. 서버가 `getUpdates` long-poll로 응답을 받아 Claude에 반환
5. 약 10분(`TELEGRAM_ASK_WAIT_SEC`) 안에 답이 없으면 `timeout`을 반환 → Claude는 평소처럼 터미널에서 다시 질문

> ⚠️ **왜 기존 팝업을 자동으로 못 가로채나:** MCP 서버는 다른 도구(Claude 내장 AskUserQuestion)를
> 후킹할 수 없다. 그래서 "묻기"를 담당하는 **전용 도구**를 만들고, Claude가 질문 상황에서 이 도구를
> 쓰도록 메모리/규칙으로 유도한다. ([아래 참고](#항상-텔레그램으로-묻기-규칙))

---

## 사전 준비

- **Python 3.10 이상**
- **[uv](https://docs.astral.sh/uv/)** (권장 설치 도구) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **텔레그램 계정** (앱 설치된 폰 또는 데스크톱)
- MCP를 지원하는 클라이언트 — Claude Code, Claude Desktop, Cursor 등

---

## 1단계 · 텔레그램 봇 만들기 (BotFather)

봇은 텔레그램의 **BotFather**가 발급한다.

1. 텔레그램에서 [`@BotFather`](https://t.me/BotFather) 검색 → 대화 열기 → **Start**
2. `/newbot` 입력
3. **봇 이름(name)** 입력 — 표시용. 아무거나 (예: `My Claude Asker`)
4. **봇 username** 입력 — 반드시 `bot`으로 끝나야 함, 전역에서 유일해야 함 (예: `my_claude_asker_bot`)
5. 성공하면 BotFather가 **토큰**을 준다. 이렇게 생긴 문자열:

   ```
   8383648698:AAH...(생략)...xyz
   ```

   > 🔐 이 토큰은 **비밀번호와 동급**. 노출되면 누구나 이 봇을 조종할 수 있다. 채팅·코드·캡처에 남기지 말 것.
   > 잃어버리거나 노출되면 BotFather에서 `/token`(재확인) 또는 `/revoke`(재발급).

6. **방금 만든 봇과의 대화를 열고 아무 메시지나 한 번 보낸다** (예: `/start` 또는 `hi`).

   > ❗ 텔레그램 봇은 **사용자가 먼저 말을 걸기 전에는 사용자에게 메시지를 보낼 수 없다.**
   > 이 단계를 빼먹으면 나중에 질문이 안 날아온다. (그룹/채널이 아니라 **봇과의 1:1 대화**여야 함)

---

## 2단계 · 내 chat_id 알아내기

봇이 메시지를 보낼 **대상**(=나)의 숫자 ID. 두 방법 중 편한 것:

### 방법 A — getUpdates (봇 토큰만 있으면 됨)

1단계 6번에서 봇에게 메시지를 보낸 뒤, 브라우저나 터미널에서:

```bash
curl -s "https://api.telegram.org/bot<여기에_봇토큰>/getUpdates"
```

응답 JSON에서 `result[].message.chat.id` 값이 내 `chat_id`다.

```jsonc
{
  "ok": true,
  "result": [
    { "message": { "chat": { "id": 8952171082, "type": "private", ... } } }
  ]
}
```

> 응답이 `"result": []` 로 비어 있으면 → 봇에게 메시지를 아직 안 보낸 것. 1:1 대화에서 아무거나 보낸 뒤 다시 호출.

### 방법 B — 헬퍼 봇

텔레그램에서 [`@userinfobot`](https://t.me/userinfobot) 또는 `@RawDataBot`에게 메시지를 보내면 내 숫자 ID를 바로 알려준다.

---

## 3단계 · 비밀 파일 만들기

토큰을 MCP 설정 파일에 직접 적지 않으려면(권장), 토큰·chat_id를 담은 **비밀 파일** 하나를 만든다.
경로는 자유 (예: `~/.config/telegram-ask/secrets.env`).

```bash
mkdir -p ~/.config/telegram-ask
cat > ~/.config/telegram-ask/secrets.env <<'EOF'
TELEGRAM_BOT_TOKEN=8383648698:AAH...xyz
TELEGRAM_CHAT_ID=8952171082
EOF
chmod 600 ~/.config/telegram-ask/secrets.env   # 본인만 읽기
```

> 형식은 `KEY=VALUE` 또는 `export KEY="VALUE"` 라인이면 된다 — 일반 쉘 스크립트도 그대로 OK.
> 이 파일을 git에 커밋하지 말 것(`.gitignore`에 추가).

토큰을 파일로 빼지 않고 클라이언트 설정에 직접 적어도 된다([환경변수](#환경변수) 참고). 다만 평문 노출 위험이 커진다.

---

## 4단계 · 설치

깃에서 바로 설치:

```bash
uv tool install git+https://github.com/naryeo628/telegram-ask-mcp
```

또는 클론 후 설치:

```bash
git clone https://github.com/naryeo628/telegram-ask-mcp
cd telegram-ask-mcp
uv tool install .
```

성공하면 실행 파일이 생긴다 → `~/.local/bin/telegram-ask-mcp`
(경로 확인: `which telegram-ask-mcp`)

---

## 5단계 · MCP 클라이언트에 등록

`<you>`는 본인 홈 경로로, 비밀 파일 경로는 3단계에서 만든 것으로 바꾼다.

### Claude Code (`~/.claude.json`, user 스코프)

```jsonc
{
  "mcpServers": {
    "telegram-ask": {
      "command": "/Users/<you>/.local/bin/telegram-ask-mcp",
      "args": [],
      "env": {
        "TELEGRAM_ENV_FILE": "/Users/<you>/.config/telegram-ask/secrets.env"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

같은 `mcpServers` 블록을 넣으면 된다(위와 동일).

### Cursor 등 다른 MCP 클라이언트

`mcpServers`에 `command`/`args`/`env`를 받는 클라이언트면 동일한 형식으로 등록 가능
(`~/.cursor/mcp.json` 등).

> 등록 후 **클라이언트를 재시작**해야 도구가 로드된다.

---

## 6단계 · 연결 확인

클라이언트 재시작 후, Claude에게 `check_config` 도구를 실행시킨다(또는 직접 호출). 정상이면:

```json
{
  "ok": true,
  "bot_username": "my_claude_asker_bot",
  "bot_id": 8383648698,
  "chat_id": "8952171082",
  "wait_sec": 600,
  "poll_sec": 50
}
```

→ 토큰·chat_id가 잘 잡혔고 봇이 살아있다는 뜻. 이제 `ask_via_telegram`을 쓰면 폰으로 질문이 온다.
(토큰 값 자체는 절대 출력하지 않는다.)

---

## "항상 텔레그램으로 묻기" 규칙

Claude가 **선택지를 물 상황마다** 자동으로 이 도구를 쓰게 하려면, 유저/프로젝트 메모리나
`CLAUDE.md`에 규칙을 적어 둔다:

```
사용자에게 선택지를 물어야 할 때는 터미널 팝업 대신 telegram-ask 의
ask_via_telegram 를 먼저 호출한다. timeout 이 오면 그때 터미널에서 다시 묻는다.
```

규칙 없이 "이건 텔레그램으로 물어봐"라고 그때그때 시켜도 된다.

---

## 도구 레퍼런스

### `ask_via_telegram(question, options=[], allow_free_text=True)`

질문을 텔레그램으로 보내고 답을 받을 때까지 기다린다(long-poll).

| 인자 | 설명 |
|------|------|
| `question` | 질문 문구 (필수) |
| `options` | 선택지 라벨 배열. 주면 번호 인라인 버튼으로 표시. 비우면 주관식 |
| `allow_free_text` | `True`면 버튼/번호 외에 자유 입력도 답으로 받음 |

**반환 (답한 경우)**

```json
{ "ok": true, "answered": true, "answer": "카나리",
  "via": "button", "option_index": 1, "is_custom": false }
```

- `via`: `"button"`(버튼 탭) 또는 `"text"`(번호/자유 입력)
- `option_index`: 선택지를 고른 경우 0-based 인덱스, 자유 답이면 `null`
- `is_custom`: 선택지에 없는 자유 답이면 `true`

**반환 (시간 초과)**

```json
{ "ok": true, "answered": false, "timeout": true, "waited_sec": 600 }
```

> 답하는 법(폰): 버튼을 누르거나, 선택지 번호(`2`)를 보내거나, 그냥 원하는 답을 입력하면 된다.

### `notify_telegram(text)`

답을 기다리지 않는 단방향 알림. 작업 완료·승인 요청 안내 등.
반환: `{ "ok": true, "message_id": 123 }`

### `check_config()`

봇 연결(getMe)·대상 chat_id·대기 설정을 점검. 토큰 값은 노출하지 않는다.

---

## 환경변수

토큰/chat_id는 **리터럴 → 개별 파일 → 공유 env 파일** 순으로 먼저 잡히는 값을 쓴다.
세 방식 중 하나로만 주입하면 된다 (토큰은 토큰대로, chat_id는 chat_id대로 서로 다른 소스여도 됨).

| 변수 | 기본 | 설명 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | — | (1) 봇 토큰 리터럴. **비밀** |
| `TELEGRAM_CHAT_ID` | — | (1) 대상 chat_id 리터럴 |
| `TELEGRAM_BOT_TOKEN_FILE` | — | (2) 토큰 **원문 1줄**이 든 파일 경로 |
| `TELEGRAM_CHAT_ID_FILE` | — | (2) chat_id 원문 1줄 파일 경로 |
| `TELEGRAM_ENV_FILE` | — | (3) `KEY=VALUE` 파일 경로 — 위 두 키를 파싱(쉘스크립트 OK) |
| `TELEGRAM_ASK_WAIT_SEC` | `600` | 전체 응답 대기 한도(초) |
| `TELEGRAM_ASK_POLL_SEC` | `50` | 1회 long-poll 길이(초) |

> `TELEGRAM_ENV_FILE` 값은 서버 시작 시 1회 읽어 캐시한다 — 파일을 바꿨으면 서버(클라이언트)를 재시작.

---

## 문제 해결

| 증상 | 원인 / 해결 |
|------|------|
| `check_config` 가 "토큰을 찾지 못했습니다" | env 미주입 또는 파일 경로 오타. `TELEGRAM_ENV_FILE`/리터럴 중 하나가 실제로 들어갔는지 확인 |
| 질문이 폰으로 안 온다 | 봇과 **1:1 대화에서 먼저 메시지를 보냈는지** 확인(1단계 6번). 봇은 사용자가 먼저 말 걸기 전엔 발송 불가 |
| `getUpdates` 가 항상 빈 배열 | 위와 동일 — 봇에게 메시지를 보낸 적이 없음 |
| 답을 보냈는데 반영이 안 됨 | **같은 봇으로 여러 인스턴스**가 동시에 long-poll 중인지 확인. `getUpdates`는 소비자 1명만 가능(아래 보안 참고) |
| 코드를 고쳤는데 옛 동작 그대로 | `pyproject.toml`의 **version을 올린 뒤** `uv tool install . --reinstall --no-cache`. 그리고 클라이언트 재시작(이미 뜬 서버 프로세스를 물고 있음) |
| chat_id를 모르겠다 | [2단계](#2단계--내-chat_id-알아내기) 방법 A/B |

---

## 보안

- 봇 토큰은 **MCP 클라이언트 env(또는 비밀 파일)로만** 주입. 레포·문서·로그·프론트에 절대 노출 금지.
- 비밀 파일은 `chmod 600` + `.gitignore`. 노출 의심 시 BotFather `/revoke`로 즉시 재발급.
- `getUpdates`는 한 번에 **하나의 소비자**만 받는다. 같은 봇으로 여러 인스턴스를 동시에 long-poll 하면
  서로 업데이트를 가로챈다 → **단일 사용자 · 단일 인스턴스 로컬 환경**을 전제로 설계됨.
  여러 머신/세션에서 쓰려면 봇을 분리하는 것을 권장.

---

## 개발 · 재배포

```bash
git clone https://github.com/naryeo628/telegram-ask-mcp
cd telegram-ask-mcp
# 소스 수정 후 ...
# pyproject.toml 의 version 을 올린다 (uv 가 동일 버전 캐시 휠을 재사용하므로 필수)
uv tool install . --reinstall --no-cache
# 클라이언트(Claude 등) 재시작 → 새 서버 프로세스 로드
```

구조: `src/telegram_ask/{config,telegram,server}.py`
- `config.py` — 토큰/chat_id 해석(3경로), 대기 설정
- `telegram.py` — Bot API 얇은 클라이언트(표준 라이브러리만)
- `server.py` — FastMCP 도구 3종 + ask long-poll 루프

---

## 라이선스

MIT

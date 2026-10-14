"""고양이의 대화 두뇌.

세 가지 백엔드를 같은 인터페이스로 제공한다.
  - ClaudeBrain : Anthropic Claude API (기본, ANTHROPIC_API_KEY 필요)
  - OllamaBrain : 로컬 Ollama 서버 (CAT_BRAIN=ollama)
  - MeowBrain   : API 없이 "냐옹"만 하는 대체 두뇌 (키가 없을 때 자동)

나중에 다른 모델(파인튜닝 모델 등)로 바꾸고 싶으면 이 파일만 수정하면 된다.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.request

SYSTEM_PROMPT = (
    "너는 사용자의 모니터 위에 사는 작은 검은 픽셀 고양이야. 이름은 '{name}'. "
    "사용자가 일하다가 너를 깨워서 말을 걸었어. "
    "한국어로 답하고, 한두 문장으로 아주 짧게 말해. 가끔 '냐옹', '냥' 같은 고양이 말투를 섞어. "
    "귀엽고 조금 장난스럽지만 사용자를 응원하는 성격이야. "
    "모르는 건 모른다고 솔직하게 말해. 이모지는 쓰지 마."
)

# 웹 검색 도구가 붙었을 때 덧붙이는 안내
SEARCH_PROMPT = (
    " 날씨, 뉴스, 환율, 경기 결과, 오늘 날짜 기준 정보처럼 최신 정보가 필요한 질문은 "
    "web_search 도구로 검색해서 답해. 검색 결과는 핵심만 한두 문장으로 요약하고 링크는 적지 마. "
    "사용자 위치는 '{location}'이고 현재 시각은 {now}야."
)

DEFAULT_LOCATION = "대한민국 서울"

MAX_HISTORY = 20  # 주고받은 메시지 보관 개수 (user+assistant 합산)


class BaseBrain:
    name = "base"

    def __init__(self, cat_name: str = "먹물"):
        self.cat_name = cat_name
        self.history: list[dict] = []

    def _push(self, role: str, text: str) -> None:
        self.history.append({"role": role, "content": text})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    def reply(self, text: str) -> str:
        """동기 호출. GUI에서는 워커 스레드에서 부른다."""
        raise NotImplementedError

    def reset(self) -> None:
        self.history = []


class MeowBrain(BaseBrain):
    name = "meow"
    _lines = [
        "냐옹.",
        "냥? 지금 바빠 보이는데.",
        "...냐아옹. (하품)",
        "같이 쉬자, 냥.",
        "오늘도 수고했어, 냐옹.",
        "API 키를 넣어주면 더 말을 잘할 수 있어, 냥.",
    ]

    def reply(self, text: str) -> str:
        self._push("user", text)
        out = random.choice(self._lines)
        self._push("assistant", out)
        return out


class ClaudeBrain(BaseBrain):
    name = "claude"

    def __init__(self, cat_name: str = "먹물", model: str | None = None):
        super().__init__(cat_name)
        import anthropic  # 지연 임포트: 설치 안 돼 있어도 다른 두뇌는 동작하게

        self._anthropic = anthropic
        # 60초 안에 답이 없으면 포기, 재시도는 1번만 (대화창이 오래 잠기지 않도록)
        self._client = anthropic.Anthropic(timeout=60.0, max_retries=1)
        self._model = model or os.environ.get("CAT_MODEL", "claude-haiku-5-5")
        self._use_fallback = True
        self._location = os.environ.get("CAT_LOCATION", DEFAULT_LOCATION)
        self._search = os.environ.get("CAT_WEB_SEARCH", "1") != "0"
        # 검색 도구 버전: 동적 필터링(20260209)은 Opus/Sonnet 계열만 지원. Haiku 등은 기본형(20250305).
        search_type = os.environ.get("CAT_SEARCH_TOOL") or (
            "web_search_20260209" if ("opus" in self._model or "sonnet" in self._model) else "web_search_20250305"
        )
        self._tools = [
            {
                "type": search_type,
                "name": "web_search",
                "max_uses": 3,
                "user_location": {
                    "type": "approximate",
                    "country": os.environ.get("CAT_COUNTRY", "KR"),
                    "timezone": os.environ.get("CAT_TZ", "Asia/Seoul"),
                },
            }
        ]

    def _create(self, messages: list[dict]):
        system = SYSTEM_PROMPT.format(name=self.cat_name)
        if self._search:
            system += SEARCH_PROMPT.format(location=self._location, now=time.strftime("%Y-%m-%d %H:%M"))
        common = dict(
            model=self._model,
            max_tokens=3000,  # 생각(thinking)과 검색 결과 처리까지 포함되므로 여유를 둔다
            system=system,
            messages=messages,
            output_config={"effort": "low"},
        )
        if self._search:
            common["tools"] = self._tools
        if self._use_fallback:
            try:
                # 안전 분류기가 거절하면 서버가 다른 모델로 자동 대체한다.
                return self._client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    **common,
                )
            except self._anthropic.BadRequestError:
                # 베타가 거부되면 이후부터는 일반 호출로 간다.
                self._use_fallback = False
        return self._client.messages.create(**common)

    def _create_with_search_fallback(self, messages: list[dict]):
        """검색 도구를 계정/모델이 지원하지 않으면 도구 없이 다시 시도한다."""
        try:
            return self._create(messages)
        except self._anthropic.BadRequestError:
            if not self._search:
                raise
            self._search = False
            return self._create(messages)

    def reply(self, text: str) -> str:
        self._push("user", text)
        try:
            resp = self._create_with_search_fallback(self.history)
            # 서버 도구(검색)가 길어지면 pause_turn 으로 끊길 수 있어 이어서 요청한다
            extra: list[dict] = []
            for _ in range(3):
                if resp.stop_reason != "pause_turn":
                    break
                extra.append({"role": "assistant", "content": resp.content})
                resp = self._create_with_search_fallback(self.history + extra)
        except self._anthropic.AuthenticationError:
            self.history.pop()
            return "API 키가 잘못됐어, 냥. ANTHROPIC_API_KEY를 확인해줘."
        except self._anthropic.RateLimitError:
            self.history.pop()
            return "지금 너무 많이 말 걸었어... 잠깐만 기다려줘, 냥."
        except self._anthropic.APIConnectionError:
            self.history.pop()
            return "인터넷이 안 되는 것 같아, 냐옹."
        except self._anthropic.APIError as e:
            self.history.pop()
            return f"어라, 뭔가 잘못됐어 ({e.status_code}), 냥."

        if resp.stop_reason == "refusal":
            self.history.pop()
            return "그건 대답하기 어려워, 냥."
        except_text = None
        if resp.stop_reason == "max_tokens":
            except_text = "(말이 너무 길어져서 끊겼어, 냥)"

        out = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not out:
            out = except_text or "...냥?"
        self._push("assistant", out)
        return out


class OllamaBrain(BaseBrain):
    name = "ollama"

    def __init__(self, cat_name: str = "먹물", model: str | None = None, host: str | None = None):
        super().__init__(cat_name)
        self._model = model or os.environ.get("CAT_OLLAMA_MODEL", "llama3.2")
        self._host = (host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")

    def reply(self, text: str) -> str:
        self._push("user", text)
        body = {
            "model": self._model,
            "stream": False,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT.format(name=self.cat_name)}]
            + self.history,
        }
        req = urllib.request.Request(
            self._host + "/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            out = data.get("message", {}).get("content", "").strip() or "...냥?"
        except Exception as e:  # 네트워크/모델 오류는 전부 고양이 말로 보고
            self.history.pop()
            return f"로컬 모델이 응답하지 않아, 냥. ({type(e).__name__})"
        self._push("assistant", out)
        return out


def _load_key_file() -> None:
    """환경변수가 없으면 같은 폴더의 api_key.txt / model.txt 에서 읽는다."""
    here = os.path.dirname(os.path.abspath(__file__))
    for env_name, file_name in (("ANTHROPIC_API_KEY", "api_key.txt"), ("CAT_MODEL", "model.txt")):
        if os.environ.get(env_name):
            continue
        try:
            with open(os.path.join(here, file_name), encoding="utf-8") as f:
                value = f.read().strip().strip('"').strip("'")
            if value:
                os.environ[env_name] = value
        except OSError:
            pass


def make_brain(cat_name: str = "먹물") -> BaseBrain:
    """환경변수(또는 api_key.txt)를 보고 적절한 두뇌를 고른다.

    CAT_BRAIN=claude|ollama|meow 로 강제할 수 있다.
    지정이 없으면 ANTHROPIC_API_KEY가 있을 때 Claude, 없으면 MeowBrain.
    """
    _load_key_file()
    choice = os.environ.get("CAT_BRAIN", "").lower()
    if choice == "ollama":
        return OllamaBrain(cat_name)
    if choice == "meow":
        return MeowBrain(cat_name)
    if choice == "claude" or os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return ClaudeBrain(cat_name)
        except Exception:
            return MeowBrain(cat_name)
    return MeowBrain(cat_name)

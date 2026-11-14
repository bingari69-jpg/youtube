"""반려묘 성장: 아기 -> 어린이 -> 청소년 -> 어른.

친밀도(XP)는 교감으로 쌓이고, 단계는 친밀도와 함께한 날짜를 둘 다 만족해야 오른다.
growth.json 에 저장한다.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "growth.json")

# (이름, 필요 친밀도, 필요 일수, 크기 배율, 말투)
STAGES = [
    ("아기 고양이", 0, 0, 0.62, "baby"),
    ("어린 고양이", 120, 3, 0.80, "kid"),
    ("청소년 고양이", 400, 10, 0.92, "teen"),
    ("어른 고양이", 1000, 30, 1.00, "adult"),
]

XP = {
    "daily": 15,      # 하루 첫 만남
    "chat": 2,        # 대화 한 번
    "pet": 4,         # 쓰다듬기 (1분에 한 번만 인정)
    "catch": 3,       # 쥐 한 마리
    "memo": 2,        # 메모/일정 사용
    "wake": 1,        # 깨우기
}


class Growth:
    def __init__(self):
        self.xp = 0
        self.adopted = _dt.date.today().isoformat()
        self.stage = 0
        self.last_daily: str | None = None
        self.last_pet = 0.0
        self.pets = 0
        self.chats = 0
        self.catches = 0
        self._load()
        self.touch_daily()

    # ---- 저장 ----
    def _load(self):
        try:
            with open(PATH, encoding="utf-8") as f:
                d = json.load(f)
            self.xp = int(d.get("xp", 0))
            self.adopted = d.get("adopted", self.adopted)
            self.stage = int(d.get("stage", 0))
            self.last_daily = d.get("last_daily")
            self.pets = int(d.get("pets", 0))
            self.chats = int(d.get("chats", 0))
            self.catches = int(d.get("catches", 0))
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "xp": self.xp, "adopted": self.adopted, "stage": self.stage,
                        "last_daily": self.last_daily, "pets": self.pets, "chats": self.chats, "catches": self.catches,
                    },
                    f, ensure_ascii=False, indent=2,
                )
        except OSError:
            pass

    # ---- 상태 ----
    def days_together(self) -> int:
        try:
            return (_dt.date.today() - _dt.date.fromisoformat(self.adopted)).days + 1
        except ValueError:
            return 1

    def stage_name(self) -> str:
        return STAGES[self.stage][0]

    def size_mult(self) -> float:
        return STAGES[self.stage][3]

    def tone(self) -> str:
        return STAGES[self.stage][4]

    def next_requirement(self) -> str | None:
        if self.stage >= len(STAGES) - 1:
            return None
        _, need_xp, need_days, _, _ = STAGES[self.stage + 1]
        parts = []
        if self.xp < need_xp:
            parts.append(f"친밀도 {need_xp - self.xp} 더")
        if self.days_together() < need_days:
            parts.append(f"{need_days - self.days_together()}일 더")
        return ", ".join(parts) if parts else "곧!"

    # ---- 경험치 ----
    def gain(self, kind: str) -> bool:
        """경험치를 주고, 단계가 올랐으면 True."""
        now = time.time()
        if kind == "pet":
            if now - self.last_pet < 60:
                return False
            self.last_pet = now
            self.pets += 1
        elif kind == "chat":
            self.chats += 1
        elif kind == "catch":
            self.catches += 1
        self.xp += XP.get(kind, 0)
        leveled = self._check_stage()
        self._save()
        return leveled

    def touch_daily(self) -> bool:
        today = _dt.date.today().isoformat()
        if self.last_daily == today:
            return False
        self.last_daily = today
        self.xp += XP["daily"]
        leveled = self._check_stage()
        self._save()
        return leveled

    def _check_stage(self) -> bool:
        new = self.stage
        days = self.days_together()
        for i, (_, need_xp, need_days, _, _) in enumerate(STAGES):
            if self.xp >= need_xp and days >= need_days:
                new = i
        if new > self.stage:
            self.stage = new
            return True
        return False

    def summary(self) -> str:
        nxt = self.next_requirement()
        return (
            f"{self.stage_name()} · 함께한 지 {self.days_together()}일 · 친밀도 {self.xp}\n"
            f"쓰다듬 {self.pets}번 · 대화 {self.chats}번 · 쥐 {self.catches}마리"
            + (f"\n다음 단계까지: {nxt}" if nxt else "\n다 컸어! 이제 어른이다냥.")
        )


def style(text: str, tone: str) -> str:
    """단계별 말투. 아기는 혀 짧은 소리, 어린이는 신남, 어른은 그대로."""
    if tone == "baby":
        text = text.replace("냐옹", "미야옹").replace("냥!", "냐앙!").replace("냥.", "냐앙.").replace("냥?", "냐앙?").replace(", 냥", ", 냐앙")
        return text
    if tone == "kid":
        return text.replace("냐옹", "냐옹!").replace("냥.", "냥!")
    return text

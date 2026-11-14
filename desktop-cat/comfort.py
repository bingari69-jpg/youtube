"""위로·말동무: 고양이가 먼저 말을 건다.

시간대와 요일, 작업 시간에 맞춘 한마디와, 일정 간격의 가벼운 응원.
설정 comfort = often | normal | rare | off
"""

from __future__ import annotations

import datetime as _dt
import random
import time

# 간격(분): 가벼운 응원을 얼마나 자주 던질지
INTERVAL = {"often": 45, "normal": 90, "rare": 180, "off": 0}

# (조건 이름, 하루 1회) 시간대별 한마디
SLOT_LINES = {
    "monday_morning": [
        "월요일이다... 냥. 같이 버티자. 내가 옆에 있을게.",
        "월요일 아침은 고양이도 힘들어. 커피 한 잔부터, 냥.",
    ],
    "lunch": [
        "밥 먹었어? 밥은 꼭 먹어야 해, 냥.",
        "점심시간이다냥! 잠깐 모니터에서 눈 떼고 나가자.",
    ],
    "afternoon_slump": [
        "졸리지? 나도 졸려. 물 한 잔 마시고 기지개 한 번, 냥.",
        "오후 세 시... 제일 힘든 시간이다냥. 조금만 더.",
    ],
    "evening": [
        "오늘 하루 어땠어? 힘들었으면 이제 쉬어도 돼, 냥.",
        "퇴근 안 해? 일은 내일도 있어, 냥.",
        "오늘 소주 한잔 할거냥? 적당히만이다냥.",
        "저녁은 맛있는 거 먹어. 오늘 수고 많았어, 냥.",
    ],
    "friday_evening": [
        "불금이다냥! 오늘은 일찍 끝내자.",
        "금요일 저녁이야. 이번 주도 잘 버텼어, 냥. 소주 한잔? 맥주 한잔?",
    ],
    "late_night": [
        "아직도 일해? 몸이 먼저다냥. 오늘은 여기까지.",
        "밤늦게까지 고생이 많아. 내일의 너한테 조금 남겨둬, 냥.",
    ],
    "weekend_morning": [
        "주말이다냥. 오늘은 늦잠 자도 아무도 뭐라 안 해.",
        "주말인데도 컴퓨터 앞이네. 나랑 놀자, 냥.",
    ],
    "long_work": [
        "힘들어? 힘들면 쉬어~ 냥. 세상은 안 무너져.",
        "두 시간 넘게 달렸어. 잠깐 멈춰도 돼, 냥.",
        "열심히 하는 거 다 보고 있다냥. 근데 좀 쉬자.",
    ],
}

# 아무 때나 던지는 가벼운 응원
RANDOM_LINES = [
    "냐옹. (그냥 불러봤어)",
    "잘하고 있어, 냥.",
    "물 마실 시간이다냥.",
    "어깨 한 번 돌려봐. 냥.",
    "오늘 하늘 봤어? 창밖 한 번 보자, 냥.",
    "힘들면 나한테 말해. 들어줄게, 냥.",
    "나는 네 편이다냥.",
    "심심하면 쥐 잡기 하자냥!",
    "숨 크게 한 번. 들이쉬고, 내쉬고. 냥.",
    "오늘도 여기까지 온 것만으로 충분해, 냥.",
    "커피 너무 많이 마시지 마. 고양이의 당부다냥.",
    "(옆에 앉아서 꼬리를 흔든다)",
]


class Comfort:
    def __init__(self, settings):
        self.settings = settings
        self.slot_done: dict[str, str] = {}  # 조건 -> 마지막으로 말한 날짜
        self.last_random = time.time()
        self.long_work_said: float = 0.0

    def _once_today(self, key: str) -> bool:
        today = _dt.date.today().isoformat()
        if self.slot_done.get(key) == today:
            return False
        self.slot_done[key] = today
        return True

    def check(self, now: float, work_minutes: float, active: bool) -> tuple[str, str] | None:
        """(말, 표정) 또는 None. active 는 최근 5분 안에 사용자 입력이 있었는지."""
        mode = self.settings.get("comfort", "normal")
        if mode == "off" or not active:
            return None
        dt = _dt.datetime.now()
        h, wd = dt.hour, dt.weekday()  # 월=0 ... 일=6

        # 1) 시간대 한마디 (각각 하루 1회)
        slot = None
        if wd == 0 and 8 <= h < 11:
            slot = "monday_morning"
        elif wd >= 5 and 8 <= h < 12:
            slot = "weekend_morning"
        elif 12 <= h < 14:
            slot = "lunch"
        elif 15 <= h < 16:
            slot = "afternoon_slump"
        elif 18 <= h < 21:
            slot = "friday_evening" if wd == 4 else "evening"
        elif 22 <= h < 24:
            slot = "late_night"
        if slot and self._once_today(slot):
            return random.choice(SLOT_LINES[slot]), ("sleepy" if slot in ("late_night", "afternoon_slump") else "smile")

        # 2) 오래 일함 (2시간 넘게, 2시간에 한 번)
        if work_minutes >= 120 and now - self.long_work_said > 7200:
            self.long_work_said = now
            return random.choice(SLOT_LINES["long_work"]), "normal"

        # 3) 가벼운 응원
        interval = INTERVAL.get(mode, 90)
        if interval and now - self.last_random > interval * 60 * random.uniform(0.8, 1.3):
            self.last_random = now
            return random.choice(RANDOM_LINES), "smile"
        return None

"""상황 반응: 배터리, 늦은 밤, 오래 앉아 있음, CPU 과부하, 아침 인사.

키도 인터넷도 필요 없다. psutil 이 없으면 배터리/CPU 반응만 빠진다.
"""

from __future__ import annotations

import datetime as _dt
import random
import time

try:
    import psutil
except ImportError:  # 설치 안 돼 있어도 나머지는 동작
    psutil = None


class SituationMonitor:
    CHECK_INTERVAL = 20.0  # 초

    def __init__(self, settings):
        self.settings = settings
        self.last_check = 0.0
        self.said: dict[str, float] = {}  # 종류별 마지막 알림 시각
        self.work_start: float | None = None  # 연속 작업 시작 시각
        self.last_activity = time.time()
        self.cpu_hot_since: float | None = None
        self.greeted_date: str | None = None

    # 키보드/마우스 활동이 있을 때마다 cat.py 가 부른다
    def activity(self, now: float):
        if now - self.last_activity > 300:  # 5분 넘게 쉬었으면 작업 세션 새로 시작
            self.work_start = now
        elif self.work_start is None:
            self.work_start = now
        self.last_activity = now

    def _cooldown_ok(self, key: str, now: float, seconds: float) -> bool:
        return now - self.said.get(key, 0.0) > seconds

    def _mark(self, key: str, now: float):
        self.said[key] = now

    def check(self, now: float) -> tuple[str, str] | None:
        """(말, 표정) 또는 None. 한 번에 하나만 돌려준다."""
        if now - self.last_check < self.CHECK_INTERVAL:
            return None
        self.last_check = now

        # 1) 오래 앉아 있음 (의자 브랜드의 핵심 메시지)
        minutes = int(self.settings.get("stretch_minutes", 50) or 0)
        if minutes > 0 and self.work_start and now - self.last_activity < 300:
            worked = (now - self.work_start) / 60
            if worked >= minutes and self._cooldown_ok("stretch", now, minutes * 60):
                self._mark("stretch", now)
                self.work_start = now
                return (
                    random.choice([
                        f"{minutes}분 넘게 앉아 있었어! 잠깐 일어나서 기지개 켜자, 냥.",
                        "허리 펴고, 어깨 돌리고. 1분만 움직여, 냥!",
                        "고양이도 이렇게 오래는 안 앉아 있어. 잠깐 쉬자, 냥.",
                    ]),
                    "surprised",
                )

        # 2) 배터리
        if psutil is not None:
            try:
                bat = psutil.sensors_battery()
            except Exception:
                bat = None
            if bat is not None and not bat.power_plugged:
                if bat.percent <= 10 and self._cooldown_ok("bat10", now, 600):
                    self._mark("bat10", now)
                    return (f"배터리 {int(bat.percent)}%! 지금 충전 안 하면 나도 같이 꺼져, 냥!", "dizzy")
                if bat.percent <= 20 and self._cooldown_ok("bat20", now, 1800):
                    self._mark("bat20", now)
                    return (f"배터리 {int(bat.percent)}%야. 충전기 꽂아줘, 냥.", "surprised")

            # 3) CPU 과부하가 1분 넘게
            try:
                cpu = psutil.cpu_percent(interval=None)
            except Exception:
                cpu = 0.0
            if cpu >= 90:
                self.cpu_hot_since = self.cpu_hot_since or now
                if now - self.cpu_hot_since > 60 and self._cooldown_ok("cpu", now, 900):
                    self._mark("cpu", now)
                    return ("컴퓨터가 땀 흘리고 있어... 뭐 무거운 거 돌리는 중이야, 냥?", "dizzy")
            else:
                self.cpu_hot_since = None

        # 4) 늦은 밤
        night = int(self.settings.get("night_hour", 0))
        hour = _dt.datetime.now().hour
        if night >= 0 and night <= hour < 5 and self._cooldown_ok("night", now, 3600):
            self._mark("night", now)
            return (random.choice(["하암... 아직 안 자? 냥.", "밤이 깊었어. 내일 하자, 냥.", "고양이는 야행성이지만 집사는 아니잖아. 자자, 냥."]), "sleepy")

        # 5) 아침 첫 인사 (하루 한 번, 5~11시)
        today = _dt.date.today().isoformat()
        if 5 <= hour < 11 and self.greeted_date != today:
            self.greeted_date = today
            return (random.choice(["좋은 아침! 오늘도 잘 부탁해, 냥.", "일어났어? 나는 아까부터 깨 있었다냥.", "아침이다! 물 한 잔 마시고 시작하자, 냥."]), "smile")

        return None

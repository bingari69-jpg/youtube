"""사용자 설정 저장 (settings.json). 키나 비밀은 여기 넣지 않는다."""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "settings.json")

DEFAULTS = {
    "name": "먹물",
    "scale": 6,
    "chase": True,
    "jump": True,
    "stretch_minutes": 50,      # 연속 작업 알림 간격 (0이면 끔)
    "night_hour": 0,            # 이 시각 이후면 "안 자?" (0~5 사이 권장, -1이면 끔)
    "notices": True,            # 브랜드 공지 표시
    "notice_url": "",           # 비어 있으면 notices.json 파일만 읽음
    "location": "서울",
    "auto_sleep_sec": 180,
    "comfort": "normal",        # 말 걸기 빈도: often | normal | rare | off
    "music_volume": 40,
    "music_shuffle": True,
    "music_last": "",
}


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in DEFAULTS:
                        self[k] = v
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def set(self, key: str, value):
        self[key] = value
        self.save()

"""브랜드 소식 알림. 서버 없이 동작한다.

  - notices.json (같은 폴더): 배포판에 포함되는 공지 목록
  - settings['notice_url']: 비어 있지 않으면 거기서 같은 형식의 JSON을 하루 한 번 내려받는다.
    (정적 파일 호스팅이면 충분: GitHub Pages, 회사 홈페이지의 .json 등)

형식:
  [{"id": "2026-11-launch", "text": "말풍선에 보여줄 문장", "from": "2026-11-01", "until": "2026-11-30"}]

같은 id 는 한 번만 보여주고, 하루에 최대 1건만 보여준다. 본 id 는 seen_notices.json 에 기록한다.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "notices.json")
SEEN = os.path.join(HERE, "seen_notices.json")


class NoticeBoard:
    def __init__(self, settings):
        self.settings = settings
        self.items: list[dict] = []
        self.seen: dict[str, str] = {}
        self.last_shown_day: str | None = None
        self.last_fetch = 0.0
        self._lock = threading.Lock()
        self._load_seen()
        self._load_local()
        self.last_shown_day = self.seen.get("__last_day__")

    # ---- 저장소 ----
    def _load_seen(self):
        try:
            with open(SEEN, encoding="utf-8") as f:
                self.seen = json.load(f)
        except (OSError, ValueError):
            self.seen = {}

    def _save_seen(self):
        try:
            with open(SEEN, "w", encoding="utf-8") as f:
                json.dump(self.seen, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_local(self):
        try:
            with open(LOCAL, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.items = [d for d in data if isinstance(d, dict) and d.get("id") and d.get("text")]
        except (OSError, ValueError):
            self.items = []

    def _fetch_remote(self):
        url = (self.settings.get("notice_url") or "").strip()
        if not url.startswith("https://"):
            return
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "desktop-cat/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, list):
                remote = [d for d in data if isinstance(d, dict) and d.get("id") and d.get("text")]
                with self._lock:
                    known = {d["id"] for d in self.items}
                    self.items += [d for d in remote if d["id"] not in known]
        except Exception:
            pass

    # ---- 호출 ----
    @staticmethod
    def _active(item: dict, today: _dt.date) -> bool:
        try:
            if item.get("from") and today < _dt.date.fromisoformat(item["from"]):
                return False
            if item.get("until") and today > _dt.date.fromisoformat(item["until"]):
                return False
        except ValueError:
            return False
        return True

    def next(self, now: float) -> str | None:
        """지금 보여줄 공지 한 건. 없으면 None."""
        if not self.settings.get("notices", True):
            return None
        if now - self.last_fetch > 24 * 3600:
            self.last_fetch = now
            threading.Thread(target=self._fetch_remote, daemon=True).start()
        today = _dt.date.today()
        if self.last_shown_day == today.isoformat():
            return None
        with self._lock:
            for item in self.items:
                if item["id"] in self.seen or not self._active(item, today):
                    continue
                self.seen[item["id"]] = today.isoformat()
                self.seen["__last_day__"] = today.isoformat()
                self.last_shown_day = today.isoformat()
                self._save_seen()
                return str(item["text"])[:300]
        return None

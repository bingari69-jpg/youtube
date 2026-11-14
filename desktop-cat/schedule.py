"""일정(예약) 기능: 한국어 날짜/시간을 알아듣고 schedule.json 에 저장, 때가 되면 고양이가 알려준다.

말하기 예
  "다음주 화요일 3시 치과 기억해줘"     -> 저장
  "내일 오후 2시 회의"                   -> 저장
  "11월 20일 저녁 7시 동창회 예약"       -> 저장
  "모레 10시 반 면접 알려줘"             -> 저장
  "다음주 일정 뭐 있어?" / "오늘 일정" / "이번주 일정" / "일정 보여줘"  -> 조회
  "일정 3 삭제" / "일정 다 지워"          -> 삭제

알림
  - 당일 첫 활동 때 오늘 일정 브리핑
  - 전날 저녁(18~21시) 내일 일정 예고
  - 10분 전, 정각
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "schedule.json")

WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
SAVE_WORDS = ("기억", "일정", "예약", "약속", "알려", "리마인드", "스케줄", "잊지", "등록", "추가")
QUERY_WORDS = ("일정", "스케줄", "약속", "예약")
QUERY_VERBS = ("뭐", "있어", "있나", "보여", "알려", "확인", "뭐야", "뭐지", "목록", "리스트", "어때")


# ---------------------------------------------------------------- 저장소
def load() -> list[dict]:
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(items: list[dict]) -> None:
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def add(when: _dt.datetime, text: str, has_time: bool) -> dict:
    items = load()
    item = {
        "id": uuid.uuid4().hex[:8],
        "when": when.strftime("%Y-%m-%dT%H:%M"),
        "text": text,
        "has_time": has_time,
        "reminded": [],
    }
    items.append(item)
    items.sort(key=lambda x: x["when"])
    save(items)
    return item


def upcoming(days: int = 30) -> list[dict]:
    now = _dt.datetime.now()
    end = now + _dt.timedelta(days=days)
    out = []
    for it in load():
        w = _parse_iso(it["when"])
        if w and now - _dt.timedelta(hours=12) <= w <= end:
            out.append(it)
    return out


def remove(index_or_id) -> dict | None:
    items = load()
    target = None
    if isinstance(index_or_id, int):
        up = upcoming(365)
        if 1 <= index_or_id <= len(up):
            target = up[index_or_id - 1]
    else:
        target = next((i for i in items if i["id"] == index_or_id), None)
    if not target:
        return None
    items = [i for i in items if i["id"] != target["id"]]
    save(items)
    return target


def clear_all() -> int:
    n = len(load())
    save([])
    return n


def _parse_iso(s: str) -> _dt.datetime | None:
    try:
        return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


# ---------------------------------------------------------------- 한국어 날짜/시간 해석
_TIME_RE = re.compile(
    r"(?P<ampm>오전|오후|아침|저녁|밤|새벽|낮)?\s*"
    r"(?:(?P<h>\d{1,2})\s*시\s*(?:(?P<m>\d{1,2})\s*분|(?P<half>반))?|(?P<hh>\d{1,2}):(?P<mm>\d{2}))"
)
_DATE_MD_RE = re.compile(r"(?P<mon>\d{1,2})\s*(?:월|/)\s*(?P<day>\d{1,2})\s*일?")
_DATE_D_RE = re.compile(r"(?<![\d월/])(?P<day>\d{1,2})\s*일(?!\s*(?:뒤|후|동안|간))")
_REL_DAYS_RE = re.compile(r"(?P<n>\d+)\s*일\s*(?:뒤|후)")
_WEEK_RE = re.compile(r"(?P<week>이번\s*주|다음\s*주|다다음\s*주|담주|다담주)?\s*(?P<wd>[월화수목금토일])(?:요일|욜)")


def parse_datetime(text: str, now: _dt.datetime | None = None) -> tuple[_dt.datetime, bool, str] | None:
    """(일시, 시간이 명시됐는지, 날짜/시간 표현을 제거한 나머지 문장) 또는 None"""
    now = now or _dt.datetime.now()
    t = text
    date: _dt.date | None = None
    consumed: list[tuple[int, int]] = []

    # --- 날짜 ---
    m = _REL_DAYS_RE.search(t)
    if m:
        date = (now + _dt.timedelta(days=int(m.group("n")))).date()
        consumed.append(m.span())
    if date is None:
        for word, delta in (("글피", 3), ("모레", 2), ("내일", 1), ("오늘", 0)):
            i = t.find(word)
            if i >= 0:
                date = (now + _dt.timedelta(days=delta)).date()
                consumed.append((i, i + len(word)))
                break
    if date is None:
        m = _WEEK_RE.search(t)
        if m:
            wd = WEEKDAYS[m.group("wd")]
            week = (m.group("week") or "").replace(" ", "")
            monday = now.date() - _dt.timedelta(days=now.weekday())
            if week in ("다음주", "담주"):
                base = monday + _dt.timedelta(days=7)
            elif week in ("다다음주", "다담주"):
                base = monday + _dt.timedelta(days=14)
            elif week == "이번주":
                base = monday
            else:  # 요일만 말하면 다음 번 그 요일 (오늘이면 오늘)
                base = None
            if base is not None:
                date = base + _dt.timedelta(days=wd)
            else:
                ahead = (wd - now.weekday()) % 7
                date = now.date() + _dt.timedelta(days=ahead)
            consumed.append(m.span())
    if date is None:
        m = _DATE_MD_RE.search(t)
        if m:
            mon, day = int(m.group("mon")), int(m.group("day"))
            year = now.year
            try:
                cand = _dt.date(year, mon, day)
                if cand < now.date() - _dt.timedelta(days=1):
                    cand = _dt.date(year + 1, mon, day)
                date = cand
                consumed.append(m.span())
            except ValueError:
                pass
    if date is None:
        m = _DATE_D_RE.search(t)
        if m:
            day = int(m.group("day"))
            try:
                cand = _dt.date(now.year, now.month, day)
                if cand < now.date():
                    nm = now.month % 12 + 1
                    ny = now.year + (1 if nm == 1 else 0)
                    cand = _dt.date(ny, nm, day)
                date = cand
                consumed.append(m.span())
            except ValueError:
                pass

    # --- 시간 ---
    hour, minute, has_time = 9, 0, False
    m = _TIME_RE.search(t)
    if m:
        has_time = True
        if m.group("hh"):
            hour, minute = int(m.group("hh")), int(m.group("mm"))
        else:
            hour = int(m.group("h"))
            minute = 30 if m.group("half") else int(m.group("m") or 0)
        ampm = m.group("ampm") or ""
        if ampm in ("오후", "저녁", "밤") and hour < 12:
            hour += 12
        elif ampm == "새벽" and hour == 12:
            hour = 0
        elif not ampm and 1 <= hour <= 6:
            hour += 12  # 1~6시라고만 하면 오후로 본다
        consumed.append(m.span())
    else:
        for word, h in (("아침", 9), ("점심", 12), ("저녁", 19), ("밤", 21), ("새벽", 6), ("오후", 14), ("오전", 10)):
            i = t.find(word)
            if i >= 0:
                hour, has_time = h, True
                consumed.append((i, i + len(word)))
                break

    if date is None:
        if not has_time:
            return None
        date = now.date()
        if _dt.datetime.combine(date, _dt.time(hour, minute)) < now:
            date += _dt.timedelta(days=1)

    # --- 나머지 문장 ---
    chars = list(t)
    for a, b in consumed:
        for i in range(a, b):
            chars[i] = " "
    rest = "".join(chars)
    rest = re.sub(
        r"(기억해\s*줘|기억해줘|기억해|알려\s*줘|알려줘|리마인드|일정\s*(추가|등록)?|예약(해\s*줘|해줘)?|스케줄|잊지\s*마|등록해\s*줘|추가해\s*줘|해\s*줘|해줘|있어|이야|야|에|좀|나|내|줘)",
        " ",
        rest,
    )
    rest = re.sub(r"\s+", " ", rest).strip(" ,.!~?")
    try:
        when = _dt.datetime.combine(date, _dt.time(hour, minute))
    except ValueError:
        return None
    return when, has_time, rest


# ---------------------------------------------------------------- 명령 해석
def parse_command(text: str) -> tuple[str, object] | None:
    """('add', (when, has_time, text)) / ('query', (start_date, end_date, label)) / ('remove', int) / ('clear', None) / None"""
    t = text.strip()
    compact = t.replace(" ", "")

    if any(w in compact for w in QUERY_WORDS):
        if re.search(r"(다|전부|모두|모든).*(지워|삭제|지우)", compact):
            return "clear", None
        m = re.search(r"(\d+)\s*(?:번)?\s*(?:지워|삭제|지우)", t) or re.search(r"(?:지워|삭제|지우)\s*(\d+)", t)
        if m:
            return "remove", int(m.group(1))
        if any(v in compact for v in QUERY_VERBS) and not any(k in compact for k in ("기억", "예약해", "등록", "추가")):
            today = _dt.date.today()
            monday = today - _dt.timedelta(days=today.weekday())
            if "다음주" in compact or "담주" in compact:
                s = monday + _dt.timedelta(days=7)
                return "query", (s, s + _dt.timedelta(days=6), "다음주")
            if "이번주" in compact:
                return "query", (monday, monday + _dt.timedelta(days=6), "이번주")
            if "내일" in compact:
                d = today + _dt.timedelta(days=1)
                return "query", (d, d, "내일")
            if "오늘" in compact:
                return "query", (today, today, "오늘")
            if "이번달" in compact or "이번 달" in t:
                end = (today.replace(day=28) + _dt.timedelta(days=4)).replace(day=1) - _dt.timedelta(days=1)
                return "query", (today, end, "이번 달")
            return "query", (today, today + _dt.timedelta(days=30), "앞으로 한 달")

    has_save = any(w in compact for w in SAVE_WORDS)
    question = any(q in compact for q in ("뭐해", "뭐하", "할까", "어때", "되나", "될까", "?", "있나", "없나"))
    if has_save or not question:
        parsed = parse_datetime(t)
        if parsed and not has_save:
            # '기억해' 없이도 "내일 오후 2시 회의"처럼 날짜/시간+내용이면 등록. 단, 날짜나 시간 표현이 실제로 있어야 한다.
            when, has_time, rest = parsed
            explicit_date = bool(_REL_DAYS_RE.search(t) or _WEEK_RE.search(t) or _DATE_MD_RE.search(t) or _DATE_D_RE.search(t)
                                 or any(w in t for w in ("오늘", "내일", "모레", "글피")))
            if not (explicit_date and has_time and rest and rest not in ("일정", "약속", "스케줄", "예약")):
                parsed = None
        if parsed:
            when, has_time, rest = parsed
            if not rest or rest in ("일정", "약속", "스케줄", "예약"):
                # 내용이 없으면 등록이 아니라 그 날짜의 일정 조회로 본다
                d = when.date()
                return "query", (d, d, f"{d.month}/{d.day}")
            return "add", (when, has_time, rest)
        if "일정" in compact and any(k in compact for k in ("기억", "얘기", "말해", "알려")):
            return "help", None
    return None


# ---------------------------------------------------------------- 표시
def fmt(item: dict, with_date: bool = True) -> str:
    w = _parse_iso(item["when"])
    if not w:
        return item.get("text", "")
    days = "월화수목금토일"
    d = f"{w.month}/{w.day}({days[w.weekday()]}) " if with_date else ""
    tm = w.strftime("%H:%M ") if item.get("has_time") else ""
    return f"{d}{tm}{item['text']}"


def items_between(start: _dt.date, end: _dt.date) -> list[dict]:
    out = []
    for it in load():
        w = _parse_iso(it["when"])
        if w and start <= w.date() <= end:
            out.append(it)
    return out


# ---------------------------------------------------------------- 알림
class Reminder:
    def __init__(self):
        self.briefed_day: str | None = None
        self.previewed_day: str | None = None
        self.last_check = 0.0

    def check(self, now_ts: float, active: bool) -> str | None:
        if now_ts - self.last_check < 20:
            return None
        self.last_check = now_ts
        now = _dt.datetime.now()
        items = load()
        changed = False

        # 10분 전 / 정각
        for it in items:
            w = _parse_iso(it["when"])
            if not w or not it.get("has_time"):
                continue
            delta = (w - now).total_seconds()
            rem = it.setdefault("reminded", [])
            if 0 < delta <= 600 and "10m" not in rem:
                rem.append("10m")
                save(items)
                return f"10분 뒤에 '{it['text']}' 있어, 냥! 준비하자."
            if -120 <= delta <= 0 and "now" not in rem:
                rem.append("now")
                save(items)
                return f"지금이야! '{it['text']}' 시간이다냥!"

        if not active:
            return None
        today = now.date().isoformat()
        # 아침 브리핑 (첫 활동, 6시 이후)
        if self.briefed_day != today and now.hour >= 6:
            self.briefed_day = today
            todays = items_between(now.date(), now.date())
            if todays:
                lines = ", ".join(fmt(i, with_date=False) for i in todays)
                return f"오늘 일정 {len(todays)}개야, 냥: {lines}"
        # 전날 저녁 예고
        if self.previewed_day != today and 18 <= now.hour < 22:
            self.previewed_day = today
            tmr = now.date() + _dt.timedelta(days=1)
            tomorrows = items_between(tmr, tmr)
            if tomorrows:
                lines = ", ".join(fmt(i, with_date=False) for i in tomorrows)
                return f"내일은 {lines}. 미리 알려주는 거다냥."
        # 지난 일정 정리 (3일 지난 것)
        kept = [i for i in items if (_parse_iso(i["when"]) or now) >= now - _dt.timedelta(days=3)]
        if len(kept) != len(items):
            save(kept)
        return None

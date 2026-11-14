"""API 키 없이 쓰는 정보 조회.

  날씨/미세먼지 : Open-Meteo (비상업 무료. 상업 배포 시 유료 플랜 또는 기상청 API로 교체 권장)
  환율          : Frankfurter api.frankfurter.dev (유럽중앙은행 고시, 무료)
  뉴스 헤드라인 : Google 뉴스 RSS
  공휴일        : Nager.Date (무료)

brain.py 가 사용자의 말을 보고 여기서 정보를 가져와 모델에게 참고 자료로 넘기거나,
모델이 없으면 answer_for() 가 바로 문장으로 답한다.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

RATE_WORDS = ("환율", "달러", "엔화", "유로", "위안", "원화", "usd", "jpy", "eur")
NEWS_WORDS = ("뉴스", "헤드라인", "소식", "무슨 일", "오늘 이슈", "이슈")
HOLIDAY_WORDS = ("공휴일", "연휴", "휴일", "빨간날", "빨간 날", "쉬는 날", "쉬는날")
AIR_WORDS = ("미세먼지", "초미세", "공기", "마스크")
WEATHER_WORDS = ("날씨", "기온", "온도", "비 와", "비와", "비 오", "비오", "우산", "더워", "더운", "추워", "추운", "눈 와", "눈와", "눈 오", "미세먼지", "습도", "바람")

# WMO weather code -> 한국어
_WMO = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
    45: "안개", 48: "안개(서리)",
    51: "약한 이슬비", 53: "이슬비", 55: "강한 이슬비",
    56: "어는 이슬비", 57: "강한 어는 이슬비",
    61: "약한 비", 63: "비", 65: "강한 비", 66: "어는 비", 67: "강한 어는 비",
    71: "약한 눈", 73: "눈", 75: "강한 눈", 77: "싸락눈",
    80: "소나기", 81: "강한 소나기", 82: "매우 강한 소나기",
    85: "눈 소나기", 86: "강한 눈 소나기",
    95: "뇌우", 96: "우박 동반 뇌우", 99: "강한 우박 동반 뇌우",
}

_cache: dict[str, tuple[float, str]] = {}
CACHE_SEC = 600  # 같은 위치는 10분간 재사용


def wants_weather(text: str) -> bool:
    t = text.replace(" ", "")
    return any(w.replace(" ", "") in t for w in WEATHER_WORDS)


def _get(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "desktop-cat/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# 한국 주요 도시 좌표 (Open-Meteo 지명 검색이 한글 짧은 이름에 약해서 내장)
KR_CITIES = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4800, 127.2890), "수원": (37.2636, 127.0286),
    "성남": (37.4200, 127.1265), "고양": (37.6584, 126.8320), "용인": (37.2411, 127.1776),
    "창원": (35.2281, 128.6811), "청주": (36.6424, 127.4890), "전주": (35.8242, 127.1480),
    "천안": (36.8151, 127.1139), "안산": (37.3219, 126.8309), "안양": (37.3943, 126.9568),
    "남양주": (37.6360, 127.2165), "화성": (37.1995, 126.8312), "김해": (35.2285, 128.8894),
    "평택": (36.9921, 127.1129), "포항": (36.0190, 129.3435), "제주": (33.4996, 126.5312),
    "강릉": (37.7519, 128.8761), "춘천": (37.8813, 127.7298), "원주": (37.3422, 127.9202),
    "여수": (34.7604, 127.6622), "순천": (34.9507, 127.4872), "목포": (34.8118, 126.3922),
    "경주": (35.8562, 129.2247), "구미": (36.1195, 128.3446), "진주": (35.1800, 128.1076),
    "파주": (37.7600, 126.7800), "김포": (37.6153, 126.7156), "의정부": (37.7381, 127.0337),
    "광명": (37.4786, 126.8644), "부천": (37.5034, 126.7660), "시흥": (37.3800, 126.8029),
    "서귀포": (33.2541, 126.5600), "속초": (38.2070, 128.5918), "동해": (37.5247, 129.1143),
}


def _geocode(place: str) -> tuple[float, float, str] | None:
    """장소 이름 -> (위도, 경도, 표시 이름). 한국 주요 도시는 내장 표, 그 외는 Open-Meteo 지명 검색."""
    raw = place.strip() or "서울"
    name = raw.split()[-1]
    name = re.sub(r"(특별시|광역시|특별자치시|특별자치도|시|도)$", "", name) or name
    if name in KR_CITIES:
        lat, lon = KR_CITIES[name]
        return lat, lon, name
    q = urllib.parse.quote(name)
    data = _get(f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=10&language=ko&format=json")
    results = data.get("results") or []
    if not results:
        return None
    # 한국 결과 우선, 그중 인구가 많은 곳. 인구 정보가 없으면 첫 결과.
    kr = [r for r in results if r.get("country_code") == "KR"] or results
    r = max(kr, key=lambda x: x.get("population") or 0)
    label = r.get("name") or name
    if r.get("admin1") and r["admin1"] != label:
        label = f"{r['admin1']} {label}"
    return float(r["latitude"]), float(r["longitude"]), label


def get_weather(place: str | None = None) -> str | None:
    """사람이 읽을 수 있는 한 줄 요약. 실패하면 None."""
    place = place or os.environ.get("CAT_LOCATION", "서울")
    now = time.time()
    hit = _cache.get(place)
    if hit and now - hit[0] < CACHE_SEC:
        return hit[1]
    try:
        geo = _geocode(place)
        if not geo:
            return None
        lat, lon, label = geo
        tz = urllib.parse.quote(os.environ.get("CAT_TZ", "Asia/Seoul"))
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat:.4f}&longitude={lon:.4f}"
            "&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            f"&timezone={tz}&forecast_days=2"
        )
        d = _get(url)
        cur = d.get("current", {})
        day = d.get("daily", {})
        desc = _WMO.get(int(cur.get("weather_code", -1)), "알 수 없음")
        parts = [
            f"{label} 현재 {desc}, 기온 {cur.get('temperature_2m')}도 (체감 {cur.get('apparent_temperature')}도)",
            f"습도 {cur.get('relative_humidity_2m')}%",
            f"바람 {cur.get('wind_speed_10m')}km/h",
        ]
        if day.get("temperature_2m_max"):
            parts.append(
                f"오늘 최고 {day['temperature_2m_max'][0]}도 / 최저 {day['temperature_2m_min'][0]}도"
                f", 강수확률 {day.get('precipitation_probability_max', [None])[0]}%"
            )
            if len(day["temperature_2m_max"]) > 1:
                tdesc = _WMO.get(int(day.get("weather_code", [0, 0])[1]), "")
                parts.append(
                    f"내일 {tdesc} 최고 {day['temperature_2m_max'][1]}도 / 최저 {day['temperature_2m_min'][1]}도"
                    f", 강수확률 {day.get('precipitation_probability_max', [None, None])[1]}%"
                )
        text = ", ".join(parts) + f" (기준 {cur.get('time', '')}, 출처 Open-Meteo)"
        _cache[place] = (now, text)
        return text
    except Exception:
        return None


def _has(text: str, words) -> bool:
    t = text.replace(" ", "").lower()
    return any(w.replace(" ", "").lower() in t for w in words)


def get_air(place: str | None = None) -> str | None:
    """미세먼지(PM10/PM2.5) 한 줄 요약."""
    place = place or os.environ.get("CAT_LOCATION", "서울")
    key = "air:" + place
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SEC:
        return hit[1]
    try:
        geo = _geocode(place)
        if not geo:
            return None
        lat, lon, label = geo
        d = _get(
            "https://air-quality-api.open-meteo.com/v1/air-quality"
            f"?latitude={lat:.4f}&longitude={lon:.4f}&current=pm10,pm2_5&timezone=auto"
        )
        cur = d.get("current", {})
        pm10, pm25 = cur.get("pm10"), cur.get("pm2_5")

        def grade(v, good, normal, bad):
            if v is None:
                return "?"
            return "좋음" if v <= good else "보통" if v <= normal else "나쁨" if v <= bad else "매우 나쁨"

        text = (
            f"{label} 미세먼지 PM10 {pm10}㎍/㎥ ({grade(pm10, 30, 80, 150)}), "
            f"초미세먼지 PM2.5 {pm25}㎍/㎥ ({grade(pm25, 15, 35, 75)}) (출처 Open-Meteo)"
        )
        _cache[key] = (now, text)
        return text
    except Exception:
        return None


def get_rates(text: str = "") -> str | None:
    """원화 기준 주요 환율."""
    now = time.time()
    hit = _cache.get("rates")
    if hit and now - hit[0] < 3600:
        return hit[1]
    try:
        d = _get("https://api.frankfurter.dev/v1/latest?base=KRW&symbols=USD,JPY,EUR,CNY")
        r = d.get("rates", {})
        parts = []
        for code, name, unit in (("USD", "1달러", 1), ("JPY", "100엔", 100), ("EUR", "1유로", 1), ("CNY", "1위안", 1)):
            v = r.get(code)
            if v:
                parts.append(f"{name} = {unit / v:,.0f}원")
        if not parts:
            return None
        out = "환율 " + ", ".join(parts) + f" (기준일 {d.get('date', '')}, 출처 Frankfurter/ECB)"
        _cache["rates"] = (now, out)
        return out
    except Exception:
        return None


def get_news(count: int = 3) -> str | None:
    """구글 뉴스 한국 헤드라인."""
    now = time.time()
    hit = _cache.get("news")
    if hit and now - hit[0] < 900:
        return hit[1]
    try:
        req = urllib.request.Request(
            "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko", headers={"User-Agent": "desktop-cat/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            root = ET.fromstring(r.read())
        titles = []
        for item in root.iter("item"):
            t = (item.findtext("title") or "").strip()
            if t:
                titles.append(re.sub(r"\s+-\s+[^-]+$", "", t))  # 끝의 ' - 언론사' 제거
            if len(titles) >= count:
                break
        if not titles:
            return None
        out = "지금 헤드라인: " + " / ".join(titles) + " (출처 Google 뉴스)"
        _cache["news"] = (now, out)
        return out
    except Exception:
        return None


def get_holidays() -> str | None:
    """다음 공휴일과 D-day."""
    now = time.time()
    hit = _cache.get("holidays")
    if hit and now - hit[0] < 6 * 3600:
        return hit[1]
    try:
        data = _get("https://date.nager.at/api/v3/NextPublicHolidays/KR")
        today = _dt.date.today()
        items = []
        for h in data[:3]:
            d = _dt.date.fromisoformat(h["date"])
            name = h.get("localName") or h.get("name")
            days = (d - today).days
            when = "오늘" if days == 0 else f"D-{days}"
            items.append(f"{d.month}월 {d.day}일 {name} ({when})")
        if not items:
            return None
        out = "다음 공휴일: " + ", ".join(items) + " (출처 Nager.Date)"
        _cache["holidays"] = (now, out)
        return out
    except Exception:
        return None


def context_for(text: str) -> str | None:
    """사용자 말에 맞는 참고 정보를 돌려준다. 없으면 None."""
    if _has(text, AIR_WORDS):
        return get_air()
    if wants_weather(text):
        return get_weather()
    if _has(text, RATE_WORDS):
        return get_rates(text)
    if _has(text, NEWS_WORDS):
        return get_news()
    if _has(text, HOLIDAY_WORDS):
        return get_holidays()
    return None


def answer_for(text: str) -> str | None:
    """모델 없이 바로 쓸 수 있는 고양이 말투 답. 해당 없으면 None."""
    if _has(text, AIR_WORDS):
        info = get_air()
        return f"냐옹, {info}" if info else "미세먼지 정보를 못 가져왔어, 냥. 인터넷 확인해줘."
    if wants_weather(text):
        info = get_weather()
        return f"냐옹, {info}" if info else "날씨를 못 가져왔어, 냥. 인터넷 확인해줘."
    if _has(text, RATE_WORDS):
        info = get_rates(text)
        return f"냥, {info}" if info else "환율을 못 가져왔어, 냥."
    if _has(text, NEWS_WORDS):
        info = get_news()
        return f"냥, {info}" if info else "뉴스를 못 가져왔어, 냥."
    if _has(text, HOLIDAY_WORDS):
        info = get_holidays()
        return f"냥, {info}" if info else "공휴일 정보를 못 가져왔어, 냥."
    return None

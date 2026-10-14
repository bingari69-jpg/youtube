"""API 키 없이 쓰는 정보 조회. 현재는 날씨(Open-Meteo, 무료, 키 불필요).

brain.py 가 사용자의 말에 날씨 관련 단어가 있으면 여기서 정보를 가져와
모델에게 참고 자료로 넘기거나, 모델이 없으면 그대로 답한다.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request

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


def _geocode(place: str) -> tuple[float, float, str] | None:
    # "대한민국 서울" 처럼 나라가 앞에 붙어 있으면 마지막 단어(도시)로 찾는다
    name = place.strip().split()[-1] if place.strip() else "서울"
    name = re.sub(r"(특별시|광역시|특별자치시|특별자치도|시|도)$", "", name) or name
    q = urllib.parse.quote(name)
    data = _get(f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=ko&format=json")
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
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


def context_for(text: str) -> str | None:
    """사용자 말에 맞는 참고 정보를 돌려준다. 없으면 None."""
    if wants_weather(text):
        return get_weather()
    return None

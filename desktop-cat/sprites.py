"""픽셀 고양이 스프라이트 정의.

이미지 파일 없이 문자 격자로 그림을 정의한다.
  '.' 투명   '#' 몸(어두운색)   'w' 흰색(눈)   'p' 분홍(볼/졸린 눈)

격자는 16칸 x 14칸이며, 눈 영역(행 4~6)은 표정별로 교체한다.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap, QPainter

GRID_W = 16
GRID_H = 14

COLORS = {
    "#": QColor("#2b2b2b"),
    "w": QColor("#f4f4f4"),
    "p": QColor("#f2a6b0"),
}

# 몸통 기본형 (눈 자리는 '#'로 두고 아래에서 덮어쓴다)
_BODY = [
    "..##........##..",  # 0 귀
    "..###......###..",  # 1
    "..############..",  # 2
    "..############..",  # 3
    ".##############.",  # 4 눈 영역 시작
    ".##############.",  # 5
    "################",  # 6 팔 돌기 (양끝)
    ".##pp######pp##.",  # 7 볼
    "..############..",  # 8
    "..############..",  # 9
    "..############..",  # 10
    "...##.....##....",  # 11 다리 (프레임별로 교체)
    "...##.....##....",  # 12
    "................",  # 13
]

# 다리 프레임: 서 있기 / 걷기 1 / 걷기 2 / 앉기(잠)
LEGS = {
    "stand": ["...##.....##....", "...##.....##...."],
    "walk1": ["..##.......##...", "..##.......##..."],
    "walk2": ["....##...##.....", "....##...##....."],
    "sit": ["..####...####...", "................"],
}

# 표정별 눈. 왼쪽 눈 3x3 패치 (열 4~6), 오른쪽 눈 3x3 패치 (열 9~11), 행 4~6
EYES = {
    "normal": (["ww#", "ww#", "###"], ["#ww", "#ww", "###"]),
    "smile": (["#w#", "w#w", "###"], ["#w#", "w#w", "###"]),
    "excited": (["w##", "#w#", "w##"], ["##w", "#w#", "##w"]),
    "surprised": (["www", "w#w", "www"], ["www", "w#w", "www"]),
    "dizzy": (["www", "w#w", "ww#"], ["www", "w#w", "#ww"]),
    "sleepy": (["###", "ppp", "###"], ["###", "ppp", "###"]),
    "blink": (["###", "ww#", "###"], ["###", "#ww", "###"]),
}

EXPRESSION_NAMES_KO = {
    "normal": "기본",
    "smile": "웃음",
    "excited": "신남",
    "surprised": "놀람",
    "dizzy": "어지러움",
    "sleepy": "졸림",
    "blink": "깜빡",
}


def build_grid(expression: str = "normal", legs: str = "stand") -> list[str]:
    rows = [list(r) for r in _BODY]
    left, right = EYES[expression]
    for i in range(3):
        for j in range(3):
            rows[4 + i][4 + j] = left[i][j]
            rows[4 + i][9 + j] = right[i][j]
    leg_rows = LEGS[legs]
    rows[11] = list(leg_rows[0])
    rows[12] = list(leg_rows[1])
    return ["".join(r) for r in rows]


_cache: dict[tuple, QPixmap] = {}


def pixmap(expression: str, legs: str, scale: int, flip: bool = False) -> QPixmap:
    """격자를 QPixmap으로 변환한다. 같은 조합은 캐시한다."""
    key = (expression, legs, scale, flip)
    if key in _cache:
        return _cache[key]
    grid = build_grid(expression, legs)
    img = QImage(GRID_W * scale, GRID_H * scale, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            color = COLORS.get(ch)
            if color is None:
                continue
            px = (GRID_W - 1 - x) if flip else x
            painter.fillRect(px * scale, y * scale, scale, scale, color)
    painter.end()
    pm = QPixmap.fromImage(img)
    _cache[key] = pm
    return pm

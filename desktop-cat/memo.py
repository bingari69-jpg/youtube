"""메모장: 포스트잇 스타일 창 + 대화로 빠르게 적기 + 간단한 타이머.

  - 메모창: 우클릭 메뉴 '메모장'. 입력하면 1초 뒤 memo.txt 에 자동 저장. 위치/크기 기억.
  - 대화로 적기: "메모: 내일 3시 회의" / "메모 내일 3시 회의" -> memo.txt 끝에 날짜와 함께 추가
  - 대화로 보기: "메모 보여줘", "메모 뭐 있어" -> 최근 5줄
  - 타이머: "10분 뒤 알려줘", "30분 후 회의", "1시간 뒤 스트레칭" -> 시간이 되면 고양이가 말함
"""

from __future__ import annotations

import datetime as _dt
import os
import re

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

HERE = os.path.dirname(os.path.abspath(__file__))
MEMO_PATH = os.path.join(HERE, "memo.txt")

_MEMO_ADD = re.compile(r"^\s*메모(?:\s+|\s*[:：]\s*)(.+)$")
_MEMO_SHOW = re.compile(r"^\s*메모\s*(보여|뭐|목록|리스트|확인|읽어|열어)")
_TIMER = re.compile(r"(\d+)\s*(분|시간)\s*(뒤|후|있다가)\s*(.*)$")


# ---------------------------------------------------------------- 파일
def read_memo() -> str:
    try:
        with open(MEMO_PATH, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def write_memo(text: str) -> None:
    try:
        with open(MEMO_PATH, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def append_memo(line: str) -> None:
    stamp = _dt.datetime.now().strftime("%m/%d %H:%M")
    cur = read_memo()
    if cur and not cur.endswith("\n"):
        cur += "\n"
    write_memo(cur + f"- [{stamp}] {line.strip()}\n")


def recent_memo(n: int = 5) -> list[str]:
    lines = [ln for ln in read_memo().splitlines() if ln.strip()]
    return lines[-n:]


# ---------------------------------------------------------------- 대화 명령
def parse_command(text: str) -> tuple[str, object] | None:
    """('timer', (초, 메시지)) / ('memo_add', 내용) / ('memo_show', None) / None"""
    t = text.strip()
    m = _TIMER.search(t)
    if m and ("알려" in t or "타이머" in t or m.group(4).strip()):
        n, unit, _, rest = m.groups()
        seconds = int(n) * (3600 if unit == "시간" else 60)
        rest = re.sub(r"(알려\s*줘|알려줘|타이머|해줘|해 줘)\s*$", "", rest).strip(" .!~")
        return "timer", (seconds, rest or "시간 됐어")
    if _MEMO_SHOW.match(t):
        return "memo_show", None
    m = _MEMO_ADD.match(t)
    if m and not _MEMO_SHOW.match(t):
        body = m.group(1).strip()
        if body:
            return "memo_add", body
    return None


# ---------------------------------------------------------------- 창
class MemoWindow(QWidget):
    changed = Signal()
    WIDTH, HEIGHT = 300, 320

    def __init__(self, settings):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("메모장")
        self.settings = settings
        geo = settings.get("memo_geometry")
        if isinstance(geo, list) and len(geo) == 4:
            self.setGeometry(*geo)
        else:
            self.resize(self.WIDTH, self.HEIGHT)
        self._drag_pos = None
        self._resizing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 12)
        root.setSpacing(6)
        title = QHBoxLayout()
        lab = QLabel("메모")
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        lab.setFont(f)
        lab.setStyleSheet("color:#6b5d2a;")
        self.status = QLabel("")
        self.status.setStyleSheet("color:#a3975f;font-size:8pt;")
        close = QPushButton("×")
        close.setFixedSize(24, 24)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            "QPushButton{border:none;border-radius:12px;background:transparent;color:#a3975f;font-size:17px;}"
            "QPushButton:hover{background:#f3e9b8;color:#2b2b2b;}"
        )
        close.clicked.connect(self.hide)
        title.addWidget(lab)
        title.addStretch()
        title.addWidget(self.status)
        title.addWidget(close)
        root.addLayout(title)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("여기에 적으면 자동 저장돼요.\n대화창에서 '메모: 내용' 이라고 해도 여기 쌓여요.")
        self.edit.setStyleSheet(
            "QPlainTextEdit{border:none;background:transparent;color:#2b2b2b;font-size:10pt;"
            "selection-background-color:#f2a6b0;}"
            "QScrollBar:vertical{width:6px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#e2d79a;border-radius:3px;min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self.edit.setPlainText(read_memo())
        self.edit.textChanged.connect(self._schedule_save)
        root.addWidget(self.edit, 1)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1000)
        self._save_timer.timeout.connect(self._save)

    # ---- 저장 ----
    def _schedule_save(self):
        self.status.setText("입력 중...")
        self._save_timer.start()

    def _save(self):
        write_memo(self.edit.toPlainText())
        self.status.setText("저장됨 " + _dt.datetime.now().strftime("%H:%M"))
        self.changed.emit()

    def reload(self):
        """파일이 바뀌었을 때(대화로 추가 등) 다시 읽는다."""
        self.edit.blockSignals(True)
        cur = self.edit.textCursor()
        self.edit.setPlainText(read_memo())
        self.edit.moveCursor(cur.MoveOperation.End)
        self.edit.blockSignals(False)

    # ---- 그리기: 포스트잇 ----
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(4, 4, -4, -4)
        shadow = QPainterPath()
        shadow.addRoundedRect(r.adjusted(0, 3, 0, 3), 16, 16)
        p.fillPath(shadow, QColor(0, 0, 0, 40))
        card = QPainterPath()
        card.addRoundedRect(r, 16, 16)
        p.fillPath(card, QColor("#fff7c2"))
        p.setPen(QPen(QColor("#ead98a"), 1.5))
        p.drawPath(card)
        # 오른쪽 아래 크기 조절 표시
        p.setPen(QPen(QColor("#d6c56e"), 2))
        br = r.bottomRight()
        for i in (4, 9):
            p.drawLine(br.x() - i, br.y() - 2, br.x() - 2, br.y() - i)
        p.end()

    # ---- 이동/크기 ----
    def _in_resize_corner(self, pos) -> bool:
        return pos.x() > self.width() - 18 and pos.y() > self.height() - 18

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._in_resize_corner(e.position().toPoint()):
            self._resizing = True
        elif e.position().y() < 36:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        gp = e.globalPosition().toPoint()
        if self._resizing:
            self.resize(max(200, gp.x() - self.x()), max(160, gp.y() - self.y()))
        elif self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(gp - self._drag_pos)

    def mouseReleaseEvent(self, _e):
        if self._resizing or self._drag_pos is not None:
            g: QRect = self.geometry()
            self.settings.set("memo_geometry", [g.x(), g.y(), g.width(), g.height()])
        self._resizing = False
        self._drag_pos = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def hideEvent(self, e):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save()
        super().hideEvent(e)

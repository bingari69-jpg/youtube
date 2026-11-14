"""모니터 위에 사는 픽셀 고양이.

실행:  python cat.py
종료:  트레이 아이콘 우클릭 -> 종료  (또는 고양이 우클릭 -> 종료)

동작
  - 화면 아래쪽(작업표시줄 위)을 돌아다니고, 가만히 있다가, 졸다가, 잔다.
  - 마우스가 움직이면 커서를 쫓아간다. (트레이 메뉴에서 끌 수 있음)
  - 키보드를 누르면 점프한다. 너무 빨리 치면 어지러워한다.
  - 고양이를 클릭하면 깨어나서 대화창이 열린다.
  - 드래그하면 옮길 수 있다.
  - 몇 분간 입력이 없으면 스스로 잠든다.
"""

from __future__ import annotations

import logging
import math
import os
import random
import sys
import time
import traceback

from PySide6.QtCore import QObject, QPoint, QRect, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprites  # noqa: E402
from brain import make_brain  # noqa: E402
from comfort import Comfort  # noqa: E402
import memo as memo_mod  # noqa: E402
from growth import Growth  # noqa: E402
import schedule as sched  # noqa: E402
from music import MusicPlayer  # noqa: E402
from notices import NoticeBoard  # noqa: E402
from settings import Settings  # noqa: E402
from situations import SituationMonitor  # noqa: E402

SETTINGS = Settings()

HERE = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    filename=os.path.join(HERE, "cat.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("cat")

CAT_NAME = os.environ.get("CAT_NAME") or SETTINGS.get("name", "먹물")
BRAND = os.environ.get("CAT_BRAND", "XENICS")
APP_VERSION = "1.0.0"
REPLY_TIMEOUT_SEC = float(os.environ.get("CAT_REPLY_TIMEOUT_SEC", "90"))
if not os.environ.get("CAT_LOCATION") and SETTINGS.get("location"):
    os.environ["CAT_LOCATION"] = SETTINGS["location"]
TICK_MS = 33  # 약 30fps
AUTO_SLEEP_SEC = float(os.environ.get("CAT_AUTO_SLEEP_SEC") or SETTINGS.get("auto_sleep_sec", 180))


# ----------------------------------------------------------------------------
# 전역 키보드 감지 (다른 창에 포커스가 있어도 동작). pynput이 없으면 조용히 비활성.
# ----------------------------------------------------------------------------
class GlobalKeys(QObject):
    pressed = Signal()

    def __init__(self):
        super().__init__()
        self._listener = None
        self.available = False
        try:
            from pynput import keyboard

            self._listener = keyboard.Listener(on_press=lambda _k: self.pressed.emit())
            self._listener.daemon = True
            self._listener.start()
            self.available = True
        except Exception as e:  # X 서버 없음, 권한 없음 등
            print(f"[cat] 전역 키보드 감지 비활성: {e}")

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass


# ----------------------------------------------------------------------------
# 대화 워커: API 호출을 GUI 스레드 밖에서 처리
# ----------------------------------------------------------------------------
class ChatWorker(QObject):
    done = Signal(str, int)

    def __init__(self, brain, text: str, seq: int):
        super().__init__()
        self._brain = brain
        self._text = text
        self._seq = seq

    def run(self):
        try:
            out = self._brain.reply(self._text)
        except BaseException as e:  # noqa: BLE001 - 무조건 신호를 보내야 입력이 풀린다
            log.error("reply failed: %s\n%s", e, traceback.format_exc())
            out = f"머리가 아파서 대답을 못 하겠어, 냥. ({type(e).__name__})"
        self.done.emit(out, self._seq)


# ----------------------------------------------------------------------------
# 말풍선
# ----------------------------------------------------------------------------
class Bubble(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._flip = False
        self._font = QFont()
        self._font.setPointSize(10)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def say(self, text: str, anchor: QPoint, seconds: float = 4.0, below: QPoint | None = None):
        self._text = text
        fm = self.fontMetrics()
        rect = fm.boundingRect(QRect(0, 0, 220, 1000), Qt.TextFlag.TextWordWrap, text)
        w, h = rect.width() + 24, rect.height() + 18 + 8
        self.resize(w, h)
        x = anchor.x() - w // 2
        y = anchor.y() - h - 4
        scr = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        self._flip = False
        if y < g.top() and below is not None:
            y = below.y() + 4
            self._flip = True  # 꼬리를 위로
        x = max(g.left(), min(x, g.right() - w))
        y = max(g.top(), min(y, g.bottom() - h))
        self.move(x, y)
        self.show()
        self.update()
        self._hide_timer.start(int(seconds * 1000))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() // 2
        path = QPainterPath()
        if self._flip:
            body = QRect(0, 8, self.width(), self.height() - 8)
            path.addRoundedRect(body, 10, 10)
            path.moveTo(cx - 6, body.top())
            path.lineTo(cx, body.top() - 8)
            path.lineTo(cx + 6, body.top())
        else:
            body = QRect(0, 0, self.width(), self.height() - 8)
            path.addRoundedRect(body, 10, 10)
            path.moveTo(cx - 6, body.bottom())
            path.lineTo(cx, body.bottom() + 8)
            path.lineTo(cx + 6, body.bottom())
        p.fillPath(path, QColor("#fffdf5"))
        p.setPen(QPen(QColor("#2b2b2b"), 2))
        p.drawPath(path)
        p.setFont(self._font)
        p.setPen(QColor("#2b2b2b"))
        p.drawText(body.adjusted(12, 8, -12, -8), Qt.TextFlag.TextWordWrap, self._text)


# ----------------------------------------------------------------------------
# 대화창 (메신저 스타일 말풍선)
# ----------------------------------------------------------------------------
UI_BG = QColor("#fffdf7")
UI_INK = QColor("#2b2b2b")
UI_CAT_BUBBLE = QColor("#f1efe8")
UI_USER_BUBBLE = QColor("#2b2b2b")
UI_ACCENT = QColor("#f2a6b0")


class MessageBubble(QWidget):
    """말풍선 하나. mine=True 면 오른쪽(사용자), 아니면 왼쪽(고양이)."""

    def __init__(self, text: str, mine: bool, max_width: int):
        super().__init__()
        self.text = text
        self.mine = mine
        self.max_width = max_width
        self._font = QFont()
        self._font.setPointSize(10)
        self.avatar = None if mine else sprites.pixmap("smile", "stand", 2)
        self._layout_text()

    def _layout_text(self):
        fm = QFontMetrics(self._font)
        limit = self.max_width - 28
        rect = fm.boundingRect(QRect(0, 0, limit, 10000), Qt.TextFlag.TextWordWrap, self.text)
        inner_w = min(limit, rect.width() + 6)  # 줄바꿈 오차 여유
        rect = fm.boundingRect(QRect(0, 0, inner_w, 10000), Qt.TextFlag.TextWordWrap, self.text)
        self.bw = inner_w + 28
        self.bh = rect.height() + 22
        extra = 0 if self.mine else 40
        self.setFixedHeight(self.bh + 6)
        self.setMinimumWidth(self.bw + extra)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font)
        if self.mine:
            x = self.width() - self.bw
            r = QRect(x, 0, self.bw, self.bh)
            path = QPainterPath()
            path.addRoundedRect(r, 14, 14)
            path.addRect(r.right() - 14, r.bottom() - 14, 15, 15)  # 오른쪽 아래 모서리만 각지게
            p.fillPath(path.simplified(), UI_USER_BUBBLE)
            p.setPen(QColor("#ffffff"))
        else:
            if self.avatar:
                p.drawPixmap(0, self.bh - self.avatar.height() - 2, self.avatar)
            x = 40
            r = QRect(x, 0, self.bw, self.bh)
            path = QPainterPath()
            path.addRoundedRect(r, 14, 14)
            path.addRect(r.left(), r.bottom() - 14, 15, 15)  # 왼쪽 아래 모서리만 각지게
            p.fillPath(path.simplified(), UI_CAT_BUBBLE)
            p.setPen(UI_INK)
        p.drawText(r.adjusted(14, 10, -14, -10), Qt.TextFlag.TextWordWrap, self.text)
        p.end()


class TypingBubble(QWidget):
    """고양이가 생각 중일 때 점 세 개가 움직이는 풍선."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(110, 40)
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(300)
        self.avatar = sprites.pixmap("normal", "stand", 2)

    def _tick(self):
        self.phase = (self.phase + 1) % 3
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(0, 34 - self.avatar.height() - 2, self.avatar)
        r = QRect(40, 0, 64, 34)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.fillPath(path, UI_CAT_BUBBLE)
        for i in range(3):
            c = QColor(UI_INK) if i == self.phase else QColor("#9a978f")
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(40 + 18 + i * 14, 17), 4, 4)
        p.end()


class ChatWindow(QWidget):
    send_requested = Signal(str)
    WIDTH, HEIGHT = 340, 440

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(f"{CAT_NAME}와 대화")
        self.resize(self.WIDTH, self.HEIGHT)
        self._drag_pos = None
        self._typing: TypingBubble | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 6, 14, 14)
        root.setSpacing(8)

        # 제목줄: 끌어서 옮기는 손잡이와 닫기 버튼만
        title = QHBoxLayout()
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            "QPushButton{border:none;border-radius:13px;background:transparent;color:#8a877f;font-size:18px;}"
            "QPushButton:hover{background:#f1efe8;color:#2b2b2b;}"
        )
        self.close_btn.clicked.connect(self.hide)
        title.addStretch()
        title.addWidget(self.close_btn)
        root.addLayout(title)

        # 메시지 영역
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea{background:transparent;}"
            "QScrollBar:vertical{width:6px;background:transparent;margin:0;}"
            "QScrollBar::handle:vertical{background:#d9d6cc;border-radius:3px;min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self.container = QWidget()
        self.container.setStyleSheet("background:transparent;")
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setContentsMargins(0, 4, 6, 4)
        self.vbox.setSpacing(6)
        self.vbox.addStretch()  # 항상 마지막 항목. 메시지는 이 앞에 끼워 넣는다
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        # 입력줄
        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("말 걸기...")
        self.input.setFixedHeight(38)
        self.input.setStyleSheet(
            "QLineEdit{border:2px solid #e6e3da;border-radius:19px;padding:0 14px;background:#ffffff;"
            "color:#2b2b2b;font-size:10pt;selection-background-color:#f2a6b0;}"
            "QLineEdit:focus{border-color:#f2a6b0;}"
            "QLineEdit:disabled{background:#f6f4ee;color:#9a978f;}"
        )
        self.btn = QPushButton("➤")
        self.btn.setFixedSize(38, 38)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setStyleSheet(
            "QPushButton{border:none;border-radius:19px;background:#2b2b2b;color:#ffffff;font-size:14px;}"
            "QPushButton:hover{background:#444444;}"
            "QPushButton:disabled{background:#d9d6cc;color:#ffffff;}"
        )
        row.addWidget(self.input, 1)
        row.addWidget(self.btn)
        root.addLayout(row)

        self.input.returnPressed.connect(self._send)
        self.btn.clicked.connect(self._send)

    # 창 배경(둥근 카드)과 그림자
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(4, 4, -4, -4)
        shadow = QPainterPath()
        shadow.addRoundedRect(r.adjusted(0, 3, 0, 3), 22, 22)
        p.fillPath(shadow, QColor(0, 0, 0, 40))
        card = QPainterPath()
        card.addRoundedRect(r, 22, 22)
        p.fillPath(card, UI_BG)
        p.setPen(QPen(QColor("#e6e3da"), 1.5))
        p.drawPath(card)
        p.end()

    # 제목줄 드래그로 창 옮기기
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 36:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _e):
        self._drag_pos = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    # ---- 외부에서 쓰는 API ----
    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.append("나", text)
        self.set_busy(True)
        self.send_requested.emit(text)

    def append(self, who: str, text: str):
        mine = who == "나"
        bubble = MessageBubble(text, mine, int(self.width() * 0.72))
        self._remove_typing()
        self._insert(bubble, Qt.AlignmentFlag.AlignRight if mine else Qt.AlignmentFlag.AlignLeft)

    def set_busy(self, busy: bool):
        self.input.setEnabled(not busy)
        self.btn.setEnabled(not busy)
        if busy:
            if self._typing is None:
                self._typing = TypingBubble()
                self._insert(self._typing, Qt.AlignmentFlag.AlignLeft)
        else:
            self._remove_typing()
            self.input.setFocus()

    def _insert(self, w: QWidget, align):
        self.vbox.insertWidget(self.vbox.count() - 1, w, 0, align)
        QTimer.singleShot(0, self._scroll_bottom)

    def _remove_typing(self):
        if self._typing is not None:
            self.vbox.removeWidget(self._typing)
            self._typing.deleteLater()
            self._typing = None

    def _scroll_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def transcript(self) -> str:
        out = []
        for i in range(self.vbox.count()):
            w = self.vbox.itemAt(i).widget()
            if isinstance(w, MessageBubble):
                out.append(("나: " if w.mine else f"{CAT_NAME}: ") + w.text)
        return "\n".join(out)


# ----------------------------------------------------------------------------
# 쥐 (쥐 잡기 게임)
# ----------------------------------------------------------------------------
class Mouse(QWidget):
    clicked = Signal()
    GAME_SEC = 45.0

    def __init__(self, scale: int):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scale = max(3, scale - 1)
        self.W = sprites.MOUSE_W * self.scale
        self.H = sprites.MOUSE_H * self.scale
        self.resize(self.W, self.H)
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.facing_left = False
        self.mode = "hidden"  # hidden / run / pause / stunned / escaping
        self.mode_until = 0.0
        self.phase = 0
        self.geom = QRect()

    def spawn(self, g: QRect):
        """화면 네 변 중 한 곳에서 튀어나온다."""
        self.geom = g
        side = random.choice(["left", "right", "top", "bottom"])
        if side == "left":
            self.x, self.y = float(g.left() - self.W), random.uniform(g.top(), g.bottom() - self.H)
        elif side == "right":
            self.x, self.y = float(g.right() + 1), random.uniform(g.top(), g.bottom() - self.H)
        elif side == "top":
            self.x, self.y = random.uniform(g.left(), g.right() - self.W), float(g.top() - self.H)
        else:
            self.x, self.y = random.uniform(g.left(), g.right() - self.W), float(g.bottom() + 1)
        self._run(now=time.time(), toward_center=True)
        self.show()

    def _set_velocity(self, angle: float, speed: float):
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        if abs(self.vx) > 0.5:
            self.facing_left = self.vx < 0

    def _run(self, now: float, toward_center: bool = False):
        self.mode = "run"
        speed = random.uniform(4.0, 7.5)
        if toward_center:
            c = self.geom.center()
            angle = math.atan2(c.y() - self.y, c.x() - self.x) + random.uniform(-0.6, 0.6)
        else:
            angle = random.uniform(0, 2 * math.pi)
        self._set_velocity(angle, speed)
        self.mode_until = now + random.uniform(0.6, 1.8)

    def stun(self, seconds: float = 1.1):
        self.mode = "stunned"
        self.vx = self.vy = 0.0
        self.mode_until = time.time() + seconds

    def escape(self):
        """고양이를 피해 가장 가까운 화면 가장자리로 달아난다."""
        self.mode = "escaping"
        g = self.geom
        d = {
            "left": self.x - g.left(),
            "right": g.right() - self.x,
            "top": self.y - g.top(),
            "bottom": g.bottom() - self.y,
        }
        side = min(d, key=d.get)
        angle = {"left": math.pi, "right": 0.0, "top": -math.pi / 2, "bottom": math.pi / 2}[side]
        self._set_velocity(angle + random.uniform(-0.3, 0.3), 9.0)

    def hide_mouse(self):
        self.mode = "hidden"
        self.hide()

    def step(self, now: float) -> str | None:
        """한 틱 진행. 쥐가 화면 밖으로 빠져나가면 'gone' 을 돌려준다."""
        if self.mode == "hidden":
            return None
        g = self.geom
        if self.mode == "run":
            self.x += self.vx
            self.y += self.vy
            self.phase += 1
            if now > self.mode_until:
                self.mode = "pause"
                self.vx = self.vy = 0.0
                self.mode_until = now + random.uniform(0.3, 1.0)
            # 가장자리에서 튕긴다 (일반 달리기 중에는 화면 안에 머문다)
            if self.x < g.left():
                self.x, self.vx = float(g.left()), abs(self.vx)
                self.facing_left = False
            elif self.x > g.right() - self.W:
                self.x, self.vx = float(g.right() - self.W), -abs(self.vx)
                self.facing_left = True
            if self.y < g.top():
                self.y, self.vy = float(g.top()), abs(self.vy)
            elif self.y > g.bottom() - self.H:
                self.y, self.vy = float(g.bottom() - self.H), -abs(self.vy)
        elif self.mode == "pause":
            if now > self.mode_until:
                self._run(now)
        elif self.mode == "stunned":
            if now > self.mode_until:
                self.escape()
        elif self.mode == "escaping":
            self.x += self.vx
            self.y += self.vy
            self.phase += 1
            if (
                self.x < g.left() - self.W
                or self.x > g.right() + 1
                or self.y < g.top() - self.H
                or self.y > g.bottom() + 1
            ):
                self.hide_mouse()
                return "gone"
        self.move(int(self.x), int(self.y))
        self.update()
        return None

    def center(self) -> tuple[float, float]:
        return self.x + self.W / 2, self.y + self.H / 2

    def paintEvent(self, _e):
        p = QPainter(self)
        run = self.mode in ("run", "escaping") and (self.phase // 4) % 2 == 0
        p.drawPixmap(0, 0, sprites.mouse_pixmap(self.scale, self.facing_left, run))
        if self.mode == "stunned":
            p.setPen(QColor("#2b2b2b"))
            f = QFont()
            f.setPointSize(9)
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.W // 2 - 6, 12, "!")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.mode in ("run", "pause"):
            self.clicked.emit()


# ----------------------------------------------------------------------------
# 고양이 본체
# ----------------------------------------------------------------------------
class Cat(QWidget):
    IDLE, WALK, CHASE, JUMP, SLEEP, DIZZY, CHAT, DRAG, POUNCE = range(9)

    def __init__(self, scale: int = 6):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.growth = Growth()
        self.base_scale = scale
        self.scale = max(3, round(scale * self.growth.size_mult()))
        self.W = sprites.GRID_W * self.scale
        self.H = sprites.GRID_H * self.scale
        # 위쪽에 점프/Zzz 여유 공간을 둔다
        self.pad_top = self.H
        self.resize(self.W, self.H + self.pad_top)

        self.state = self.IDLE
        self.expression = "normal"
        self.legs = "stand"
        self.facing_left = False
        self.x = 0.0  # 스프라이트 왼쪽 위 (화면 좌표)
        self.y = 0.0
        self.y_off = 0.0  # 점프로 떠오른 높이
        self.vy = 0.0
        self.target: tuple[float, float] | None = None
        self.state_until = 0.0
        self.walk_phase = 0
        self.last_input = time.time()
        self.last_cursor = QCursor.pos()
        self.cursor_still_since = time.time()
        self.key_times: list[float] = []
        self.blink_until = 0.0
        self.zzz_phase = 0.0
        self.chase_enabled = bool(SETTINGS.get("chase", True))
        self.jump_enabled = bool(SETTINGS.get("jump", True))
        self.situations = SituationMonitor(SETTINGS)
        self.notices = NoticeBoard(SETTINGS)
        self.comfort = Comfort(SETTINGS)
        self.memo = memo_mod.MemoWindow(SETTINGS)
        self.timers: list[QTimer] = []
        self.reminder = sched.Reminder()
        self.music = MusicPlayer(SETTINGS)
        self.music.track_changed.connect(lambda t: self.say(f"♪ {t}", 3))
        self.drag_offset = QPoint()
        self.press_pos = QPoint()
        self.dragged = False
        self._prev_sleeping = False

        self.game_on = False
        self.game_end = 0.0
        self.score = 0
        self.missed = 0
        self.pounce_target = (0.0, 0.0)
        self.mouse = Mouse(self.scale)
        self.mouse.clicked.connect(self.on_mouse_clicked)

        self.brain = make_brain(CAT_NAME)
        if hasattr(self.brain, "tone"):
            self.brain.tone = self.growth.tone()
        self.bubble = Bubble()
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._single_click)
        self.chat = ChatWindow()
        self.chat.send_requested.connect(self.on_user_said)
        self._thread: QThread | None = None
        self._worker: ChatWorker | None = None
        self._pending_seq = 0
        self._reply_watchdog = QTimer(self)
        self._reply_watchdog.setSingleShot(True)
        self._reply_watchdog.timeout.connect(self._on_reply_timeout)

        self.keys = GlobalKeys()
        self.keys.pressed.connect(self.on_global_key)

        self._place_on_floor()
        self._build_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)
        self._enter(self.IDLE)
        self.show()
        QTimer.singleShot(600, lambda: self.say(self.growth_style(
            f"안녕, 나는 {CAT_NAME}이야. 냐옹." if self.growth.stage > 0 else f"미야옹... 나는 {CAT_NAME}. 아직 아기야. 잘 키워줘, 냐앙."), 4))

    # ---------------- 화면/위치 ----------------
    def _screen_geom(self, at: QPoint | None = None) -> QRect:
        pt = at or QPoint(int(self.x) + self.W // 2, int(self.y) + self.H // 2)
        scr = QGuiApplication.screenAt(pt) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()

    def _place_on_floor(self):
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.x = g.right() - self.W - 80
        self.y = g.bottom() - self.H + 1
        self._sync_pos()

    def _sync_pos(self):
        g = self._screen_geom()
        self.x = max(g.left(), min(self.x, g.right() - self.W + 1))
        self.y = max(g.top(), min(self.y, g.bottom() - self.H + 1))
        self.move(int(self.x), int(self.y) - int(self.y_off) - self.pad_top)

    def anchor_point(self) -> QPoint:
        """말풍선 꼬리가 닿는 머리 위 지점"""
        return QPoint(int(self.x) + self.W // 2, int(self.y) - int(self.y_off))

    def anchor_below(self) -> QPoint:
        return QPoint(int(self.x) + self.W // 2, int(self.y) + self.H - int(self.y_off))

    def _move_toward(self, tx: float, ty: float, speed: float) -> float:
        """목표 쪽으로 speed 만큼 이동하고 남은 거리를 돌려준다."""
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist <= speed:
            self.x, self.y = tx, ty
            return 0.0
        self.x += dx / dist * speed
        self.y += dy / dist * speed
        if abs(dx) > 1:
            self.facing_left = dx < 0
        return dist - speed

    # ---------------- 트레이 ----------------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(sprites.pixmap("normal", "stand", 4)), self)
        self.tray.setToolTip(f"{CAT_NAME} · {BRAND} 데스크톱 고양이")
        self.tray.setContextMenu(self._make_menu())
        self.tray.activated.connect(
            lambda r: self.open_chat() if r == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    def _make_menu(self) -> QMenu:
        m = QMenu()
        m.addAction("대화하기", self.open_chat)
        m.addAction("메모장", self.open_memo)
        m.addAction("일정 보기", self.show_schedule)
        self.act_sleep = QAction("재우기", m)
        self.act_sleep.triggered.connect(self.toggle_sleep)
        m.addAction(self.act_sleep)
        self.act_game = QAction("쥐 잡기 게임 그만" if self.game_on else "쥐 잡기 게임", m)
        self.act_game.triggered.connect(self.toggle_game)
        m.addAction(self.act_game)
        m.addSeparator()
        a = QAction("마우스 따라가기", m, checkable=True, checked=self.chase_enabled)
        a.toggled.connect(lambda v: (setattr(self, "chase_enabled", v), SETTINGS.set("chase", v)))
        m.addAction(a)
        b = QAction("키보드 점프", m, checkable=True, checked=self.jump_enabled)
        b.toggled.connect(lambda v: (setattr(self, "jump_enabled", v), SETTINGS.set("jump", v)))
        m.addAction(b)
        size = m.addMenu("크기")
        for label, s in (("작게", 4), ("보통", 6), ("크게", 9)):
            size.addAction(label, lambda s=s: self.set_scale(s))
        stretch = m.addMenu("스트레칭 알림")
        cur = int(SETTINGS.get("stretch_minutes", 50) or 0)
        for label, mins in (("끄기", 0), ("30분마다", 30), ("50분마다", 50), ("60분마다", 60), ("90분마다", 90)):
            act = QAction(label, stretch, checkable=True, checked=(mins == cur))
            act.triggered.connect(lambda _c=False, mins=mins: SETTINGS.set("stretch_minutes", mins))
            stretch.addAction(act)
        talk = m.addMenu("말 걸기")
        cur_c = SETTINGS.get("comfort", "normal")
        for label, mode in (("자주", "often"), ("보통", "normal"), ("가끔", "rare"), ("끄기", "off")):
            act = QAction(label, talk, checkable=True, checked=(mode == cur_c))
            act.triggered.connect(lambda _c=False, mode=mode: SETTINGS.set("comfort", mode))
            talk.addAction(act)
        self._music_menu(m)
        n = QAction("소식 알림", m, checkable=True, checked=bool(SETTINGS.get("notices", True)))
        n.toggled.connect(lambda v: SETTINGS.set("notices", v))
        m.addAction(n)
        m.addSeparator()
        m.addAction("대화 기억 지우기", self.brain.reset)
        m.addAction("쓰다듬기", self.pet)
        m.addAction("성장 상태", lambda: self.say(self.growth.summary(), 8))
        m.addAction("정보", self.show_about)
        m.addAction("종료", self.quit)
        return m

    def open_memo(self):
        if self.memo.isVisible():
            self.memo.hide()
            return
        if not SETTINGS.get("memo_geometry"):
            g = self._screen_geom()
            x = int(self.x) - self.memo.width() - 16
            if x < g.left():
                x = int(self.x) + self.W + 16
            y = max(g.top(), min(int(self.y) - self.memo.height() + self.H, g.bottom() - self.memo.height()))
            self.memo.move(max(g.left(), min(x, g.right() - self.memo.width())), y)
        self.memo.reload()
        self.memo.show()
        self.memo.raise_()
        self.memo.activateWindow()
        self.memo.edit.setFocus()

    def show_schedule(self):
        items = sched.upcoming(30)
        if not items:
            self.say("앞으로 한 달 동안 잡힌 일정이 없어, 냥. 대화창에서 '다음주 화요일 3시 치과 기억해줘'처럼 말해봐.", 7)
            return
        lines = [f"{i + 1}. {sched.fmt(it)}" for i, it in enumerate(items[:8])]
        self.say("앞으로 한 달 일정이야, 냥:\n" + "\n".join(lines), 10)

    def _handle_schedule(self, text: str) -> str | None:
        cmd = sched.parse_command(text)
        if not cmd:
            return None
        kind, arg = cmd
        if kind == "add":
            when, has_time, body = arg
            item = sched.add(when, body, has_time)
            return f"기억했어, 냥: {sched.fmt(item)}. 그날 아침에 알려주고, 10분 전에도 깨울게."
        if kind == "query":
            start, end, label = arg
            items = sched.items_between(start, end)
            if not items:
                return f"{label} 일정은 없어, 냥. 한가하네!"
            lines = "\n".join(f"{i + 1}. {sched.fmt(it)}" for i, it in enumerate(items))
            return f"{label} 일정 {len(items)}개야, 냥:\n{lines}"
        if kind == "remove":
            it = sched.remove(arg)
            return f"지웠어, 냥: {sched.fmt(it)}" if it else "그 번호 일정은 없어, 냥. '일정 보여줘'로 번호를 확인해봐."
        if kind == "clear":
            n = sched.clear_all()
            return f"일정 {n}개 다 지웠어, 냥."
        if kind == "help":
            return "날짜랑 내용을 말해주면 기억할게, 냥. 예: '다음주 화요일 3시 치과', '내일 오후 2시 회의', '11월 20일 저녁 동창회'. 보려면 '다음주 일정 뭐 있어?'"
        return None

    def _handle_command(self, text: str) -> str | None:
        """메모/타이머/일정 같은 즉답 명령. 처리했으면 답을 돌려주고, 아니면 None."""
        out = self._handle_schedule(text)
        if out is not None:
            return out
        cmd = memo_mod.parse_command(text)
        if not cmd:
            return None
        kind, arg = cmd
        if kind == "memo_add":
            memo_mod.append_memo(arg)
            if self.memo.isVisible():
                self.memo.reload()
            return f"적어뒀어, 냥: \"{arg}\" (우클릭 → 메모장에서 볼 수 있어)"
        if kind == "memo_show":
            lines = memo_mod.recent_memo(5)
            if not lines:
                return "아직 메모가 없어, 냥. '메모: 내용' 이라고 말하면 적어둘게."
            return "최근 메모야, 냥:\n" + "\n".join(lines)
        if kind == "timer":
            seconds, msg = arg
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda t=t, msg=msg: self._timer_fired(t, msg))
            t.start(int(seconds * 1000))
            self.timers.append(t)
            when = (time.strftime("%H:%M", time.localtime(time.time() + seconds)))
            return f"알았어, {when}에 \"{msg}\" 라고 알려줄게, 냥."
        return None

    def _timer_fired(self, t: QTimer, msg: str):
        if t in self.timers:
            self.timers.remove(t)
        if self.state == self.SLEEP:
            self.wake(greet=False)
        self.expression = "surprised"
        self.state_until = time.time() + 2.0
        self.say(f"⏰ {msg}! 냥!", 10)
        if self.chat.isVisible():
            self.chat.append(CAT_NAME, f"⏰ {msg}!")

    def _music_menu(self, parent: QMenu):
        mm = parent.addMenu("음악")
        self.music.rescan()
        if not self.music.available:
            mm.addAction("(이 빌드는 소리 재생을 지원하지 않음)").setEnabled(False)
            return
        if not self.music.tracks:
            mm.addAction("(music 폴더에 mp3를 넣으세요)").setEnabled(False)
            return
        mm.addAction("일시정지" if self.music.is_playing() else "재생", self.music.toggle)
        mm.addAction("다음 곡", self.music.next)
        mm.addAction("정지", self.music.stop)
        mm.addSeparator()
        cur = self.music.current_title()
        for i, title in enumerate(self.music.titles()):
            act = QAction(("♪ " if title == cur else "") + title, mm)
            act.triggered.connect(lambda _c=False, i=i: self.music.play_index(i))
            mm.addAction(act)
        mm.addSeparator()
        vol = mm.addMenu("볼륨")
        for v in (20, 40, 60, 80, 100):
            act = QAction(f"{v}%", vol, checkable=True, checked=(v == self.music.volume()))
            act.triggered.connect(lambda _c=False, v=v: self.music.set_volume(v))
            vol.addAction(act)
        sh = QAction("섞어서 재생", mm, checkable=True, checked=self.music.shuffle)
        sh.toggled.connect(self.music.set_shuffle)
        mm.addAction(sh)

    def show_about(self):
        self.say(
            f"{CAT_NAME} v{APP_VERSION} · {BRAND}\n두뇌: {self.brain.name}\n"
            "날씨 Open-Meteo · 환율 Frankfurter · 뉴스 Google · 공휴일 Nager.Date",
            6,
        )

    def set_scale(self, s: int):
        SETTINGS.set("scale", s)
        self.base_scale = s
        self._apply_size()

    def _apply_size(self):
        s = max(3, round(self.base_scale * self.growth.size_mult()))
        self.scale = s
        self.W = sprites.GRID_W * s
        self.H = sprites.GRID_H * s
        self.pad_top = self.H
        self.resize(self.W, self.H + self.pad_top)
        self._sync_pos()

    # ---------------- 상태 ----------------
    def _enter(self, state: int, duration: float | None = None):
        self.state = state
        now = time.time()
        if state == self.IDLE:
            self.expression = "normal"
            self.legs = "stand"
            self.state_until = now + random.uniform(2.0, 6.0)
        elif state == self.WALK:
            g = self._screen_geom()
            self.target = (
                random.uniform(g.left(), g.right() - self.W),
                random.uniform(g.top(), g.bottom() - self.H),
            )
            self.expression = "normal"
            self.state_until = now + 25
        elif state == self.CHASE:
            self.expression = "excited"
        elif state == self.JUMP:
            self.vy = 11.0
            self.expression = "surprised"
            self.legs = "stand"
        elif state == self.SLEEP:
            self.expression = "sleepy"
            self.legs = "sit"
            self.target = None
            self.act_sleep.setText("깨우기")
        elif state == self.DIZZY:
            self.expression = "dizzy"
            self.state_until = now + (duration or 2.5)
        elif state == self.CHAT:
            self.expression = "smile"
            self.legs = "stand"
        elif state == self.POUNCE:
            self.expression = "excited"
            self.vy = 9.0
        if state != self.SLEEP:
            self.act_sleep.setText("재우기")
        self.update()

    def toggle_sleep(self):
        if self.state == self.SLEEP:
            self.wake()
        else:
            self.sleep()

    def sleep(self):
        if self.game_on:
            self.end_game(by_user=True)
        self.music.pause()
        self.bubble.hide()
        self._enter(self.SLEEP)

    def wake(self, greet: bool = True):
        if self.state != self.SLEEP:
            return
        self._enter(self.IDLE)
        self.last_input = time.time()
        if greet:
            self.expression = "surprised"
            self.state_until = time.time() + 1.0
            self.say(random.choice(["냐...? 깼어.", "음냐... 불렀어?", "하암. 냥."]), 2.5)

    # ---------------- 입력 ----------------
    def on_global_key(self):
        now = time.time()
        self.last_input = now
        self.situations.activity(now)
        if self.chat.isActiveWindow():
            return  # 대화창 타이핑은 점프 대상이 아님
        self.key_times = [t for t in self.key_times if now - t < 2.0] + [now]
        if self.state in (self.SLEEP, self.CHAT, self.DRAG, self.DIZZY, self.POUNCE) or self.game_on:
            return
        if len(self.key_times) > 14:
            self.key_times.clear()
            self._enter(self.DIZZY)
            self.say("어지러워... 너무 빨리 쳐, 냥.", 2.5)
            return
        if self.jump_enabled and self.state != self.JUMP:
            self._enter(self.JUMP)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.press_pos = e.globalPosition().toPoint()
            self.drag_offset = self.press_pos - self.frameGeometry().topLeft()
            self.dragged = False
        elif e.button() == Qt.MouseButton.RightButton:
            self._make_menu().exec(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.MouseButton.LeftButton):
            return
        gp = e.globalPosition().toPoint()
        if not self.dragged and (gp - self.press_pos).manhattanLength() < 6:
            return
        self.dragged = True
        if self.state != self.DRAG:
            self._prev_sleeping = self.state == self.SLEEP
            self.state = self.DRAG
            self.expression = "surprised"
            self.legs = "stand"
        new_top = gp - self.drag_offset
        self.x = float(new_top.x())
        self.y = float(new_top.y() + self.pad_top)
        self.y_off = 0.0
        self._sync_pos()
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.last_input = time.time()
        if self.state == self.DRAG:
            # 놓은 자리에 그대로 머문다
            self._enter(self.SLEEP if self._prev_sleeping else self.IDLE)
            if not self._prev_sleeping:
                self.expression = "normal"
            return
        # 클릭: 더블클릭 가능성 때문에 잠깐 기다렸다가 대화창. 더블클릭이면 쓰다듬기.
        self._click_timer.start(QApplication.doubleClickInterval())

    # ---------------- 쥐 잡기 게임 ----------------
    def toggle_game(self):
        if self.game_on:
            self.end_game(by_user=True)
        else:
            self.start_game()

    def start_game(self):
        if self.state == self.SLEEP:
            self.wake(greet=False)
        self.chat.hide()
        self.game_on = True
        self.score = 0
        self.missed = 0
        self.game_end = time.time() + Mouse.GAME_SEC
        self._enter(self.IDLE)
        self.say(f"쥐 잡기 시작! {int(Mouse.GAME_SEC)}초 동안 쥐를 클릭해서 멈추면 내가 덮칠게, 냥!", 4)
        QTimer.singleShot(1500, lambda: self.game_on and self.mouse.spawn(self._screen_geom()))

    def end_game(self, by_user: bool = False):
        self.game_on = False
        self.mouse.hide_mouse()
        if self.state == self.POUNCE:
            self.y_off = 0.0
            self.vy = 0.0
        self._enter(self.IDLE)
        if by_user:
            self.say(f"게임 끝. 잡은 쥐 {self.score}마리, 놓친 쥐 {self.missed}마리, 냥.", 4)
        else:
            if self.score >= 8:
                grade = "대단해! 넌 진짜 사냥꾼이다냥!"
            elif self.score >= 4:
                grade = "괜찮은데? 다음엔 더 잡자냥."
            else:
                grade = "...쥐가 너무 빨랐다냥."
            self.say(f"시간 끝! 잡은 쥐 {self.score}마리, 놓친 쥐 {self.missed}마리. {grade}", 6)
        self.last_input = time.time()

    def on_mouse_clicked(self):
        if not self.game_on or self.state in (self.SLEEP, self.DRAG):
            return
        self.last_input = time.time()
        self.mouse.stun(1.1)
        mx, my = self.mouse.center()
        self.pounce_target = (mx - self.W / 2, my - self.H / 2)
        self._enter(self.POUNCE)

    def _do_pounce(self, now: float):
        remaining = self._move_toward(self.pounce_target[0], self.pounce_target[1], 14.0)
        self.y_off += self.vy
        self.vy -= 0.8
        if self.y_off <= 0:
            self.y_off = 0.0
            self.vy = 0.0
            if remaining <= 10 and self.mouse.mode == "stunned":
                self.score += 1
                self._gain("catch")
                self.mouse.hide_mouse()
                self.expression = "excited"
                self.say(random.choice(["잡았다냥!", "냐하하, 한 마리!", "이 정도야 식은 죽 먹기다냥."]) + f" ({self.score}마리)", 1.6)
                QTimer.singleShot(random.randint(900, 1800), lambda: self.game_on and self.mouse.spawn(self._screen_geom()))
                self._enter(self.IDLE)
                self.state_until = now + 0.8
            elif remaining > 10:
                self.vy = 9.0  # 아직 못 닿았으면 한 번 더 뛴다
            else:
                self._enter(self.IDLE)
                self.state_until = now + 0.5

    def _on_mouse_gone(self):
        self.missed += 1
        self.expression = "surprised"
        self.say(random.choice(["앗, 놓쳤다냥...", "쥐가 더 빨랐어...", "다음엔 꼭 잡는다냥."]), 1.6)
        QTimer.singleShot(random.randint(700, 1500), lambda: self.game_on and self.mouse.spawn(self._screen_geom()))

    def _single_click(self):
        if self.state == self.SLEEP:
            self.wake()
            self.growth.gain("wake")
        self.open_chat()

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._click_timer.stop()
        self.pet()

    def pet(self):
        """쓰다듬기: 하트 말풍선, 친밀도 +, 가끔 성장."""
        self.last_input = time.time()
        if self.state == self.SLEEP:
            self.expression = "sleepy"
            self.say(random.choice(["...골골골 (자면서 좋아한다)", "냐암... 조금만 더..."]), 2)
            return
        gained = self.growth.gain("pet")
        self.expression = "smile"
        self.state_until = time.time() + 2.0
        if gained is None:
            return
        line = random.choice(["♥ 골골골...", "♥ 냐아옹~ 거기 좋아.", "♥ 더 해줘, 냥.", "♥ (눈을 가늘게 뜬다)", "♥ 배는 만지지 마... 아니, 조금은 돼."])
        if self.growth.last_pet and time.time() - self.growth.last_pet > 0.5:
            line = random.choice(["♥ 또? 좋아, 냥.", "♥ (꼬리로 손을 감는다)"])
        self.say(self.growth_style(line), 2.5)
        if gained:
            self._on_level_up()

    def growth_style(self, text: str) -> str:
        from growth import style
        return style(text, self.growth.tone())

    def _on_level_up(self):
        self._apply_size()
        if hasattr(self.brain, "tone"):
            self.brain.tone = self.growth.tone()
        self.expression = "excited"
        self.state_until = time.time() + 3.0
        self.say(f"나... 컸어! 이제 {self.growth.stage_name()}야, 냥! ({self.growth.days_together()}일째)", 8)

    def _gain(self, kind: str):
        if self.growth.gain(kind):
            self._on_level_up()

    # ---------------- 대화 ----------------
    def open_chat(self):
        if self.state == self.SLEEP:
            self.wake(greet=False)
        self._enter(self.CHAT)
        g = self._screen_geom()
        cx = int(self.x) + self.W // 2 - self.chat.width() // 2
        cy = int(self.y) - self.chat.height() - 24
        if cy < g.top():
            cy = int(self.y) + self.H + 24
        self.chat.move(
            max(g.left(), min(cx, g.right() - self.chat.width())),
            max(g.top(), min(cy, g.bottom() - self.chat.height())),
        )
        if not self._reply_watchdog.isActive():
            self.chat.set_busy(False)
        self.chat.show()
        self.chat.raise_()
        self.chat.activateWindow()
        self.chat.input.setFocus()
        if self.brain.name == "meow":
            self.chat.append(CAT_NAME, "(API 키가 없어서 '냐옹'만 할 수 있어. README 참고.)")

    def on_user_said(self, text: str):
        self.last_input = time.time()
        self._enter(self.CHAT)
        self.expression = "normal"
        quick = self._handle_command(text)
        if quick is not None:
            self._gain("memo")
            QTimer.singleShot(150, lambda: self.on_cat_said(self.growth_style(quick), -1))
            return
        self._gain("chat")
        self._pending_seq += 1
        seq = self._pending_seq
        log.info("user(%d): %s", seq, text)
        thread = QThread(self)
        worker = ChatWorker(self.brain, text, seq)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        # 반드시 GUI 스레드에서 처리되도록 큐 연결
        worker.done.connect(self.on_cat_said, Qt.ConnectionType.QueuedConnection)
        worker.done.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread, self._worker = thread, worker  # GC 방지
        thread.start()
        self._reply_watchdog.start(int(REPLY_TIMEOUT_SEC * 1000))

    @Slot(str, int)
    def on_cat_said(self, text: str, seq: int = -1):
        if seq >= 0 and seq != self._pending_seq:
            log.info("stale reply ignored (%s)", seq)
            return
        self._reply_watchdog.stop()
        log.info("cat: %s", text)
        try:
            self.chat.append(CAT_NAME, text)
            self.expression = "excited"
            self.say(text, min(8.0, 2.0 + len(text) * 0.08))
            QTimer.singleShot(1500, lambda: self.state == self.CHAT and setattr(self, "expression", "smile"))
        except Exception:
            log.error("on_cat_said failed\n%s", traceback.format_exc())
        finally:
            self.chat.set_busy(False)

    def _on_reply_timeout(self):
        log.warning("reply timeout (seq %d)", self._pending_seq)
        self._pending_seq += 1  # 늦게 오는 답은 버린다
        self.chat.append(CAT_NAME, "...답이 너무 늦네. 다시 말 걸어줘, 냥. (응답 시간 초과)")
        self.chat.set_busy(False)
        self.expression = "dizzy"

    def say(self, text: str, seconds: float = 4.0):
        self.bubble.say(text, self.anchor_point(), seconds, below=self.anchor_below())

    # ---------------- 메인 루프 ----------------
    def tick(self):
        now = time.time()
        cur = QCursor.pos()
        if (cur - self.last_cursor).manhattanLength() > 2:
            self.last_cursor = cur
            self.cursor_still_since = now
            self.last_input = now
            self.situations.activity(now)
            cursor_moved = True
        else:
            cursor_moved = False

        if not self.chat.isVisible() and self.state == self.CHAT:
            self._enter(self.IDLE)

        if self.growth.touch_daily():
            self._on_level_up()
        if not self.game_on and self.state != self.DRAG:
            due = self.reminder.check(now, self.situations.is_active(now))
            if due:
                if self.state == self.SLEEP:
                    self.wake(greet=False)
                self.expression = "surprised"
                self.state_until = now + 2.0
                self.say("⏰ " + due, 10)
                if self.chat.isVisible():
                    self.chat.append(CAT_NAME, "⏰ " + due)
        if self.state in (self.IDLE, self.WALK) and not self.game_on and not self.bubble.isVisible():
            hit = self.situations.check(now)
            if hit:
                text, expr = hit
                self.expression = expr
                self.state_until = now + 2.0
                self.say(text, 6)
            else:
                notice = self.notices.next(now)
                if notice:
                    self.expression = "smile"
                    self.say(notice, 8)
                else:
                    hit = self.comfort.check(now, self.situations.work_minutes(now), self.situations.is_active(now))
                    if hit:
                        text, expr = hit
                        self.expression = expr
                        self.state_until = now + 2.0
                        self.say(text, 7)

        if self.game_on:
            if now > self.game_end:
                self.end_game()
            elif self.mouse.step(now) == "gone":
                self._on_mouse_gone()
                if self.state == self.POUNCE:
                    self._enter(self.IDLE)

        if self.state == self.SLEEP:
            self.zzz_phase += 0.04
        elif self.state == self.DRAG:
            pass
        elif self.state == self.POUNCE:
            self._do_pounce(now)
        elif self.state == self.JUMP:
            self.y_off += self.vy
            self.vy -= 0.8
            if self.y_off <= 0:
                self.y_off = 0.0
                self.vy = 0.0
                self._enter(self.IDLE)
                self.state_until = now + random.uniform(0.6, 2.0)
        elif self.state == self.DIZZY:
            if now > self.state_until:
                self._enter(self.IDLE)
        elif self.state == self.CHAT:
            pass
        else:
            # IDLE / WALK / CHASE
            if self.chase_enabled and cursor_moved and self.state != self.CHASE and not self.game_on:
                self._enter(self.CHASE)
            if self.state == self.CHASE:
                self._do_chase(cur, now)
            elif self.state == self.WALK:
                self._do_walk(now)
            elif self.state == self.IDLE:
                if self.music.is_playing():
                    # 음악에 맞춰 발을 구른다
                    self.walk_phase += 1
                    self.legs = "walk1" if (self.walk_phase // 9) % 2 == 0 else "walk2"
                    if self.expression == "normal":
                        self.expression = "smile"
                if now > self.state_until:
                    self._enter(random.choice([self.WALK, self.WALK, self.IDLE]))
                if now > self.blink_until and random.random() < 0.01:
                    self.blink_until = now + 0.15
            if now - self.last_input > AUTO_SLEEP_SEC and not self.game_on:
                self.sleep()

        self._sync_pos()
        self.update()

    def _do_chase(self, cur: QPoint, now: float):
        g = self._screen_geom(cur)
        # 커서를 가리지 않도록 커서 바로 아래쪽에 선다
        tx = max(g.left(), min(cur.x() - self.W // 2, g.right() - self.W + 1))
        ty = max(g.top(), min(cur.y() + 12, g.bottom() - self.H + 1))
        if math.hypot(tx - self.x, ty - self.y) > 6:
            self._move_toward(tx, ty, 5.0)
            self.walk_phase += 1
            self.legs = "walk1" if (self.walk_phase // 5) % 2 == 0 else "walk2"
            self.expression = "excited"
        else:
            self.legs = "stand"
            self.expression = "smile"
        # 커서가 멈춘 채 2초 지나면 관심을 잃는다
        if now - self.cursor_still_since > 2.0:
            self._enter(self.IDLE)

    def _do_walk(self, now: float):
        if self.target is None or now > self.state_until:
            self._enter(self.IDLE)
            return
        if self._move_toward(self.target[0], self.target[1], 1.6) <= 0:
            self._enter(self.IDLE)
            return
        self.walk_phase += 1
        self.legs = "walk1" if (self.walk_phase // 8) % 2 == 0 else "walk2"

    # ---------------- 그리기 ----------------
    def paintEvent(self, _e):
        p = QPainter(self)
        expr = self.expression
        if self.state == self.IDLE and time.time() < self.blink_until:
            expr = "blink"
        pm = sprites.pixmap(expr, self.legs, self.scale, self.facing_left, baby=(self.growth.stage == 0))
        p.drawPixmap(0, self.pad_top, pm)
        if self.state == self.SLEEP:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            f = QFont()
            f.setBold(True)
            for i, (size, dx) in enumerate(((10, 0), (13, 10), (16, 22))):
                phase = (self.zzz_phase + i * 0.9) % 3.0
                f.setPointSize(size)
                p.setFont(f)
                alpha = int(255 * max(0.0, 1.0 - phase / 3.0))
                p.setPen(QColor(43, 43, 43, alpha))
                x = self.W - 24 + dx + int(math.sin(phase * 2) * 4)
                y = self.pad_top - 4 - int(phase * 14)
                p.drawText(x, y, "z")
        p.end()

    # ---------------- 종료 ----------------
    def quit(self):
        self.keys.stop()
        self.music.stop()
        self.memo.hide()
        self.mouse.hide()
        self.bubble.hide()
        self.chat.close()
        self.tray.hide()
        QApplication.quit()


def main():
    sys.excepthook = lambda t, v, tb: log.error("uncaught: %s", "".join(traceback.format_exception(t, v, tb)))
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    scale = int(os.environ.get("CAT_SCALE", "6"))
    cat = Cat(scale=scale)
    print(f"[cat] 두뇌: {cat.brain.name}, 전역 키 감지: {cat.keys.available}")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

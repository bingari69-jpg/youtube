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

HERE = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    filename=os.path.join(HERE, "cat.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("cat")

CAT_NAME = os.environ.get("CAT_NAME", "먹물")
REPLY_TIMEOUT_SEC = float(os.environ.get("CAT_REPLY_TIMEOUT_SEC", "90"))
TICK_MS = 33  # 약 30fps
AUTO_SLEEP_SEC = float(os.environ.get("CAT_AUTO_SLEEP_SEC", "180"))


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
        self._font = QFont()
        self._font.setPointSize(10)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def say(self, text: str, anchor: QPoint, seconds: float = 4.0):
        self._text = text
        fm = self.fontMetrics()
        rect = fm.boundingRect(QRect(0, 0, 220, 1000), Qt.TextFlag.TextWordWrap, text)
        w, h = rect.width() + 24, rect.height() + 18 + 8
        self.resize(w, h)
        x = anchor.x() - w // 2
        y = anchor.y() - h - 4
        scr = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        x = max(g.left(), min(x, g.right() - w))
        y = max(g.top(), y)
        self.move(x, y)
        self.show()
        self.update()
        self._hide_timer.start(int(seconds * 1000))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRect(0, 0, self.width(), self.height() - 8)
        path = QPainterPath()
        path.addRoundedRect(body, 10, 10)
        cx = self.width() // 2
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
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)

        # 제목줄
        title = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(sprites.pixmap("smile", "stand", 2))
        name = QLabel(CAT_NAME)
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        name.setFont(f)
        name.setStyleSheet("color: #2b2b2b;")
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            "QPushButton{border:none;border-radius:13px;background:transparent;color:#8a877f;font-size:18px;}"
            "QPushButton:hover{background:#f1efe8;color:#2b2b2b;}"
        )
        self.close_btn.clicked.connect(self.hide)
        title.addWidget(icon)
        title.addSpacing(4)
        title.addWidget(name)
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
        self.vbox.addStretch()
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
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 44:
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
        self.vbox.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight if mine else Qt.AlignmentFlag.AlignLeft)
        QTimer.singleShot(0, self._scroll_bottom)

    def set_busy(self, busy: bool):
        self.input.setEnabled(not busy)
        self.btn.setEnabled(not busy)
        if busy:
            if self._typing is None:
                self._typing = TypingBubble()
                self.vbox.addWidget(self._typing, 0, Qt.AlignmentFlag.AlignLeft)
                QTimer.singleShot(0, self._scroll_bottom)
        else:
            self._remove_typing()
            self.input.setFocus()

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
# 고양이 본체
# ----------------------------------------------------------------------------
class Cat(QWidget):
    IDLE, WALK, CHASE, JUMP, SLEEP, DIZZY, CHAT, DRAG = range(8)

    def __init__(self, scale: int = 6):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.scale = scale
        self.W = sprites.GRID_W * scale
        self.H = sprites.GRID_H * scale
        # 위쪽에 점프/Zzz 여유 공간을 둔다
        self.pad_top = self.H
        self.resize(self.W, self.H + self.pad_top)

        self.state = self.IDLE
        self.expression = "normal"
        self.legs = "stand"
        self.facing_left = False
        self.x = 0.0
        self.y_off = 0.0  # 바닥 기준 위로 띄운 높이(점프용)
        self.vy = 0.0
        self.target_x: float | None = None
        self.state_until = 0.0
        self.walk_phase = 0
        self.last_input = time.time()
        self.last_cursor = QCursor.pos()
        self.cursor_still_since = time.time()
        self.key_times: list[float] = []
        self.blink_until = 0.0
        self.zzz_phase = 0.0
        self.chase_enabled = True
        self.jump_enabled = True
        self.drag_offset = QPoint()
        self.press_pos = QPoint()
        self.dragged = False
        self._prev_sleeping = False

        self.brain = make_brain(CAT_NAME)
        self.bubble = Bubble()
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
        QTimer.singleShot(600, lambda: self.say(f"안녕, 나는 {CAT_NAME}이야. 냐옹.", 3))

    # ---------------- 화면/위치 ----------------
    def _screen_geom(self, at: QPoint | None = None) -> QRect:
        pt = at or QPoint(int(self.x) + self.W // 2, self.y())
        scr = QGuiApplication.screenAt(pt) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()

    def _place_on_floor(self):
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.x = g.right() - self.W - 80
        self._sync_pos()

    def _floor_y(self, g: QRect) -> int:
        return g.bottom() - self.H + 1

    def _sync_pos(self):
        g = self._screen_geom()
        self.x = max(g.left(), min(self.x, g.right() - self.W + 1))
        top = self._floor_y(g) - int(self.y_off) - self.pad_top
        self.move(int(self.x), top)

    def anchor_point(self) -> QPoint:
        return QPoint(int(self.x) + self.W // 2, self._floor_y(self._screen_geom()) - int(self.y_off))

    # ---------------- 트레이 ----------------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(sprites.pixmap("normal", "stand", 4)), self)
        self.tray.setToolTip(f"{CAT_NAME} (데스크톱 고양이)")
        self.tray.setContextMenu(self._make_menu())
        self.tray.activated.connect(
            lambda r: self.open_chat() if r == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    def _make_menu(self) -> QMenu:
        m = QMenu()
        m.addAction("대화하기", self.open_chat)
        self.act_sleep = QAction("재우기", m)
        self.act_sleep.triggered.connect(self.toggle_sleep)
        m.addAction(self.act_sleep)
        m.addSeparator()
        a = QAction("마우스 따라가기", m, checkable=True, checked=self.chase_enabled)
        a.toggled.connect(lambda v: setattr(self, "chase_enabled", v))
        m.addAction(a)
        b = QAction("키보드 점프", m, checkable=True, checked=self.jump_enabled)
        b.toggled.connect(lambda v: setattr(self, "jump_enabled", v))
        m.addAction(b)
        size = m.addMenu("크기")
        for label, s in (("작게", 4), ("보통", 6), ("크게", 9)):
            size.addAction(label, lambda s=s: self.set_scale(s))
        m.addSeparator()
        m.addAction("대화 기억 지우기", self.brain.reset)
        m.addAction("종료", self.quit)
        return m

    def set_scale(self, s: int):
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
            self.target_x = random.uniform(g.left(), g.right() - self.W)
            self.expression = "normal"
            self.state_until = now + 20
        elif state == self.CHASE:
            self.expression = "excited"
        elif state == self.JUMP:
            self.vy = 11.0
            self.expression = "surprised"
            self.legs = "stand"
        elif state == self.SLEEP:
            self.expression = "sleepy"
            self.legs = "sit"
            self.target_x = None
            self.act_sleep.setText("깨우기")
        elif state == self.DIZZY:
            self.expression = "dizzy"
            self.state_until = now + (duration or 2.5)
        elif state == self.CHAT:
            self.expression = "smile"
            self.legs = "stand"
        if state != self.SLEEP:
            self.act_sleep.setText("재우기")
        self.update()

    def toggle_sleep(self):
        if self.state == self.SLEEP:
            self.wake()
        else:
            self.sleep()

    def sleep(self):
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
        if self.chat.isActiveWindow():
            return  # 대화창 타이핑은 점프 대상이 아님
        self.key_times = [t for t in self.key_times if now - t < 2.0] + [now]
        if self.state in (self.SLEEP, self.CHAT, self.DRAG, self.DIZZY):
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
        self.x = new_top.x()
        g = self._screen_geom(gp)
        lift = self._floor_y(g) - self.pad_top - new_top.y()
        self.y_off = max(0.0, float(lift))
        self._sync_pos()
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.last_input = time.time()
        if self.state == self.DRAG:
            if getattr(self, "_prev_sleeping", False):
                self._enter(self.SLEEP)
            else:
                self.vy = 0.0
                self._enter(self.JUMP)  # 떨어지는 연출
                self.expression = "normal"
            return
        # 클릭: 깨우고 대화창 열기
        if self.state == self.SLEEP:
            self.wake()
        self.open_chat()

    # ---------------- 대화 ----------------
    def open_chat(self):
        if self.state == self.SLEEP:
            self.wake(greet=False)
        self._enter(self.CHAT)
        g = self._screen_geom()
        cx = int(self.x) + self.W // 2 - self.chat.width() // 2
        cy = self._floor_y(g) - self.chat.height() - 24
        self.chat.move(max(g.left(), min(cx, g.right() - self.chat.width())), max(g.top(), cy))
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
        self.bubble.say(text, self.anchor_point(), seconds)

    # ---------------- 메인 루프 ----------------
    def tick(self):
        now = time.time()
        cur = QCursor.pos()
        if (cur - self.last_cursor).manhattanLength() > 2:
            self.last_cursor = cur
            self.cursor_still_since = now
            self.last_input = now
            cursor_moved = True
        else:
            cursor_moved = False

        if not self.chat.isVisible() and self.state == self.CHAT:
            self._enter(self.IDLE)

        if self.state == self.SLEEP:
            self.zzz_phase += 0.04
        elif self.state == self.DRAG:
            pass
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
            if self.chase_enabled and cursor_moved and self.state != self.CHASE:
                self._enter(self.CHASE)
            if self.state == self.CHASE:
                self._do_chase(cur, now)
            elif self.state == self.WALK:
                self._do_walk(now)
            elif self.state == self.IDLE:
                if now > self.state_until:
                    self._enter(random.choice([self.WALK, self.WALK, self.IDLE]))
                if now > self.blink_until and random.random() < 0.01:
                    self.blink_until = now + 0.15
            if now - self.last_input > AUTO_SLEEP_SEC:
                self.sleep()

        self._sync_pos()
        self.update()

    def _do_chase(self, cur: QPoint, now: float):
        g = self._screen_geom(cur)
        tx = cur.x() - self.W // 2
        tx = max(g.left(), min(tx, g.right() - self.W + 1))
        dx = tx - self.x
        if abs(dx) > 6:
            step = min(abs(dx), 5.0)
            self.x += step if dx > 0 else -step
            self.facing_left = dx < 0
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
        if self.target_x is None or now > self.state_until:
            self._enter(self.IDLE)
            return
        dx = self.target_x - self.x
        if abs(dx) < 2:
            self._enter(self.IDLE)
            return
        step = min(abs(dx), 1.6)
        self.x += step if dx > 0 else -step
        self.facing_left = dx < 0
        self.walk_phase += 1
        self.legs = "walk1" if (self.walk_phase // 8) % 2 == 0 else "walk2"

    # ---------------- 그리기 ----------------
    def paintEvent(self, _e):
        p = QPainter(self)
        expr = self.expression
        if self.state == self.IDLE and time.time() < self.blink_until:
            expr = "blink"
        pm = sprites.pixmap(expr, self.legs, self.scale, self.facing_left)
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

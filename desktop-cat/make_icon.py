"""고양이 스프라이트로 cat.ico / cat.png 를 만든다. (build_exe.bat 이 호출)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402

import sprites  # noqa: E402

app = QGuiApplication([])
here = os.path.dirname(os.path.abspath(__file__))
# 16칸 x 14칸 격자를 256x256 정사각형 안에 가운데 배치
scale = 16
w, h = sprites.GRID_W * scale, sprites.GRID_H * scale
img = QImage(256, 256, QImage.Format.Format_ARGB32)
img.fill(Qt.GlobalColor.transparent)
p = QPainter(img)
p.drawPixmap((256 - w) // 2, (256 - h) // 2, sprites.pixmap("smile", "stand", scale))
p.end()
img.save(os.path.join(here, "cat.png"))
ok = img.save(os.path.join(here, "cat.ico"))
print("icon:", "ok" if ok else "failed")

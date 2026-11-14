"""내장 음악 재생. music/ 폴더의 mp3, wav, ogg, m4a, flac 파일을 목록으로 만든다.

Qt Multimedia(FFmpeg 백엔드)를 쓴다. 오디오 장치가 없거나 모듈이 없어도 프로그램은 죽지 않는다.
"""

from __future__ import annotations

import os
import random

from PySide6.QtCore import QObject, QUrl, Signal

HERE = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(HERE, "music")
EXTS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    _AVAILABLE = True
except Exception:  # 모듈이 빠진 빌드
    _AVAILABLE = False


class MusicPlayer(QObject):
    track_changed = Signal(str)  # 곡 제목
    stopped = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.tracks: list[str] = []
        self.index = -1
        self.shuffle = bool(settings.get("music_shuffle", True))
        self.available = _AVAILABLE
        self._player = None
        self._out = None
        self.rescan()
        if not _AVAILABLE:
            return
        try:
            self._out = QAudioOutput()
            self._out.setVolume(int(settings.get("music_volume", 40)) / 100)
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._out)
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.errorOccurred.connect(lambda *_: self.stopped.emit())
        except Exception:
            self.available = False

    # ---- 목록 ----
    def rescan(self):
        try:
            names = sorted(f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(EXTS))
        except OSError:
            names = []
        self.tracks = [os.path.join(MUSIC_DIR, n) for n in names]
        if self.index >= len(self.tracks):
            self.index = -1

    @staticmethod
    def title_of(path: str) -> str:
        return os.path.splitext(os.path.basename(path))[0]

    def titles(self) -> list[str]:
        return [self.title_of(p) for p in self.tracks]

    # ---- 재생 ----
    def is_playing(self) -> bool:
        return bool(self._player) and self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def current_title(self) -> str | None:
        return self.title_of(self.tracks[self.index]) if 0 <= self.index < len(self.tracks) else None

    def play_index(self, i: int):
        if not self.available or not self.tracks:
            return
        self.index = i % len(self.tracks)
        path = self.tracks[self.index]
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        self.settings.set("music_last", os.path.basename(path))
        self.track_changed.emit(self.title_of(path))

    def play(self):
        if not self.available or not self.tracks:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self._player.play()
            return
        if self.index < 0:
            last = self.settings.get("music_last")
            names = [os.path.basename(p) for p in self.tracks]
            start = names.index(last) if last in names else (random.randrange(len(self.tracks)) if self.shuffle else 0)
            self.play_index(start)
        else:
            self.play_index(self.index)

    def pause(self):
        if self._player:
            self._player.pause()

    def toggle(self):
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def stop(self):
        if self._player:
            self._player.stop()
        self.stopped.emit()

    def next(self):
        if not self.tracks:
            return
        if self.shuffle and len(self.tracks) > 1:
            choices = [i for i in range(len(self.tracks)) if i != self.index]
            self.play_index(random.choice(choices))
        else:
            self.play_index(self.index + 1)

    def prev(self):
        if self.tracks:
            self.play_index(self.index - 1)

    def set_volume(self, percent: int):
        percent = max(0, min(100, int(percent)))
        self.settings.set("music_volume", percent)
        if self._out:
            self._out.setVolume(percent / 100)

    def volume(self) -> int:
        return int(self.settings.get("music_volume", 40))

    def set_shuffle(self, on: bool):
        self.shuffle = bool(on)
        self.settings.set("music_shuffle", self.shuffle)

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if len(self.tracks) > 1:
                self.next()
            else:
                self.play_index(self.index)

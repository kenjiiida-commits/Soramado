"""画面の画像保存と動画の録画。

動画は ffmpeg に1コマずつ画像を渡して MP4（H.264）にする。
録画中は「1コマ = 1/30秒」として時間やカメラの動きを進めるので、
パソコンの描画が遅くても、できあがる動画はなめらかになる。
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage

FPS = 30


def _folder(kind) -> Path:
    base = QStandardPaths.writableLocation(kind) or str(Path.home())
    p = Path(base) / "Soramado"
    p.mkdir(parents=True, exist_ok=True)
    return p


def picture_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _folder(QStandardPaths.PicturesLocation) / f"soramado_{stamp}.png"


def video_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _folder(QStandardPaths.MoviesLocation) / f"soramado_{stamp}.mp4"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


class VideoRecorder:
    def __init__(self, path: Path, width: int, height: int):
        # H.264 は縦横が偶数である必要があるので、そろえておく
        self.w, self.h = width - width % 2, height - height % 2
        self.path = path
        self.frames = 0
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb0", "-s", f"{self.w}x{self.h}", "-r", str(FPS), "-i", "-",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(path)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def add(self, img: QImage) -> bool:
        if self.proc.poll() is not None:
            return False
        img = img.convertToFormat(QImage.Format_RGBX8888)
        if img.width() != self.w or img.height() != self.h:
            # 録画中にウィンドウの大きさが変わっても、最初の大きさにそろえる
            img = img.scaled(self.w, self.h)
        data = bytes(img.constBits())[: self.w * self.h * 4]
        try:
            self.proc.stdin.write(data)
        except (BrokenPipeError, OSError):
            return False
        self.frames += 1
        return True

    @property
    def seconds(self) -> float:
        return self.frames / FPS

    def finish(self) -> tuple[bool, str]:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        self.proc.wait(timeout=120)
        err = self.proc.stderr.read().decode("utf-8", "replace") if self.proc.stderr else ""
        ok = self.proc.returncode == 0 and self.path.is_file() and self.frames > 0
        return ok, err

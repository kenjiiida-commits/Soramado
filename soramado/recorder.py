"""画面の画像保存と動画の録画。

動画は ffmpeg に1コマずつ画像を渡して MP4（H.264）にする。
録画中は「1コマ = 1/30秒」として時間やカメラの動きを進めるので、
パソコンの描画が遅くても、できあがる動画はなめらかになる。

BGM は録画中には鳴らさず、「何秒目からどの曲」を覚えておいて、
録画を終えたあとに ffmpeg で動画に重ねる（映像は作り直さない）。
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
        self.music: list[tuple[float, str | None]] = []   # (動画の何秒目から, 曲のファイル。None は止める)
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

    def set_music(self, path: str | None):
        """いまの場面から流す曲を変える（None で止める）。"""
        t = self.seconds
        while self.music and self.music[-1][0] >= t - 1e-6:
            self.music.pop()           # 同じ瞬間に続けて変えたときは、最後のものだけ
        if (self.music[-1][1] if self.music else None) != path:
            self.music.append((t, path))

    def finish(self) -> tuple[bool, str]:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        self.proc.wait(timeout=120)
        err = self.proc.stderr.read().decode("utf-8", "replace") if self.proc.stderr else ""
        ok = self.proc.returncode == 0 and self.path.is_file() and self.frames > 0
        self.music_error = ""
        if ok and any(f for _, f in self.music):
            self.music_error = add_music(self.path, self.music, self.seconds)
        return ok, err


def music_filter(segments, total: float, fade_end: float = 3.0):
    """曲の区切り [(開始秒, ファイル)] から、ffmpeg の入力ファイルと filter_complex を作る。
    曲が短ければくり返し、最後は fade_end 秒かけて小さくする。曲を変えるところは短くつなぐ。"""
    files, parts = [], []
    segs = [(t, f) for t, f in segments if t < total - 0.05]
    for k, (t0, f) in enumerate(segs):
        if not f:
            continue
        t1 = segs[k + 1][0] if k + 1 < len(segs) else total
        dur = t1 - t0
        if dur <= 0.05:
            continue
        last = k + 1 >= len(segs)
        fo = min(fade_end if last else 0.8, dur / 2)
        fi = 0.0 if t0 < 0.05 else min(0.3, dur / 4)
        j = len(files) + 1                  # 0 番は動画
        files.append(f)
        ms = int(round(t0 * 1000))
        chain = (f"[{j}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                 + (f"afade=t=in:d={fi:.3f}," if fi > 0 else "")
                 + f"afade=t=out:st={max(0.0, dur - fo):.3f}:d={fo:.3f},adelay={ms}:all=1[a{len(parts)}]")
        parts.append(chain)
    if not parts:
        return [], ""
    n = len(parts)
    mix = "".join(f"[a{i}]" for i in range(n))
    tail = f"{mix}amix=inputs={n}:normalize=0:dropout_transition=0,apad[out]" if n > 1 else "[a0]apad[out]"
    return files, ";".join(parts) + ";" + tail


def add_music(path: Path, segments, total: float) -> str:
    """録画した動画に BGM を重ねる。うまくいけば ""、だめなら理由（動画は音なしのまま残す）。"""
    files, graph = music_filter(segments, total)
    if not files:
        return ""
    for f in files:
        if not Path(f).is_file():
            return f"曲のファイルが見つかりません: {f}"
    tmp = path.with_name(path.stem + "_bgm.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path)]
    for f in files:
        cmd += ["-stream_loop", "-1", "-i", str(f)]
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[out]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(tmp)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if r.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return r.stderr.decode("utf-8", "replace")[-600:]
    tmp.replace(path)
    return ""

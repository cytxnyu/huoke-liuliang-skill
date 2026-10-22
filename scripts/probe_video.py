#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一条视频变成「带时间戳的画面证据」。

用途：抽帧后直接读画面里的字幕、封面、前后对比，拼出口播稿与证据链。
不转写音频、不识别身份、不判断内容好坏。

用法：
    python probe_video.py 视频.mp4 --out frames --count 12
    python probe_video.py 视频.mp4 --out frames --interval 2.5
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if not sys.stdout.isatty():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        sys.exit(f"找不到 {binary}。请先安装 FFmpeg，并确保它在 PATH 中。")
    return path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def probe(path: Path) -> dict:
    result = run(
        [
            require("ffprobe"),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    if result.returncode != 0:
        sys.exit(f"ffprobe 读取失败：{result.stderr.strip()}")

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    video = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    if video is None:
        sys.exit("这个文件里没有视频流，抽帧没有意义。")

    duration = fmt.get("duration") or video.get("duration") or "0"
    return {
        "duration": float(duration),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": video.get("r_frame_rate", "unknown"),
        "codec": video.get("codec_name", "unknown"),
        "has_audio": any(
            s.get("codec_type") == "audio" for s in data.get("streams", [])
        ),
    }


def timestamps(duration: float, count: int | None, interval: float | None) -> list[float]:
    if duration <= 0:
        return [0.0]
    if interval:
        step = max(interval, 0.2)
        marks, t = [], step / 2
        while t < duration:
            marks.append(round(t, 2))
            t += step
        return marks or [0.0]
    count = max(int(count or 12), 1)
    return [round(duration * (i + 0.5) / count, 2) for i in range(count)]


def main() -> int:
    parser = argparse.ArgumentParser(description="抽帧并输出时间戳，供读字幕与画面")
    parser.add_argument("video", type=Path, help="视频文件路径")
    parser.add_argument("--out", type=Path, required=True, help="帧输出目录")
    parser.add_argument("--count", type=int, default=12, help="均匀抽帧张数，默认 12")
    parser.add_argument("--interval", type=float, default=None, help="按秒数间隔抽帧，优先于 --count")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    if not args.video.is_file():
        sys.exit(f"文件不存在：{args.video}")

    info = probe(args.video)
    args.out.mkdir(parents=True, exist_ok=True)
    marks = timestamps(info["duration"], args.count, args.interval)

    ffmpeg = require("ffmpeg")
    frames = []
    for index, second in enumerate(marks, start=1):
        target = args.out / f"frame_{index:02d}_{second:06.2f}s.jpg"
        result = run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-ss", f"{second:.2f}",
                "-i", str(args.video),
                "-frames:v", "1",
                "-q:v", "3",
                str(target),
            ]
        )
        frames.append(
            {
                "index": index,
                "seconds": second,
                "file": str(target) if target.exists() else None,
                "ok": target.exists() and result.returncode == 0,
            }
        )

    payload = {
        "video": str(args.video.resolve()),
        "duration": round(info["duration"], 2),
        "size": f'{info["width"]}x{info["height"]}',
        "fps": info["fps"],
        "has_audio": info["has_audio"],
        "frame_count": len(frames),
        "frames": frames,
        "notes": [
            "抽帧只给画面，不给台词；有字幕的视频可以靠帧读出口播内容。",
            "字幕密集时用 --interval 2 提高密度，避免漏读整句。",
            "静帧不等于听懂了音频，需要语气和停顿时要口播稿或字幕文件。",
        ],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f'视频：{payload["video"]}')
        print(f'时长：{payload["duration"]}s  尺寸：{payload["size"]}  帧率：{payload["fps"]}')
        print(f'抽帧：{len(frames)} 张 → {args.out.resolve()}')
        for frame in frames:
            print(f'  {frame["index"]:>2}. {frame["seconds"]:>6.2f}s  {frame["file"] or "失败"}')
        print("提示：读画面里的字幕即可拼出口播稿；没有字幕请索取文字稿。")

    failed = [f for f in frames if not f["ok"]]
    return 1 if failed and len(failed) == len(frames) else 0


if __name__ == "__main__":
    raise SystemExit(main())

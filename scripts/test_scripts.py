#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三个脚本的自测。标准库 unittest，无第三方依赖。

    python test_scripts.py -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HERE / script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV,
    )


GOOD_SCRIPT = """# 脚本

## 格 1 · 钩子（0–3s）
漏尿不是月子病，是盆底没练。

## 格 2 · 痛点（3–8s）
咳嗽一下、抱孩子上楼就漏，很多人以为忍忍就好。

## 格 3 · 误区（8–20s）
第一个错误是先减肥不练盆底，第二个是直接上卷腹。

## 格 4 · 解决思路（20–45s）
先自测，再练盆底，最后才减脂。

## 格 5 · 留资（45–55s）
我做了张自测表，三个动作照着做就知道自己在第几步，评论区扣「自测」。
"""

LONG_HOOK = GOOD_SCRIPT.replace(
    "漏尿不是月子病，是盆底没练。",
    "我做自媒体已经整整三年了，今天想跟大家聊一聊我的一些真实感受和想法。",
)

NO_TAIL = GOOD_SCRIPT.split("## 格 5")[0]

BANNED_WORD = GOOD_SCRIPT.replace("先自测，再练盆底，最后才减脂。", "保证有效，无副作用，永久有效。")


class LintTest(unittest.TestCase):
    def check(self, text: str) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        try:
            result = run("lint_script.py", path, "--json")
            return json.loads(result.stdout)
        finally:
            os.unlink(path)

    def test_good_script_passes(self) -> None:
        report = self.check(GOOD_SCRIPT)
        self.assertEqual(report["status"], "pass", report)

    def test_long_hook_fails(self) -> None:
        report = self.check(LONG_HOOK)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(r["item"] == "钩子时长" and r["level"] == "FAIL" for r in report["results"]))

    def test_missing_tail_fails(self) -> None:
        report = self.check(NO_TAIL)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("缺格 5" in r["detail"] for r in report["results"]))

    def test_banned_words_fail(self) -> None:
        report = self.check(BANNED_WORD)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(r["item"] == "合规用词" and r["level"] == "FAIL" for r in report["results"]))

    def test_exit_code_matches_status(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(LONG_HOOK)
            path = fh.name
        try:
            self.assertEqual(run("lint_script.py", path).returncode, 1)
        finally:
            os.unlink(path)


class DiagnoseTest(unittest.TestCase):
    def call(self, *args: str) -> tuple[int, dict]:
        result = run("diagnose_metrics.py", *args, "--json")
        return result.returncode, json.loads(result.stdout)

    def test_requires_baseline(self) -> None:
        code, payload = self.call("--impressions", "12000", "--views", "1080", "--duration", "55")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "need_baseline")

    def test_low_ctr_blames_cover(self) -> None:
        code, payload = self.call(
            "--impressions", "12000", "--views", "480", "--duration", "55",
            "--avg-watch", "20", "--baseline-ctr", "0.09", "--baseline-completion", "0.3",
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["verdict"]["layer"], "点击")

    def test_low_completion_blames_opening(self) -> None:
        code, payload = self.call(
            "--impressions", "12000", "--views", "1080", "--avg-watch", "6.4",
            "--duration", "55", "--baseline-ctr", "0.09", "--baseline-completion", "0.28",
        )
        self.assertEqual(payload["verdict"]["layer"], "看完")

    def test_no_inquiry_blames_missing_offer(self) -> None:
        code, payload = self.call(
            "--impressions", "12000", "--views", "1080", "--avg-watch", "20",
            "--duration", "55", "--likes", "42", "--saves", "18",
            "--inquiries", "0", "--baseline-ctr", "0.09", "--baseline-completion", "0.3",
        )
        self.assertEqual(payload["verdict"]["layer"], "咨询")

    def test_no_close_blames_pricing(self) -> None:
        code, payload = self.call(
            "--impressions", "12000", "--views", "1080", "--avg-watch", "20",
            "--duration", "55", "--inquiries", "6", "--closes", "0",
            "--baseline-ctr", "0.09", "--baseline-completion", "0.3",
        )
        self.assertEqual(payload["verdict"]["layer"], "成交")

    def test_single_verdict_only(self) -> None:
        code, payload = self.call(
            "--impressions", "12000", "--views", "480", "--avg-watch", "3",
            "--duration", "55", "--inquiries", "0",
            "--baseline-ctr", "0.09", "--baseline-completion", "0.3",
        )
        self.assertIn("layer", payload["verdict"])
        self.assertEqual(payload["verdict"]["layer"], "点击", "优先归因最上游的那一层")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 FFmpeg")
class ProbeTest(unittest.TestCase):
    def test_extracts_frames_with_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "t.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "testsrc=size=320x240:rate=10:duration=4",
                 "-pix_fmt", "yuv420p", str(video)],
                check=True, capture_output=True,
            )
            out = Path(tmp) / "frames"
            result = run("probe_video.py", str(video), "--out", str(out), "--count", "4", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["frame_count"], 4)
            self.assertGreater(payload["duration"], 3)
            self.assertTrue(all(f["seconds"] > 0 for f in payload["frames"]))
            self.assertTrue(all(f["ok"] for f in payload["frames"]))
            self.assertEqual(len(list(out.glob("*.jpg"))), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脚本体检：五格齐不齐、钩子超没超 3 秒、结尾有没有留资、有没有踩合规词。

只做机械检查，不管文笔，也不判断选题好坏。

用法：
    python lint_script.py script.md
    python lint_script.py script.md --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if not sys.stdout.isatty():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CHARS_PER_SECOND = (4.2, 4.8)
HOOK_SECONDS = 3
HOOK_HARD_MAX = 20
HOOK_SOFT_MAX = 14

# 只放真正的违规/夸大说法。"第一步""第二天"这类正常用法不在表内。
BANNED = (
    "最好", "最强", "最佳", "全国第一", "行业第一", "销量第一", "第一名",
    "唯一选择", "顶级", "国家级", "保证有效", "保证瘦", "必瘦", "必赚",
    "稳赚", "躺赚", "立刻见效", "立竿见影", "无副作用", "根治", "永久有效",
    "百分之百", "100%", "三天见效", "包过", "保过", "绝对有效", "全网最", "史上最",
)

ACTION_VERBS = ("扣", "私", "搜", "领", "评", "留言", "主页", "评论区")
STRONG_VERBS = ("扣", "私", "搜", "领", "评", "留言")

SECTION = re.compile(r"^[#>\-\*\s]*(?:【)?格\s*([1-5])(?!\d)", re.MULTILINE)


def spoken_length(text: str) -> int:
    """口播字数：汉字 + 字母数字，标点不计。"""
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def split_sections(text: str) -> dict[int, str]:
    marks = list(SECTION.finditer(text))
    sections: dict[int, str] = {}
    for i, match in enumerate(marks):
        number = int(match.group(1))
        start = match.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end]
        # 去掉同一行的标题残留
        body = re.sub(r"^[^）)\n]*[）)]\s*", "", body, count=1)
        sections.setdefault(number, body.strip())
    return sections


def lint(text: str) -> dict:
    sections = split_sections(text)
    results: list[dict] = []

    def add(level: str, item: str, detail: str) -> None:
        results.append({"level": level, "item": item, "detail": detail})

    missing = [n for n in range(1, 6) if n not in sections]
    if missing:
        add("FAIL", "五格完整", f"缺格 {', '.join(map(str, missing))}")
    else:
        add("PASS", "五格完整", "格 1–5 都在")

    hook = sections.get(1, "")
    if 1 in sections:
        length = spoken_length(hook)
        seconds_low = length / CHARS_PER_SECOND[1]
        seconds_high = length / CHARS_PER_SECOND[0]
        detail = f"{length} 字，约 {seconds_low:.1f}–{seconds_high:.1f} 秒"
        if length > HOOK_HARD_MAX:
            add("FAIL", "钩子时长", detail + f"，超过 {HOOK_SECONDS} 秒上限")
        elif length > HOOK_SOFT_MAX:
            add("WARN", "钩子时长", detail + f"，建议压到 {HOOK_SOFT_MAX} 字内")
        else:
            add("PASS", "钩子时长", detail)

    hits = sorted({word for word in BANNED if word in text})
    if hits:
        add("FAIL", "合规用词", "命中禁用说法：" + "、".join(hits) + "（改成第一人称记录口径）")
    else:
        add("PASS", "合规用词", "未命中夸大或绝对化说法")

    tail = sections.get(5, "")
    if 5 in sections:
        strong = [v for v in STRONG_VERBS if v in tail]
        weak = [v for v in ACTION_VERBS if v in tail and v not in strong]
        if not strong and not weak:
            add("FAIL", "留资动作", "格 5 没有明确动作动词（扣/私/搜/领/评/留言）")
        elif len(set(strong)) > 1:
            add("WARN", "留资动作", "出现多个动作：" + "、".join(strong) + "，只保留一个")
        else:
            add("PASS", "留资动作", "动作：" + (strong or weak)[0])

    failed = [r for r in results if r["level"] == "FAIL"]
    return {
        "status": "fail" if failed else "pass",
        "counts": {
            "pass": sum(r["level"] == "PASS" for r in results),
            "warn": sum(r["level"] == "WARN" for r in results),
            "fail": len(failed),
        },
        "results": results,
        "next": "先修 FAIL 项，再处理 WARN；PASS 项不用动。" if failed else "可以进入拍摄。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="五格脚本机械体检")
    parser.add_argument("script", type=Path, help="脚本文件（md / txt）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    if not args.script.is_file():
        sys.exit(f"文件不存在：{args.script}")

    raw = args.script.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit("无法识别文件编码，请转成 UTF-8。")

    payload = lint(text)
    payload["file"] = str(args.script.resolve())

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f'体检：{payload["file"]}')
        for item in payload["results"]:
            print(f'  [{item["level"]}] {item["item"]}：{item["detail"]}')
        print(f'结论：{payload["status"]}　下一步：{payload["next"]}')

    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

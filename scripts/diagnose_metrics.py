#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把后台数据归因到**单一卡点**，避免一次改三处。

不做绝对阈值判断：所有比较都相对你自己的基线（近 30 天同形态内容中位数）。
没有基线时拒绝下结论，只报指标并要求采集基线。

用法：
    python diagnose_metrics.py --impressions 12000 --views 1080 \
        --avg-watch 6.4 --duration 55 --inquiries 2 \
        --baseline-ctr 0.092 --baseline-completion 0.28
"""
from __future__ import annotations

import argparse
import json
import sys

if not sys.stdout.isatty():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

THRESHOLD = 0.8  # 低于基线的 80% 才算异常

ACTION_VERBS = ("扣", "私", "搜", "领", "评", "留言")


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def main() -> int:
    p = argparse.ArgumentParser(description="内容数据五层归因")
    p.add_argument("--impressions", type=float, help="曝光量")
    p.add_argument("--views", type=float, help="点击/观看量")
    p.add_argument("--avg-watch", type=float, help="平均观看秒数")
    p.add_argument("--duration", type=float, help="内容总时长秒数")
    p.add_argument("--likes", type=float, default=0)
    p.add_argument("--saves", type=float, default=0)
    p.add_argument("--comments", type=float, default=0)
    p.add_argument("--follows", type=float, default=0)
    p.add_argument("--inquiries", type=float, default=None, help="咨询/私信数")
    p.add_argument("--closes", type=float, default=None, help="成交数")
    p.add_argument("--baseline-ctr", type=float, help="基线点击率，如 0.092")
    p.add_argument("--baseline-completion", type=float, help="基线完播率，如 0.28")
    p.add_argument("--baseline-impressions", type=float, help="基线曝光量")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    ctr = None
    if args.impressions and args.views is not None and args.impressions > 0:
        ctr = args.views / args.impressions
    completion = None
    if args.avg_watch is not None and args.duration and args.duration > 0:
        completion = args.avg_watch / args.duration
    interactions = args.likes + args.saves + args.comments + args.follows

    metrics = {
        "impressions": args.impressions,
        "views": args.views,
        "ctr": None if ctr is None else round(ctr, 4),
        "avg_watch": args.avg_watch,
        "duration": args.duration,
        "completion": None if completion is None else round(completion, 4),
        "interactions": interactions,
        "inquiries": args.inquiries,
        "closes": args.closes,
    }

    baselines = {
        "ctr": args.baseline_ctr,
        "completion": args.baseline_completion,
        "impressions": args.baseline_impressions,
    }
    has_baseline = any(v is not None for v in baselines.values())

    if not has_baseline:
        payload = {
            "status": "need_baseline",
            "metrics": metrics,
            "message": "缺基线，不给结论。请先取近 30 天同形态内容的中位数，再跑一次。",
            "how_to_collect": "至少 5–7 条同形态内容，记录曝光、点击率、完播率，取中位数。",
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("缺基线，不下结论。")
            print(f"  点击率：{pct(ctr)}   完播率：{pct(completion)}   互动：{interactions:g}")
            print("  请先取近 30 天同形态内容的中位数（至少 5–7 条），再带 --baseline-* 重跑。")
        return 2

    verdict = None
    if baselines["impressions"] and args.impressions is not None:
        if args.impressions < baselines["impressions"] * THRESHOLD:
            verdict = {
                "layer": "曝光",
                "cause": "选题方向或账号标签不匹配",
                "fix_only": "只换选题方向，保持标签一致，不要同时改封面格式",
            }
    if verdict is None and baselines["ctr"] and ctr is not None:
        if ctr < baselines["ctr"] * THRESHOLD:
            verdict = {
                "layer": "点击",
                "cause": "封面 + 标题",
                "fix_only": "只改封面和标题，正文结构不动",
            }
    if verdict is None and baselines["completion"] and completion is not None:
        if completion < baselines["completion"] * THRESHOLD:
            verdict = {
                "layer": "看完",
                "cause": "开头没接住，或中段掉速",
                "fix_only": "只改前 3–8 秒，把铺垫和自我介绍删掉",
            }
    if verdict is None and args.inquiries is not None and args.inquiries == 0 and interactions > 0:
        verdict = {
            "layer": "咨询",
            "cause": "内容没连接产品：有共鸣，但没有让人下一步做什么",
            "fix_only": "只补留资那一格，加一个看得见的留资物",
        }
    if verdict is None and args.inquiries is not None and args.closes is not None:
        if args.inquiries > 0 and args.closes == 0:
            verdict = {
                "layer": "成交",
                "cause": "产品、价格或承接话术",
                "fix_only": "不动内容，只改报价结构与第一句承接话术",
            }
    if verdict is None:
        verdict = {
            "layer": "结构",
            "cause": "各层都接近基线，没有明显短板",
            "fix_only": "不改内容，改分发：多平台同步或提高更新密度",
        }

    payload = {
        "status": "ok",
        "metrics": metrics,
        "baselines": baselines,
        "threshold": THRESHOLD,
        "verdict": verdict,
        "next": {
            "只改一处": verdict["fix_only"],
            "对照方式": "同选题、同封面、只改这一处，3 天后比同一指标",
            "禁止": "同时改两层以上，否则无法归因",
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        impressions_text = "—" if args.impressions is None else f"{args.impressions:g}"
        print(f'曝光 {impressions_text}'
              f' ｜点击率 {pct(ctr)}（基线 {pct(baselines["ctr"])}）'
              f' ｜完播 {pct(completion)}（基线 {pct(baselines["completion"])}）')
        print(f'卡点：{verdict["layer"]}')
        print(f'病因：{verdict["cause"]}')
        print(f'这一版只改：{verdict["fix_only"]}')
        print("对照：同选题同封面，3 天后只看这一个指标。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

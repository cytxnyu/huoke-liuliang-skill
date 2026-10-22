# 获客与流量 · huoke-liuliang

一个给内容创作者用的 Agent Skill。它只回答四个具体问题，每个问题都有输入要求、固定产出和一道判定门——过不了门，不往下走。

| 你要解决的问题 | Skill 给你什么 |
| --- | --- |
| **今天拍什么** | 10 张选题卡，按「付费意图 × 48 小时可拍」排序 |
| **前 3 秒说啥** | 5 个钩子候选，标注写法、泛/付费、字数与预估秒数 |
| **讲完怎么让人来找你** | 五格脚本 + 留资三版（口播／评论区／主页） |
| **数据差该改哪** | 单点归因 + 只改一处 + 对照方式 |

## 它凭什么不一样

多数内容工具在"帮你写",这个在**帮你卡**:

- **判定门**：选题必须是一句客户原话；钩子 3 秒内必须出现具体结果或损失；结尾必须只有一个动作动词。过不了就是过不了。
- **一次只改一层**：归因只给一个结论。同时改封面、开头和发布时间，数据变好了你也不知道为什么。
- **不猜**：缺材料就一次性问全，不编痛点、不编数据、不编客户评价。
- **不承诺爆款**：它保证结构不犯错，不保证结果。

## 安装

把整个目录放到你的 agent skills 目录：

```bash
# macOS / Linux
cp -r huoke-liuliang ~/.dsh/skills/
```

```powershell
# Windows
Copy-Item -Recurse huoke-liuliang "$env:USERPROFILE\.dsh\skills\"
```

Claude Skills、Codex、DSH 一类的 `SKILL.md` 结构都兼容：只要读取 `name` + `description` 做路由、按正文执行即可。`agents/openai.yaml` 是给支持该清单的运行时的可选接口描述。

## 用法

直接说人话即可，不需要记命令：

```text
用 $huoke-liuliang 帮我定今天拍什么。我的定位是帮产后妈妈恢复体态，
这是最近 20 条私信原话：[粘贴]
```

```text
用 $huoke-liuliang 改开头。这条视频的完播率只有 11%，脚本在下面：[粘贴]
```

命令行工具（可选，用来做机械检查）：

```bash
# 1. 从视频抽帧，读画面里的字幕（需要 FFmpeg）
python scripts/probe_video.py 视频.mp4 --out frames --count 12

# 2. 脚本体检：五格齐不齐、钩子超没超 3 秒、结尾有没有留资、有没有违规词
python scripts/lint_script.py script.md --json

# 3. 数据归因：必须带基线，否则拒绝下结论
python scripts/diagnose_metrics.py \
  --impressions 12000 --views 1080 --avg-watch 6.4 --duration 55 \
  --inquiries 2 --baseline-ctr 0.092 --baseline-completion 0.28
```

自测：

```bash
python scripts/test_scripts.py -v
```

## 目录结构

```text
huoke-liuliang/
├── SKILL.md                     # 主流程：四条流水线 + 判定门
├── references/
│   ├── method.md                # 方法论内核：定位、漏斗、五格公式、钩子、痛点、人性、归因
│   ├── templates.md             # 五张填空卡（定位／选题／钩子／脚本／归因）
│   ├── examples.md              # 三个走通的完整实例
│   └── platform-notes.md        # 平台差异、导流合规底线、口径边界
├── scripts/
│   ├── probe_video.py           # 抽帧 + 时间戳，不转写音频
│   ├── lint_script.py           # 五格 / 时长 / 留资 / 违规词体检
│   ├── diagnose_metrics.py      # 数据单点归因
│   └── test_scripts.py          # 12 项自测
└── agents/openai.yaml
```

## 几条设计原则

1. **不猜。** 缺材料就一次性问全。痛点必须来自客户原话，不是总结。
2. **一次只改一层。** 归因没定位到单点之前，不改第二处。
3. **只写第一人称事实。** 效果承诺改成记录口径（"我掉了 21 斤" ✅ ／ "饿瘦 21 斤只要 8 步" ❌）。
4. **不越界。** 剪辑、动效、封面交给对应的 skill，这里只负责脚本和判断。

## 口径声明

- 方法论整理自个人学习笔记与实践，**不含课程原文、课件图片或讲义**。
- 其中所有数字、权重、时间窗口都属于**经验口径**，不是任何平台的官方规则。平台从未完整公开推荐算法。
- 判断数据好坏建议用自己的基线（近 30 天同形态内容的中位数），不要套用别人的绝对阈值。
- 效果承诺、绝对化用语、医疗/金融类夸大表述会带来限流与合规风险，脚本里只写第一人称真实经历。

## License

MIT

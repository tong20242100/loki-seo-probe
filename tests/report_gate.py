#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告可读性门禁：钉死渲染层不泄漏内部黑话、verdict 翻人话、状态翻译、四列动作表。

为什么需要：1.0.3 把可读性红线写进了 SKILL.md 输出合同，但那只约束 agent 在对话里
写的散文；1.0.4 把渲染层固化进 audit_url.py，探针 run 完自动出 md/html。渲染层
一旦回退（比如又直接抄 findings[].loki 或 diagnosis.top_risk / focus_reading 原串），
报告就会重新漏黑话。这里把红线变成可执行断言，回归即红。

红线来源（SKILL.md 输出合同「可读性」）：
  - 去内部溯源：loki / #n / 口诀 / G7 / siteFocus 一律不进报告。
  - verdict 四值翻成人话，不准直接贴英文（needs-focus / at-risk / critical / insufficient）。
  - 状态值翻译：na→探针没看到（≠没问题）。
  - 术语首翻：posts→博客文章 等。
  - 四列动作表：谁改 / 改哪一页 / 改成什么 / 怎么验收。
  - 开头大白话：第一句让人知道现在该干啥。

用法: python3 tests/report_gate.py
"""
import os
import sys
import types
from pathlib import Path

AU = os.environ.get(
    "LOKI_SEO_AUDIT",
    str(Path(__file__).resolve().parent.parent / "scripts" / "audit_url.py"))


def load():
    """compile 源码绕过 pyc 缓存（同 confidence_gate，避免门禁被缓存骗过）。"""
    src = Path(AU).read_text(encoding="utf-8")
    mod = types.ModuleType("audit_url")
    mod.__file__ = AU
    exec(compile(src, AU, "exec"), mod.__dict__)
    return mod


def sample():
    """合成 bundle，故意塞满内部黑话，测渲染层会不会漏出来。"""
    return {
        "input": "https://x.com", "origin": "https://x.com",
        "status": "ok", "run_confidence": 1.0, "sitemap_follow": "ok",
        "findings": [
            {"rule": "sitemap-mix", "status": "warn",
             "evidence": "n=444 prefixes=[('posts',333)] share=75%",
             "loki": "7.4 siteFocus；单一前缀 posts 占 75% 集中度过高=warn",
             "focus": {"top": "posts", "share": 0.75, "n": 444}},
            {"rule": "robots-ua", "status": "warn", "evidence": "[]",
             "loki": "G7 常识：分 UA 的 Disallow 必须读，不能当成全站隔离"},
            {"rule": "sitemap", "status": "na",
             "evidence": "sitemap paths={'/sitemap.xml': 0}", "loki": "常识"},
            {"rule": "title-h1", "status": "seen",
             "evidence": "title='友伴 PeerCare' h1='为学校做零废弃教育'", "loki": "6.3"},
        ],
        "diagnosis": {
            "verdict": "needs-focus",
            "priority": [
                {"rule": "sitemap-mix", "status": "warn",
                 "loki": "7.4 siteFocus", "why": "n=444 share=75%"},
                {"rule": "robots-ua", "status": "warn",
                 "loki": "G7 常识", "why": "[]"},
            ],
            "top_risk": "最优先: sitemap-mix (warn, loki 7.4 siteFocus；单一前缀 posts 占 75%)",
            "focus_reading": "站点可能被当成 posts 站（posts 占 75%，n=444）",
            "gaps": [], "to_judge": [], "n_fail": 0, "n_warn": 2,
            "evidence_partial": False,
        },
        "next_collect": [
            {"need": "GSC 效果页对齐下跌窗口：掉的是转化页还是博客页",
             "loki": "6.2 6.1", "trigger": "sampled-originality",
             "read_as": "探针只 sniff 抽样页，全站原创度要 GSC 或人工看"},
        ],
    }


LEAK = ("loki", "G7", "siteFocus", "口诀", "posts 站", "posts", "#116", "#n")
VERDICT_EN = ("needs-focus", "at-risk", "critical", "insufficient")
# (必须出现的字符串, 在哪个产物里找, 失败信息)
NEED = (("探针没看到", "md", "na 状态未翻译（应出现「探针没看到」）"),
        ("博客文章", "md", "术语未首翻：posts 应翻成「博客文章」"),
        ("| 谁改 |", "md", "markdown 缺少四列动作表（| 谁改 |）"),
        ("<table", "html", "html 缺少四列动作表"),
        ("谁改", "html", "html 动作表缺表头"))


def check(md, html, bad):
    for b in LEAK + VERDICT_EN:
        if b in md or b in html:
            bad.append(f"黑话/英文 verdict 泄漏：{b}")
    src_of = {"md": md, "html": html}
    for tok, where, msg in NEED:
        if tok not in src_of[where]:
            bad.append(msg)
    lines = [l for l in md.splitlines() if l.strip()]
    if not md.startswith("# 网站 SEO 体检报告") or len(lines) < 2 or "技术" not in lines[1]:
        bad.append("开头缺少大白话总结")


def main():
    if not Path(AU).exists():
        print("找不到 audit_url.py", AU, file=sys.stderr)
        return 1
    au = load()
    d = sample()
    md = au.render_markdown(d)
    html = au.render_html(d)
    bad = []
    check(md, html, bad)
    for b in bad:
        print("  FAIL", b)
    print(f"报告可读性门禁: {len(bad)} 项失败" if bad else "报告可读性门禁: 全部通过")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

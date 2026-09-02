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
            {"rule": "title-h1", "status": "seen", "evidence": "title='友伴 PeerCare' h1='交付'", "loki": "6.3"},
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
        "title_text": "友伴 PeerCare｜口号", "h1_text": "为学校做可验证的教育交付",
        "sniffs": [{"url": "https://x.com/a/event", "status": 200, "title": "一场活动"}],
        "html": {"linkedin": 0}, "partial": False,
        "sitemap": {"n": 444, "prefixes": [("posts", 333), ("news", 7)]},
        "cannot": ["GSC Field 要后台（7.3）", "整站差要爬（#116 他本人）"],
    }


LEAK = ("loki", "G7", "siteFocus", "口诀", "posts 站", "posts", "#116", "#n")
VERDICT_EN = ("needs-focus", "at-risk", "critical", "insufficient")
# (必须出现的字符串, 在哪个产物里找, 失败信息)
NEED = (("探针没看到", "md", "na 状态未翻译（应出现「探针没看到」）"),
        ("博客文章", "md", "术语未首翻：posts 应翻成「博客文章」"),
        ("| 谁改 |", "md", "markdown 缺少四列动作表（| 谁改 |）"),
        ("<table", "html", "html 缺少四列动作表"),
        ("谁改", "html", "html 动作表缺表头"),
        ("先停", "md", "技术全绿时仍须有先停（别追外链 / 别上作业清单 / 别充分数）"),
        ("这页说不出自己排什么", "md", "一页一词说不清须照写，不许「待你填」"),
        ("证据等级", "md", "缺证据等级"),
        ("实验室打分", "md", "缺「不要用实验室打分充真实体验」"),
        ("不是硬伤", "md", "栏目集中须标定性不是硬伤"),
        ("/a/event", "md", "有抽样却没进一页一词表"),
        ("本站对照", "md", "缺本站对照（pass 项的口径边界）"),
        ("待你处理", "md", "cannot[] 没改写成「待你处理（待办/需确认）」"),
        ("site:", "md", "缺 site: 收录结构这一步"),
        ("不替你发明", "md", "一页一词未明示探针不发明关键词"),
        ("成交或产品目录", "md", "纯博客地图应点亮缺成交页"))

GENERIC = ("探针未抽样", "待你填", "降低单一前缀", "结构更均衡", "增加业务页")


def _table_rows(md, header):
    in_sec, n = False, 0
    for ln in md.splitlines():
        if ln.startswith("## "):
            in_sec = ln.startswith(header)
            continue
        if in_sec and ln.strip().startswith("|"):
            if "谁改" in ln or set(ln) <= set("|- "):
                continue
            n += 1
    return n


def check_agent(au, d, bad):
    """JSON.agent 是源、md 是其投影：动作只算一遍，二者必须逐条一致。

    也钉死 agent 块的结构契约：schema / kind 白名单 / cannot 为 {id,forbid}。
    AI 闭环只读这块，不读 md；md 只是给人看的投影，二者一旦分叉即红。
    """
    a = d.get("agent") or au.build_agent(d)
    md = au.render_markdown(d)
    kinds = {x.get("kind") for x in a.get("actions", [])}
    if (a.get("schema") != "loki-seo-agent/v1"
            or not kinds <= {"do", "stop", "collect", "ask"}
            or not all(isinstance(x, dict) and "id" in x and "forbid" in x
                       for x in a.get("cannot", []))):
        bad.append("agent 结构契约破坏：schema / kind 白名单 / cannot{id,forbid} 之一不符")
    unproj = [x["id"] for x in a["actions"]
              if x["kind"] in ("do", "stop") and x.get("change", "") not in md]
    bad += [f"agent 动作未投影到 md: {i}" for i in unproj]
    do_n = sum(1 for x in a["actions"] if x["kind"] == "do")
    stop_n = sum(1 for x in a["actions"] if x["kind"] == "stop")
    if _table_rows(md, "## 二、先做") != do_n or _table_rows(md, "## 三、先停") != stop_n:
        bad.append("先做/先停表行数与 agent do/stop 数不一致")
    if a.get("conclude") != "full" or a.get("may_conclude") is not True:
        bad.append("ok 样本 conclude 应为 full 且 may_conclude=true")


def check_conclude(au, bad):
    """partial ≠ inconclusive。A 方案（partial 也不开方）会丢掉降级诊断。"""
    p = sample()
    p.update(status="partial", partial=True, inconclusive=False)
    a = au.build_agent(p)
    if a.get("conclude") != "tentative" or a.get("may_conclude"):
        bad.append("partial 应为 conclude=tentative 且 may_conclude=false")
    if not any(x.get("kind") == "do" for x in a.get("actions") or []):
        bad.append("partial 仍应对看得见的部分开方，不应拆掉 do")
    q = sample()
    q.update(status="inconclusive", inconclusive=True, partial=False)
    b = au.build_agent(q)
    if b.get("conclude") != "none" or any(x.get("kind") == "do" for x in b.get("actions") or []):
        bad.append("inconclusive 应 conclude=none 且无 do")


def check(md, html, bad, au=None):
    blob = md + "\n" + html
    bad += [f"黑话/英文 verdict 泄漏：{b}" for b in LEAK + VERDICT_EN if b in blob]
    src = {"md": md, "html": html}
    bad += [msg for tok, where, msg in NEED if tok not in src[where]]
    bad += [f"通用体检腔调：{g}" for g in GENERIC if g in blob]
    lines = [l for l in md.splitlines() if l.strip()]
    if not md.startswith("# 站点诊断") or len(lines) < 2 or "技术" not in lines[1]:
        bad.append("开头缺少大白话总结")
    if au is None:
        return
    d = sample()
    d["sitemap"] = {"n": 444, "prefixes": [("posts", 333), ("cases", 65)]}
    d["agent"] = au.build_agent(d)
    if "成交或产品目录" in au.render_markdown(d):
        bad.append("有成交目录时不应点亮纯博客缺成交页")


def main():
    if not Path(AU).exists():
        print("找不到 audit_url.py", AU, file=sys.stderr)
        return 1
    au = load()
    d = sample()
    d["agent"] = au.build_agent(d)
    md = au.render_markdown(d)
    html = au.render_html(d)
    bad = []
    check(md, html, bad, au)
    check_agent(au, d, bad)
    check_conclude(au, bad)
    for b in bad:
        print("  FAIL", b)
    print(f"报告可读性门禁: {len(bad)} 项失败" if bad else "报告可读性门禁: 全部通过")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

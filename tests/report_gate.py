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
import json
import os
import re
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
            "gaps": [], "to_judge": [], "n_fail": 0, "n_warn": 2, "evidence_partial": False,
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
        "cannot": ["GSC Field 要后台（7.3）", "整站差要爬（#116 他本人）", "搜索 site:域名 看收录结构"],
    }


LEAK = ("loki", "G7", "siteFocus", "口诀", "posts 站", "posts", "#116", "#n")
VERDICT_EN = ("needs-focus", "at-risk", "critical", "insufficient")
# (必须出现的字符串, 在哪个产物里找, 失败信息)
NEED = (("这次没检测到", "md", "na 状态未翻译（应出现「这次没检测到」）"),
        ("博客文章", "md", "术语未首翻：posts 应翻成「博客文章」"),
        ("| 谁改 |", "md", "markdown 缺少四列动作表（| 谁改 |）"),
        ("<table", "html", "html 缺少四列动作表"),
        ("谁改", "html", "html 动作表缺表头"),
        ("先停", "md", "技术全绿时仍须有先停（别追外链 / 别上作业清单 / 别充分数）"),
        ("这页说不出自己排什么", "md", "一页一词说不清须照写，不许「待你填」"),
        ("哪些数据可信", "md", "缺「哪些数据可信」章节"),
        ("分数冒充真实用户体验", "md", "缺「用测速工具分数冒充真实体验」警告"),
        ("不是技术故障", "md", "栏目集中须标定性不是硬伤"),
        ("/a/event", "md", "有抽样却没进一页一词表"),
        ("| # | 别碰哪块 |", "md", "先停表须用自己的表头，不能沿用「谁改/改成什么」"),
        ("逐项核查结果", "md", "缺「逐项核查结果」章节"),
        ("需要你手动处理", "md", "cannot[] 没改写成「需要你手动处理」"),
        ("site:", "md", "缺 site: 收录结构这一步"),
        ("不替你发明", "md", "每页要排的词未明示检测工具不替你发明关键词"),
        ("能产生订单/咨询的页面", "md", "纯博客地图应点亮缺成交页"))

GENERIC = ("探针未抽样", "待你填", "降低单一前缀", "结构更均衡", "增加业务页")


def _table_rows(md, header):
    """数某节表格的数据行。

    跳表头不能靠「谁改」这类显示字符串：先停表换成自己的表头后，
    那种写法会把表头算成数据行（行数永远对不上）。改为按结构跳：
    每节遇到的第一行非空表格行即表头。
    """
    in_sec, n, head = False, 0, False
    for ln in md.splitlines():
        if ln.startswith("## "):
            in_sec, head = ln.startswith(header), False
            continue
        if ln.startswith("### "):
            # 子标题（如「### 技术项」）意味着新表块开始，重置表头标记，
            # 否则第二张表的表头行会被当成数据行多算 1 行。
            head = False
            continue
        if not (in_sec and ln.strip().startswith("|")):
            continue
        if set(ln) <= set("|- "):
            continue
        if not head:
            head = True
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
    # 机器层 site: 单源钉死：不得双写进 actions，且必须仍在 cannot 单源保留
    if any(x.get("id") == "collect-site" for x in a.get("actions", [])):
        bad.append("agent.actions 仍含 collect-site：site: 应只走 cannot → 8.1（机器层双写）")
    if not any("site:" in (c.get("task") or c.get("forbid") or "") for c in a.get("cannot", [])):
        bad.append("agent.cannot 缺少 site: 缺口项：消重后 site: 必须仍在 cannot 单源保留")
    if a.get("conclude") != "full" or a.get("may_conclude") is not True:
        bad.append("ok 样本 conclude 应为 full 且 may_conclude=true")


def check_facts_dup(au, bad):
    """facts 行是「规则名：结论。证据」。规则名里解释过一次的术语，证据里不许再解释一遍。

    曾出现「软 404（错误页却返回 200）：检测到硬伤，必须修。存在软 404（错误页却返回 200）」，
    同一句里把同一个括号念两遍。这里按结构查重复，不按固定字符串查。
    """
    d = sample()
    for r in ("soft-404 probe", "https", "display:none", "m-subdomain", "h1"):
        d["findings"].append({"rule": r, "status": "fail", "evidence": "", "loki": "常识"})
        d["diagnosis"]["priority"].append({"rule": r, "status": "fail", "loki": "常识", "why": ""})
    d["diagnosis"]["verdict"] = "critical"
    d["agent"] = au.build_agent(d)
    md = au.render_markdown(d)
    for ln in md.splitlines():
        if not ln.startswith("- "):
            continue
        for m in re.finditer(r"（([^（）]{2,24})）", ln):
            if ln.count(m.group(1)) > 1:
                bad.append(f"证据句重复了规则名里的解释：{m.group(1)}")


FAIL_WORDS = ("硬伤", "必须修", "检出风险")


def _section(md, header):
    out, keep = [], False
    for ln in md.splitlines():
        if ln.startswith("## "):
            keep = ln.startswith(header)
            continue
        if keep:
            out.append(ln)
    return "\n".join(out)


def _all_status(d, st, rules):
    d["findings"] = [{"rule": r, "status": st, "evidence": "", "loki": "常识"}
                     for r in rules]
    d["diagnosis"]["priority"] = [{"rule": r, "status": st, "loki": "常识", "why": ""}
                                  for r in rules]
    d["diagnosis"]["verdict"] = "critical" if st == "fail" else "needs-focus"
    return d


def _fail_rows_missing(au, facts, rules):
    out = []
    for r in rules:
        name = au.RULE_HUMAN.get(r, r)
        row = [l for l in facts.splitlines() if l.startswith("- ") and name in l]
        if not row:
            out.append(f"fail 项没进第四节：{r}")
        elif not any(w in row[0] for w in FAIL_WORDS):
            out.append(f"fail 项没写成硬伤：{r}")
    return out


def check_status_wording(au, bad):
    """json 的 true/false 必须老实翻成人话：不许把 pass 说成硬伤，也不许把 fail 说软。

    翻译表一旦写反（pass 槽填了问题文案），技术日志一片绿的站会在报告里变成
    「有 4 个硬伤要马上修」。读报告的人拿去问技术，技术一看日志说都没问题，
    两边就吵起来了。为让报告显得有活干而制造硬伤，比漏报更糟。
    这里按行为断言，不查源码字符串：同一份 bundle 全设 pass 渲一遍、全设 fail 渲一遍。
    """
    rules = ("https", "soft-404 probe", "m-subdomain", "semantic main",
             "display:none", "h1", "title-h1")
    p = _all_status(sample(), "pass", rules)
    p["agent"] = au.build_agent(p)
    if any(w in _section(au.render_markdown(p), "## 四") for w in FAIL_WORDS):
        bad.append("pass 被翻成硬伤/风险：json 说没事、第四节却在报警")
    f = _all_status(sample(), "fail", rules)
    f["agent"] = au.build_agent(f)
    bad += _fail_rows_missing(au, _section(au.render_markdown(f), "## 四"), rules)


def check_sample_consistency(au, bad):
    """工作区样例三件套必须同源：json 重渲出的 md/html 要和盘上逐字一致。

    出过的事故：为测硬伤场景，手改 findings 后渲了 md/html 覆盖掉样例，json 却
    还是原样。样例是 gitignore 的、没人 review，于是交付出去的 md 写着 4 个硬伤，
    同一份 json 里那 4 项全是 pass。样例不存在则跳过（CI 上不产样例）。
    """
    tag = "_audit_report.json"
    for jp in sorted(Path(".").glob("*" + tag)):
        stem = jp.name[: -len(tag)]
        mp, hp = Path(stem + "_audit_report.md"), Path(stem + "_audit_report.html")
        if not (mp.exists() and hp.exists()):
            continue
        d = json.loads(jp.read_text(encoding="utf-8"))
        d["agent"] = au.build_agent(d)
        if mp.read_text(encoding="utf-8") != au.render_markdown(d):
            bad.append(f"样例 md 与 json 不同源：{mp.name}（按 json 重渲后不一致）")
        if hp.read_text(encoding="utf-8") != au.render_html(d):
            bad.append(f"样例 html 与 json 不同源：{hp.name}（按 json 重渲后不一致）")


def check_reading(au, bad):
    """读法句不能硬编码「技术没硬伤」——critical 报告里这句话会自相矛盾。"""
    c = sample()
    c["findings"].append({"rule": "https", "status": "fail", "evidence": "无跳转", "loki": "常识"})
    c["diagnosis"]["priority"].insert(0, {"rule": "https", "status": "fail",
                                          "loki": "常识", "why": "无跳转"})
    c["diagnosis"]["verdict"] = "critical"
    c["diagnosis"]["n_fail"] = 1
    c["agent"] = au.build_agent(c)
    md = au.render_markdown(c)
    if "技术没硬伤" in md:
        bad.append("critical 报告仍在说「技术没硬伤」，读法句须按 verdict 分流")
    if "先按「先做」修完" not in md:
        bad.append("critical 报告未给出「先按先做修完」的读法")


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
    if "能产生订单/咨询的页面或产品目录" in au.render_markdown(d):
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
    check_reading(au, bad)
    check_facts_dup(au, bad)
    check_status_wording(au, bad)
    check_sample_consistency(au, bad)
    check_conclude(au, bad)
    for b in bad:
        print("  FAIL", b)
    print(f"报告可读性门禁: {len(bad)} 项失败" if bad else "报告可读性门禁: 全部通过")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

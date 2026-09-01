#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""置信度 / 研判语义门禁（第六行）。

为什么不能只靠 shape_check：
  shape_check 只证明函数没超行数，不证明诊断语义对。「首页 502 仍报 ok」
  「sitemap 跟丢藏在一条 na 里」「7.4 定性被打成 at-risk」都是形态全绿下发生的。
  这里把语义钉成可执行断言，改代码改回去会在 exit code 上暴露。

断言来源（2026-09-01 拍板）：
  P0  5xx / 网络错(0) = 探针失败=没看到；4xx = 站点事实(确实没有)，不算没看到。
  P1  研判按碰撞表五档排序，不用口诀号当致命度。
      at-risk 只由 fail 或 tier<=2（技术阻断/信任红线）触发；
      只剩定性/常识类 warn 时是 needs-focus，并在 focus_reading 给定性解读。
  P1b next_collect 只留「探针核不到」的项，不得出现「再拉 sitemap」这类重跑同一探针。
      linkedin 不进 NEED：探针数到的链接数是材料，5.1 的类目边界探针判不了，
      不做会按站无差别索要截图。
  P3  sitemap index 200 但子表跟丢(n=0) → sitemap_follow=lost 且不算 seen。
  P4  2026-09-01 拆 na 双义：na=探针没看到；seen=看到了材料但不自动打分。
      seen 的四条（title-h1/json-ld/jsonld-types/linkedin）必须进 to_judge[]，
      既不进 gaps（不是缺数据）也不进 priority（不是风险）。
      llms.txt 404 是站点事实（4xx），不得标 na。
  P5  CLI 退出码跟 status 对齐：ok/partial=0，inconclusive=1。
      partial 不得 exit 1，否则调用方会丢掉可用的降级诊断。
  P6  interpret 也要罩住：首页 502（空 HTML）时 semantic main / h1 / title-h1
      必须 na，不得把空 HTML 写成站点事实（fail）。
  P7  2026-09-01 补钉（实跑 peercare 抓到、之前只改代码没进门禁）：
      sitemap 路径变体（/sitemap-index.xml）任一 200 即 pass——门禁必须抓住
      「回退旧两路径写法」的回归；http 源 https=fail→warn→at-risk，不一刀 critical；
      抽样空须显式与 sitemap 跟丢分开说；inconclusive 的 diagnosis 必须带
      to_judge=[] 空数组（否则调用方读键 KeyError）。
  P8  发现层单独钉：test_sitemap_path 用合成 bundle 直接塞 well_known 键，测的是
      interpret 会不会扫全部含 sitemap 的路径，看不到 probe_well_known 到底抓不抓
      /sitemap-index.xml。清单（PROBE_PATHS）若丢该变体，真实抓取永不产键、门禁却仍绿。
      故断言三个 sitemap 变体必须在 PROBE_PATHS 里。
  P9  2026-09-01 补钉（实跑 peercare 抓到、用户以合成 bundle 复算确认）：
      a) soft-404 探针网络失败(0)/5xx = 没看到 = na。旧版 status==0 落 warn(tier1)
         → diagnose 打 at-risk：站点没变，抖动就把结论从 pass 翻成 at-risk，
         与已拍板的「0/5xx=没看到=na」直接冲突。真 404 仍 pass、疑似软 404 仍 fail。
      b) diagnose 在 partial 且无 fail/warn 时不得字面输出 healthy——下游不守合同
         会读成「站没问题」。给 insufficient，配合 evidence_partial=true 表暂定。
         非 partial 时的 healthy 不变。
  P10 2026-09-01 补钉（发布前实测抓到；m-subdomain/wayback 是 17 条 rule 里
      门禁此前零覆盖的两条，sampled 分母是 P7 只钉一半）：
      a) m-subdomain 的 status=0 双义分流：NXDOMAIN(nodename/gaierror)=站点事实
         「没有 m 站」→ pass 真阳性（peercare.cn 实测）；超时/拒连=没看到 → na。
         旧版「非 200 一律 pass」让代理隧道 502 假 pass 溜过。统一 responded() 收口
         会把 NXDOMAIN 真阳性改坏，故必须按 error 文本分流。
      b) wayback CDX 必须 limit=-3 取最新（默认升序 limit=3 拿最早 3 条，
         last200 曾比真实最新早 10 个月）；'-' 状态行不作 dated 候选。
      c) sampled-originality 分母只计 status==200 的活样本；
         非空全死 → na（不是 pass），evidence 须报 live/dead 分解。

用法: python3 confidence_gate.py    # 全通过 exit 0，有失败 exit 1
"""
import inspect
import os
import sys
import types
from pathlib import Path

# 相对本文件定位 ../../scripts/audit_url.py，仓库根 / skill 目录都能跑；
# 环境变量 LOKI_SEO_AUDIT 可覆盖（把门禁指向另一份安装时用）。
AU = os.environ.get(
    "LOKI_SEO_AUDIT",
    str(Path(__file__).resolve().parent.parent / "scripts" / "audit_url.py"))


def load():
    """直接 compile 源码，**不走 __pycache__**。

    SourceFileLoader 的 pyc 失效只看 mtime(整秒) + size。变异测试实测：
    把 `partial": 0` 改成 `1` 再改回来，字节数不变、且两次都在同一秒内完成，
    pyc 被判定仍然有效——门禁于是拿**旧字节码**出结果，文件明明已复原却报失败。
    语义门禁被缓存骗过比没有门禁更危险，所以这里绕开缓存。"""
    src = Path(AU).read_text(encoding="utf-8")
    mod = types.ModuleType("audit_url")
    mod.__file__ = AU
    exec(compile(src, AU, "exec"), mod.__dict__)
    return mod


def bundle(home, robots, sm, n):
    return {"home": {"status": home}, "sitemap": {"n": n},
            "well_known": {"/robots.txt": {"status": robots},
                           "/sitemap.xml": {"status": sm}},
            "wayback": {"ok": True}, "soft_404": {"status": 404},
            "m_host": {"status": 0}}


def full_bundle(home=200, title="PeerCare 首页", h1_text="私董会", ld=("Organization",),
                linkedin=0, n=444, sm=200, ll=404):
    """interpret() 全字段 bundle：只喂 compute_confidence 那套最小 bundle 会 KeyError。"""
    empty = home != 200
    return {"home": {"status": home},
            "html": {"title": "" if empty else title, "h1": 0 if empty else 1,
                     "semantic": {"main": not empty, "header": not empty},
                     "jsonld": 0 if empty else 1, "display_none": False,
                     "linkedin": linkedin, "about": []},
            "well_known": {"/robots.txt": {"status": 200}, "/sitemap.xml": {"status": sm},
                           "/sitemap_index.xml": {"status": 0}, "/llms.txt": {"status": ll}},
            "sitemap": {"n": n, "prefixes": [("posts", n)] if n else []},
            "sniffs": [], "robots": [], "origin": "https://x.com",
            "soft_404": {"status": 404, "bytes": 10, "suspect_soft_404": False},
            "wayback": {"ok": True, "first200": "20230101", "last200": "20260101"},
            "m_host": {"host": "m.x.com", "status": 0},
            "home_ld_types": list(ld), "title_text": "" if empty else title,
            "h1_text": "" if empty else h1_text}


def _st(fs, rule):
    return next((f["status"] for f in fs if f["rule"] == rule), None)


SEEN_RULES = ("title-h1", "linkedin", "json-ld", "jsonld-types")

CASES = [
    ("P0 首页 502 不能当 seen，且必须降级（旧 got() 把 502 当 seen）",
     dict(home=502, robots=200, sm=200, n=444),
     lambda c: not c["probes"]["home"] and (c["partial"] or c["inconclusive"])),
    ("P3 index 200 但子表跟丢(n=0) → lost 且不算 seen 且降置信度",
     dict(home=200, robots=200, sm=200, n=0),
     lambda c: c["sitemap_follow"] == "lost" and not c["probes"]["sitemap"]
     and c["partial"]),
    ("P0 sitemap 404 是站点事实，不算没看到（否则误判 inconclusive）",
     dict(home=200, robots=200, sm=404, n=0),
     lambda c: c["sitemap_follow"] == "absent" and c["probes"]["sitemap"]),
    ("P0 核心探针全 5xx → inconclusive",
     dict(home=502, robots=503, sm=503, n=0),
     lambda c: c["inconclusive"]),
    ("P0 三核都好 → 不 inconclusive、不 partial",
     dict(home=200, robots=200, sm=200, n=444),
     lambda c: not c["inconclusive"] and not c["partial"]),
]


def test_confidence(au, bad):
    for name, kw, ok in CASES:
        if not ok(au.compute_confidence(bundle(**kw))):
            bad.append(name)


def test_diagnose(au, bad):
    def f(rule, status, loki="", focus=None):
        return {"rule": rule, "status": status, "loki": loki, "evidence": "e",
                "focus": focus}
    d = au.diagnose([f("sitemap-mix", "warn", "7.4", {"top": "posts",
                                                      "share": .75, "n": 444}),
                     f("sitemap", "warn", "常识")])
    if d["verdict"] == "at-risk":
        bad.append("P1 7.4 定性被打成 at-risk（应 needs-focus）")
    if "posts" not in (d.get("focus_reading") or ""):
        bad.append("P1 缺 focus_reading 定性解读（应说站点可能被当成 posts 站）")
    if d["priority"] and d["priority"][0]["rule"] != "sitemap-mix":
        bad.append("P1 档位排序错：常识(档4) 压过了 7.4 定性(档3)")
    d = au.diagnose([f("soft-404 probe", "fail", "1.4 7.1")])
    if d["verdict"] != "critical":
        bad.append("P1 tier1 fail 应 critical")
    d = au.diagnose([f("wayback", "warn", "4.1")])
    if d["verdict"] != "at-risk":
        bad.append("P1 信任类(tier2) warn 应 at-risk")


NO_NEED = ("sitemap", "sitemap-mix", "title-h1", "linkedin",
           "llms.txt", "json-ld", "jsonld-types")


def test_need(au, bad):
    for k in NO_NEED:
        if k in au.NEED:
            bad.append(f"P1b {k} 不该在 NEED 里（有数据/非搜集项/类目判断在合同，"
                       "进了=重跑同一探针或无差别索要）")
    for k, v in au.NEED.items():
        if "再拉 sitemap" in v[0] or "重数" in v[0]:
            bad.append(f"P1b NEED[{k}] 是重跑同一探针：{v[0]}")


def test_interpret(au, bad):
    f502 = au.interpret(full_bundle(home=502))
    ok = au.interpret(full_bundle())
    d = au.diagnose(ok)
    tj = [x["rule"] for x in d.get("to_judge") or []]
    gp = [x["rule"] for x in d.get("gaps") or []]
    pr = [x["rule"] for x in d.get("priority") or []]
    cases = [
        ("首页 502：semantic main 必须 na（空 HTML 不是站点事实，不得 fail）",
         lambda: _st(f502, "semantic main") == "na"),
        ("首页 502：h1 必须 na（空 HTML 不是站点事实，不得 warn/fail）",
         lambda: _st(f502, "h1") == "na"),
        ("首页 502：title-h1 必须 na（没抓到文案，材料不在手）",
         lambda: _st(f502, "title-h1") == "na"),
        ("首页 200：title-h1 必须 seen（材料在 evidence，不自动打分）",
         lambda: _st(ok, "title-h1") == "seen"),
        ("首页 200 且 linkedin=0：是站点事实，必须 seen 不是 na",
         lambda: _st(ok, "linkedin") == "seen"),
        ("llms.txt 404 是站点事实（4xx），不得标 na",
         lambda: _st(ok, "llms.txt") == "seen"),
        ("seen 项不得进 gaps（不是缺数据）",
         lambda: not [r for r in SEEN_RULES if r in gp]),
        ("seen 项不得进 priority（不是风险）",
         lambda: not [r for r in SEEN_RULES if r in pr]),
        ("seen 项必须进 to_judge[]（判断权归输出合同第 4 条）",
         lambda: set(SEEN_RULES) <= set(tj)),
    ]
    for name, cond in cases:
        if not cond():
            bad.append("P4/P6 " + name)


def test_exit(au, bad):
    e = getattr(au, "EXIT", {})
    if e.get("partial") == 1:
        bad.append("P5 partial 不得 exit 1（调用方会整份丢掉可用的降级诊断）")
    if e.get("ok") != 0 or e.get("inconclusive") != 1:
        bad.append("P5 退出码应 ok=0 / inconclusive=1")
    n = getattr(au, "NOTE", {})
    if "inconclusive" in n and "仍有" in n["inconclusive"]:
        bad.append("P5 inconclusive 的 stderr 提示不得说「仍有输出」（那时 findings 全 na）")
    if set(n) - {"ok", "partial", "inconclusive"}:
        bad.append("P5 NOTE 只应覆盖 ok/partial/inconclusive")


def test_sitemap_path(au, bad):
    """P7 钉死：站点用 /sitemap-index.xml（非 /sitemap.xml）时仍应 pass。
    interpret() 改成扫全部含 sitemap 的路径；若回退旧两路径写法会漏，门禁必须抓到。"""
    b = full_bundle(home=200, sm=404)
    wk = b["well_known"]
    wk["/sitemap_index.xml"] = {"status": 404}
    wk["/sitemap-index.xml"] = {"status": 200}
    b["sitemap"] = {"n": 444, "prefixes": [("posts", 444)], "samples": {}, "fetch_fail": []}
    fs = au.interpret(b)
    st = next(f["status"] for f in fs if f["rule"] == "sitemap")
    if st != "pass":
        bad.append("P7 仅 /sitemap-index.xml=200 也应 pass（回退旧两路径写法会误报 warn）")


def test_https(au, bad):
    """P7 http 源不得一刀 critical：https=fail→warn(tier1)→at-risk。"""
    b = full_bundle(home=200)
    b["origin"] = "http://x.com"
    fs = au.interpret(b)
    hs = next(f["status"] for f in fs if f["rule"] == "https")
    if hs != "warn":
        bad.append(f"P7 http 源 https 应为 warn，实际 {hs}")
    d = au.diagnose(fs)
    if d["verdict"] == "critical":
        bad.append("P7 http 源不应一刀 critical（应 at-risk）")
    elif d["verdict"] not in ("at-risk", "needs-focus"):
        bad.append(f"P7 http 源 verdict 应 at-risk/needs-focus，实际 {d['verdict']}")


def test_sampled(au, bad):
    """P7 抽样空须显式与 sitemap 跟丢分开说。"""
    b = full_bundle(home=200)
    b["sniffs"] = []
    f = next(x for x in au.interpret(b) if x["rule"] == "sampled-originality")
    if f["status"] != "na":
        bad.append("P7 未抽样应 na")
    if "未抽样" not in f["evidence"]:
        bad.append("P7 sampled-originality 证据须显式写「未抽样」")
    if "跟丢" not in f["evidence"]:
        bad.append("P7 未抽样的证据须同时点明「非 sitemap 跟丢」，"
                   "否则「没抓到内页」会被读成「子表跟丢」，两条缺口混淆")


def test_inconclusive(au, bad):
    """P7 三核全挂走 inconclusive 分支时，diagnosis 必须带 to_judge=[]（否则调用方 KeyError）。"""
    b = full_bundle(home=502)
    b["well_known"]["/robots.txt"] = {"status": 503}
    b["well_known"]["/sitemap.xml"] = {"status": 503}
    b["well_known"]["/sitemap_index.xml"] = {"status": 503}
    b["sitemap"] = {"n": 0}
    out = au.attach_report(b)
    if out["status"] != "inconclusive":
        bad.append(f"P7 三核全挂应 inconclusive，实际 {out['status']}")
        return
    dx = out["diagnosis"]
    if "to_judge" not in dx:
        bad.append("P7 inconclusive diagnosis 缺 to_judge 键（调用方 KeyError）")
    elif dx["to_judge"] != []:
        bad.append("P7 inconclusive diagnosis to_judge 应为空数组")


def test_probe_paths(au, bad):
    """P8 发现层门禁：清单丢 sitemap 变体时，test_sitemap_path 的合成 bundle 会掩盖，
    只有这里能红——probe_well_known 不再抓，真实 well_known 永不产该键。"""
    for p in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        if p not in au.PROBE_PATHS:
            bad.append(f"P8 PROBE_PATHS 少了 {p}（发现层回归：interpret 扫描测不到）")


def test_soft404_na(au, bad):
    """P9a 网络失败(0)/5xx 是「没看到」，不是站点风险。"""
    b = full_bundle(home=200)
    b["robots"] = [{"ua": "*", "disallow": [], "sitemap": []}]  # 否则 robots-ua warn(tier1) 污染 at-risk 断言
    b["soft_404"] = {"status": 0, "bytes": 0, "suspect_soft_404": False,
                     "error": "timed out"}
    fs = au.interpret(b)
    st = _st(fs, "soft-404 probe")
    if st != "na":
        bad.append(f"P9 soft-404 网络失败(0)应 na（没看到），实际 {st}")
    d = au.diagnose(fs)
    if d["verdict"] == "at-risk":
        bad.append("P9 soft-404 网络失败不得抬成 at-risk（站点没变，抖动翻结论）")
    b["soft_404"] = {"status": 502, "bytes": 0, "suspect_soft_404": False}
    if _st(au.interpret(b), "soft-404 probe") != "na":
        bad.append("P9 soft-404 5xx 应 na（同 P0 口径：没看到）")
    b["soft_404"] = {"status": 404, "bytes": 13707, "suspect_soft_404": False}
    if _st(au.interpret(b), "soft-404 probe") != "pass":
        bad.append("P9 soft-404 真 404 仍应 pass（站点事实，勿被误伤）")
    b["soft_404"] = {"status": 200, "bytes": 999, "suspect_soft_404": True}
    if _st(au.interpret(b), "soft-404 probe") != "fail":
        bad.append("P9 疑似软 404(200 带 not-found 文案)仍应 fail")


def test_verdict_partial(au, bad):
    """P9b partial 且无 fail/warn 时 verdict 不得字面 healthy。"""
    d = au.diagnose([], partial=True)
    if d["verdict"] != "insufficient":
        bad.append(f"P9 partial 无 fail/warn 应 insufficient，实际 {d['verdict']}"
                   "（healthy 字面值会被下游读成站没问题）")
    if not d.get("evidence_partial"):
        bad.append("P9 insufficient 必须同时 evidence_partial=true（表暂定）")
    d2 = au.diagnose([], partial=False)
    if d2["verdict"] != "healthy":
        bad.append(f"P9 非 partial 无 fail/warn 仍应 healthy，实际 {d2['verdict']}"
                   "（勿把修复扩大成全站禁 healthy）")


def test_mhost(au, bad):
    """P10a m-subdomain 双义分流：NXDOMAIN=pass 真阳性，超时=na。"""
    b = full_bundle(home=200)
    b["robots"] = [{"ua": "*", "disallow": [], "sitemap": []}]  # 否则 robots-ua warn 污染 verdict 断言
    b["sitemap"] = {"n": 100, "prefixes": [("a", 50), ("b", 50)]}  # 均衡前缀，避免 sitemap-mix warn 污染
    b["m_host"] = {"host": "m.x.com", "status": 0,
                   "error": "<urlopen error [Errno 8] nodename nor servname provided>"}
    if _st(au.interpret(b), "m-subdomain") != "pass":
        bad.append("P10 NXDOMAIN 应 pass（站点事实：没有 m 站，peercare.cn 实测真阳性）")
    b["m_host"] = {"host": "m.x.com", "status": 0, "error": "<urlopen error timed out>"}
    st = _st(au.interpret(b), "m-subdomain")
    if st != "na":
        bad.append(f"P10 m-host 超时(0) 应 na（没看到），实际 {st}")
    d = au.diagnose(au.interpret(b))
    if d["verdict"] == "at-risk":
        bad.append("P10 m-host 超时不得抬 at-risk（假 warn 假 pass 同害）")


def test_mhost_http(au, bad):
    """P10c m-host 的 HTTP 状态分流：5xx=na（同 soft-404 通则），200=warn（两套 HTML）。"""
    b = full_bundle(home=200)
    b["robots"] = [{"ua": "*", "disallow": [], "sitemap": []}]
    b["sitemap"] = {"n": 100, "prefixes": [("a", 50), ("b", 50)]}
    b["m_host"] = {"host": "m.x.com", "status": 502, "error": None}
    st5 = _st(au.interpret(b), "m-subdomain")
    if st5 != "na":
        bad.append(f"P10 m-host 5xx 应 na（同 soft-404：5xx=探针失败=没看到），实际 {st5}")
    if au.diagnose(au.interpret(b))["verdict"] == "at-risk":
        bad.append("P10 m-host 5xx 不得抬 at-risk（代理 502 与源站 502 无从区分，"
                   "warn 会往 tier-1 优先级塞假警报）")
    b["m_host"] = {"host": "m.x.com", "status": 200, "error": None}
    if _st(au.interpret(b), "m-subdomain") != "warn":
        bad.append("P10 m-host 200 应 warn（两套 HTML 风险，7.2）")


def test_display_none(au, bad):
    """P10e display:none 是 tier-1，此前门禁零覆盖（17 条 rule 里唯一一条）。
    隐藏文本只在首页 HTML 里数 inline style，首页没抓到就是没看到（na），
    不许退化成 pass——首轮实测 peercare 首页超时即走这条。"""
    b = full_bundle(home=200)
    b["html"]["display_none"] = 0
    if _st(au.interpret(b), "display:none") != "pass":
        bad.append("P10 首页无 inline display:none 应 pass")
    b["html"]["display_none"] = 7
    st = _st(au.interpret(b), "display:none")
    if st != "warn":
        bad.append(f"P10 有 inline display:none 应 warn（7.2 隐藏文本），实际 {st}")
    if au.diagnose(au.interpret(b))["verdict"] != "at-risk":
        bad.append("P10 display:none warn 属 tier-1，应把 verdict 抬到 at-risk")
    b2 = full_bundle(home=502)
    b2["html"]["display_none"] = 0
    if _st(au.interpret(b2), "display:none") != "na":
        bad.append("P10 首页没抓到时 display:none 应 na（没看到），不是 pass")


def test_mhost_dns(au, bad):
    """P10d NXDOMAIN 走真实 DNS，不靠 urllib 错误文本：文本随环境变（沙箱代理/本地化），
    同一站点事实会出两种结论——peercare.cn 二轮实测即被代理隧道 502 误判成 na，
    而 socket 直查该主机 errno=8 确认是 NXDOMAIN（站点事实：没有 m 站）。
    只 patch **下一层** socket.getaddrinfo：patch 被测函数 host_resolves 本身会让它的
    分支一行都跑不到（曾因此漏掉 gaierror→False 分支，变异 N6 静默通过）。"""
    import socket as _sk
    b = full_bundle(home=200)
    b["robots"] = [{"ua": "*", "disallow": [], "sitemap": []}]
    b["sitemap"] = {"n": 100, "prefixes": [("a", 50), ("b", 50)]}
    noise = "<urlopen error Tunnel connection failed: 502 Bad Gateway>"
    saved = au.socket.getaddrinfo

    def fake(raises):
        def f(host, port, *a, **k):
            if raises:
                raise raises
            return [(2, 1, 6, "", ("1.2.3.4", 443))]
        return f

    for err, want, note in (
        (_sk.gaierror(8, "nodename nor servname"), "pass",
         "DNS 确认 NXDOMAIN：代理噪声下仍须 pass（peercare 二轮实测真阳性）"),
        (None, "na", "DNS 解析得到但连不上=没看到"),
        (OSError("dns probe failed"), "na", "DNS 自己也没做成=没看到"),
    ):
        au.socket.getaddrinfo = fake(err)
        b["m_host"] = {"host": "m.peercare.cn", "status": 0, "error": noise}
        st = _st(au.interpret(b), "m-subdomain")
        if st != want:
            bad.append(f"P10 m-host 代理噪声 + DNS {err!r} 应 {want}（{note}），实际 {st}")
    au.socket.getaddrinfo = saved


def test_wayback(au, bad):
    """P10b CDX 倒序取最新。合成本地 HttpEcho 层不好做，双保险：
    (1) 查询行必须出现 limit=-3，且同一行不得出现 limit=3 结尾（docstring 提及不算）；
    (2) 用 monkeypatch 的 fetch 直接喂合成 cdx 响应，端到端断言 last200=最新有效行。"""
    import re as _re
    src = inspect.getsource(au.wayback)
    qline = [l for l in src.splitlines() if "fl=timestamp,statuscode" in l]
    if not qline or "limit=-3" not in qline[0]:
        bad.append("P10 wayback 查询行须 limit=-3（升序 limit=3 拿最早 3 条，last200 假数据）")
    # (2) 端到端：monkeypatch fetch 返回合成响应（最新窗口，最末行是 '-' 非有效状态，
    #     dated 过滤掉了它 last200 才取到 200 行；去掉过滤 last200 会变 '-'）
    cdx = ('[["timestamp","statuscode"],["20250323214853","200"],'
           '["20250323214855","301"],["20250323214856","-"]]')
    saved, seen = au.fetch, {}

    def fake_fetch(url, method="GET", timeout=20):
        seen["url"] = url
        return {"status": 200, "body": cdx, "url": url}

    au.fetch = fake_fetch
    try:
        wb = au.wayback("x.com")
    finally:
        au.fetch = saved
    # 必须断言**实际发出的请求**：只查源码字符串时，前置一行诱饵再赋真查询
    # （q = "...limit=-3"; q = "...limit=3"）就能让门禁放行，而行为已经坏了。
    if "limit=-3" not in (seen.get("url") or ""):
        bad.append(f"P10 wayback 实际请求 URL 须含 limit=-3（源码字符串检查可被诱饵行骗过），"
                   f"实际发出 {(seen.get('url') or '')[:80]!r}")
    if wb.get("last200") != "20250323214855":
        bad.append(f"P10 wayback last200 应为最新有效行 20250323214855，实际 {wb.get('last200')}"
                   "（'-' 行未过滤会取到无效 timestamp）")
    if wb.get("first200") != "20250323214853":
        bad.append(f"P10 wayback first200 应为窗口内最早有效行，实际 {wb.get('first200')}")


def test_sampled_live(au, bad):
    """P10c 分母只计活样本；非空全死 → na 且 evidence 报 live/dead。"""
    def sniff(status, reprint=False):
        return {"url": "https://x.com/p", "status": status, "title": "",
                "ld_types": [], "isBasedOn": reprint, "reprint_flag": reprint,
                "text_chars": 0, "html_chars": 0, "ssr": False, "error": None}
    b = full_bundle(home=200)
    b["sniffs"] = [sniff(502) for _ in range(8)]
    f = next(x for x in au.interpret(b) if x["rule"] == "sampled-originality")
    if f["status"] != "na":
        bad.append(f"P10 抽样非空全死应 na（曾 pass，代理噪声当站点事实），实际 {f['status']}")
    if "live=0" not in f["evidence"] or "dead=8" not in f["evidence"]:
        bad.append(f"P10 全死 evidence 须报 live/dead 分解，实际 {f['evidence']}")
    # 混合：5 活 3 死，3 转载 → 分母按 5 算，fail 门槛 max(1, 5//2)=2，3>=2 → fail
    b["sniffs"] = [sniff(200, reprint=True) for _ in range(3)] + \
                  [sniff(200) for _ in range(2)] + [sniff(502) for _ in range(3)]
    f = next(x for x in au.interpret(b) if x["rule"] == "sampled-originality")
    if f["status"] != "fail":
        bad.append(f"P10 混合样本分母应只计活样本(5)，3 转载应 fail，实际 {f['status']}")
    # 全活无转载 → pass
    b["sniffs"] = [sniff(200) for _ in range(6)]
    f = next(x for x in au.interpret(b) if x["rule"] == "sampled-originality")
    if f["status"] != "pass":
        bad.append(f"P10 全活无转载应 pass，实际 {f['status']}（勿扩大修复误伤真阳性）")


def main():
    if not Path(AU).exists():
        print("找不到 audit_url.py", AU, file=sys.stderr)
        return 1
    au, bad = load(), []
    test_confidence(au, bad)
    test_diagnose(au, bad)
    test_need(au, bad)
    test_interpret(au, bad)
    test_exit(au, bad)
    test_sitemap_path(au, bad)
    test_https(au, bad)
    test_sampled(au, bad)
    test_inconclusive(au, bad)
    test_probe_paths(au, bad)
    test_soft404_na(au, bad)
    test_verdict_partial(au, bad)
    test_mhost(au, bad)
    test_mhost_http(au, bad)
    test_display_none(au, bad)
    test_mhost_dns(au, bad)
    test_wayback(au, bad)
    test_sampled_live(au, bad)
    for b in bad:
        print("  FAIL", b)
    print(f"置信度/研判门禁: {len(bad)} 项失败" if bad else "置信度/研判门禁: 全部通过")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对用户给出的网址做未登录探针，只输出客观 HTTP 事实。

能核：状态码、跳转、robots/sitemap/llms.txt、语义 HTML、作者/LinkedIn 链接、
假 404 是否 200、m. 子域、Wayback 历史。
不能核：GSC Field CWV、Manual Action vs Deindex、品牌搜索量、外链 DR、
作者履历真伪。这些必须在报告里标「无数据」，禁止编造。

用法: python3 audit_url.py https://example.com

退出码（跟 JSON 的 status 对齐，不再只看 home.status）：
  0 = ok / partial   有可研判的输出；partial 时 stderr 另有提示，降级靠读 status+core_missing
  1 = inconclusive   三核全没拿到数据，findings 全 na，无研判
  2 = 用法错误
旧行为「home.status 为 0 就 exit 1」会把 robots/sitemap 仍可用的 partial 诊断整份丢掉，已废。

输出 JSON 顶层字段：
- status            ok | partial | inconclusive
                    核心探针(home/robots/sitemap)全没看到→inconclusive，findings 全 na
                    5xx/网络错=没看到；4xx=站点事实(确实没有)，不算没看到
- run_confidence    探针拿到数据的比例。partial 时 <1，代表「看到的少」不是「站差」。
                    m 站 NXDOMAIN（DNS 确认没有）是站点事实，计入「拿到了」
- sitemap_follow    ok=跟到(n>0) / lost=index200但子表n=0 / absent=站点没有(404) / fail=探针失败
- core_missing[]    核心探针里没看到的是哪几个
- findings[]        每条带 rule/status/evidence/loki 编号。status 五值，别混：
                    na   = 探针**没看到**（5xx/网络错/子表跟丢/没抽样）——不许读成「没问题」
                    seen = 探针**看到了材料但不自动打分**（title-h1 / json-ld / jsonld-types /
                          linkedin）。材料就在 evidence 里，判断权归输出合同第 4 条。
                          seen 既不是缺口(na)也不是风险(warn)，不进 gaps 也不进 priority。
                          （2026-09-01 拆：旧版这四条恒 na，与「na=没看到」的纪律自相矛盾——
                           材料都给了还叫没看到，Agent 只能二选一：不敢用已看到的 title，
                           或破坏 na 纪律把它当结论用。）
                    pass/warn/fail = 探针按规则判过的，warn/fail 才进 priority
- cannot[]          固定禁编清单（无数据项显式挡，禁止编造）
- next_collect[]    按本站 na/warn 动态生成，**只含探针核不到的项**（GSC/Frog/回链/域名历史），
                    不含「再拉一遍 sitemap」这类重跑同一探针的动作
- diagnosis{}       研判层（纯规则，不调 LLM），是排序草稿不是结论：
                    verdict  critical=有 fail / at-risk=有技术阻断或信任红线 warn /
                            needs-focus=只剩定性或常识类 warn（7.4 集中度归此类，不是风险）/
                            insufficient=partial 且无 fail/warn（看到的少，勿读成站没问题）
                    focus_reading  7.4 定性一句话，如「站点可能被当成 posts 站」
                    priority[]     按碰撞表五档排序（技术阻断→信任→定性→内容→刹车），
                                   不用口诀号当致命度
                    gaps[]         na 缺口单列，不冒充风险
                    to_judge[]     seen 项单列：材料已给出，待输出合同第 4 条判断。
                                   **不进 gaps（不是缺数据）、不进 priority（不是风险）**
                    evidence_partial  证据不全（status=partial）时为 true
"""
import json
import re
import sys
import ssl
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
TIMEOUT = 20
FAKE = "/loki-audit-not-found-7f3c9e"


def origin_of(url):
    p = urlparse(url if "://" in url else "https://" + url)
    scheme = p.scheme or "https"
    host = p.netloc or p.path.split("/")[0]
    return f"{scheme}://{host}".rstrip("/")


def fetch(url, method="GET", timeout=TIMEOUT):
    req = Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=timeout, context=CTX) as r:
            body = r.read(2_000_000)
            return {
                "url": r.geturl(), "status": r.status,
                "ctype": r.headers.get("Content-Type", ""),
                "body": body.decode("utf-8", "replace"),
            }
    except HTTPError as e:
        raw = e.read(20_000) if e.fp else b""
        return {"url": url, "status": e.code, "ctype": "",
                "body": raw.decode("utf-8", "replace")}
    except (URLError, TimeoutError, ssl.SSLError, ValueError) as e:
        return {"url": url, "status": 0, "ctype": "", "body": "", "error": str(e)}


# 探针发现层的清单——「到底抓哪些 well-known 路径」由这份常量决定。
# 单独提出是为了能被 confidence_gate 直接断言：interpret 只扫 well_known 里已存在
# 的键，若这里漏掉某个 sitemap 变体，真实抓取永不产该键、扫描再全也白搭，而合成
# bundle 会绕过这一层。所以发现层要有自己的门禁（见 P8 / test_probe_paths）。
PROBE_PATHS = ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml",
               "/sitemap-index.xml", "/llms.txt", "/ads.txt")


def probe_well_known(origin):
    """探 well-known 路径，返回 (well_known, sm_bodies)。
    JSON 侧只留 status/bytes/error；200 的 sitemap body **另行留住**，
    供 sitemap_mix 复用——实测 well_known 已 200(186B) 而 sitemap_mix 二抓
    同一 URL 超时，双次 fetch 让本可避免的抖动翻掉结论。"""
    out, sm_bodies = {}, {}
    for path in PROBE_PATHS:
        r = fetch(origin + path)
        out[path] = {"status": r["status"], "bytes": len(r.get("body") or ""),
                     "error": r.get("error")}
        if r["status"] == 200 and "sitemap" in path:
            sm_bodies[origin + path] = r.get("body") or ""
    return out, sm_bodies


class HomeParse(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.links, self.h1 = set(), [], 0
        self._title, self._capture = [], None
        self.jsonld, self.display_none = 0, 0
        self.generator = None

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        ad = {k.lower(): (v or "") for k, v in attrs}
        self._mark(tag, ad)
        self._capture = "title" if tag == "title" else None

    def _mark(self, tag, ad):
        href, style, typ = ad.get("href"), ad.get("style", ""), ad.get("type", "")
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and href:
            self.links.append(href)
        if tag == "script" and "ld+json" in typ.lower():
            self.jsonld += 1
        if tag == "meta" and ad.get("name", "").lower() == "generator":
            self.generator = ad.get("content") or ""
        if "display:none" in style.lower().replace(" ", ""):
            self.display_none += 1

    def handle_data(self, data):
        if self._capture == "title":
            self._title.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self._capture = None


def parse_home(html):
    p = HomeParse()
    try:
        p.feed(html or "")
    except Exception:
        pass
    hrefs = p.links
    return {
        "title": re.sub(r"\s+", " ", "".join(p._title)).strip()[:200],
        "h1": p.h1,
        "semantic": {t: t in p.tags for t in
                     ("header", "nav", "main", "article", "footer", "aside")},
        "jsonld": p.jsonld,
        "display_none": p.display_none,
        "generator": p.generator,
        "linkedin": sum(1 for h in hrefs if "linkedin.com" in h.lower()),
        "about": [h for h in hrefs if re.search(r"about|author|team|作者|关于", h, re.I)][:8],
        "n_links": len(hrefs),
    }


def wayback(host):
    """P10：CDX limit=-3 取**最新** 3 条（默认升序，limit=3 拿到的是最早 3 条——
    旧代码 last200 实为第 3 早快照，比真实最新早约 10 个月，属假数据）。
    statuscode 取了要过滤：'-'（非 HTTP 抓取）与重定向行不代表该时刻的页面状态，
    first/last 各取**带有效状态码**行的 timestamp。"""
    q = ("https://web.archive.org/cdx/search/cdx?url=" + host +
         "&output=json&fl=timestamp,statuscode&limit=-3")
    r = fetch(q, timeout=15)
    if r["status"] != 200 or not (r.get("body") or "").strip():
        return {"ok": False, "error": r.get("error") or f"http {r['status']}"}
    try:
        rows = json.loads(r["body"])
    except json.JSONDecodeError:
        return {"ok": False, "error": "cdx not json"}
    hits = [h for h in (rows[1:] if rows else []) if len(h) > 1]
    dated = [h for h in hits if h[1].isdigit()]
    first = dated[0][0] if dated else (hits[0][0] if hits else None)
    last = dated[-1][0] if dated else (hits[-1][0] if hits else None)
    return {"ok": bool(hits), "first200": first, "last200": last, "sample": len(hits)}


def soft_404(origin):
    r = fetch(origin + FAKE)
    body = r.get("body") or ""
    looks_nf = bool(re.search(r"not found|404|页面不存在|找不到", body, re.I))
    return {
        "status": r["status"], "bytes": len(body),
        "suspect_soft_404": r["status"] == 200 and looks_nf,
        "error": r.get("error"),
    }


def soft404_verdict(s404):
    """P9（2026-09-01 实跑 peercare 抓到）：0/5xx=探针失败=没看到=na，同 P0 口径。
    旧版 status==0 落 warn（tier1）→ diagnose 打 at-risk：站点没变，网络抖动就能把
    结论从 pass 翻成 at-risk。4xx/200/3xx 是站点事实，走 pass/warn/fail 不变。"""
    st = s404["status"]
    if s404["suspect_soft_404"]:
        return "fail"
    if st == 0 or st >= 500:
        return "na"
    return "pass" if st in (404, 410) else "warn"


def is_nxdomain(mh):
    """P10b（2026-09-01 二轮实测抓到）：NXDOMAIN 必须走真实 DNS，不能靠 urllib 的
    错误文本正则。错误文本随环境变——peercare.cn 同一主机、同一站点事实（m 子域无
    DNS 解析，socket 直查 errno=8），一次报 nodename（→pass 真阳性）、一次因沙箱代理
    隧道报 "Tunnel connection failed: 502"（文本不匹配→误判 na）。同一个站两种结论，
    正是 P9「抖动不该翻结论」的翻版。DNS 解析不受 HTTP 代理影响，才是站点事实。
    布尔返回：True=确认 NXDOMAIN（gaierror）；解析到/解析没做成都返 False
    （后者按「没看到」处理，由调用方落 na——单消费者双态，不留三态等价分支）。"""
    host = (mh.get("host") or "").split("://")[-1].split("/")[0].strip()
    if not host:
        return False
    try:
        socket.getaddrinfo(host, None)
        return False
    except socket.gaierror:
        return True
    except (OSError, UnicodeError):
        return False


def mhost_verdict(mh):
    """P10：m-host 的 status=0 是**双义**，按站点事实分流，不能统一收口：
    NXDOMAIN（DNS 查不到）＝站点事实「没有 m 站」→ pass 真阳性；
    主机存在但连不上＝探针没看到 → na。统一 responded() 会把 NXDOMAIN 真阳性改坏成 na。
    200＝两套 HTML 风险 → warn（7.2 不变）。
    5xx＝na（同 soft-404 与本仓判定 HTTP 通则：5xx 是探针失败＝没看到）。
    曾按「m 站活着但报错」给 warn，但代理 502 与源站 502 在 HTTP 层无从区分，
    闸门一开就往 tier-1 优先级塞假警报；na 不撒谎，且会正确触发 NEED 的 Frog 搜集项。"""
    st, err = mh["status"], (mh.get("error") or "")
    if st == 200:
        return "warn"
    if st >= 500:
        return "na"
    if st != 0:
        return "pass"
    if re.search(r"nodename|gaierror|not known|Name or service", err):
        return "pass"
    return "pass" if is_nxdomain(mh) else "na"


def mobile_host(origin):
    p = urlparse(origin)
    host = p.netloc
    if host.startswith("www."):
        m = "m." + host[4:]
    else:
        m = "m." + host
    r = fetch(f"{p.scheme}://{m}/")
    return {"host": m, "status": r["status"], "final": r.get("url"),
            "error": r.get("error")}


def _robots_flush(blocks, ua, acc):
    blocks.append({"ua": ua, "disallow": list(acc["disallow"]),
                   "sitemap": list(acc["sitemap"])})


def parse_robots(text):
    """按 User-agent 块拆 Allow/Disallow/Sitemap。
    首个 User-agent 行不 flush 初始累加器——旧版会在这里先吐一个空 * 幽灵块，
    让几乎每个 robots 的 evidence 头部撒谎，且 parse 永不返回空列表
    （「解析不出 UA 块→warn」对真实解析器成了死断言）。"""
    blocks, ua, acc, started = [], "*", {"disallow": [], "sitemap": []}, False
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if started:
                _robots_flush(blocks, ua, acc)
            started, ua = True, v
            acc = {"disallow": [], "sitemap": []}
            continue
        if k in ("disallow", "sitemap") and v:
            acc[k].append(v)
    if started:
        _robots_flush(blocks, ua, acc)
    return blocks


def sitemap_mix(origin, well_known, sm_bodies=None):
    """跟 sitemap index，统计路径前缀并各抽 2 个内页。
    种子 body 优先复用 well_known 层已抓到的 200 结果（sm_bodies），
    不再对同一 URL 二次请求——二抓撞上抖动会把已确认 200 的站翻成 lost。"""
    seeds, seen, locs, fails = [], set(), [], []
    for path, meta in well_known.items():
        if "sitemap" in path and meta.get("status") == 200:
            seeds.append(origin + path)
    for s in seeds:
        body = (sm_bodies or {}).get(s)
        if body is None:
            r = fetch(s)
            if r["status"] != 200:
                fails.append(f"{s.split('/')[-1]}={r['status']}")
                continue
            body = r.get("body") or ""
        kids = re.findall(r"<loc>\s*(.*?)\s*</loc>", body, re.I)
        _ingest_locs(kids, seen, locs, seeds)
        if len(locs) >= 4000:
            break
    from collections import Counter, defaultdict
    pref, buckets = Counter(), defaultdict(list)
    for loc in locs:
        top = (urlparse(loc).path.strip("/").split("/") or ["(home)"])[0] or "(home)"
        pref[top] += 1
        if len(buckets[top]) < 3 and urlparse(loc).path.strip("/").count("/") >= 1:
            buckets[top].append(loc)
    return {"n": len(locs), "prefixes": pref.most_common(15),
            "samples": {k: v for k, v in buckets.items() if v},
            "fetch_fail": fails[:8]}


def _ingest_locs(kids, seen, locs, seeds):
    for loc in kids:
        if loc in seen:
            continue
        seen.add(loc)
        (seeds if loc.endswith(".xml") else locs).append(loc)


def sniff_page(url):
    r = fetch(url)
    html = r.get("body") or ""
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
    based = bool(re.search(r"isBasedOn", html))
    reprint = bool(re.search(r"转载|原文链接|来源：", html))
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return {
        "url": r.get("url") or url, "status": r["status"],
        "title": re.sub(r"\s+", " ", (title.group(1) if title else ""))[:160],
        "ld_types": sorted(set(types))[:12],
        "isBasedOn": based, "reprint_flag": reprint,
        "text_chars": len(text), "html_chars": len(html),
        "ssr": len(text) > 800,
        "error": r.get("error"),
    }


def sitemap_presence(wk):
    """sitemap 存在性三值：任一 200=pass；全 4xx=站点事实(确实没有)=warn；
    混有 0/5xx=探针没看到=na。旧版把 0/5xx 也落 warn，是拿「探针超时」
    装扮成「站点没有 sitemap」，与 P9「0/5xx=没看到=na」对打。"""
    sm_paths = [p for p in wk if "sitemap" in p]
    stats = [(wk[p] or {}).get("status") for p in sm_paths]
    if any(s == 200 for s in stats):
        st = "pass"
    elif stats and all(isinstance(s, int) and 400 <= s < 500 for s in stats):
        st = "warn"
    else:
        st = "na"
    ev = f"sitemap paths={ {p: (wk[p] or {}).get('status') for p in sm_paths} }"
    return st, ev


def interpret(bundle, conclusive=True):
    """把探针事实映射到 Loki 口诀编号。status: pass/warn/fail/na。
    conclusive=False（核心探针全挂）时所有 rule 强制 na——没真看到站就不下结论。"""
    home, wk, s404 = bundle["home"], bundle["well_known"], bundle["soft_404"]
    html, sem = bundle["html"], bundle["html"]["semantic"]
    out = []

    def add(rule, status, evidence, loki):
        out.append({"rule": rule, "status": status, "evidence": evidence, "loki": loki})

    ok = home.get("status") == 200
    robots = wk["/robots.txt"]["status"]
    add("robots.txt", "pass" if robots == 200 else "warn", f"HTTP {robots}", "常识·不进口诀，仅作探针")
    add("sitemap", *sitemap_presence(wk), "常识")
    ll = wk["/llms.txt"]["status"]
    add("llms.txt", "seen" if 0 < ll < 500 else "na", f"HTTP {ll}（谷歌 AIO 不管；广义 GEO 可能要）", "2.3")
    add("semantic main", "na" if not ok else ("pass" if sem.get("main") else "fail"),
        f"home={home.get('status')} tags={ {k:v for k,v in sem.items()} }", "7.5")
    add("h1", "na" if not ok else ("pass" if html["h1"] == 1 else "warn"), f"home={home.get('status')} h1 count={html['h1']}", "常识")
    st_seen = "seen" if ok else "na"
    add("linkedin", st_seen, f"linkedin links={html['linkedin']} about={html['about'][:4]}", "5.1")
    add("json-ld", st_seen, f"jsonld scripts={html['jsonld']}", "2.1 反例·schema 非必做")
    add("display:none", "na" if not ok else ("warn" if html["display_none"] else "pass"),
        f"inline display:none={html['display_none']}", "7.2")
    add("soft-404 probe", soft404_verdict(s404),
        f"GET {FAKE} → {s404['status']} bytes={s404['bytes']}", "1.4 7.1")
    wb = bundle["wayback"]
    add("wayback", "na" if not wb.get("ok") else "pass",
        f"first200={wb.get('first200')} last200={wb.get('last200')}", "4.1")
    mh = bundle["m_host"]
    add("m-subdomain", mhost_verdict(mh),
        f"{mh['host']} status={mh['status']} error={mh.get('error')}", "7.2")
    out.extend(interpret_focus(bundle))
    if not conclusive:
        out = [{**f, "status": "na"} for f in out]
    return out


def originality_finding(samples):
    """P10c 原创度**分母只计活样本**：502/超时的死样本没拿到正文，不算「看过且原创」；
    全死 = 一个都没看到 = na（旧分母含死样本时 8 个全 502 也报 pass，把代理噪声当
    站点事实）。evidence 报 live/dead 分解，让「看到几个」与「看到什么」分开读。"""
    live = [s for s in samples if s.get("status") == 200]
    dead = len(samples) - len(live)
    reprint = sum(1 for s in live if s.get("isBasedOn") or s.get("reprint_flag"))
    ld = sorted({t for s in live for t in (s.get("ld_types") or [])})
    if not samples:
        ev = "未抽样(探针未抓内页，非 sitemap 跟丢) sniffed=0"
    elif dead:
        ev = f"sniffed={len(samples)} live={len(live)} dead={dead} reprint={reprint} inner_ld={ld}"
    else:
        ev = f"sniffed={len(samples)} reprint={reprint} inner_ld={ld}"
    return {"rule": "sampled-originality",
            "status": ("na" if not samples or not live else
                       "fail" if reprint >= max(1, len(live) // 2) else "pass"),
            "evidence": ev,
            "loki": "6.2 Effort/原创；未抽样/抽样全死是 na，不是 pass；跟丢归 sitemap_follow"}


def interpret_focus(bundle):
    """sitemap 路径结构 + 抽样页原创度 → Loki 7.4 / 6.2 / 2.1。"""
    out, mix = [], bundle.get("sitemap") or {}
    prefs, n, add = mix.get("prefixes") or [], mix.get("n") or 0, out.append
    st_seen = "seen" if bundle["home"].get("status") == 200 else "na"
    top = prefs[0][0] if prefs else ""
    share = (prefs[0][1] / n) if n and prefs else 0
    unseen = n == 0 and bundle.get("sitemap_follow") in ("lost", "fail")
    add({"rule": "sitemap-mix",
         "status": ("na" if unseen else "warn" if share >= 0.6 else "pass"),
         "evidence": f"n={n} prefixes={prefs[:8]} top={top} share={share:.0%} fail={mix.get('fetch_fail')}",
         "focus": {"top": top, "share": share, "n": n},
         "loki": ("7.4 siteFocus；没看到分布(子表跟丢或探针失败)=na，不是健康" if unseen
                  else f"7.4 siteFocus；单一前缀 {top} 占 {share:.0%} 集中度过高=warn" if share >= 0.6
                  else "7.4 siteFocus；前缀分布均衡=pass")})
    add(originality_finding(bundle.get("sniffs") or []))
    add({"rule": "jsonld-types", "status": st_seen,
         "evidence": f"home @type={bundle.get('home_ld_types') or []}",
         "loki": "2.1 schema 非 GEO 必做；有也不等于能排"})
    add({"rule": "title-h1", "status": st_seen,
         "evidence": f"title={(bundle.get('title_text') or '')[:80]!r} h1={(bundle.get('h1_text') or '')[:80]!r}",
         "loki": "6.3 不要铺词；7.4 About/首页是定性不是堆品牌 slogan"})
    bots = bundle.get("robots") or []
    add({"rule": "robots-ua", "status": "pass" if bots else "warn",
         "evidence": str(bots)[:240],
         "loki": "G7 常识：分 UA 的 Disallow 必须读，不能当成全站隔离"})
    origin = bundle.get("origin") or ""
    add({"rule": "https",
         "status": "pass" if origin.startswith("https") else "warn",
         "evidence": f"origin={origin} home_final={(bundle.get('home') or {}).get('url')}",
         "loki": "7.1"})
    return out


def sniff_samples(mix):
    out = []
    for urls in list((mix.get("samples") or {}).values())[:4]:
        for u in urls[:2]:
            if urlparse(u).path.count("/") >= 2:
                out.append(sniff_page(u))
    return out


CANNOT = [
    "GSC Field CWV（7.3）要 Search Console 或 cruxvis，禁止编 PSI 分数充 Field Data",
    "Manual Action vs Deindex（1.1）要 GSC 处罚报告",
    "品牌搜索量 vs 外链（3.3）无搜索量接口",
    "外链质量/DR（3.1-3.2）无 Ahrefs，禁止编造",
    "作者履历真伪（5.1）只能看见有没有 LinkedIn 链接",
    "site: 收录结构要搜索引擎结果，脚本后必须再 web_search site:域名",
    "整站软 404/JS 渲染差要 Screaming Frog（#116 他本人工具优先）",
]


def compute_confidence(bundle):
    """P0/P3 置信度门禁。5xx/网络错(0)=探针失败=没看到；4xx=站点事实(确实没有)不算没看到。
    旧 got() 把 502 也当 seen（502 不是 0/None），首页 502 仍报 status=ok，已修。
    follow: ok=跟到(n>0) / lost=index200但n=0 / absent=站点没有(404) / fail=探针失败。"""
    wk = bundle["well_known"]
    mix = bundle.get("sitemap") or {}

    def responded(m):
        st = (m or {}).get("status")
        return bool(m) and isinstance(st, int) and 0 < st < 500 and not m.get("error")

    sm = [(p, m) for p, m in wk.items() if "sitemap" in p]
    seen_any = any(responded(m) for _, m in sm)
    ok_any = any(responded(m) and m["status"] == 200 for _, m in sm)
    n = mix.get("n") or 0
    follow = ("fail" if not seen_any else "absent" if not ok_any
              else "lost" if n == 0 else "ok")
    mh = bundle["m_host"]
    # NXDOMAIN 是真实 DNS 确认的站点事实（判定层已落 pass），同样算「看到了」，
    # 否则判定层与置信层对同一事实各说各话（实测 conf 0.5 应为 0.67）。
    nx_seen = mh.get("status") == 0 and mhost_verdict(mh) == "pass"
    probes = {
        "home": responded(bundle["home"]),
        "robots": responded(wk.get("/robots.txt")),
        "sitemap": follow in ("ok", "absent"),
        "wayback": bool(bundle["wayback"].get("ok")),
        "soft_404": responded(bundle["soft_404"]),
        "m_host": responded(mh) or nx_seen,
    }
    core = ("home", "robots", "sitemap")
    seen = sum(1 for v in probes.values() if v)
    missing = [c for c in core if not probes[c]]
    return {"probes": probes, "score": round(seen / len(probes), 2),
            "sitemap_follow": follow, "core_missing": missing,
            "inconclusive": len(missing) == len(core),
            "partial": 0 < len(missing) < len(core)}


TIER = {
    # 1 技术阻断（抓取/404/<main>/两套 HTML）
    "soft-404 probe": 1, "semantic main": 1, "https": 1,
    "display:none": 1, "m-subdomain": 1, "robots-ua": 1, "robots.txt": 1,
    # 2 信任红线（YMYL 假作者、脏域名、原创门槛）
    "wayback": 2, "sampled-originality": 2, "linkedin": 2,
    # 3 站点定性（focus / About / 一页一词）
    "sitemap-mix": 3, "title-h1": 3,
    # 4 内容门槛与常识（不拔高，不压过定性）
    "sitemap": 4, "h1": 4,
    # 5 机制刹车 / 明确不进口诀
    "llms.txt": 5, "json-ld": 5, "jsonld-types": 5,
}


def diagnose(findings, partial=False):
    """P1a 研判层。按 SKILL.md 碰撞表五档排序（技术阻断→信任→定性→内容→刹车），
    **不用口诀号当致命度**：7.4 是定性不是致命；「常识」无数字不该默认拔高压过 7.4。
    at-risk 只由 fail、或 tier<=2（技术阻断/信任红线）的 warn 触发；
    只剩定性/常识类 warn 时给 needs-focus，并在 focus_reading 给定性解读。
    partial 且无 fail/warn 时给 insufficient（P9）：healthy 字面值会被下游读成
    「站没问题」，而那时一半核心探针没看到——合同护栏只挡守纪律的调用方。"""
    action, gaps, judge = [], [], []
    BK = {"seen": judge, "na": gaps}
    for f in findings:
        if f["status"] == "pass":
            continue
        if f["status"] in BK:
            BK[f["status"]].append({"rule": f["rule"], "loki": f["loki"],
                                    "evidence": f["evidence"]})
            continue
        action.append((TIER.get(f["rule"], 5), 0 if f["status"] == "fail" else 1, f))
    action.sort(key=lambda x: (x[0], x[1]))
    priority = [{"rule": f["rule"], "status": f["status"], "loki": f["loki"],
                 "why": f["evidence"]} for _, _, f in action[:5]]
    fails = [f for f in findings if f["status"] == "fail"]
    blocking = [f for f in findings
                if f["status"] == "warn" and TIER.get(f["rule"], 5) <= 2]
    verdict = ("critical" if fails else "at-risk" if blocking
               else "needs-focus" if action else "healthy")
    if partial and verdict == "healthy":
        verdict = "insufficient"
    focus = next((f.get("focus") for f in findings
                  if f["rule"] == "sitemap-mix" and (f.get("focus") or {}).get("n")), None)
    reading = (f"站点可能被当成 {focus['top']} 站（{focus['top']} 占 {focus['share']:.0%}，"
               f"n={focus['n']}）" if focus else None)
    risk = (f"最优先: {action[0][2]['rule']} ({action[0][2]['status']}, "
            f"loki {action[0][2]['loki']})" if action else
            "无 fail/warn；na=探针没看到，seen=材料已给出待按输出合同判断")
    return {"verdict": verdict, "priority": priority, "top_risk": risk,
            "focus_reading": reading, "gaps": gaps, "to_judge": judge, "n_fail": len(fails),
            "n_warn": sum(1 for f in findings if f["status"] == "warn"),
            "evidence_partial": partial}


NEED = {
    "soft-404 probe": ("GSC 索引→网页索引编制，导出未编入原因（软404/被robots屏蔽/已抓取未编入）",
                       "1.4 7.1", "整站软404 规模只有 GSC 有；探针只打了一个假 URL"),
    "semantic main": ("Frog 整站爬，导 Raw 与 Rendered HTML，看 <main> 里实际进了什么",
                      "7.5 7.2", "探针只看首页，整站结构要 Frog"),
    "display:none": ("Frog 查 inline display:none 与 Raw/Rendered 文本差", "7.2",
                     "隐藏文本的整站分布要爬"),
    "m-subdomain": ("Frog 分别爬 m. 与主域，比 Raw vs Rendered", "7.2",
                    "两套 HTML 的规模要整站爬"),
    "robots-ua": ("逐 UA 读 robots 全文 Disallow，核对 User-agent:*", "G7",
                  "分 UA 屏蔽要人工读全文"),
    "robots.txt": ("GSC 覆盖报告看被 robots 屏蔽的 URL 量", "7.1",
                   "屏蔽的影响面要 GSC"),
    "https": ("跟一次 http→https 跳转链与证书（浏览器地址栏即可）", "7.1",
              "跳转链探针只看 origin 一层"),
    "wayback": ("Ahrefs/SEMrush/Majestic + Wayback 查域名历史（spam/PBN/黄赌毒）", "4.1",
                "域名黑历史要付费工具；探针只有 wayback 首收录"),
    "sampled-originality": ("GSC 效果页对齐下跌窗口：掉的是转化页还是博客页", "6.2 6.1",
                            "探针只 sniff 抽样页，全站原创度要 GSC 或人工看"),
}
# 刻意不在 NEED 里的 rule（有数据/不是搜集项，进了就是「再跑同一探针」或稀释）：
#   sitemap、sitemap-mix：已有 n 与 share，下一步是 7.4 定性动作（About/焦点），
#     不是「再拉 sitemap-0.xml 重数一遍」；跟丢由 sitemap_follow=lost 显式报，不靠搜集兜。
#   title-h1 / json-ld / jsonld-types：seen 走输出合同第 4 条「一页一词表」，是动作不是搜集。
#   linkedin：探针数到的链接数就是材料（seen）。5.1 只在 EEAT 被问责的类目适用，
#     工具/文档站不硬套——这个类目判断探针做不了，交给合同，不按站无差别索要截图。
#   h1：常识，不进口诀。
#   llms.txt：2.3 刹车项，不列为搜集项。


def collect_next(bundle):
    """P1b 按站生成下一步：只对本站 na/warn 的 rule 出搜集动作。"""
    out = []
    for f in bundle.get("findings") or []:
        if f["status"] in ("na", "warn") and f["rule"] in NEED:
            need, loki, read_as = NEED[f["rule"]]
            out.append({"need": need, "loki": loki, "trigger": f["rule"], "read_as": read_as})
    if not out:
        out = [{"need": "GSC 效果/覆盖基线", "loki": "6.3 7.1",
                "trigger": "baseline", "read_as": "先拿 GSC 数据再研判"}]
    return out


def attach_report(bundle):
    conf = compute_confidence(bundle)
    bundle["run_confidence"] = conf["score"]
    bundle["probe_status"] = conf["probes"]
    bundle["inconclusive"] = conf["inconclusive"]
    bundle["partial"] = conf["partial"]
    bundle["sitemap_follow"] = conf["sitemap_follow"]
    bundle["core_missing"] = conf["core_missing"]
    bundle["status"] = ("inconclusive" if conf["inconclusive"]
                        else "partial" if conf["partial"] else "ok")
    bundle["findings"] = interpret(bundle, conclusive=not conf["inconclusive"])
    bundle["cannot"] = CANNOT
    bundle["next_collect"] = collect_next(bundle)
    if conf["inconclusive"]:
        bundle["diagnosis"] = {"verdict": "inconclusive", "priority": [],
                               "top_risk": "核心探针全没拿到数据，无法研判",
                               "focus_reading": None, "gaps": [], "to_judge": [],
                               "n_fail": 0, "n_warn": 0, "evidence_partial": True}
    else:
        bundle["diagnosis"] = diagnose(bundle["findings"], partial=conf["partial"])
    return bundle


def audit(url):
    origin = origin_of(url)
    home = fetch(origin + "/")
    html = parse_home(home.get("body") or "")
    host = urlparse(origin).netloc
    wk, sm_bodies = probe_well_known(origin)
    rb = fetch(origin + "/robots.txt")
    mix = sitemap_mix(origin, wk, sm_bodies)
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", home.get("body") or "", re.I | re.S)
    h1_txt = re.sub(r"<[^>]+>", "", h1s[0] if h1s else "")
    bundle = {
        "input": url, "origin": origin,
        "home": {k: home[k] for k in ("url", "status", "ctype") if k in home},
        "html": html, "well_known": wk, "robots": parse_robots(rb.get("body") or ""),
        "soft_404": soft_404(origin), "wayback": wayback(host),
        "m_host": mobile_host(origin), "sitemap": mix, "sniffs": sniff_samples(mix),
        "home_ld_types": sorted(set(re.findall(
            r'"@type"\s*:\s*"([^"]+)"', home.get("body") or "")))[:20],
        "title_text": html.get("title") or "", "h1_text": re.sub(r"\s+", " ", h1_txt)[:160],
    }
    if home.get("error"):
        bundle["home"]["error"] = home["error"]
    if rb.get("status") == 200:
        wk["/robots.txt"] = {"status": 200, "bytes": len(rb.get("body") or "")}
    return attach_report(bundle)


EXIT = {"ok": 0, "partial": 0, "inconclusive": 1}
NOTE = {"partial": "JSON 仍有可研判的输出，但不要当整站看见了",
        "inconclusive": "三核全没拿到，findings 全 na——别硬答，只报这次没看到什么"}
# partial 也 exit 0：那是有可研判输出的降级态，不是失败。旧「home.status 为 0 就 exit 1」
# 会把 robots/sitemap 仍可用的 partial 诊断整份丢掉；降级信号改由 JSON status +
# core_missing 表达，并在 stderr 补一行，不靠退出码。
# NOTE 必须按状态分开写：inconclusive 时 JSON 里并没有可研判的输出，
# 沿用 partial 那句「仍有输出」会让调用方去读一份全 na 的 JSON 找结论。


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("用法: python3 audit_url.py https://example.com", file=sys.stderr)
        return 2
    data = audit(sys.argv[1].strip())
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()
    st = data.get("status") or "inconclusive"
    if st != "ok":
        print(f"[loki-seo] status={st} core_missing={data.get('core_missing')} "
              f"sitemap_follow={data.get('sitemap_follow')} "
              f"run_confidence={data.get('run_confidence')}：{NOTE[st]}",
              file=sys.stderr)
    return EXIT.get(st, 1)


if __name__ == "__main__":
    sys.exit(main())

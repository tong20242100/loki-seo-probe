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
import argparse
import json
import re
import sys
import time
import ssl
import socket
from pathlib import Path
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
TIMEOUT = 20
RETRIES = 3
BACKOFF = 1.0
_RETRY_HTTP = frozenset((502, 503, 504))
FAKE = "/loki-audit-not-found-7f3c9e"

# 可选抓取后端：curl_cffi 用真实浏览器 TLS/JA3 指纹（impersonate=chrome）绕过大多数
# WAF/Cloudflare 对裸 urllib 的拦截，避免把被拦的请求误判成 na / 站差。
# 缺失时自动回退标准库 urllib——CI 与干净环境默认走 urllib，门禁不受影响。
try:
    from curl_cffi import requests as _creq
    from curl_cffi.requests.errors import RequestsError
    _HAVE_STEALTH = True
except Exception:
    _creq = None
    RequestsError = Exception
    _HAVE_STEALTH = False


def origin_of(url):
    p = urlparse(url if "://" in url else "https://" + url)
    scheme = p.scheme or "https"
    host = p.netloc or p.path.split("/")[0]
    return f"{scheme}://{host}".rstrip("/")


def _fetch_urllib(url, method, timeout):
    req = Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=timeout, context=CTX) as r:
            body = r.read(2_000_000)
            return {"url": r.geturl(), "status": r.status,
                    "ctype": r.headers.get("Content-Type", ""),
                    "body": body.decode("utf-8", "replace")}
    except HTTPError as e:
        raw = e.read(20_000) if e.fp else b""
        return {"url": url, "status": e.code, "ctype": "",
                "body": raw.decode("utf-8", "replace")}


def _fetch_stealth(url, method, timeout):
    resp = _creq.request(method, url, impersonate="chrome",
                         headers={"User-Agent": UA}, timeout=timeout,
                         allow_redirects=True)
    body = resp.content[:2_000_000]
    return {"url": resp.url, "status": resp.status_code,
            "ctype": resp.headers.get("Content-Type", ""),
            "body": body.decode("utf-8", "replace")}


def fetch(url, method="GET", timeout=TIMEOUT):
    last = None
    for attempt in range(RETRIES):
        try:
            if _HAVE_STEALTH:
                r = _fetch_stealth(url, method, timeout)
            else:
                r = _fetch_urllib(url, method, timeout)
        except (URLError, TimeoutError, ssl.SSLError,
                ValueError, OSError, RequestsError) as e:
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF * (2 ** attempt))
                continue
            return {"url": url, "status": 0, "ctype": "", "body": "",
                    "error": str(e)}
        if r["status"] in _RETRY_HTTP and attempt < RETRIES - 1:
            last = r
            time.sleep(BACKOFF * (2 ** attempt))
            continue
        return r
    return {"url": url, "status": 0, "ctype": "", "body": "",
            "error": f"重试 {RETRIES} 次仍失败: {last}"}


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


# 探针核不到、必须由用户亲自处理/确认的项。
# mode: "todo"=待办任务（用户去拉/查）；"confirm"=需用户自己确认（探针看不到该状态）。
# task: 用户要做什么；why: 为什么探针不能代做（不写成「禁止编」式防御腔）。
# forbid: 给 AI 闭环的机器指令（不要替用户伪造该项结论）。
CANNOT = [
    {"mode": "todo", "task": "打开 Google Search Console（谷歌站长工具），看近 28 天真实用户打开网站时会不会慢、会不会抖、点了会不会卡",
     "loki": "7.3", "why": "检测工具没有 PageSpeed Insights / Lighthouse（谷歌的网页速度检测工具）的分数，不能替你填真实用户数据",
     "forbid": "不要编 PageSpeed Insights / Lighthouse 分数充当真实用户数据"},
    {"mode": "confirm", "task": "确认是 Manual Action（谷歌人工处罚）还是 Deindex（被谷歌从搜索结果中移除），并从 Google Search Console 导出处罚报告",
     "loki": "1.1", "why": "两种情况的修复方法完全不同，检测工具看不到处罚状态",
     "forbid": "不要替用户认定是 Manual Action 还是 Deindex"},
    {"mode": "confirm", "task": "确认品牌词的搜索量和外链（其他网站链接到你的网站）数量",
     "loki": "3.3", "why": "检测工具没有搜索量/外链数据库，不能编造数字",
     "forbid": "不要编品牌搜索量或外链数量数字"},
    {"mode": "todo", "task": "用 Ahrefs / SEMrush / Majestic（外链分析工具）查外链质量和 DR（Domain Rating，域名评分）",
     "loki": "3.1-3.2", "why": "检测工具没有外链数据库，不能编造 DR/质量数字",
     "forbid": "不要编外链质量/DR 数字"},
    {"mode": "confirm", "task": "确认作者履历真伪：检测工具只能看到首页有没有 LinkedIn 链接",
     "loki": "5.1", "why": "学历和工作经历只有 LinkedIn 能承载，需你点开核对",
     "forbid": "不要把「首页无 LinkedIn 链接」当成履历问题或替用户认定真伪"},
    {"mode": "todo", "task": "在搜索引擎搜索 site:域名 看哪些页面被收录了",
     "loki": "", "why": "自动检测做不了搜索，需你手动补这一步",
     "forbid": "不要凭 sitemap 推断收录结构，也不要把已收录总数当健康分"},
    {"mode": "todo", "task": "用 Screaming Frog（一款整站扫描工具）查全站：有没有「看起来是错误页、地址却返回正常」的假页面，以及必须开脚本才能看见的正文",
     "loki": "#116", "why": "整站规模检测工具抽样不到，Screaming Frog 更全面",
     "forbid": "不要凭单页抽样认定整站软 404/JS 渲染状况"},
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
    bundle["agent"] = build_agent(bundle)
    return bundle


# ===== AI 原生层：动作只算一遍，JSON.agent 为源，md/html 仅投影 =====
# 四个 kind：do / stop / collect / ask。verify.kind 三态是闭环的 moat：
#   probe   = 同一命令复跑，对 rule+status（软404/<main>/https/m站/display:none）
#   human   = 探针打不绿（About 定性、一页一词、成交页），AI 禁止为绿而改 sitemap 比例/堆标题
#   collect = GSC/Frog/site:，没文件就停，不准编
# 注意：agent 块允许保留 loki/#n（AI 闭环要的键）；md/html 投影时才去黑话。

def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "x"


def _stop_loki(where):
    return {"外链预算": "3.1", "AI 结果 / 清单": "2.1 2.3",
            "分数和处罚": "7.3 1.1"}.get(where, "")


def _accept_text(a):
    v = a.get("verify") or {}
    k = v.get("kind")
    if k == "probe":
        # 不嵌规则名：先做表常有六七个探针项，每行都挂一句 60 字长句会淹掉表格，
        # 而「改哪一页 + 改成什么」已经点明是哪一项。
        return "改完再跑一次这条命令，看这一行是否转为通过"
    if k == "human":
        return v.get("accept", "")
    if k == "none":
        return v.get("note", "")
    return ""


def _agent_do_sitemap(bundle):
    out = [
        {"id": "do-about", "kind": "do", "rule": "sitemap-mix", "loki": "7.4",
         "who": "内容", "where": "关于我们 + 首页",
         "change": "写清谁在做、实际交付什么、凭据；首页口号不能代替定位",
         "verify": {"kind": "human", "reprobe_can_pass": False,
                    "accept": "外人能否一句话说出你是什么机构"}},
        {"id": "do-convert-blog", "kind": "do", "rule": "sitemap-mix", "loki": "7.4",
         "who": "内容/运营", "where": "能产生订单/咨询的页面 vs 博客文章",
         "change": "博客多不等于该删博客；先标出哪几页真正能产生订单或咨询，再用同一个后台看是这些页在掉，还是博客在涨",
         "verify": {"kind": "human", "reprobe_can_pass": False,
                    "accept": "能成交的页面掉、博客涨，不代表网站变好了"}},
    ]
    if _looks_blog_only(bundle):
        out.append({"id": "do-money-page", "kind": "do", "rule": "sitemap-mix",
            "loki": "7.4", "who": "内容", "where": "能产生订单/咨询的页面",
            "change": "地图里几乎只有博客/新闻目录，看不到能产生订单/咨询的页面或产品目录。先确认有没有能成交的页；没有就先停铺博客。",
            "verify": {"kind": "human", "reprobe_can_pass": False,
                       "accept": "标出能产生订单/咨询的页面在哪几页"}})
    return out


def _agent_do(bundle):
    out = []
    for item in (bundle.get("diagnosis") or {}).get("priority") or []:
        rule = item.get("rule", "")
        if rule == "sitemap-mix":
            out += _agent_do_sitemap(bundle)
            continue
        f = _finding(bundle, rule)
        spec = ACTIONS.get(rule)
        if spec and f and f.get("status") in ("fail", "warn"):
            out.append({"id": f"do-{rule}", "kind": "do", "rule": rule,
                "loki": f.get("loki", ""), "who": spec[0], "where": spec[1],
                "change": spec[2],
                "verify": {"kind": "probe", "reprobe_can_pass": True,
                           "expect": {"rule": rule, "status": "pass"}}})
    out.append({"id": "do-onepage", "kind": "do", "rule": "title-h1", "loki": "6.3",
        "who": "内容", "where": "首页 + 抽样内页",
        "change": "每页只认一个要排的词；说不清就写「这页说不出自己排什么」，不要把公司内部的叫法当成外人会搜的词",
        "verify": {"kind": "human", "reprobe_can_pass": False,
                   "accept": "填下面的「每页要排哪个词」表，另标出能产生订单/咨询的页面在哪几页"}})
    if not any((x or {}).get("status") == "fail" for x in bundle.get("findings") or []):
        out.append({"id": "do-after-tech", "kind": "do", "rule": None, "loki": "7.4",
            "who": "内容", "where": "改完技术之后",
            "change": "技术检查过了，接下来看每一页写了什么，不要再往标题里堆词。一次改一处，用同一个后台再看一遍。",
            "verify": {"kind": "human", "reprobe_can_pass": False,
                       "accept": "不要一次改十处，回头却问是不是外链的问题"}})
    return out


def _agent_stop(bundle):
    out = [{"id": "stop-h1", "kind": "stop", "loki": "6.3", "who": "先别做",
            "where": "标题和主标题",
            "change": "不要为了塞搜索词去改主标题，也不要按关键词出现次数给页面打分",
            "verify": {"kind": "none", "note": "每页要排的词能说清即可"}}]
    for stop in ALWAYS_STOP:
        out.append({"id": f"stop-{_slug(stop[1])}", "kind": "stop",
            "loki": _stop_loki(stop[1]), "who": stop[0], "where": stop[1],
            "change": stop[2], "verify": {"kind": "none", "note": stop[3]}})
    ll = _finding(bundle, "llms.txt")
    if ll and ll.get("status") == "seen" and "HTTP 200" in (ll.get("evidence") or ""):
        out.append({"id": "stop-llms", "kind": "stop", "loki": "2.3", "who": "先别做",
            "where": "给 AI 看的说明文件",
            "change": "本站已经有这份文件。谷歌的 AI 搜索结果不一定会读。有文件不等于这件事做完了。",
            "verify": {"kind": "none", "note": "有了说明文件就够，不用额外去发帖、做问答、写公关稿那一套"}})
    return out


def _agent_collect(bundle):
    """collect 只来自 next_collect。site: 搜索是探针永久能力缺口，
    只走 cannot[] → 八节（8.1），不在这里重复 append，避免 JSON.agent 双写。"""
    out = []
    for item in bundle.get("next_collect") or []:
        out.append({"id": f"collect-{item.get('trigger','x')}", "kind": "collect",
            "loki": item.get("loki", ""), "where": "搜集",
            "need": item.get("need", ""), "read_as": item.get("read_as", ""),
            "verify": {"kind": "collect"}})
    return out


def _agent_ask():
    return [
        {"id": "ask-convert", "kind": "ask", "who": "你",
         "question": "成交发生在哪几页（检测看不到订单）"},
        {"id": "ask-query", "kind": "ask", "who": "你",
         "question": "每页要排的搜索词（检测不替你编关键词）"},
    ]


def _agent_actions(bundle):
    return (_agent_do(bundle) + _agent_stop(bundle)
            + _agent_collect(bundle) + _agent_ask())


def _conclude(bundle):
    """三态，禁止把 partial 和 inconclusive 收成同一个布尔。
    none=三核全没看到，不开方；tentative=看得见的部分可开方、整份暂定；
    full=核心都看到，正常开方。"""
    if bundle.get("inconclusive") or bundle.get("status") == "inconclusive":
        return "none"
    if bundle.get("partial") or bundle.get("status") == "partial":
        return "tentative"
    return "full"


def build_agent(bundle):
    origin = bundle.get("origin", "")
    host = urlparse(origin).netloc or origin
    disp = host[4:] if host.startswith("www.") else host
    mode = _conclude(bundle)
    acts = (_agent_collect(bundle) if mode == "none" else _agent_actions(bundle))
    cannot = [{"id": f"no-{i+1:02d}",
               "mode": (c.get("mode") if isinstance(c, dict) else "todo"),
               "task": _plain(c.get("task") if isinstance(c, dict) else c).replace("site:域名", "site:" + disp),
               "forbid": (c.get("forbid") if isinstance(c, dict) else _plain(c))}
              for i, c in enumerate(bundle.get("cannot") or [])]
    return {
        "schema": "loki-seo-agent/v1",
        "source_of_truth": "this_json",
        "human_projection": f"{disp}_audit_report.md",
        "conclude": mode,
        "may_conclude": mode == "full",
        "reprobe": {
            "cmd": ["python3", "scripts/audit_url.py", origin + "/"],
            "diff": ["findings.rule", "findings.status",
                     "sitemap.n", "sitemap.prefixes"],
        },
        "actions": acts,
        "cannot": cannot,
        "ask_human": [
            "成交发生在哪几页（检测看不到订单）",
            "每页要排的搜索词（检测不替你编关键词）",
        ],
    }


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


# ===== 人话报告渲染层（遵循 SKILL.md 输出合同「可读性」红线）=====
# 探针 run 完会自动生成 <域名>_audit_report.md / .html，不依赖 agent 手动翻译 JSON。

VERDICT_HUMAN = {
    "critical": "有必须修的硬伤，先处理下面标红的几条。",
    "at-risk": "有高风险项需要先处理，不解决会影响收录。",
    "needs-focus": "技术面没查到硬伤，但搜索引擎可能搞不清你是干嘛的——先把首页和「关于我们」写清楚，别急着发文章。",
    "insufficient": "这次查的不够全，下不了结论，先补数据（见「还需要补充的数据」）。",
    "inconclusive": "这次核心检测都没拿到数据，无法判断，只报没看到什么。",
    "healthy": "技术面没发现会挡收录的问题。",
}
# 三项枚举不要共用一张表：站点「查全了」≠ 单条「检测通过」≠ 网站地图「读到了」
RUN_HUMAN = {
    "ok": "核心页面都查到了",
    "partial": "只查到一部分（没查到的不等于没问题）",
    "inconclusive": "核心检测都没查到",
}
FOLLOW_HUMAN = {
    "ok": "已读到",
    "lost": "地图文件在，里面的清单没跟上",
    "absent": "这个站没有网站地图",
    "fail": "这次没读到网站地图",
}
STATUS_HUMAN = {
    "na": "这次没检测到（不等于没问题）",
    "seen": "看到了材料，要你判断",
    "pass": "这项没发现问题",
    "warn": "检出风险，需先处理",
    "fail": "检测到硬伤，必须修",
}
RULE_HUMAN = {
    "robots.txt": "搜索引擎抓取规则文件", "sitemap": "网站地图",
    "llms.txt": "给 AI 看的站点说明文件", "semantic main": "正文区标记",
    "h1": "页面主标题", "linkedin": "作者 LinkedIn 链接",
    "json-ld": "给搜索引擎看的结构化数据",
    "display:none": "藏起来的文字", "soft-404 probe": "假的「找不到」页面",
    "wayback": "历史存档记录", "m-subdomain": "手机站另开的 m. 地址",
    "sitemap-mix": "网站地图内的页面结构", "sampled-originality": "抽样页原创度",
    "jsonld-types": "结构化数据里标的类型", "title-h1": "页面标题与主标题",
    "robots-ua": "按搜索引擎分别设的屏蔽规则", "https": "加密地址（网址开头的 https）",
}
# 两张动作表的表头。先停表不复用先做的表头：那里既没有「谁改」也没有「改成什么」。
HDR_DO = ["#", "谁改", "改哪一页", "改成什么", "怎么验收"]
HDR_STOP = ["#", "别碰哪块", "别做什么", "边界在哪"]
# 渲染层翻译：已移至 build_agent / CANNOT / ALWAYS_STOP，数据模型本身即人话
# 探针 fail/warn 的动作。sitemap-mix 不走「把栏目比例做均衡」——那是通用体检。
# 只留 who / where / change 三元组。这里曾并存第四元素（验收文案，写了
# 「重跑探针看该项是否转 pass」）却从未被读取——验收那列实际由 _accept_text
# 统一生成，第四元素是死数据，删掉以免下一个人照着它改错地方。
ACTIONS = {
    "robots-ua": ("管网站的人", "/robots.txt 这份文件",
        "把这份文件从头读一遍，看有没有把重要目录误挡在搜索引擎外面"),
    "semantic main": ("做网站前端的人", "首页",
        "把正文放进页面主内容区标签，让搜索引擎认的是正文而不是侧栏页脚"),
    "display:none": ("做网站前端的人", "有隐藏文字的页面",
        "去掉用隐藏样式藏起来的正文（同一页只留一处正文）"),
    "m-subdomain": ("做网站前端的人", "手机端",
        "不要另做一套手机站页面；手机和电脑共用同一份网页"),
    "soft-404 probe": ("做网站后台的人", "「找不到」页面",
        "页面真的找不到时，就让它返回「找不到」这个状态，不要正常打开却显示找不到"),
    "https": ("管服务器的人", "全站", "启用 HTTPS，让 http 开头的网址自动跳到 https"),
    "sampled-originality": ("内容", "整段照搬或拼接出来的页面",
        "拿掉没有增量的转载和拼接，换成可核对的原创内容"),
}

# 测不到也要说的刹车。技术全 pass 时报告仍靠这几条，不许只剩「结构均衡」。
ALWAYS_STOP = (
    ("先别做", "买外链这件事",
     "不要把第三方网站打分（比如 DA/DR）当成排名原因去追，更不要花钱买外链",
     "外链数据你查不到就写无数据，不要编个数字凑上去"),
    ("先别做", "AI 搜索结果",
     "不要为了被 AI 提到，专门去做一套「给 AI 看的内容」（发帖、问答、公关稿、硬塞结构化数据）；本站已经有了说明文件，AI 也不一定读",
     "不用专门跑去小红书发帖求 AI 收录，把本站内容做好就行"),
    ("先别做", "分数和处罚",
     "不要用网页测速工具给的分数冒充真实用户体验；没有后台截图不要说被处罚",
     "真实体验看谷歌站长后台近 28 天的数据"),
)


# 各 rule 的人话事实文案（warn / na / pass）。seen 不在 facts 里，不列。
# 证据句不再重复规则名里的括号解释：facts 行的格式是「规则名：结论。证据」，
# 规则名已经解释过一次的术语（如「错误页却返回 200」），证据里就不许再解释一遍。
EVID = {
    "robots-ua": ("这份文件读到了，但里面针对某些搜索引擎单独写的那几段没读到全文，可能把重要目录误挡在了外面",
                  "这一项没抓到结果", "已读到全文，没有误挡"),
    "semantic main": ("首页缺了这个标记，或者放的位置不对，搜索引擎可能把侧栏或页脚当成正文", "这一项没抓到结果", "首页正文区标记正常"),
    "display:none": ("有些文字被样式藏了起来，人看不见、搜索引擎却读得到，可能被当成耍花样", "这一项没抓到结果", "没有发现藏起来的文字"),
    "soft-404 probe": ("页面上写着「找不到」，却告诉搜索引擎这页是正常的。搜索引擎会反复来抓这些其实不存在的页面，白占它花在你站上的时间", "这一项没抓到结果", "没有发现这类页面"),
    "m-subdomain": ("手机站另开了一个 m. 开头的地址，内容可能和电脑版是两回事，搜索引擎会当成两个站", "这一项没抓到结果", "没有发现手机电脑两套页面"),
    "https": ("网址开头没有统一用 https，访客和搜索引擎看到的可能不是同一个地址", "这一项没抓到结果", "网址已经统一用 https"),
    "sampled-originality": ("抽查到的页面里有整段照搬或改几个字的搬运内容", "没抽到内页，无法判断原创度", "抽查到的页面没发现搬运"),
    "sitemap": ("这份文件读到了，但里面的内容有问题", "这次没拿到网站地图（可能超时或被挡），说不清有没有", "网站地图正常"),
    "h1": ("一页只该有一个主标题，这个页面不是", "这一项没抓到结果", "主标题正常"),
    "title-h1": ("标题和主标题的写法有问题", "这一项没抓到结果", "标题和主标题正常"),
}


def _term(t):
    return {"posts": "博客文章", "news": "新闻", "about": "关于我们"}.get(t, t or "其他")


def _factual_evidence(f):
    rule, st = f["rule"], f["status"]
    if rule == "sitemap-mix":
        foc = f.get("focus") or {}
        n = foc.get("n") or 0
        if st == "na":
            return "没拿到网站地图的页面分布（可能超时或被挡），无法判断结构"
        if st == "warn" and n:
            return (f"约 {foc.get('share', 0):.0%} 的页面落在「{_term(foc.get('top'))}」目录"
                    f"（共 {n} 个页面，包含子目录的首页和列表页，不等于有 {n} 篇文章）。"
                    "搜索引擎可能因此把你的站当成「博客站」认识。")
        return "页面结构分布均衡，无明显单类独大"
    t = EVID.get(rule)
    if t:
        return {"warn": t[0], "fail": t[0], "na": t[1], "pass": t[2], "seen": t[2]}.get(
            st, _clean_evidence(f.get("evidence", "")))
    return _clean_evidence(f.get("evidence", ""))


def _report_meta(data):
    origin = data.get("origin", "")
    host = urlparse(origin).netloc or origin
    dx = data.get("diagnosis") or {}
    verdict = dx.get("verdict", "inconclusive")
    return (host, verdict, VERDICT_HUMAN.get(verdict, verdict),
            data.get("run_confidence"), data.get("sitemap_follow"),
            data.get("status", "inconclusive"))


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _clean_evidence(ev):
    ev = ev or ""
    for bad in ("loki", "G7", "口诀", "siteFocus", " #", "（#", "posts 站"):
        ev = ev.replace(bad, "")
    return ev.strip()


def _opening(data, host, vh):
    dx = data.get("diagnosis") or {}
    if dx.get("verdict") == "needs-focus":
        mix = next((f for f in data.get("findings", []) if f["rule"] == "sitemap-mix"), None)
        f = (mix or {}).get("focus") or {}
        n, share = f.get("n") or 0, f.get("share") or 0
        if n:
            return ("技术面没硬伤。搜索引擎可能把你的站当成「博客站」——"
                    f"网站共 {n} 个页面，其中约 {share:.0%} 是博客文章。"
                    "最该做的一件事：把「关于我们」和首页写清楚你是谁、做什么、凭什么。")
        return ("技术面没硬伤。最该做的一件事：把「关于我们」和首页写清楚你是谁、做什么、凭什么，"
                "每页只盯一个搜索词。")
    if dx.get("verdict") in ("at-risk", "critical"):
        return "有必须先处理的硬伤或高风险项。先看「先做 / 先停」表，不要同时改十处。"
    if dx.get("verdict") == "insufficient":
        return "这次查的不够全，下不了结论。先补「还需要补充的数据」，再判断。"
    return vh


def _finding(data, rule):
    return next((f for f in data.get("findings") or [] if f["rule"] == rule), None)


def _looks_blog_only(data):
    names = [str(p[0]).lower() for p in (data.get("sitemap") or {}).get("prefixes") or []]
    if not names:
        return False
    money = ("cases", "shop", "product", "service", "pricing", "store",
             "booking", "solutions", "offer", "course")
    return not any(any(k in n for k in money) for n in names)


def _do_rows(data, tech=None):
    """先做表数据源。tech=None 返回全部；True 只返回技术项（rule 在 ACTIONS 里，
    即交给前端的 main/隐藏文本、后台的 404、运维的 https 等），False 只返回业务/
    内容项。技术全 pass 时业务表先行、技术表不渲染，非技术读者不会被术语劝退。"""
    ag = (data.get("agent") or {}).get("actions") or []
    rows, seen = [], set()
    for a in ag:
        if a.get("kind") != "do":
            continue
        is_tech = a.get("rule") in ACTIONS
        if tech is not None and is_tech != tech:
            continue
        key = (a.get("where", ""), a.get("change", "")[:24])
        if key in seen or len(rows) >= 12:
            continue
        seen.add(key)
        rows.append([len(rows) + 1, a.get("who", "内容"),
                     a.get("where", ""), a.get("change", ""), _accept_text(a)])
    return rows


def _stop_rows(data):
    ag = (data.get("agent") or {}).get("actions") or []
    rows, seen = [], set()
    for a in ag:
        if a.get("kind") != "stop":
            continue
        note = (a.get("verify") or {}).get("note", "")
        key = (a.get("where", ""), a.get("change", "")[:24])
        if key in seen or len(rows) >= 12:
            continue
        seen.add(key)
        rows.append([len(rows) + 1, a.get("where", ""), a.get("change", ""), note])
    return rows


def _facts_rows(data):
    fs = data.get("findings", [])
    na_show = {"sitemap", "sampled-originality", "semantic main", "h1", "title-h1"}
    shown = [f for f in fs if f["status"] in ("fail", "warn")
             or (f["status"] == "na" and f["rule"] in na_show)]
    if not shown:
        return ["（没有检测到问题。不等于站没问题——见「先停」和「哪些数据可信」。）"]
    out = []
    for f in shown:
        rule = RULE_HUMAN.get(f["rule"], f["rule"])
        st = ("这是一个需要注意的情况，不是技术故障" if f["rule"] == "sitemap-mix" and f["status"] == "warn"
              else STATUS_HUMAN.get(f["status"], f["status"]))
        out.append(f"{rule}：{st}。{_factual_evidence(f)}")
    return out


def _home_th(data):
    title = (data.get("title_text") or "").strip()
    h1 = (data.get("h1_text") or "").strip()
    if title or h1:
        return title, h1
    th = next((f for f in data.get("findings") or [] if f["rule"] == "title-h1"), None)
    ev = (th or {}).get("evidence") or ""
    m, mh = re.search(r"title='([^']*)'", ev), re.search(r"h1='([^']*)'", ev)
    return (m.group(1) if m else ""), (mh.group(1) if mh else "").strip()


def _onepage_rows(data):
    unclear = "你来填：这页用什么词能找到你？"
    title, h1 = _home_th(data)
    rows = [["首页", unclear, f"标题：{title}；页面主标题（H1）：{h1}"]]
    live = 0
    for s in data.get("sniffs") or []:
        if s.get("status") != 200:
            continue
        live += 1
        raw = urlparse(s.get("url") or "").path or (s.get("url") or "")
        path = unquote(raw)[:50] + ("…" if len(unquote(raw)) > 50 else "")
        rows.append([path, unclear, f"标题：{(s.get('title') or '')[:80]}"])
    if not live:
        rows.append(["内页", "这次没抽到活样本", "全站一词表需效果报告或人工看"])
    rows.append(["能产生订单/咨询的页面", "（你填：这些页面在哪）", "检测工具看不到成交数据"])
    return rows


def _grade_lines(data):
    return [
        "下面的数字都是这次检测抓到的，不是猜的。",
        "能直接动手的：首页和「关于我们」写清楚你是谁；每页盯一个外人会搜的词；技术没问题后看每页内容，别堆标题。",
        "要打折扣的：DA / DR 这类第三方打的「网站权重分」是结果不是原因，不能拿来解释排名为什么掉。",
        "没有数据的：见「八、需要你手动处理」。没有你的后台导出就不写那些数字。",
        "还要你自己定的：能产生订单/咨询的页面在哪（你填）。搜索词列检测工具不替你编关键词。",
    ]


def _site_notes(data):
    if data.get("status") == "inconclusive":
        return ["这次核心检测都没拿到数据，不能下任何结论，包括「看起来还行」。"]
    out = []
    if data.get("partial") or (data.get("diagnosis") or {}).get("evidence_partial"):
        out.append("证据不全，下面是暂定结论，没查到的部分结论可能变。")
    pairs = (
        ("semantic main", "pass", "首页有主内容区标签 <main>（告诉搜索引擎哪块是正文）。只查了首页，整站要另查。"),
        ("soft-404 probe", "pass", "故意访问一个不存在的页面，返回了真正的 404 错误码（没有假装页面存在）。只测了一个地址，整站规模要靠工具。"),
        ("wayback", "pass", "Wayback Machine（互联网档案馆）的历史存档只看到最近几条记录，没有长期空白或异常。"),
        ("sampled-originality", "pass", "抽查了几页，没发现明显抄袭。抽查不等于全站原创。"),
        ("m-subdomain", "pass", "没有做独立移动站（m.xxx.com）两套页面，移动端和 PC 端是同一套。"),
        ("jsonld-types", "seen", "首页有结构化数据代码（JSON-LD 格式，帮搜索引擎理解页面内容），但有代码不等于能排上去。"),
        ("robots-ua", "pass", "robots 文件（告诉搜索引擎哪些页面能抓、哪些不能抓）对不同搜索引擎做了不同屏蔽，逐条读过没发现误挡。"),
    )
    for rule, want, msg in pairs:
        f = _finding(data, rule)
        if f and f.get("status") == want:
            out.append(msg)
    if (data.get("html") or {}).get("linkedin") == 0:
        out.append("首页没有 LinkedIn 作者链接。只有金融/医疗/法律类网站才需要作者专业背景（Google 对这类站的要求），教育交付站不必当缺陷。")
    return out or ["（没有额外需要说明的项）"]


def _plain(s):
    s = re.sub(r"（[^）]*）", " ", s or "")
    s = _clean_evidence(s)
    return re.sub(r"\s+", " ", s).strip()


def _cannot_items(data):
    out = []
    for c in (data.get("cannot") or []):
        if isinstance(c, dict):
            out.append(c)
        else:
            out.append({"mode": "todo", "task": _plain(c), "why": "", "loki": ""})
    return out


def _cannot_todo(data):
    host = urlparse(data.get("origin") or "").netloc or "该域名"
    if host.startswith("www."):
        host = host[4:]
    items = [c for c in _cannot_items(data) if c.get("mode") == "todo"]
    if not items:
        return []
    out = []
    for c in items:
        task = c.get("task", "").replace("site:域名", "site:" + host)
        line = task
        if c.get("why"):
            line += " —— " + c["why"]
        out.append(line)
    return out


def _cannot_confirm(data):
    items = [c for c in _cannot_items(data) if c.get("mode") == "confirm"]
    if not items:
        return []
    out = []
    for c in items:
        line = c.get("task", "")
        if c.get("why"):
            line += " —— " + c["why"]
        out.append(line)
    return out


def _cannot_lines(data):
    # 兼容旧调用：合并两类，保持返回列表
    return _cannot_todo(data) + _cannot_confirm(data)


def _next_rows(data):
    out = [_plain(item.get("need", "")) for item in data.get("next_collect") or []]
    return [x.replace("GSC 效果/覆盖基线",
                      "Google Search Console（谷歌站长工具）的效果数据和覆盖率基线数据")
            if "GSC" in x else x for x in out if x]


def _md_table(rows, headers):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out


def _html_table(rows, headers):
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _reading_line(data):
    """报告第一屏的读法提示。硬编码成「技术没硬伤」会在 critical 报告里自相矛盾。"""
    v = (data.get("diagnosis") or {}).get("verdict", "")
    if v in ("critical", "at-risk"):
        return "读法：没写出来的数字不是漏了，是没抓到就不编。有硬伤就先按「先做」修完，别的先放一放。"
    return "读法：没写出来的数字不是漏了，是没抓到就不编。技术没硬伤时，先看「先停」。"


def _do_section(data):
    """先做节：业务表（必出，非技术读者也能动手）+ 技术表（仅技术项有 fail/warn 时出现）。"""
    out = _md_table(_do_rows(data, tech=False), HDR_DO)
    tech_rows = _do_rows(data, tech=True)
    if tech_rows:
        out += ["", "### 技术项（交给技术团队，非技术读者可跳过）"] + _md_table(tech_rows, HDR_DO)
    return out


def render_markdown(data):
    host, verdict, vh, conf, follow, status = _report_meta(data)
    L = [f"# 站点诊断报告：{host}", "", _opening(data, host, vh), "",
         "## 一、现在的状态",
         f"- 这次查全了吗：**{RUN_HUMAN.get(status, status)}**",
         f"- 数据可信度：{conf}（1.0 = 该查的都查到了；越低只说明这次看到的越少，不是站越差）",
         f"- 网站地图：**{FOLLOW_HUMAN.get(follow, follow)}**",
         f"- 总体判断：**{vh}**",
         f"- {_reading_line(data)}",
         "", "## 二、先做（业务侧：你和内容团队能做）"]
    L.extend(_do_section(data))
    L += ["", "## 三、先停"]
    L.extend(_md_table(_stop_rows(data), HDR_STOP))
    L += ["", "## 四、检测发现的问题"]
    L += [f"- {r}" for r in _facts_rows(data)]
    L += ["", "## 五、每页要排哪个词",
          "每个页面只盯一个搜索词。下面是检测到的页面，「搜索词」列留给你填——检测工具不知道你的业务目标，不替你发明关键词。"]
    L.extend(_md_table(_onepage_rows(data), ["页面", "搜索词（你填）", "当前标题"]))
    L += ["", "## 六、哪些数据可信"]
    L += [f"- {r}" for r in _grade_lines(data)]
    L += ["", "## 七、逐项核查结果"]
    L += [f"- {r}" for r in _site_notes(data)]
    L += ["", "## 八、需要你手动处理",
          "以下几项检测工具查不了，需要你自己登录后台或用其他工具去查。没查之前不要猜结论。"]
    todo = _cannot_todo(data)
    conf = _cannot_confirm(data)
    if todo:
        L += ["", "### 8.1 待办任务（你去做）"]
        L += [f"- {r}" for r in todo]
    if conf:
        L += ["", "### 8.2 需你确认（检测工具看不到）"]
        L += [f"- {r}" for r in conf]
    if not todo and not conf:
        L += ["（本次没有额外待处理项）"]
    L += ["", "## 九、还需要补充的数据"]
    L += [f"- {r}" for r in _next_rows(data)]
    L += ["", "## 十、最终决定权在你",
          "> 做不做由你定。该做的写在「先做」，别碰的写在「先停」。没有后台数据的数字一律标无数据。"]
    return "\n".join(L)


def _ul(items):
    return "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in items) + "</ul>"


def render_html(data):
    host, verdict, vh, conf, follow, status = _report_meta(data)
    p = [f"<h1>站点诊断报告：{_esc(host)}</h1>",
         f"<p class='open'>{_esc(_opening(data, host, vh))}</p>",
         "<h2>一、现在的状态</h2><ul>",
         f"<li>这次查全了吗：<b>{_esc(RUN_HUMAN.get(status, status))}</b></li>",
         f"<li>数据可信度：{_esc(conf)}（1.0 = 该查的都查到了；越低只说明这次看到的越少，不是站越差）</li>",
         f"<li>网站地图：<b>{_esc(FOLLOW_HUMAN.get(follow, follow))}</b></li>",
         f"<li>总体判断：<b>{_esc(vh)}</b></li>",
         f"<li>{_esc(_reading_line(data))}</li></ul>",
         "<h2>二、先做（业务侧：你和内容团队能做）</h2>", _html_table(_do_rows(data, tech=False), HDR_DO),
         ("<h3>技术项（交给技术团队）</h3>" + _html_table(_do_rows(data, tech=True), HDR_DO)) if _do_rows(data, tech=True) else "",
         "<h2>三、先停</h2>", _html_table(_stop_rows(data), HDR_STOP),
         "<h2>四、检测发现的问题</h2>", _ul(_facts_rows(data)),
         "<h2>五、每页要排哪个词</h2>",
         "<p>每个页面只盯一个搜索词。下面是检测到的页面，「搜索词」列留给你填——检测工具不知道你的业务目标，不替你发明关键词。</p>",
         _html_table(_onepage_rows(data), ["页面", "搜索词（你填）", "当前标题"]),
         "<h2>六、哪些数据可信</h2>", _ul(_grade_lines(data)),
         "<h2>七、逐项核查结果</h2>", _ul(_site_notes(data)),
         "<h2>八、需要你手动处理</h2>",
         "<p>以下几项检测工具查不了，需要你自己登录后台或用其他工具去查。没查之前不要猜结论。</p>",
         ("<h3>8.1 待办任务（你去做）</h3>" + _ul(_cannot_todo(data))) if _cannot_todo(data) else "",
         ("<h3>8.2 需你确认（检测工具看不到）</h3>" + _ul(_cannot_confirm(data))) if _cannot_confirm(data) else "",
         "<h2>九、还需要补充的数据</h2>", _ul(_next_rows(data)),
         "<h2>十、最终决定权在你</h2>",
         "<p>做不做由你定。该做的写在「先做」，别碰的写在「先停」。没有后台数据的数字一律标无数据。</p>"]
    style = ("<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:820px;"
             "margin:2rem auto;padding:0 1rem;color:#1a1a1a;line-height:1.6}"
             "h1{color:#0a7d4f}h2{color:#0a7d4f;border-bottom:1px solid #ddd;padding-bottom:.3rem}"
             ".open{background:#f3f9f4;border-left:4px solid #0a7d4f;padding:1rem}"
             "table{border-collapse:collapse;width:100%;margin:.5rem 0}"
             "th,td{border:1px solid #ddd;padding:.5rem;text-align:left}th{background:#f3f9f4}"
             "ul{margin:.5rem 0}li{margin:.3rem 0}</style>")
    return (f"<!doctype html><html lang='zh'><head><meta charset='utf-8'>"
            f"<title>站点诊断：{_esc(host)}</title>{style}</head>"
            f"<body>{''.join(p)}</body></html>")


def diff_json(prev, now):
    out = []
    pf = {f["rule"]: f.get("status") for f in prev.get("findings", [])}
    nf = {f["rule"]: f.get("status") for f in now.get("findings", [])}
    for rule in sorted(set(pf) | set(nf)):
        ps, ns = pf.get(rule), nf.get(rule)
        if ps != ns:
            jitter = (ps, ns) in (("na", "pass"), ("pass", "na"))
            tag = " [可能是代理抖动,非真实修复]" if jitter else ""
            out.append(f"{rule}: {ps} -> {ns}{tag}")
    pn = (prev.get("sitemap") or {}).get("n")
    nn = (now.get("sitemap") or {}).get("n")
    if pn != nn:
        out.append(f"sitemap.n: {pn} -> {nn}")
    pp = (prev.get("sitemap") or {}).get("prefixes")
    np_ = (now.get("sitemap") or {}).get("prefixes")
    if pp != np_:
        out.append(f"sitemap.prefixes: {pp} -> {np_}")
    return out


def main():
    ap = argparse.ArgumentParser(description="未登录 SEO 探针：输出 JSON + 人话 md/html 报告")
    ap.add_argument("url")
    ap.add_argument("--diff", metavar="PREV_JSON",
                    help="对比上一次探针 JSON，只打印 findings/sitemap 的变化（复测对账）")
    args = ap.parse_args()
    data = audit(args.url.strip())
    if args.diff:
        prev = json.load(open(args.diff, encoding="utf-8"))
        for line in diff_json(prev, data):
            print(line)
        return 0
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()
    host = urlparse(data.get("origin", "")).netloc or "site"
    if host.startswith("www."):
        host = host[4:]
    json_path, md_path, html_path = (f"{host}_audit_report.json",
                                     f"{host}_audit_report.md",
                                     f"{host}_audit_report.html")
    try:
        Path(json_path).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        Path(md_path).write_text(render_markdown(data), encoding="utf-8")
        Path(html_path).write_text(render_html(data), encoding="utf-8")
        wrote = f"{json_path} / {md_path} / {html_path}"
    except Exception as e:
        wrote = f"（报告写入失败：{e}）"
    st = data.get("status") or "inconclusive"
    if st != "ok":
        print(f"[loki-seo] status={st} core_missing={data.get('core_missing')} "
              f"sitemap_follow={data.get('sitemap_follow')} "
              f"run_confidence={data.get('run_confidence')}：{NOTE[st]}",
              file=sys.stderr)
    print(f"[loki-seo] 报告已生成: {wrote}", file=sys.stderr)
    return EXIT.get(st, 1)


if __name__ == "__main__":
    sys.exit(main())

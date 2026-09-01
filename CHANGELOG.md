# Changelog

## 1.0.1 — 2026-09-01

发布前二轮实测（peercare.cn 真站复跑）抓出三项并修复，均为**门禁全绿时抓不到**的语义错。

- **Wayback `last200` 是假数据**：CDX 默认升序，`limit=3` 取到**最早** 3 条，字段名叫 `last200` 值却是第 3 早快照。peercare.cn 实测报 `20240528`，真实最新为 `20250323214856`，**差 10 个月**。改 `limit=-3` 取最新窗口；`statuscode` 取了要过滤，`-` 与非数字行不作候选（否则 `last200` 可能返回无状态码的时间戳）。
- **m-host 的 NXDOMAIN 判定改用真实 DNS**：原按 urllib 错误文本正则分流，而错误文本随代理/本地化变——peercare.cn 同一主机、同一站点事实（socket 直查 errno=8 确认无 m 站），一次报 `nodename`→pass 真阳性，一次因沙箱代理隧道报 `Tunnel connection failed: 502`→文本不匹配→误判 na。**同一个站两种结论**，是 P9「抖动不该翻结论」的翻版。新增 `host_resolves()` 走 `socket.getaddrinfo`（不受 HTTP 代理影响），`gaierror`=确认没有 m 站→pass，解析得到但连不上=na。200 仍 warn（两套 HTML 风险）；
  **5xx 改 na**（同 soft-404 通则：代理 502 与源站 502 在 HTTP 层无从区分，warn 会往 tier-1 塞假警报，
  na 会正确触发 NEED 的 Frog 搜集项）。
- **display:none 补门禁**（tier-1，此前是 17 条 rule 里唯一零覆盖）：warn/pass/na 三态 + at-risk 断言。
- **test_mhost 拆分**（if 6>5 形态超标）为 test_mhost / test_mhost_http；新测试注册进 main。
- **抽样分母只计活样本**：`sniffed=8` 里 502/超时的死样本没拿到正文，却计入原创度分母；8 个全 502 也报 pass（把代理噪声当站点事实）。改分母只算 `status==200`，全死→na，evidence 报 `live/dead` 分解让「看到几个」与「看到什么」分开读。peercare.cn 复跑实证 `sniffed=8 live=3 dead=5`——旧版会把 5 个死样本藏进分母。
- **门禁层补 P10**：`test_mhost` / `test_mhost_dns` / `test_wayback`（倒序+dated 过滤）/ `test_sampled_live`，共 16 组 46 个静态断言点。
- **门禁自身被实测纠了两次错**（都是「断言了不该断言的那一层」）：只查源码字符串的 `limit=-3` 断言会被**诱饵行**骗过（前置一行含 `limit=-3` 的赋值，真查询仍是 `limit=3`）→ 改为断言**实际发出的请求 URL**；只 patch **被测函数 `host_resolves` 自身**的断言让该函数一行都跑不到（`gaierror` 分支静默失效）→ 改为只 patch 下一层 `socket.getaddrinfo`。
- **形态门禁 shape_check 归零**：1.0.0 提交的 `interpret_focus` 44 行 > 40 上限（当时只跑了语义门禁，形态这条轴没跑）。抽出 `originality_finding()`，两条轴现均全绿。
- 文档：SKILL.md「探针 JSON 怎么读」补四条值级读法（`semantic main` 只看首页 / `soft-404` 的 na 语义 / `m-subdomain` 判据是 DNS 不是 error 文本、含 5xx=warn / `wayback` 是最新窗口不是完整历史），`sampled-originality` 补活样本口径；README 行数与验证声明改实数。

## 1.0.0 — 2026-09-01

首发。

- 口径层：SKILL.md（路由表 / 碰撞表 / 输出合同 / 风险信号 RF01–RF28 / 判定规则 1.x–7.x）+ expert_claims.md 134 条主张（窗口 2026-02-11 ~ 2026-08-29，dump 2025-07-11 起，门禁切片非全账号）。
- 探针层：audit_url.py——robots/sitemap（三路径变体）/软404/`<main>`/m 站/Wayback/抽样原创度；五值状态机 na/seen/pass/warn/fail；降级状态机 partial/inconclusive + run_confidence + core_missing。
- 门禁层：confidence_gate.py P0–P9（十组、32 个静态断言点）。P9 为本日补钉：探针网络失败(0/5xx)→na 不再抬 at-risk；partial 无 fail/warn → verdict=insufficient 不再字面 healthy。两项均经变异测试验证（回退必红、复原复绿）。
- 文档：expert_claims 语料边界声明、SKILL.md 发稿前自查（编造/进口/升格/传记/GEO 幻觉五查）、RF18 复核钉死（#125 在库、G7 判常识，不采用是审过非漏采）、附录B 风险信号清单自正文判定规则反推（不引外部来源）。
- 新增 corpus.json：134 条推文原文（#n 与索引表同序、full_text、日期、X 链接），回源核验不再依赖 X 平台可用性；README/SKILL.md/expert_claims.md 同步指向。

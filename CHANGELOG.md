# Changelog

## 1.0.6 — 2026-09-02（报告层按口径开方，不再做通用体检）

自动报告只把探针 `warn` 翻成「降低博客占比」时，跟通用 SEO 体检没有区别：先停、一页一词、证据等级、测不到也要说的刹车全部被裁掉。改渲染层，判定语义不动。

- 先做/先停封顶 7 条：栏目集中走「关于我们写清谁、做什么、凭据」+「先标转化页」，不再写「结构更均衡」。
- 技术全绿也输出刹车：别追外链、别上 AI 作业清单、别用实验室打分充体验、别把主标题改成密度榜。
- 一页一词写入首页 + 活样本；说不清就写「这页说不出自己排什么」。有抽样却写「探针未抽样」视为回归。
- 证据等级 + 测不到也要注意（整站爬、Field 体验、结构化数据≠能排、教育站不强制职业档案互链）。
- `report_gate` 把「通用体检腔调」和「缺先停」钉成失败。

## 1.0.5 — 2026-09-02（抓取 502/超时退避重试，无语义变更）

给 `fetch()` 加统一退避重试：502/503/504 与网络超时（URLError/TimeoutError/SSLError）自动重试，最多 3 次、间隔 1s→2s→4s。sitemap/robots/well-known 全链路受覆盖（它们都走 `fetch()`），单次代理/隧道抖动不再把结果打成 `na`。

- 站点**真**返回 502 时如实报 502（上游仍按「没看到」处理），不被重试掩盖成探测失败 0。
- 新增 `tests/fetch_retry_gate.py`：只 patch 下一层 `urllib.request.urlopen`，断言 `fetch` 真实重试行为（502/网络错重试到 200、穷尽后 URLError→status=0、真 502→502），不是只查源码字符串。
- 顺手删掉 1.0.4 遗留的重复死代码旧 `main()`（Python 只会用最后的 main，旧版只出 JSON 的 main 成了死代码）。
- 门禁全绿：confidence_gate 24 组 + report_gate + fetch_retry_gate + shape_check（4 个 .py 超标 0）。诊断语义未动。

## 1.0.4 — 2026-09-02（探针自动出人话报告 md/html，无语义变更）

让探针**自己**输出人话版报告，不再依赖 agent 手动翻译 JSON。代码与判定语义未动，门禁仍全绿（confidence_gate 24 组 + 新增 report_gate + shape_check 三个 .py 超标 0）。

- `scripts/audit_url.py` 新增渲染层（遵循「可读性」红线）：
  - 运行后默认生成 `<域名>_audit_report.md` 与 `<域名>_audit_report.html`，JSON 仍打 stdout（管道兼容）。
  - 自动去内部溯源（`loki`/`#n`/`口诀`/`G7`/`siteFocus` 不进报告）、`verdict` 四值翻人话、状态值翻译（`na`→探针没看到）、术语首翻（`posts`→博客文章）、四列动作表（谁改/改哪页/改成什么/怎么验收）。
  - 事实段证据经 `_factual_evidence` 人话化，不再原样抄机器串（`prefixes=[('posts',333)]` 之类）。
- 新增 `tests/report_gate.py`：用塞满黑话的合成 bundle 钉死渲染红线（去黑话 / verdict 人话 / na 翻译 / 术语首翻 / 四列表 / 开头大白话），回归即红。

## 1.0.3 — 2026-09-02（输出合同可读性，无语义变更）

让运行时报告对**不懂 SEO 的用户**也能读懂、且不会误读结论。**代码与判定语义未动，门禁仍 24 组全绿。**

- SKILL.md 输出合同新增「可读性（写给不懂 SEO 的人）」红线：
  - 报告第一句必须是一段大白话（≤120 字）：站现在什么状态 + 最该做的一件事。
  - `verdict` 四值翻成人话再写（`needs-focus` 不是「站有问题」，是「技术没硬伤、去写清站点定位」），不准直接贴英文。
  - 状态值翻译：`na`→探针没看到（≠没问题）；`seen`→看到了材料待判断；`pass`/`warn`/`fail`→按规则判过。
  - **去内部溯源**：JSON 里的 `loki` / `#n` / `口诀` / `G7` / `siteFocus` 一律不进报告正文，只留落地动作与证据数字。
  - 术语首次出现翻成人话（sitemap / soft-404 / EEAT / `<main>` / focus_reading）。
- 发稿前自查加「黑话」闸门：内部溯源或术语未翻译、verdict 没翻人话、开头没大白话总结，命中即改。

## 1.0.2 — 2026-09-02（发布打磨，无语义变更）

公开发布前的文案与呈现收口。**代码与判定语义未动，门禁仍 24 组全绿。**

- 新增 `NOTICE.md`：语料版权归属、非官方 / 无授权 / 无背书声明、收录边界、下架方式。
- README：
  - 安装路径不再绑定单一宿主（原示例只写 `.grok/skills/`），改通用写法并说明目录名要对齐 frontmatter 的 `name`。
  - 补版本行与「语料与版权」小节；修掉 git clone 的占位符。
  - 改写「形态门禁由作者仓库 `shape_check.py` 管 —— 它是本仓库的写作纪律」这句自相矛盾的表述。
  - 断言点口径写实：改为「73 处断言点」，并注明其中 7 处在表驱动循环内、运行时展开为更多独立失败信号。旧写法「73 个静态断言点」把代码处数与运行时信号数混为一谈。
- SKILL.md：
  - 补非官方声明——skill 被单独安装后，使用者只看得到这一个文件。
  - 探针命令块补 `bash` 标注（此前是全仓库唯一没有语言标注的代码块）。
  - 风险信号表补 RF18 / RF20 编号缺口说明：这两条整条不采用，编号保留不回收。
  - 去掉「2026-09-01 拍板 / 复核钉死」这类自我决策日志腔，保留其约束本身（约束不依赖日期成立）。
- 去内部语境（外部读者复现不了或与本包无关）：
  - SKILL.md 去掉自有实测站域名与「沙箱代理」环境名（给 agent 读的运行时指令里，站点名零信息量）、本地 labels 库引用。
  - `expert_claims.md` 索引节删掉依赖本地库的生成命令，改为指向 `corpus.json` 快照。
  - `corpus.json` 的 `meta.note` 同步，不再提「同 SQL 生成 / 依赖作者本地库」。
- 1.0.1 的勘误真名**保留在 CHANGELOG**（给人读的证据链），只从 SKILL.md 移除——两者不是同一层：
  运行时指令不需要站点名，勘误史需要。1.0.1 顶部新增「关于真名」说明，并给第 1 条补了可直接跑的
  CDX 复算命令。

## 1.0.1 — 2026-09-01

发布前二、三轮实测（peercare.cn 真站复跑）共抓出七项并修复，均为**门禁全绿时抓不到**的语义错。

> **关于真名**：下文点名 peercare.cn，只为让第 1 条的数字可被独立复算——它是本节唯一一条
> **站点相关且公开可查**的证据（`limit=3` 应得 `20240528`、`limit=-3` 应得 `20250323214856`，
> 下面给了可直接跑的命令）。第 2、3 条依赖的是当时的代理链路状态，**给真名也复现不了**，
> 只能当历史记录读。它是维护者的自有站点，不是示例站，也不代表一般站点。

1. **Wayback `last200` 是假数据**：CDX 默认升序，`limit=3` 取到**最早** 3 条，字段名叫 `last200` 值却是第 3 早快照。peercare.cn 实测报 `20240528`，真实最新为 `20250323214856`，**差 10 个月**。改 `limit=-3` 取最新窗口；`statuscode` 取了要过滤，`-` 与非数字行不作候选（否则 `last200` 可能返回无状态码的时间戳）。

   复算（2026-09-02 重跑仍逐字吻合）：

   ```bash
   U='http://web.archive.org/cdx/search/cdx?url=peercare.cn&fl=timestamp,statuscode&collapse=timestamp:8'
   curl -s "$U&limit=3"    # 旧 bug：20230905081924 / 20240528072220 / 20240827015106
   curl -s "$U&limit=-3"   # 修后：  20240827015108 / 20250311003153 / 20250323214856
   ```

2. **m-host 的 NXDOMAIN 判定改用真实 DNS**：原按 urllib 错误文本正则分流，而错误文本随代理 / 本地化变——peercare.cn 同一主机、同一站点事实（socket 直查 errno=8 确认无 m 站），一次报 `nodename`→pass 真阳性，一次因本地代理隧道报 `Tunnel connection failed: 502`→文本不匹配→误判 na。**同一个站两种结论**，是 P9「抖动不该翻结论」的翻版。
   - 新增走 `socket.getaddrinfo` 的判定（不受 HTTP 代理影响）：`gaierror` = 确认没有 m 站→pass，解析得到但连不上 = na。
   - 200 仍 warn（两套 HTML 风险）；**5xx 改 na**（同 soft-404 通则：代理 502 与源站 502 在 HTTP 层无从区分，warn 会往 tier-1 塞假警报，na 会正确触发 NEED 的 Frog 搜集项）。

3. **抽样分母只计活样本**：`sniffed=8` 里 502 / 超时的死样本没拿到正文，却计入原创度分母；8 个全 502 也报 pass（把代理噪声当站点事实）。改分母只算 `status==200`，全死→na，evidence 报 `live/dead` 分解让「看到几个」与「看到什么」分开读。peercare.cn 复跑实证 `sniffed=8 live=3 dead=5`——旧版会把 5 个死样本藏进分母。

4. **display:none 补门禁**（tier-1，此前是 17 条 rule 里唯一零覆盖）：warn / pass / na 三态 + at-risk 断言。

5. **robots.txt / robots-ua 补门禁**（均为 tier-1、零覆盖；robots 是下跌场景第一探针）：200 / 非 200、解析不出 UA 块回退全 CAUGHT。

6. **重构与形态**：`host_resolves` 三态收敛为 `is_nxdomain` 双态（单消费者不留等价分支）；`full_bundle` 工厂默认消毒（robots 非空 + 前缀均衡），删 4 处测试内重复消毒；`test_mhost` 拆分（if 6>5 形态超标），新测试注册进 main。

7. **门禁层补 P10**：`test_mhost` / `test_mhost_dns` / `test_wayback`（倒序 + dated 过滤）/ `test_sampled_live`。

### 三轮重测又抓出四项（同样全是门禁全绿时抓不到）

1. `parse_robots` 首个 User-agent 行 flush 出空 `*` 幽灵块（peercare.cn 实测 evidence 头部撒谎）；空 / 纯注释文件改返回 0 块，「解析不出 UA 块→warn」对真实解析器不再死断言。
2. `probe_well_known` 丢掉 200 sitemap 的 body，`sitemap_mix` 二抓同一 URL——实测 well_known 已 200(186B) 而二抓超时，险些把结论翻成 lost。改返回 `(well_known, sm_bodies)` 供复用，JSON 侧不变。
3. NXDOMAIN（DNS 确认没有 m 站）判定层落 pass、置信层却记「没看到」。`compute_confidence` 改计入拿到了数据。
4. sitemap 探针 0 / 5xx 落 warn、mix 假 pass，与 P9「0=na」对打。新增 `sitemap_presence`：混有 0 / 5xx = na，全 4xx = 站点事实仍 warn；`sitemap-mix` 在 lost / fail 且 n=0 时走 na。

### 门禁补钉与自纠

- **补 P11**：`test_parse_robots` / `test_sm_reuse` / `test_wk_bodies` / `test_sm_timeout_na` / `test_mhost_conf`，最终 24 组、73 个断言点；5 变异（幽灵块 / body 二抓 / nx_seen / 超时 warn / mix 只认 lost）逐个回退全 CAUGHT，复原 byte-identical 复绿。
- **门禁自身被实测纠了两次错**（都是「断言了不该断言的那一层」）：
  - 只查源码字符串的 `limit=-3` 断言会被**诱饵行**骗过（前置一行含 `limit=-3` 的赋值，真查询仍是 `limit=3`）→ 改为断言**实际发出的请求 URL**。
  - 只 patch **被测函数 `host_resolves` 自身**的断言让该函数一行都跑不到（`gaierror` 分支静默失效）→ 改为只 patch 下一层 `socket.getaddrinfo`。
- **形态门禁 shape_check 归零**：1.0.0 提交的 `interpret_focus` 44 行 > 40 上限（当时只跑了语义门禁，形态这条轴没跑）。抽出 `originality_finding()`，两条轴现均全绿。

### 文档

- SKILL.md「探针 JSON 怎么读」补四条值级读法（`semantic main` 只看首页 / `soft-404` 的 na 语义 / `m-subdomain` 判据是 DNS 不是 error 文本、含 5xx=na / `wayback` 是最新窗口不是完整历史），`sampled-originality` 补活样本口径。
- 收尾：SKILL frontmatter 版本升 1.0.1、description 改中文；README 门禁组数 / 断言点 / 行数全部改实测（24 组 73 点、700 / 692 行），`shape_check.py` 明确为写作纪律、不随包发布；删「超时一律 na」的绝对化表述（robots 非 200=warn 是门禁刻意例外）。

## 1.0.0 — 2026-09-01

首发。

- 口径层：SKILL.md（路由表 / 碰撞表 / 输出合同 / 风险信号 RF01–RF28 / 判定规则 1.x–7.x）+ expert_claims.md 134 条主张（窗口 2026-02-11 ~ 2026-08-29，门禁切片非全账号）。
- 探针层：audit_url.py——robots / sitemap（三路径变体）/ 软 404 / `<main>` / m 站 / Wayback / 抽样原创度；五值状态机 na / seen / pass / warn / fail；降级状态机 partial / inconclusive + `run_confidence` + `core_missing`。
- 门禁层：confidence_gate.py P0–P9（十组）。P9 为当日补钉：探针网络失败 (0 / 5xx)→na 不再抬 at-risk；partial 无 fail / warn → verdict=insufficient 不再字面 healthy。两项均经变异测试验证（回退必红、复原复绿）。
- 文档：expert_claims 语料边界声明、SKILL.md 发稿前自查（编造 / 进口 / 升格 / 传记 / GEO 幻觉五查）、RF18 复核钉死（#125 在库、G7 判常识，不采用是审过非漏采）、附录B 风险信号清单自正文判定规则反推（不引外部来源）。
- 新增 corpus.json：134 条推文原文（#n 与索引表同序、full_text、日期、X 链接），回源核验不再依赖 X 平台可用性；README / SKILL.md / expert_claims.md 同步指向。

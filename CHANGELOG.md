# Changelog

## 未发布（报告人话：以渲出来的报告为准）

上一轮改完门禁全绿，但样例按新文案重渲后通读仍撞到四处。这一轮全部以**渲染结果**为准，
不再以改动清单为准：

- 第一节「读法」句曾硬编码「技术没硬伤时，先看先停」——`critical` 报告里这句话和同一屏的
  「有必须修的硬伤」自相矛盾。改为按 `verdict` 分流，有硬伤时指向「先做」。
- 「先停」表沿用「先做」的四列（谁改 / 改哪一页 / 改成什么 / 怎么验收），格子里却填
  「先别做 / 买外链这件事 / 不要把… / 没有工具就写无数据」，四列没有一列对得上。
  改为独立表头 # / 别碰哪块 / 别做什么 / 边界在哪，并同步 SKILL.md 输出合同。
- 第四节证据句重复规则名里的括号解释（「软 404（错误页却返回 200）：…存在软 404（错误页却
  返回 200）」）。整块重写 `EVID`，并译掉「抓取预算」「重复内容风险」「User-agent」等黑话。
- 「先做」表验收列九行里六行是同一句 60 字长句、末尾还挂 `<main>` / `display:none`。
  收短为「改完再跑一次这条命令，看这一行是否转为通过」。

顺带清掉与新增断言：

- `ACTIONS` 第四个元组元素（验收文案，写着「重跑探针看该项是否转 pass」）从未被读取，
  验收那列实际由 `_accept_text` 生成。这是死数据，删掉，并注明以免后人照它改错地方。
- `tests/report_gate.py` 的 `_table_rows` 原靠 `"谁改" in ln` 跳表头——先停表一换列名就会
  把表头算成数据行。改为按结构跳（每节第一行非空表格行即表头）。
- 新增 `check_reading`：断言 `critical` 报告里不得出现「技术没硬伤」。
- 新增 `check_facts_dup`：按结构查 facts 行里重复出现的括号解释（不按固定字符串查）。

四条变异均已实测：读法句分支失效（诱饵行）/ 先停表复用先做表头 / 证据句重复括号，三个都被抓到；
「证据句改回『站点未全站启用 HTTPS』」未被抓到——该句既不漏内部词、也不重复括号解释，
对门禁合同而言是**等价变异**，不是漏网。

## 未发布（先做拆表 + 先停口语化；根因：测试污染非渲染写反）

用户复核指出两点：① json 说没事、md 说有硬伤；② 先做 9 条里 6 条技术把人劝退、先停边界列变回长句。

**① 是假阳性，已闭环**：那 4 条「硬伤」来自我做硬伤场景变异测试时把假数据渲进了工作区样例
（peercare md/html 时间戳 19:18，晚于提交 19:06）。用未修改的真 json 重渲，报告只有 1 条
博客站定性 warn、0 硬伤。`check_status_wording` 门禁也证明翻译层没有把 `true` 翻成「需处理」。
已用真 json 重渲样例，并加 `check_sample_consistency` 门禁（盘上 md/html 必须与真 json 重渲一致，
样例缺失则跳过）防再犯。

**② 是真实结构问题，本轮修：**
- 「先做」表拆成两张：业务侧（你/内容团队能做，必出）+ 技术侧（交给技术团队，仅技术项有
  fail/warn 时出现，非技术读者可跳过）。分类用 `a.get("rule") in ACTIONS`（`ACTIONS` 里的项即技术项）。
  peercare 真样例技术全 pass，所以只出业务表（4 行）；硬伤场景才出现技术表（如 https/404/main/robots）。
- 先停「边界在哪」列改口语：买外链→「外链数据你查不到就写无数据，不要编个数字凑上去」；
  AI→「不用专门跑去小红书发帖求 AI 收录，把本站内容做好就行」（用户原话）；
  分数→「真实体验看谷歌站长后台近 28 天的数据」；llms→「有了说明文件就够，不用额外去发帖、做问答、写公关稿那一套」。
- `ALWAYS_STOP` 的「分数冒充」措辞由「PageSpeed Insights 这类工具」泛化为「网页测速工具」，门禁
  `NEED` 断言同步改查「分数冒充真实用户体验」。

门禁自身修两处洞（均诱导性变异实测承重）：
- `render_markdown` 因拆表增到 44 行（超 40）→ 抽出 `_do_section` 助手压回。
- `_table_rows` 的结构跳表头只认每节第一个表头；加第二张技术表后，技术表头被误算成数据行
  （行数 7≠6）。改为遇 `### ` 子标题重置表头标记。变异删该重置块 → 行数比对重新 FAIL，证明承重。

四道门禁 + 形态（超标 0）+ 软链一致性 + 两个新变异（删分数冒充断言 / 删 ### 重置）全绿。

## 未发布（报告人话：查全了 ≠ 站没问题）

- 渲染层把「检测跑完」和「单条检测通过」拆开：站点状态不再写成「通过，没问题」。
- 「先停」表执行人改为「先别做」；验收栏去掉「转 pass」；`cannot` 不再把「域名评分」误替换成站点名。
- 重渲 peercare 样例；README 补「和常见检测工具不一样」。四道门禁全绿。

## 未发布（仓库清理，无语义变更）

- 删除 `scripts/publish.sh`：origin 早已配好、日常手动 `git push` 即可，脚本只是 `git push`
  的薄壳，且其注释「仓库默认无 remote / 本机无认证 gh」已失实。同步移除 README「发布」小节里
  对它的注释引用。
- README「发布」小节纠偏：origin 实为 **HTTPS**（`https://github.com/tong20242100/loki-seo-probe.git`），
  此前误写成 SSH；「推送走 SSH」改为「推送走 HTTPS」。
- **README 改为读者视角**：删除整段「发布（推到 GitHub 触发 CI）」（纯维护过程，读者既不 push 本库也不 care 提交状态）；
  删「使用」里「本地改完先跑三条再提」的贡献流程、仓库结构里「692 行/绕过 pyc 缓存」等实现注、
  「验证」里「历次抓虫记录」过程腔；「验证」改名「正确性保证」并只留对读者有用的信任信号。
  文档定位：README = 读者文档（这是什么/凭什么信/怎么装/怎么跑/版权），过程史归 CHANGELOG。
- README 视觉重写：**去掉 intro 里的写死版本号**（避免每次发版手动改），改用 shields.io 静态 badge 墙（license/python/AI-native/corpus 134/non-official/zero-deps，均不含版本，免维护）；
  标题与「三层结构」改用 🔬🧭🚧 emoji 图标体系、`<h1>/<p align="center">` 居中 hero、`<hr>` 分隔；
  「为什么不是又一份 prompt 合集」对标腔标题改为「三层结构」，直述做了什么、不再找对标。

## 1.0.13 — 2026-09-02（fetch 隐身后端 + 文档修正 + 形态门禁全绿）

### 抓取后端：裸 urllib → 可选 curl_cffi 隐身
裸 `urllib` + 单一写死 UA 的 TLS/JA3 指纹易被 WAF/Cloudflare 识破，把被拦的请求误判成
`na` / 站差——直接污染探针最核心的「客观 HTTP 事实」。

- `fetch()` 拆成「后端无关的重试循环 + `_fetch_urllib`（回退）+ `_fetch_stealth`（curl_cffi
  `impersonate="chrome"`）」。装了 `curl_cffi` 自动改用浏览器指纹抓取，缺省回退 urllib。
- 返回形状（url/status/ctype/body/error）不变，三道门禁的输入契约不动。
- `scrapling-stealth` 经实测：import 即要求 `playwright`（浏览器二进制），对只查
  状态码/robots/sitemap 的探针是过度依赖，故选其底层引擎 `curl_cffi` 而非整包。

### 门禁
- `fetch_retry_gate`：强制 `au._HAVE_STEALTH = False` 再 patch `urlopen`——装了 curl_cffi
  的本地跑门禁也不会因 urlopen 不被调用而失效，与 CI（无 curl_cffi）语义一致。
- `report_gate.sample` 41>40 → 合并两行字典回到 ≤40，形态门禁全仓 0 超标（此前一直红着）。

### 文档修正（README）
- 「发布」小节：原写「仓库默认无 remote、本机无认证 gh」已过时——origin 早已配置且已 push；
  改为如实描述（已配 origin，直接 `git push` 即触发 CI，推送走 SSH）。
- 「语料与版权」+ 顶部 intro：澄清「134 条是切片（非全账号），这 134 条的完整原文收录在
  corpus.json」的措辞矛盾；显式点名版权归 **@loki_yan_seo**。
- 依赖说明：补「可选 curl_cffi 作为抓取后端，缺失自动回退标准库」。

## 1.0.12 — 2026-09-02（机器层 site: 单源收口）

1.0.11 只在人话层（md 八/九节）消重。机器层有两处问题，缺一不可：
(a) `JSON.agent.actions` 里 `_agent_collect()` 仍无条件 append `collect-site`，AI 读 agent 时 site: 在 `cannot[]` 与 `actions[]` 各出现一次（双写）；
(b) `build_agent` 序列化 `cannot[]` 时只取 `forbid`、丢掉 `task`——而 site: 指令写在 task 上，导致即使只删 (a)，site: 也会从 JSON 整条消失（md 有、机器无源）。

修复：
- `_agent_collect()` 删除无条件 append 的 `collect-site`。
- `build_agent` 的 `cannot[]` 改为逐条带 `task`/`mode`/`forbid`（task 做 host 替换），site: 指令现在以单源存在于 `agent.cannot[].task`，人话与机器读到的同一句。
- `tests/report_gate.py` 的 `check_agent` 加机器层断言：agent.actions 不得含 `collect-site`、且 `cannot[]` 必须仍存在 site: 项（查 task 字段，不再误查 forbid）。
- SKILL.md AI 闭环小节补一句：site: 只在 `cannot[]`，actions 不得重复。

## 1.0.11 — 2026-09-02（消重 site: 提醒：只在八节常驻缺口，九节不再重复）

八节「待你处理」与九节「下一步搜集」都无条件带了 site: 收录搜索提醒，两处重复。
site: 搜索是探针永久能力缺口（探针永远不能搜索），属常驻缺口，应只在八节 8.1 出现。
九节只承载 per-run 动态搜集项（GSC 基线等）。

- `_next_rows()` 删除无条件 append 的 site: 行。
- `_cannot_todo()` 渲染时把占位「域名」替换为真实 host，八节 site 项现在写成 `site:peercare.cn` 这类针对本站的明确指令。
- 门禁 NEED 令牌 `site:` 仍在八节保留，report_gate 不受影响。
- 仓库工具：新增 `scripts/publish.sh`（幂等补 remote + push）与 README「发布」小节。本机无认证 `gh`、仓库默认无 remote，push 归用户执行；push 后 `.github/workflows/gate.yml` 才真跑三道门禁。不改探针语义。

## 1.0.10 — 2026-09-02（conclude 三态：partial ≠ inconclusive）

`may_conclude` 布尔把两种完全不同的降级收成一件事。SKILL 对 partial 的合同是「只对看得见的部分开方、整份暂定」，对 inconclusive 才是「不开方」。把 partial 也打成 false 会丢掉降级诊断（与旧「home 非 200 就 exit 1」同型）。

- 新增 `_conclude()`：`full`（ok）/ `tentative`（partial）/ `none`（inconclusive）。
- `agent.conclude` 为三态；`may_conclude` 仅 `full` 为 true（布尔兼容）。
- `none` 时 `actions` 只留 collect，不产出 do。
- `tentative` 仍产出 do/stop，但 `may_conclude=false`，禁止当终局。
- report_gate 钉死三态，并显式禁止「partial 拆掉 do」。

## 1.0.9+1 — 2026-09-02（CI 补齐 report_gate / fetch_retry_gate）

`.github/workflows/gate.yml` 原先只跑 `confidence_gate`。补齐用户早先要求的「把 report_gate 并进 CI」：

- 新增 `report-gate` job：跑 `tests/report_gate.py`（可读性 + JSON.agent↔md 投影一致性）。
- 新增 `fetch-retry-gate` job：跑 `tests/fetch_retry_gate.py`（502/超时退避重试、站点真 502 如实报 502）。
- 三个 job 并行，任一红即阻断合并；README badge 文案「语义门禁」→「探针门禁」，并补一句 CI 覆盖范围说明。
- 版本号不变（仅 CI/文档，不改探针语义或输出合同）。

## 1.0.9 — 2026-09-02（「待你处理」改写：能力缺口不再写成防御腔）

`cannot[]` 的报告呈现从「本次拒绝伪造」式免责声明改写为「待你处理」：拆成**待办任务**（用户去拉/查 GSC、Ahrefs、Screaming Frog、site: 搜索）与**需你确认**（探针看不到的状态，如 Manual Action vs Deindex、品牌搜索量 vs 外链、作者履历真伪）。`CANNOT` 由纯字符串升级为结构化 `{mode, task, loki, why, forbid}`，渲染层据此分两组投影，agent 块 `cannot.forbid` 仍是机器 moat（AI 不得伪造该项）。report_gate 断言同步改为校验「待你处理」进场。

- `CANNOT` 结构化：`mode∈{todo,confirm}`、`task`（用户动作）、`why`（为何探针不能代做，不再写「禁止编」）、`forbid`（AI 闭环指令）。
- md 八、html 八拆为 `8.1 待办任务` / `8.2 需你确认` 两个子节；`_grade_lines` 引用同步。
- 判定层与门禁未动；report_gate 全绿、shape_check（audit_url.py 超标 0）。

## 1.0.8 — 2026-09-02（AI 原生：JSON.agent 机器合同 + --diff 复测）

报告只给人看、AI 若读 md 就丢掉闭环键（loki/#n/cannot）。本版把动作算一遍进 `JSON.agent`，md/html 仅投影，判定语义不动。

- 新增 `build_agent()`：在 `attach_report` 里产出 `agent` 块（`schema: loki-seo-agent/v1`），含 `actions`（do/stop/collect/ask 四态）、`cannot`（`{id,forbid}`）、`ask_human`、`reprobe.cmd`+`reprobe.diff`、`may_conclude`。
- `verify.kind` 三态是闭环 moat：`probe`=同命令复跑对 rule+status（软404/`<main>`/https/m站/display:none）；`human`=探针打不绿（About 定性、一页一词、成交页），AI 禁止为绿而改 sitemap 比例或堆标题；`collect`=GSC/Frog/site:，没文件就停不准编。
- `_do_rows`/`_stop_rows` 改为从 `agent.actions` 投影（动作只算一遍），md 与机器合同逐条一致，分叉即红（report_gate 新增一致性断言）。
- `--diff prev.json`：只打印 findings rule/status + sitemap.n/prefixes 的变化，na↔pass 抖动标「可能是代理抖动，非真实修复」，不当成修复成功。
- 判定层未动；门禁全绿：confidence 24 组 + report_gate（含 agent 一致性）+ fetch_retry_gate + shape_check（4 py 超标 0）。

## 1.0.7 — 2026-09-02（报告写入 per-run 禁区、site: 提醒、按数据触发先停）

上一版报告「长得像口径、深度停在探针天花板」。本版把已经在 JSON 里的东西写进给人看的报告，判定语义不动。

- 真实 `cannot[]` 去黑话后写入「本次拒绝伪造」，不再用硬编码四句代替本次禁区。
- 下一步固定补 `site:域名`：自动报告做不了搜索，必须写明这一步要人做。
- 先停按数据：地图几乎只有博客/新闻且无成交/产品目录才点亮「缺成交页」；有 cases 等目录不误报纯博客。已有 AI 说明文件（HTTP 200）才追加「有文件 ≠ 做完」。
- 新增「本站对照」：pass 项的口径边界（只查首页、只打一个假 404、存档是窗口不是全史、抽样不是全站、分 UA ≠ 全站隔离、结构化数据 ≠ 能排）。
- 一页一词表前明示：query 列需你按业务填，探针不发明关键词。
- 先做/先停拆成两表，条数上限从 7 放到 12。有成交目录时禁止点亮纯博客缺成交页（门禁钉死）。

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

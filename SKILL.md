---
name: loki-seo
version: 1.0.14
description: >
  用 Loki Yan (@loki_yan_seo) 的口径诊断一个线上网址：先跑 audit_url.py 探针，
  再给 3–7 条贴合该站的可落地动作，并列出要从 GSC / Frog 导出的数据。
  当用户粘贴 URL、问 检查网站 / 审计 / 流量下跌 / 软404 /
  GEO / AIO / YMYL / EEAT / 外链，或说 /loki-seo / 按 Loki 的口径 时使用。
  不是通用 SEO 百科全书。
---

# Loki SEO（专家口径，不是通用手册）

> **非官方实现**：口径从 @loki_yan_seo 的公开推文提炼，无授权、无关联、无背书。
> 误读由本文件负责，不由原作者负责。语料版权与下架方式见 `NOTICE.md`。

主张全文 `expert_claims.md`（本包同目录，`#n` → 文末 tweet_id）。本文件是**调用规程**：探针 → 选判定规则 → 落地动作。禁止把下面判定规则全倒进回复。

## 最小输入

- **有 URL：** 立刻跑探针，再开口。
- **URL + 在问什么**（下跌 / 新站 / 增长 / 守山 / GEO / YMYL / 买域名）：路由更准。
- **没 URL：** 只讲口径，或问 URL。不许假装已经看过这个站。
- 用户丢来 GSC CSV / Frog 导出 / 手动操作截图：当证据用，仍不编缺的数字。

探针（路径相对本 skill 目录；装到别处就用绝对路径）：

```bash
python3 scripts/audit_url.py https://example.com
```

退出码：`0` = `ok` / `partial`（有可研判的输出，`partial` 时 stderr 另打一行提示），
`1` = `inconclusive`（三核全没拿到，别硬答），`2` = 用法错误。
**退出码只表示「有没有可研判的输出」，不再表示首页是不是 200**——首页 502 而 robots/sitemap 能读时
是 `partial` + exit 0，那份降级诊断照样要用。降级程度读 JSON 的 `status` / `core_missing`，别靠退出码猜。

### 跑完先看 `status`，不看 status 就开口 = 编

| `status` | 含义 | 你必须怎么答 |
|---|---|---|
| `inconclusive` | 核心探针（home / robots / sitemap）**全**没拿到数据 | 只报「这次什么都没看到 + 可能原因（网络 / 5xx / 反爬）」。**禁止下任何结论**，包括「看起来还行」 |
| `partial` | 部分核心探针没看到，`core_missing[]` 列出是哪几个 | 先答「看见了什么 / 没看见什么」，再只对看得见的部分开方。**禁止对 `na` 项下结论，禁止说站点健康**。此时 `diagnosis.evidence_partial=true`，**`verdict` 一律当暂定**——没看到的那部分随时能翻案（实测：首页 502 而 robots/sitemap 可用时仍会算出 `critical`，那个 critical 只覆盖看得见的部分） |
| `ok` | 核心都看到了 | 正常开方 |

- `run_confidence`：拿到数据的探针占比（0–1）。低不代表站有问题，代表**你看到的少**。
- `sitemap_follow`：**`ok`** 跟到 / **`lost`** index 200 但子表没跟到 / **`absent`** 站点确实没有 / **`fail`** 探针失败。
  `lost` 和 `fail` 都是「没看到分布」——**不能读成「分布均衡」或「健康」**。
- `findings[]` 当事实，`cannot[]` 当禁区，`next_collect[]` 当下一步搜集。
- **`status` 五值，别混**（`na` 和 `seen` 混了会让合同自相矛盾）：
  - `na` = 探针**没看到**（5xx / 网络错 / 子表跟丢 / 没抽样）。只准说「探针没看到」，
    不准说「没有问题」。
  - `seen` = 探针**看到了材料、但不自动打分**（`title-h1` / `json-ld` / `jsonld-types` /
    `linkedin`）。文案就在 `evidence` 里，**你该直接拿它开方**——不是缺数据，也不是已判过。
  - `pass` / `warn` / `fail` = 探针按规则判过的。只有 `warn` / `fail` 才进「先做 / 先停」。
  （`sitemap-mix` n=0 是 `na` 不是 `warn`——「没看到分布」不许写成「集中度正常」；
   `title-h1` 已从恒 `na` 拆成 `seen`：材料都给了还叫「没看到」，
   只会逼你在「不敢用已看到的 title」和「破坏 na 纪律」之间二选一。）
- 然后必须 `web_search`：`site:该域名`。

## 任务类型 → 先看什么（不要 1 到 7 走一遍）

| 用户在问 | 先做 | 默认不碰 |
|---|---|---|
| 流量/排名大跌 | 探针 robots、soft-404、`<main>`、m 子域（7.1 1.4 7.5 7.2）。再问有无 GSC 手动操作（1.1） | 3.x 外链、2.x GEO 作业 |
| 新站 / 买域名 | 4.1 Wayback；7.4 About；6.3 每页 query | 3.1「停外链」、6.4 大站过滤 |
| 守山（已是类目第一） | #64 先停会伤流量的改动 | 增长向的铺页 |
| GEO / AIO / ChatGPT 引用 | 2.1 + 2.2。正面 how-to **不在语料**。2.3–2.7 只作刹车 | Reddit/schema/FAQ/PR 清单 |
| YMYL / 钱/医/法 | 4.2 4.3 5.1 5.2 | 工具站式「不必 LinkedIn」 |
| 外链 / DA / DR | 3.1 降；无 Ahrefs 就写无数据 | 把停预算当增长方子 |
| 选词 / KD | 3.4 6.3 | 审站默认不讲 KD |
| 「怎么做 SEO」太宽 | 探针 fail/warn → 最多 3–7 条 | 判定规则全文 |

## 判定规则怎么叠（覆盖、差在哪、适用谁）

同一问题上只出**一条动作**，编号可以并列。

| 碰撞 | 怎么用 |
|---|---|
| 1.4 和 7.1 都是软 404 | 合并：先改真 404。挂 `1.4 7.1` |
| 1.3 SRA vs 1.1 MA | SRA 是原因，修法走 1.1。普通下跌不要叫 SRA |
| 1.2 Core Update | 只用于「大规模 AI 矩阵 + 对齐日期」。普通波动不用 |
| 6.1 Quality vs 6.2 Effort | 6.2 是门槛；6.1 是全站。先门槛 |
| 3.1 外链 vs 7.1 技术 | 同一亲历 #61：他归到修渲染。禁止单归因停外链 |
| 4.2 域名 vs 7.4 About | 买域/换域用 4.x；已上线站用 7.4 |
| 2.1 vs 2.2 | AIO=SEO；Gemini 另一部门。GEO 提问两条一起说，然后停 |
| 5.1 LinkedIn | 只在 EEAT 被问责的类目。工具/文档站不适用 |
| 5.3 topical | News SEO 视角，不是所有站按媒体建 |
| 6.4 内部 ML noindex | 大站。小站不要装 |
| 2.7 Bing | 出海/英文侦查。中文主战场可能是百度 |
| 3.1「停外链」 | 新站不适用 |

同时命中时从上往下砍，满 7 条停：① 技术阻断（抓取/404/`<main>`/两套 HTML）② 信任红线（YMYL 假作者、脏域名）③ 站点定性（focus / About）④ 内容门槛（原创 / 一页一词）⑤ 机制刹车（GEO 污染、Navboost 乱套、追 DA）。

元规则：假设→测试→衡量→迭代（#86 #123）；官方措辞逐字读（#127 #119）。`Ranking = (Technical Foundation + Quality) × Brand Reputation` 是心智模型不是官方权重（#123）。GEO 建设 ≠ 污染（#4）。打江山 ≠ 守江山（#64）。点名为 ranking factor 的是 **Quality**（6.1），不要写「EEAT 是 ranking factor」——EEAT 是 Effort/原创门槛（6.2）。AEO/GEO 正面作业不在语料。

只采 `core × authored × strong × is_main`。常识（robots 第一、H1 放目标词、301）不进判定规则；下跌时用**探针读 robots**，不新开判定规则。

## 风险信号：命中即停 / 先拆（选判定规则之前先过一遍）

来源 `expert_claims.md` 附录B（自正文 134 条判定规则反推的红线行为汇总，每条可回查判定规则出处）。
**冲突的写「不采用」并给理由；语料只点名没给修法的标 `no-procedure`——点名可以，不许编 how-to。**

| 风险信号 | 归到 | 处置 |
|---|---|---|
| RF01 假作者 / AIGC 作者壳 / 装饰性作者框 | 5.1 + 6.2 | 停 |
| RF02 通用可贩卖 SEO·GEO Agent；「token 花得多 = Effort 花得多」 | 6.2 | 停 |
| RF03 无增量批量博客 / 洗稿拼接 / AI slop 当增长 | 6.2 + 6.4 | 停 |
| RF04 铺词铺内容 /「多发就赢」 | 6.3 | 停 |
| RF05 追外链 / 买链恢复 / 定制 anchor guest post / DA 当目标 | 3.1 + 3.2 | 停 |
| RF06 IP 自动切语言 / 自动跳转 | 7.2 cloaking-adjacent | 先拆 `no-procedure` |
| RF07 独立 m 站 / H5 小程序当导出栈 / `display:none` 藏文 | 7.2 | 停 |
| RF08 软 404（错误页 200） | 1.4 + 7.1 | 停 |
| RF09 移动端空首屏 / 首屏遮罩 | 7.5（部分采用，见下） | 停 |
| RF10 Cloaking / 给爬虫看不同版本 / AI 灌页 / Link Spam | 7.2 + 1.4 | 停 |
| RF11 廉价批量外链 | 3.2 | 停（**数字不写**，见下） |
| RF12 Ghost-writing / site reputation abuse | 1.3 | 停 |
| RF13 GBP / 本地列表无站内 NAP | 语料无 | 先拆 `no-procedure` |
| RF14 核心内容只在 JS 后出现 / 关 JS 活不下来 | 7.2 | 停 |
| RF15 JS 重内容，chatbot 不渲染 | 7.2 | 停 |
| RF16 内链带追踪参数（有 canonical 也算） | 语料无 | 先拆 `no-procedure` |
| RF17 千人千面 / 个性化 vs 爬虫看到哪一面 | 7.2 cloaking-adjacent | 先拆 |
| RF19 纯博客站、没有 money page | 7.4 + 6.3 | 停 |
| RF21 脏域名起步（spam / PBN / 黄赌毒） | 4.1 | 停 |
| RF22 常规营销没跑就上 GEO / GEO 套件当作业 | 2.1 + 2.4 | 停 |
| RF23 污染型 GEO（让模型偏向你 / 买答案层） | 元规则 #4 | 停 |
| RF24 机械 SOP / 大厂 JD 当大纲 | 6.2 non-commodity | 停 |
| RF25 产品自称 XXX AI Agent，Trends 显示用户不这么搜 | 6.3 | 停 |
| RF26 一个 Reddit 帖 / ChatGPT 博客当高客单获客 | 2.1 | 停 |
| RF27 GSC AI citations / Bing Total Citations 当成功指标 | 2.x | 先拆 `no-procedure` |
| RF28 编 Day 0 / 三连反转 /「写英文解决 LLM 劣势」 | 禁止编（全局元规则） | 停 |

**编号缺口**：上表没有 RF18 / RF20——那两条整条不采用，理由见下。编号保留不回收，避免旧引用错位。

**不采用（与「明确不进」冲突）**

- **RF18「H1 不通顺 / H1 不是排名词」— 整条不采用。** 冲突点：「H1 放目标词」是本口径明确不进判定规则的常识。本口径只在 6.3 讲「这页说不出自己排什么」，不讲 H1 必须放哪个词。
  **不采用是审过、不是漏采**：#125（2093224389605261381）已在 134 条内，`expert_claims.md` G7 判为「常识·不进判定规则」，
  跟帖 2093236681449332851 亦在库。**勿再当新缺口重开。**
  诗意空 H1 的落点＝一页一词表里「这页说不出自己排什么」，作 6.3 反例，不升格成「H1 放目标词」判定规则。
- **RF20「迁移无 1:1 301」— 不采用。** 冲突点：「301 一一对应」在明确不进里。迁移类问题走 1.1 / 4.1，不给 301 清单。
- **RF09 部分采用：**「移动端空首屏 / 首屏遮罩」归 7.5（主内容要进 `<main>`、首屏要有主内容）；其中「H1 被埋」的 H1 部分同 RF18 不采用。
- **RF11 用方向不用数字：** 方向归 3.2；`PR>51000` 这个数字在明确不进里，**不许写进报告**。

## 输出合同（每次都要）

### 可读性（写给不懂 SEO 的人）

报告是给人看的，不是给维护者看的。以下红线命中即改：

现在 `audit_url.py` 运行后**自动**生成人话版报告：`<域名>_audit_report.md` 与 `<域名>_audit_report.html`（默认随 JSON 一起落盘）。agent 不必再手动把 JSON 翻译成散文。上述红线同样约束自动报告（回归由 `tests/report_gate.py` 钉死）。

技术项全 pass 时，自动报告**仍须**给出先做/先停（含测不到的刹车）。**不得只剩一条「把栏目比例做均衡」**。一页一词表必须写入首页 + 抽样内页；说不清就写「这页说不出自己排什么」，并明示探针不发明关键词。

`cannot[]` 去黑话后**改写成「待你处理」**，分两类进报告：**待办任务**（用户去拉/查 GSC、Ahrefs、Screaming Frog、site: 搜索）与**需你确认**（探针看不到的状态，如 Manual Action vs Deindex、品牌搜索量 vs 外链、作者履历真伪）。**不要把能力缺口写成「本次拒绝伪造」式防御腔**——那是用户该做的动作，不是探针的免责声明。下一步必须写明 `site:该域名` 由人补做。地图几乎只有博客/新闻、看不到成交/产品目录时才点「缺成交页」；有成交目录不得误报纯博客。pass 项要写口径边界（只查了首页 / 只打了一个假 404 / 存档是窗口不是全史）。

- **第一句必须是一段大白话（≤120 字）**：站现在什么状态 + 最该做的一件事。不懂 SEO 的人读完要知道「我现在该干啥」，不是看到一串术语。
- **verdict 四值翻成人话再写，不准直接贴英文**：`critical`→有必须修的硬伤；`at-risk`→有高风险项先处理；`needs-focus`→技术没硬伤，但 Google 可能搞不清你是干嘛的——去把「关于我们」/首页定位写清楚（**不是「站有问题」**）；`insufficient`→这次看的不够、下不了结论，先补数据。
- **状态值翻译**：`na`→探针没看到（≠没问题）；`seen`→看到了材料、要你判断；`pass`/`warn`/`fail`→按规则判过（`warn`/`fail` 才要处理）。
- **去内部溯源**：JSON 里的 `loki`/`#n`/`口诀`/`G7`/`siteFocus` 是给维护者看的，**报告正文一律不出现**；只留能落地的动作和证据数字（如 `n=444`、`posts 占 75%`）。
- **术语首次出现翻成人话**：sitemap→网站地图文件；soft-404→错误页却返回 200 的假 404；EEAT→谷歌对「作者是否够专业可信」的要求；`<main>`→页面主内容区；focus_reading→「Google 给你的站定的类目」。

### AI 闭环（agent 只读 JSON.agent）

自动报告是「人话投影」，JSON 里的 `agent` 块才是机器可读合同。改站闭环时：

- agent 是源、md/html 是投影：动作只算一遍（在 `attach_report` 内 `build_agent`），md/html 从 `agent.actions` 渲染；二者一旦分叉，`tests/report_gate.py` 即红。`cannot[]` 是禁编/待办清单（含 `site:` 收录搜索这类探针永久缺口），`agent.cannot` 逐条带 `task`/`forbid`，是机器层单源；`site:` 只在 `cannot[]` 出现，`agent.actions` 不得重复 append。
- AI 改站前**只读 JSON.agent**，不要只读 md——md 故意删掉 `loki`/`#n`，对不上闭环键。
- `actions[].verify.kind` 三态是 moat：`probe`=同一命令复跑对 `rule+status`（软404/`<main>`/https/m站/display:none）；`human`=探针打不绿（About 定性、一页一词、成交页），**AI 禁止为了绿而改 sitemap 比例或堆标题**；`collect`=GSC/Frog/site:，没文件就停、不准编。
- `reprobe.cmd` 是复测命令，`agent.reprobe.diff` 是稳定对账键；修复循环只改一项、复跑、对 `diff` 比对，na↔pass 抖动标「可能是代理抖动」不当成修复成功。
- `conclude` 三态，不要收成一个布尔：`full`（ok，正常开方）/ `tentative`（partial，只对看得见的部分开方，整份暂定，禁止当终局）/ `none`（inconclusive，只报没看到，**不开方**，`actions` 只留 collect）。`may_conclude` 仅 `full` 为 true，给只读布尔的调用方。**禁止把 partial 当成 inconclusive**——那会把降级诊断整份丢掉。
- 不用 MCP 假接 GSC/Frog；不把 md 再喂给模型当 prompt；不给探针加 LLM（口径已在规则里，加层只会编 query/DR）。

1. **任务类型**
2. **探针事实（含置信度）**：`status` / `run_confidence` / `sitemap_follow` 一行打头，然后只列 fail/warn 和会影响开方的 `na`。数字全部来自 JSON。`partial` / `inconclusive` 时先把 `core_missing[]` 和 `na` 项列出来，明说「以下是没看到，不是没问题」。**`seen` 不是缺数据，不许列进「没看到」。**
3. **先做 / 先停（3–7 条）**：`diagnosis` 是**排序草稿，不是结论**——
   - `verdict`：`critical` 有 fail / `at-risk` 有技术阻断或信任红线 / `needs-focus` 只剩定性或常识类 warn / `insufficient` partial 且无 fail/warn（看到的少，勿读成站没问题）。`needs-focus` **不是**「有问题」，是「技术面没查到阻断，下一刀砍定性 / 内容」。
   - `focus_reading`（如「站点可能被当成 posts 站」）是 **7.4 定性，不是风险**，不要写成 must-fix。
   - `priority[]` 每条必须改写：**先做**四列 **谁改 / 改哪一页 / 改成什么 / 怎么验收**（再跑同一条命令，或 GSC 哪一屏）。只复述 `rule` 名不算开方。
   - **先停**表不复用先做的列名，四列是 **# / 别碰哪块 / 别做什么 / 边界在哪**。先停里既没有「谁改」也没有「改成什么」，套先做的列名会读不通。
   - `gaps[]` 是缺数据（`na`），单列，**不混进「先做」**。
   - `evidence_partial=true` 时整份 `verdict` / `priority` 是暂定的：先把 `core_missing[]`
     和 `gaps[]` 摆出来，再给暂定结论，并写明「补上哪份数据就能定下来」。
   - `to_judge[]` 是 `seen` 项：`title-h1` / `json-ld` / `jsonld-types` / `linkedin`。
     **材料已给、判断归你**——不进 `gaps`（不是缺数据），也不进「先做」（不是风险）。
     在第 4 条（一页一词表）和 5.1 里闭环，**不进下一步搜集**。
   - 砍的顺序按碰撞表五档：技术阻断 → 信任红线 → 站点定性 → 内容门槛 → 机制刹车。
4. **一页一词表**（6.3）：首页 + `sniffs[]` 各一行。列：URL / 这页要排的 query / 依据（title/h1 或用户说的）。说不清就写「这页说不出自己排什么」。`title-h1` 是 `seen`，title/h1 文案直接从 `to_judge[].evidence` 取用——**这一步就该用，不要因为它是 `seen` 就退回说「探针没看到」**。另问一句：转化发生在哪几页（用户填；探针看不到成交）。
5. **证据等级**：判定规则进 / 判定规则降 / 开放问题 / 探针事实 / 无数据。标题带`（降）`的，边界写进该条动作。
6. **下一步搜集**：只列 `next_collect[]` 里**探针核不到**的项（GSC / Frog / 域名历史）。用户把 CSV/截图发回来再读。禁止 PSI 充 Field CWV，禁止编 DR/外链/品牌搜索量/是否 MA。**禁止出现「再拉一遍 sitemap」这类重跑同一探针的动作。** 作者回链**不在这里**——它由 5.1 的类目边界决定（见下节），不是每个站都要。
7. **决策仍在用户**。

禁止：走完全部判定规则；编造 tweet_id；把降级案例升级成定律；GEO 作业清单；把 DA/citations 当原因。

发稿前自查（合同闸门，命中即改，改不了的在证据等级行暴露）：**编造**——id / 数字 / 站点名无源；**进口**——常识 checklist 混进判定规则（密度榜、外链建设、GEO 作业、title 字符数）；**升格**——（降）/ 单点 / asserted 被写成定律；**传记**——用户要审站、回复在讲 Loki 本人；**GEO 幻觉**——语料明说无 how-to 的领域给出了作业清单；**黑话**——loki/#n/口诀/G7/siteFocus 等内部溯源或术语未翻译进报告；verdict 四值没翻成人话；开头没给一段大白话总结。

对照通用 SEO 诊断：Title 塞词、H1 对准搜索词、关键词密度打分，是 Loki 标过的 **commodity**。用 6.3 / 2.1 顶回去。

## 探针 JSON 怎么读

**顶层先看，顺序不能反**：

- `status`：`inconclusive` / `partial` / `ok`。不是 `ok` 就按上面「跑完先看 status」那张表收着答。
- `run_confidence`：拿到数据的探针占比。低 = 你看到得少，不是站差。
- `sitemap_follow`：`lost` / `fail` = 没看到分布，**不要读成均衡**。
- `diagnosis.evidence_partial`：`true` 时 `verdict` 是**暂定**，先说清看见了什么再给结论。
- `diagnosis.verdict` / `.focus_reading` / `.priority[]` / `.gaps[]` / `.to_judge[]`：排序草稿，用法见输出合同第 3 条。`gaps` = 没看到，`to_judge` = 看到了待你判，两条走不同的闭环。

**逐条**：

- `sitemap-mix` 某一类路径占比很高 → **7.4**，问站点被定性成什么。前缀 n 含子目录首页/列表/总览，不是篇数。
  带 `focus{n,top,share}` 时 `diagnosis.focus_reading` 已给一句话定性（如「站点可能被当成 posts 站」）——**那是定性不是风险**。
  `n=0` 判 `na`：**跟丢 / 没看到分布，既不是健康，也不是集中度异常**。
- `sampled-originality` reprint/isBasedOn 多 → **6.2**。正文量用 `text_chars`，不要把 `html_chars` 当字数。
  分母只计 `status==200` 的活样本：evidence 报 `live/dead` 分解，`live=0` 判 `na`（抽样全死＝没看到，不是原创合格）。
- `robots-ua` 某个 UA 单独 Disallow 一条路径 → 不是全站隔离；核对 `User-agent: *`。
- `jsonld-types` / `json-ld` 是 `seen`（首页）；内页只报 `sniffs[].ld_types`。只写 JSON 里出现的 `@type`。schema 很全也不等于能排（2.1）。
- `linkedin` 是 `seen`：evidence 里的链接数就是材料。**`linkedin=0` 是站点事实**（首页没有 LinkedIn 链接），不是「没看到」。
  是否往下走 5.1 **先判类目**：只有 EEAT 被问责的类目（YMYL / 钱医法）才走；工具/文档站到此为止，
  不索要截图、不把「没有 LinkedIn」写成问题。这一步是类目判断，探针不做。
- `title-h1` 是 `seen`：title/h1 文案在 evidence 里，**直接拿去填一页一词表**。品牌 slogan → **6.3**；
  首页可做信任背书（7.4），不要改成密度榜。**在第 4 条闭环，不进下一步搜集。**
- `semantic main` pass = 首页 HTML 有 `<main>`（7.5）。**只看首页**：整站结构要 Frog；fail 才是技术阻断。
- `soft-404 probe` pass = 假 URL 返回真 404/410（1.4 7.1）。`na` = 探针没看到（超时/5xx），不是「没有软 404」。
- `m-subdomain` **status=0 双义**，判据是**真实 DNS 解析**而非 evidence 的 error 文本——
  文本随代理/本地化变，同一站点事实会出两种结论（实测：同一主机一次报 nodename→pass，
  一次因代理隧道报 `Tunnel connection failed: 502`→文本不匹配→误判 na）。
  DNS 查不到 = 没有 m 站（pass，站点事实）；解析得到但连不上 = 没看到（na）。
  200 = 两套 HTML 风险（warn，7.2）；5xx = 没看到（na，同 soft-404 通则——
  代理 502 与源站 502 在 HTTP 层无从区分，warn 会往 tier-1 塞假警报）。**别只看 status 数字。**
- `wayback` first/last200 是**最新窗口**内带有效状态码行的快照时间（4.1 域名历史）。只看得到 3 条样本，
  不是完整历史；黑历史（spam/PBN）要用 Ahrefs/Wayback 网页版人工查。
- 技术项全 pass → **7.1 边界**：下一刀砍内容策略，不是再堆 TDK。

**`na` 一律读作「探针没看到」**：5xx / 网络错 / 子表跟丢 / 没抽样，都不许写成「没问题」。
反过来——**站点「确实没有」是站点事实（4xx），走 `warn` / `seen`，不标 `na`**。
所以看到 `na`，问题在探针这侧，不在站点那侧；两种不要混。

## 探针核不到：怎么搜集、怎么读

没有权限就列清单让用户做，**不要替他编**。JSON 的 `next_collect[]` 是这份清单里**本次按站筛过**的那部分——只含探针核不到的项（GSC / Frog / 域名历史），不是全清单，也不含「再跑一遍同一探针」的动作。
`seen` 项（title/h1、`@type`、LinkedIn 链接数）**材料已经在 JSON 里**，不属这一类，别去搜集。

**GSC（要该资源权限）**
- 索引 → 网页索引编制：导出未编入原因。读软 404、被 robots 屏蔽、已抓取尚未编入。不要把「已编入总数」当健康分。→ 7.1 1.4
- 效果 → 页面、查询，对齐下跌窗口。读：同一 URL 是否对上一个主 query（6.3）；用户指出的转化页 vs 博客页谁在掉（转化页掉、博客涨 ≠ 站好了）。
- 体验 → 核心网页指标：**Field** URL 组。没有 GSC 用 https://cruxvis.withgoogle.com/ （origin + all，28 天，LCP/CLS/INP）。Lighthouse/PSI 只配 debug。→ 7.3
- 安全与手动操作：有条目走 1.1，先问清是 MA 还是只是排名掉。没有条目禁止说「被 K 了」。

**Screaming Frog（#116 #77，他本人优先于 Ahrefs 监控）**
- 整站爬，导出内部 HTML。看 Status、Indexability。
- 对比 Raw vs Rendered 文本。差大 → 7.2。
- 把 CSV 发回来再读。

**对手编制（3.4）**
- LinkedIn 搜该公司 SEO / Content 职位人数；招聘站看在招市场。数字是侦查，不是 KD 分数。

**作者（5.1）——先过类目边界，再决定要不要动**
- 探针材料：`linkedin` = `seen`，evidence 里的链接数是首页有没有 LinkedIn 链接（站点事实）。
- **边界（先判这个）**：只有 EEAT 被问责的类目（YMYL / 钱医法）才往下走；工具站 / 文档站
  / 电商目录到此为止——不索要截图，不把「首页没有 LinkedIn 链接」写成问题。
  这条边界过去只写在散文里、探针不收，所以每个站都被索要截图；现在由你在这里判。
- 过了边界才做：打开作者 LinkedIn 个人页，看是否回链到本域。用户截图即可。

读数总原则：假设 → 改一项 → 用同一面板复测。不要同时改十处还问「是不是外链的问题」。

---

## 1. 处罚与恢复

**1.1 Manual Action 和直接 Deindex 是两套修法**
- 他说：先确认是哪一种。MA：被 flag 的子域/子目录做专门 404，子域从源头整站 404，再提解除。Deindex：约 3–4 个月；AIGC 页源头 noindex，内链分阶段 nofollow，调 robots.txt。子目录比子域麻烦。
- 边界：Deindex 流程来自朋友案例（n=1），周期当经验不是 SLA。
- 反例：DNS 直接摘子域；页面「下了」但仍 200（软 404 = 没下）。
- 出处：#19 #20 #21 #18

**1.2 （降）怀疑大规模手动清理时，对齐 Core Update 日期**
- 他说：阿里那一轮千万级 AI 矩阵，他判断「那一轮里每次 Core Update 是一次结算」，且「基本上可以确定是手动清理」。
- 边界：观测法，不是「Core Update = Manual Action」定律。原文「每次」指那一轮，不是普适。
- 反例：把普通排名波动都说成手动处罚。
- 出处：#16 #17

**1.3 Site Reputation Abuse：借大媒体权威做板块**
- 他说：他管的站进过那波 publisher 被 K 的名单；第三方借大站 authority 做板块分成。MA 对整个域名打击致命，修法：404 再提解除。
- 边界：亲历的是美国那波 publisher，不是所有流量下跌都是 SRA。
- 反例：把任何跌幅都叫 SRA。
- 出处：#106 #61 #17

**1.4 规模化 AI 矩阵会被收；软 404 会让「下架」失效**
- 他说：跟踪过 10M+ 假作者/全 AI 页，先砍子路径再逐子域。整站几乎 soft 404 时改真 404 网站会崩，但 200 下架等于没下。
- 边界：他跟盘的一个矩阵，不是「凡 AI 必杀」。
- 反例：Agent 灌千万页还不读 EEAT/政策。
- 出处：#17 #18 #21 #65

---

## 2. GEO / AIO 与传统搜索

**2.1 AI Mode / AI Overview：crawl+index 与传统 SEO 同一套，差在 serving**
- 他说：爬、收录机制完全一致；serving 加了 Grounding on Search Index 和 Query Fanout，数据库一致。做 AIO 就是做 SEO。
- 边界：只覆盖 **Google Search 产品线**（传统搜索 + AIO/AI Mode），现场问过官方。AEO/GEO 正面 how-to **不在语料**；2.3–2.7 只作刹车，不当作业清单。
- 反例：把「GEO 必做 Reddit / schema / FAQ / PR」当清单（商品化）。Reddit 不该排 YMYL（#31）。他自己一个站没做这些 ChatGPT 流量也涨——只作反例，不当成「这些都不必做」。
- 出处：#68 #58 #43 #113 #69 #75 #32 #31

**2.2 Gemini 不归 Search 管**
- 他说：不同部门、不同爬虫；indexing Not part of search。Search 官方发布管传统 SEO 和 AIO，**不管 Gemini**。
- 边界：现场确认。Gemini 可参考传统基建，不能拿 Search 公告当 Gemini 公告。
- 反例：拿一篇 Search 博客直接指导 Gemini 引用。
- 出处：#68 #58 #43

**2.3 llms.txt 要分两层口径（单点 #29）**
- 他说：Google Search 的 AIO/AI Mode 不管 llms.txt；广义 GEO（ChatGPT/Claude 等）仍可能要做。前提 Search ≠ Gemini。
- 边界：1 条撑判定规则，专门拆混为一谈。有文件 ≠ AIO 会读。
- 反例：用「谷歌说了不管」否定所有大模型的 llms.txt。
- 出处：#29

**2.4 成熟品牌在 GEO 里好看 = 传统 branding 换说法**
- 他说：拆开就是 SEO/SEM/YouTube/IG/FB/TikTok，理论一样技巧不同。
- 边界：观察，不是实验。
- 反例：给零品牌新站开「只做 GEO 技巧、不做品牌」的方子。
- 出处：#30 #32

**2.5 Language Lock（降）**
- 他说：AI 搜索像双轨（用户语言 + 英文），所以要做多语言。
- 边界：样本是他自己的查询，数据停在 2026-05（Gemini 3.1 Pro），可能已变。
- 反例：把一次 fan-out 观察写成「所有 AI 搜索永远双轨」。
- 出处：#100 #129

**2.6 （降·开放问题）Navboost 与 AIO zero-click 对不上**
- 他说：Navboost 建立在点击和搜索旅程上，但 AIO/AI Mode 是 zero-click，点击数据源会枯竭。两种可能：生成式搜索里它被语义/向量校验取代；或「点击」换成了 hover/dwell/query steps。
- 边界：**开放问题**，他自己在问，不当定律。可作「不要把经典点击信号直接套到 AIO」的刹车。
- 反例：用传统 CTR 模型解释 AI Overview 的引用。
- 出处：#25

**2.7 不要只盯谷歌；Bing / IndexNow / Copilot 同一张网**
- 他说：Bing 是微软默认搜索；ChatGPT、Copilot、Yahoo 会用到 Bing；英美公司电脑常强制 Edge+Bing。做 Bing 别忘 IndexNow。
- 边界：中文站主战场可能是百度，这条是出海/英文流量的侦查项，不是让中文站改投 Bing。
- 反例：只优化 Google、当 ChatGPT 引用与 Bing 无关。
- 出处：#130

---

## 3. 外链与权重

**3.1 （降）权重指标是结果不是原因**
- 他说：YMYL 月 20K USD 外链后发现 DR/外链不是排名原因。小站也能在 KD70+ 赢大站。跨过门槛之后比页面对页面。
- 边界：**不等于新站可以零外链。** 「停预算没半毛钱影响」是他**那一个**站，同期修了 Angular 渲染超时/软 404，流量冲高他归到技术，不能单归因停外链。
- 反例：给已经 DR80+、产品增长很好的站开「做外链 + cloaking」。
- 出处：#2 #33 #34 #46 #61 #105 #121

**3.2 外链有质量门槛；免费可提交的外链没价值**
- 他说：追外链浪费钱；定制 anchor 的 guest post 见过删了排名涨、也见过买不停被清零。YMYL 可 disavow 或要求删除。
- 边界：方向进。PR>51000、高质量占比、spam_score+1 **数字不写**。
- 反例：人人可提交的目录链、批量 guest post 当「建设中」。
- 出处：#10 #44 #107 #108

**3.3 （降·单点 #109）品牌搜索量比外链更重要，所以起名字重要**
- 他说：Brand Search 比外链重要更多；正因为如此起名字更重要。不如好好做社交媒体，信号更强。
- 边界：1 条观点，无对照实验。可执行的是命名和品牌词，不是「从此不外链」。
- 反例：把这句话读成停掉所有外链预算。
- 出处：#109

**3.4 （单点 #78）KW Difficulty 看的是对手弹药，不是词难不难**
- 他说：选词看 KD，其实是看对手有多少人/装备。办法：LinkedIn 搜 SEO / content title 人数；看招聘动向。
- 边界：Canva「200+ SEO 相关」是他估计，不写进报告当编制事实。中小站别拿上市公司编制当标尺吓停。
- 反例：KD 高就放弃，或 KD 低当没对手。
- 出处：#78

---

## 4. 域名与 YMYL

**4.1 买域名前必须查历史**
- 他说：spam / PBN / 坏外链 / 黄赌毒 / 当过肉机。他自己买过上线 Chrome 红屏木马警报的域名，4–5 年信号还在。工具：Ahrefs/SEMrush/Majestic、SimilarWeb、Wayback。
- 边界：查的是**这个域名的历史**，不是名字好不好听。
- 反例：只看 brandable、不查 Wayback。
- 出处：#24 #110

**4.2 YMYL/EEAT 门槛绑在域名上，不只绑页面**
- 他说：见过 Gov/Clinic/Medical/Restaurant/Education 域名被拿去排 Casino、Web3。过期域名承载原 topic，所以有 expired domain abuse。
- 边界：「根据我的观察」，不是白皮书原句。
- 反例：YMYL 站换个路径就当换了一个信任主体。
- 出处：#55 #133 #6 #114 #23

**4.3 YMYL 类目要对应职业背景的人写**
- 他说：这类目只有对应背景的 creator 才排得上去；AIGC 包装作者一查就露。钱相关站点门槛是权威/专业/合规，不是第一反应的外链。
- 边界：他的行业判断。
- 反例：用假作者过 YMYL。
- 出处：#114 #112 #6

---

## 5. 作者与 EEAT

**5.1 作者实体必须可交叉验证；LinkedIn 双向连到网站**
- 他说：QRG 里学历和履历基本只有 LinkedIn 能承载；小红书、公众号没用。网站 ↔ GitHub/LinkedIn，人家没连你就不算。
- 边界：**需要 EEAT 背书的类目**（YMYL、作者可信度被问责的内容）。工具/文档站不要无差别强制双向 LinkedIn。语境见 #6。
- 反例：假作者、AI 生成作者档案。
- 出处：#70 #60 #104 #103 #102 #6

**5.2 护城河是人不是内容量**
- 他说：Wirecutter 那种资产是 150+ 署名 editor。PSEO 是放大已有 authority（真实作者/照片/review），不是造垃圾页。
- 边界：例子是媒体/旅游，不是所有垂直。
- 反例：裁掉署名编辑上 Agent 当「降本」。
- 出处：#49 #41 #118 #128

**5.3 （单点 #71）Topical authority = coverage 的时间 × 广度**
- 他说：某记者/机构在某 topic 上发得够久够广，天然有 topical authority。国外媒体（BBC/NYTimes）在不少主题上有优势；国内媒体因生态几乎没做 News SEO，在很多主题上是结构性劣势——再叠没有作者实体/学历链接，特定主题上会永远没排名优势。
- 边界：News SEO（Top Stories / News / Discover）视角，不是所有站点都按新闻机构建。
- 反例：国内媒体无作者实体却要在国际新闻主题上硬刚 NYT。
- 出处：#71

---

## 6. 内容与 Quality

**6.1 Quality 是全站信号，2025 年起官方当 ranking factor 讲**
- 他说：上海 SCL PPT；Quality 对立面是 Spam；实拍手写 vs Agent 洗稿。连听四场 SCL。
- 边界：现场转述，不是法律条文。点名为 ranking factor 的是 Quality，对立面 Spam。不要写「EEAT 是 ranking factor」；EEAT 走 6.2 门槛。库中无 2025-10 那条原文，不编 id。
- 反例：单页堆字当「Quality 已做」。
- 出处：#66 #113

**6.2 Effort + Originality 是门槛；通用 SEO Automation 跨不过**
- 他说：#92「如果每一个网站都需要定制一些策略来实现 Effort 和原创，那你还要通用型 SEO Automation 做什么？这不就是定制了么？」Non-commodity = 独家经验、知识库替不掉。
- 边界：#90 是**判断不是事实**（「技术上实现不了，还是逻辑上不通？」+ 为什么 Ahrefs/Semrush/Botify 不做自动化）。contentEffort 五条量化假设不进。
- 反例：国内头部 DTC 假作者铺 AI 博客流量腰斩（#28 #102）；两家推「AI SEO 博客自动化」的站从去年 12 月排名断崖（#14）。
- 出处：#92 #90 #91 #67 #75 #28 #102 #14

**6.3 铺词铺页面是伪命题；用户搜的不是你的行话**
- 他说：建站第一天就该知道每页排什么、title/h1/url 写什么。概念 ≠ 用户搜索词：出海别动不动叫自己 XXX AI Agent——Trends 里这个词亚洲领先、美国才第 8，C 端可能还不搜 Agent，要换叫法。落地就是输出合同里的一页一词表：说不清就写「这页说不出自己排什么」。
- 边界：#62 的地区拆解是他读 Trends 的一截，不是永久榜。Product Hunt/社媒增长可以继续用行话。
- 反例：内部分类词直接当目标词；找到词再补页面。
- 出处：#52 #38 #51 #122 #62

**6.4 （单点 #89）大站要自己做 spam 过滤并主动 noindex**
- 他说：Ameba 量级用内部 ML 做 Quality/Spam 分类，主动 noindex 低质和 AI slop。
- 边界：大站解法，小站没有同等内部语料。
- 反例：大站把垃圾 UG 全开给谷歌「多收一点」。
- 出处：#89

---

## 7. 技术地基

**7.1 Technical SEO 是 foundation；软 404 会吃预算还会被黑帽利用**
- 他说：Angular 渲染超时 → 大量 soft 404 → 修渲染流量冲上去。软 404：浪费 crawl；404 页 title/h1 从 URL 取，黑帽能造可收录垃圾页。
- 边界：#61 后半句：**技术到一个水准之后，决定性因素是微观**（每个 tag、字、alt、锚文本组成的最终页面形态）。不是「技术 SEO 万能」。
- 反例：APAC 品牌把排不上只归到 authority。
- 出处：#61 #7 #65

**7.2 Raw = Rendered，Desktop = Mobile（降）**
- 他说：一份 HTML 只出现一次，别 display:none。不是每个爬虫都能跑 JS（他列过 14 个：Google/Bing/OpenAI/Claude/Grok/Meta/DDG/Common Crawl/DeepSeek/豆包/字节/百度/Yahoo/Naver）。
- 边界：公式进；「不要 m 站」是旧常识只当反例。
- 反例：m 站两套 HTML；用 display:none 藏关键内容。
- 出处：#54 #77 #94 #132

**7.3 （单点 #119）CWV：看 Field Data，别被「是不是 ranking factor」带节奏**
- 他说：官方措辞从 2020「will become a ranking factor」收到现在「aligns with what core systems seek to reward」。Lab 只配 debug；准的是官方 dashboard 近 28 天 origin+all 的 LCP/CLS/INP。
- 边界：不要写成「谷歌宣布 CWV 已不是 ranking factor」。
- 反例：只刷 Lighthouse 分数、不管 Field Data 和内容。
- 出处：#119

**7.4 About Us 给站点「定性」**
- 他说：About Us 常被当事后页，但对 EEAT 极重要。它要交代谁在后面、业务实际做什么、凭据、内容是否对齐真实实体。可信度不是单篇文章堆出来的，是全站一致性；About 是一致性变得可见的地方（#3）。首页尽量用能盖住未来 3–5 年的 `{定语} + Entity`（#59，选词法；entity 概念本身是常识）。另：siteFocusScore / siteRadius 小半径更好做——字段在 leak 里，「小半径更容易成功」是推论（#87 #42）。
- 边界：#3 是页级动作；leak 半径仍是推论。首页 slogan ≠ 已经定性。
- 反例：About 写成通用公司简介；一个站同时当十个行业门户还指望每个都有 focus。
- 出处：#3 #59 #87 #42

**7.5 （单点 #50）主内容是 `<main>`；很多即插即用设计库有问题**
- 他说：QRG 的 MC = semantic HTML 里 `<main>` 里的东西。div 到底会把无关块送进算法。很多即插即用设计库有问题。
- 边界：这是结构要求，不是「不许用组件库」。要看渲染进 main 的是不是主内容。
- 反例：主题把推荐模块、弹层、无限页脚塞进主文档流。
- 出处：#50

---

## 明确不进

- robots.txt、301 一一对应、H1 放目标词、title 写法。
- 「至少 66.6% 一致」——2/3 步的玩笑，不是测量值。
- PR>51000、高质量外链占比、品牌+KW 线性、Bing「没有」EEAT、Casino 站崩塌细节。
- 转推、needs_review、短回复。

核对原文：包内 `corpus.json`（#n → full_text / 日期 / X 链接，与 `expert_claims.md` 索引表同序）；`expert_claims.md` 文末 `#n → tweet_id`。

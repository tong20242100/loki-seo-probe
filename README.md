# loki-seo-probe

[![探针门禁](https://github.com/tong20242100/loki-seo-probe/actions/workflows/gate.yml/badge.svg)](https://github.com/tong20242100/loki-seo-probe/actions/workflows/gate.yml)

**当前版本 1.0.13（2026-09-02）· MIT · 语料版权另见 [`NOTICE.md`](NOTICE.md)**

> Loki Yan SEO 口径的可验证实现：探针（客观 HTTP 事实）＋ 研判（专家判定规则映射）＋ 语义门禁（回归即红）。
>
> **非官方蒸馏，无授权、无关联。** 本项目从 @loki_yan_seo 的公开推文蒸馏口径，未获本人授权或背书。
> 语料是从其全账号切出的 **134 条**门禁切片（`core × authored × strong`，**非全账号**）；
> 这 134 条的**完整原文**收录在 `corpus.json`（`#n` 与 `expert_claims.md` 同序，含 X 链接），可离线回源核对每条判定规则。
> **原文版权归 @loki_yan_seo 所有**；MIT 仅覆盖本仓库的代码与文档结构（见 NOTICE.md）。

这不是通用 SEO 手册。关键词密度、H1 塞目标词、外链建设、GEO 作业清单这类 commodity 建议，
在本口径里是被明确顶回去的（见 SKILL.md「明确不进」）。

## 为什么不是又一份 prompt 合集

同类 skill（含市场里装机量最高的那批）普遍缺的不是知识，是**防编造的强制力**。
本项目的差异在三层结构：

| 层 | 文件 | 作用 |
|---|---|---|
| 口径层 | `SKILL.md` + `expert_claims.md` | 134 条专家主张：判定规则、边界、反例、出处 tweet_id；碰撞表决定判定规则叠加顺序 |
| 探针层 | `scripts/audit_url.py` | 未登录 HTTP 事实采集：robots / sitemap / 软 404 / `<main>` / m 站 / Wayback，输出带置信度的 JSON。五值状态机 `na / seen / pass / warn / fail`：**没看到 ≠ 没问题** |
| 门禁层 | `tests/confidence_gate.py` | 24 组语义断言（含变异测试验证）：判定规则语义回归直接 exit 1，不靠模型阅读自觉。形态门禁（函数 ≤40 行 / 嵌套 ≤3 / 纯 if ≤5）由本项目维护者自己的 `shape_check.py` 把关，**不随包发布**——那是写代码的纪律，不是装技能的人要的东西 |

关键设计（都在门禁里钉着，回退必红）：

- **降级状态机**：首页 502 但 robots 可读时是 `partial` + exit 0——可用的降级诊断不整份丢弃；
  `verdict` 在 partial 且无 fail/warn 时输出 `insufficient`，不让「healthy」字面值骗下游。
- **网络抖动不翻结论**：探针超时（`status=0`）／5xx 一律 `na`（没看到），不落 warn——站点没变，
  抖动不该把结论从 pass 翻成 at-risk。唯一例外：robots 是下跌场景第一探针，非 200 一律 `warn`
  （门禁刻意钉死）。
- **待你处理清单**：GSC Field CWV、DR / 外链、品牌搜索量等探针核不到的项，在 JSON 里显式挡（`cannot[]`），
  报告里改写成「待办任务 / 需你确认」两类，由用户自己去拉/查或确认，不写成防御腔。
- **`seen` 值**：title / h1 文案、JSON-LD 类型这类「材料已给但不自动打分」的事实，
  与「没看到」严格分开，判断权归输出合同。

## 安装

放进任何支持 SKILL.md 约定的 agent skills 目录：

```bash
git clone https://github.com/tong20242100/loki-seo-probe.git
cp -r loki-seo-probe ~/.workbuddy/skills/loki-seo      # ~/.claude/skills/、~/.grok/skills/ 同理
```

目录名要跟 `SKILL.md` frontmatter 里的 `name: loki-seo` 对齐，否则有些宿主认不出来。

依赖：Python 3 标准库即可运行（零第三方包）。可选装 `curl_cffi` 作为抓取后端——用真实浏览器 TLS 指纹绕过 WAF/Cloudflare 对裸 `urllib` 的拦截，缺失时自动回退标准库，门禁不受影响。

## 使用

```bash
python3 scripts/audit_url.py https://example.com   # 输出 JSON，并自动生成 <域名>_audit_report.md / .html 人话版报告
python3 scripts/audit_url.py https://example.com --diff prev.json   # 只打印 findings/sitemap 变化，复测对账（na↔pass 抖动会标「可能是代理抖动」）
python3 tests/confidence_gate.py                   # 语义门禁，应全绿
python3 tests/report_gate.py                       # 报告可读性门禁，应全绿
python3 tests/fetch_retry_gate.py                  # 抓取重试门禁（502/超时退避重试），应全绿
```

CI（`.github/workflows/gate.yml`）在每次 push 到 `main` 与每个 PR 上跑**全部三道门禁**（语意 / 报告可读性+AI 闭环一致性 / 抓取重试），任一红即阻断合并。本地改完先跑上面三条确认全绿再提。

所有外网抓取统一走 `fetch()`，对 502/503/504 与网络超时自动退避重试（最多 3 次，间隔 1s→2s→4s），单次代理/隧道抖动不再把 sitemap/robots 打成 `na`；站点真 502 则如实报 502（上游仍按「没看到」处理，不假装探测失败）。默认走标准库 `urllib`；若装了 `curl_cffi`，`fetch()` 自动改用浏览器指纹抓取，降低被 WAF 误拦导致的假 `na`。

**AI 闭环**：探针输出的 JSON 里带一个 `agent` 块（`schema: loki-seo-agent/v1`），是机器可读合同——动作只算一遍（在 `attach_report` 里 `build_agent`），md/html 只是它的投影。AI 改站前只读 `JSON.agent`，不要只读 md；`agent.actions[].verify.kind` 三态（probe/human/collect）定死「哪些能复测验收、哪些探针打不绿、哪些没文件就停」。详见 SKILL.md「AI 闭环」一节。

agent 按 SKILL.md 的输出合同（任务类型 / 探针事实 / 先做先停 / 一页一词表 / 证据等级 / 下一步搜集）出报告。
人肉使用也成立：跑探针，对着 JSON 里的 `status` / `run_confidence` / `diagnosis` / `agent` 读。

## 发布（推到 GitHub 触发 CI）

仓库已关联 `origin`（`https://github.com/tong20242100/loki-seo-probe.git`）。`git push` 即触发
`.github/workflows/gate.yml` 三道门禁，README 顶部 badge 同步状态。

```bash
git push                          # 已配好 remote，直接推
```

推送走 HTTPS（用本机 Git 凭证助手或已登录 `gh` 的凭证）。
本机 `/Users/tong/agent-hub/bin/gh` 是**只读查询封装**，不参与推送。
本地若领先 `origin/main`（例如尚未推送的清理提交），推送后即进 CI。

## 语料与版权

- 收录的是 **@loki_yan_seo** 在 X 上**公开发布的推文原文**，目的是让每条判定规则可离线回源，不是转载传播。
- **134 条是切片，不是全账号**：收录标准与不收录范围见 [`NOTICE.md`](NOTICE.md)。
- **原文版权归 @loki_yan_seo 所有**；MIT 仅覆盖本仓库的代码与文档结构，**不覆盖**推文原文。
- 有异议即下架：原作者或权利人在 issue 或 X（[@MagicQM](https://x.com/MagicQM)）提出，直接删，不问理由。

## 验证

判定语义由 `tests/` 下三道门禁钉死，回退即红：

- `confidence_gate.py`：24 组语义断言 + 变异测试（含诱导性变异），覆盖置信度、研判排序、seen/na 拆分、sitemap 变体、抖动与假 healthy、m-host / Wayback / 抽样分母 / display:none / 各探针超时路径。
- `report_gate.py`：渲染层去黑话、verdict 人话、四列表、JSON.agent↔md 投影一致。
- `fetch_retry_gate.py`：502/超时退避重试（patch 下一层 `urlopen`，断言真实重试行为）。

门禁的分组、变异清单与历次抓虫记录见 [`CHANGELOG.md`](CHANGELOG.md)。

## 仓库结构

```
SKILL.md                    调用规程：路由表、碰撞表、输出合同、风险信号、判定规则全文
expert_claims.md            134 条主张表（含 #n → tweet_id 映射）
corpus.json                 134 条推文原文（#n 同序、日期、X 链接，可离线核验）
scripts/audit_url.py        探针（纯标准库，运行后自动生成人话 md/html 报告；含 build_agent 产出 JSON.agent 机器合同 + --diff 复测对账；fetch 含 502/超时退避重试）
tests/confidence_gate.py    语义门禁（692 行，compile 源码，绕过 pyc 缓存）
tests/report_gate.py        报告可读性门禁（钉死渲染层去黑话 / verdict 人话 / 四列表 / JSON.agent↔md 投影一致）
tests/fetch_retry_gate.py   抓取重试门禁（patch 下一层 urlopen，断言真实重试行为）
NOTICE.md                   语料归属、非官方声明、下架方式
```

## License

MIT，见 [`LICENSE`](LICENSE)。推文原文不在 MIT 覆盖范围内，见 [`NOTICE.md`](NOTICE.md)。

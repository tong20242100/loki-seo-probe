<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license MIT"/>
  <img src="https://img.shields.io/badge/python-3%20%2B-blue.svg" alt="python 3+"/>
  <img src="https://img.shields.io/badge/AI--native-probe-9cf.svg" alt="AI-native probe"/>
  <img src="https://img.shields.io/badge/corpus-134%20tweets-blueviolet.svg" alt="corpus 134 tweets"/>
  <img src="https://img.shields.io/badge/non--official-orange.svg" alt="non-official"/>
  <img src="https://img.shields.io/badge/core-zero--deps-0a0.svg" alt="core zero deps"/>
</p>

<h1 align="center">🔬 loki-seo-probe</h1>

<p align="center">
  <b>用 @loki_yan_seo 的口径，把一个网址诊断成能落地的动作——并且结构上不能编</b><br/>
  探针抓客观 HTTP 事实 → 研判套专家判定规则 → 语义门禁锁死口径，任何回归直接红灯
</p>

<p align="center">
  <a href="https://github.com/tong20242100/loki-seo-probe/actions/workflows/gate.yml">
    <img src="https://github.com/tong20242100/loki-seo-probe/actions/workflows/gate.yml/badge.svg" alt="门禁 CI"/>
  </a>
</p>

---

> **非官方实现，无授权、无关联。** 判定规则以 [@loki_yan_seo](https://x.com/loki_yan_seo) 在 X 上公开发布的推文为源（见 `corpus.json`），未获本人授权或背书。
>
> 我们从其全账号切出 **134 条**门禁切片（`core × authored × strong`，**非全账号**），这 134 条的**完整原文**收录在 `corpus.json`（与 `expert_claims.md` 同序、含 X 链接），可离线回源核对每一条判定规则。**原文版权归 @loki_yan_seo 所有**；MIT 仅覆盖本仓库的代码与文档结构（见 [`NOTICE.md`](NOTICE.md)）。
>
> 这不是通用 SEO 手册。关键词密度、H1 塞目标词、外链建设、GEO 作业清单这类 commodity 建议，不在本口径的覆盖范围内（见 SKILL.md「明确不进」）。

---

## 三层结构

同类工具缺的从来不是知识，是**防编造的强制力**。本仓库把口径落成三层，每一层都可被程序验证：

| 层 | 文件 | 做什么 |
|---|---|---|
| 🔬 **口径层** | `SKILL.md` + `expert_claims.md` | 134 条专家主张：判定规则、边界、反例、出处 `tweet_id`；碰撞表决定规则叠加顺序 |
| 🧭 **探针层** | `scripts/audit_url.py` | 未登录 HTTP 事实采集：robots / sitemap / 软 404 / `<main>` / m 站 / Wayback，输出带置信度的 JSON。五值状态机 `na / seen / pass / warn / fail`：**没看到 ≠ 没问题** |
| 🚧 **门禁层** | `tests/confidence_gate.py` | 语义断言（含变异测试）：口径一旦回归直接 `exit 1`，不靠模型阅读自觉 |

---

## 安装

放进任何支持 `SKILL.md` 约定的 agent skills 目录：

```bash
git clone https://github.com/tong20242100/loki-seo-probe.git
cp -r loki-seo-probe ~/.workbuddy/skills/loki-seo      # ~/.claude/skills/、~/.grok/skills/ 同理
```

目录名要跟 `SKILL.md` frontmatter 里的 `name: loki-seo` 对齐，否则部分宿主认不出来。

**依赖**：Python 3 标准库即可运行（零第三方包）。所有外网抓取统一走 `fetch()`，对 502/503/504 与网络超时自动退避重试（最多 3 次，间隔 1s→2s→4s）；站点真 502 如实上报，不假装探测失败，也不会把单次代理抖动误判成 `na`。可选装 `curl_cffi` 作为抓取后端——用真实浏览器 TLS 指纹绕过 WAF / Cloudflare 对裸 `urllib` 的拦截，缺失时自动回退标准库。

---

## 使用

```bash
python3 scripts/audit_url.py https://example.com                  # 输出 JSON，并生成 <域名>_audit_report.md / .html 人话版
python3 scripts/audit_url.py https://example.com --diff prev.json  # 只打印 findings / sitemap 变化，复测对账
```

跑完得到两份产物：一份机器可读的 `JSON`（含 `status` / `run_confidence` / `diagnosis` / `agent`），一份人话版的 `md` / `html` 报告。

- **人读**：直接看 `md` / `html` 报告，或对着 JSON 里的 `status` / `diagnosis` 读。
- **AI 读**：只读 `JSON.agent` 块（`schema: loki-seo-agent/v1`）——它是机器合同，动作只算一遍，md / html 只是它的投影；`agent.actions[].verify.kind` 三态（probe / human / collect）定死「哪些能复测验收、哪些探针打不绿、哪些没文件就停」。完整合同见 SKILL.md「AI 闭环」一节。

---

## 可信度保证

判定语义不是靠模型自觉，而是由 `tests/` 下三道门禁强制钉死——任何回归都会让 CI 变红：

- `confidence_gate.py` — 语义断言（含变异测试）：覆盖置信度、研判排序、seen/na 拆分、sitemap 变体、抖动与假 healthy、m-host / Wayback / 抽样分母 / `display:none` / 各探针超时路径。
- `report_gate.py` — 渲染层去黑话、verdict 人话、四列表、JSON.agent↔md 投影一致。
- `fetch_retry_gate.py` — 抓取重试行为：断言真实退避，而非只在源码里写字符串。

门禁在每次 push / PR 的 CI 中自动跑，顶部 badge 显示当前状态；演进记录见 [`CHANGELOG.md`](CHANGELOG.md)。

---

## 仓库结构

| 文件 | 所属层 | 作用 |
|---|---|---|
| `SKILL.md` | 口径 | 调用规程：路由表、碰撞表、输出合同、风险信号、判定规则全文 |
| `expert_claims.md` | 口径 | 134 条主张表（含 `#n → tweet_id` 映射） |
| `corpus.json` | 口径（语料） | 134 条推文原文（`#n` 同序、日期、X 链接，可离线核验） |
| `scripts/audit_url.py` | 探针 | 纯标准库探针；运行后自动生成人话 md/html 报告；含 `build_agent` 产出 `JSON.agent` 机器合同 + `--diff` 复测对账；`fetch` 含 502/超时退避重试 |
| `tests/confidence_gate.py` | 门禁 | 语义门禁 |
| `tests/report_gate.py` | 门禁 | 报告可读性门禁（钉死渲染层去黑话 / verdict 人话 / 四列表 / JSON.agent↔md 投影一致） |
| `tests/fetch_retry_gate.py` | 门禁 | 抓取重试门禁 |
| `NOTICE.md` | 声明 | 语料归属、非官方声明、下架方式 |
| `LICENSE` | 声明 | MIT 许可证 |

---

## 语料与版权

- 收录的是 **@loki_yan_seo** 在 X 上**公开发布的推文原文**，目的是让每条判定规则可离线回源，不是转载传播。
- **134 条是切片，不是全账号**：收录标准与不收录范围见 [`NOTICE.md`](NOTICE.md)。
- **原文版权归 @loki_yan_seo 所有**；MIT 仅覆盖本仓库的代码与文档结构，**不覆盖**推文原文。
- 有异议即下架：原作者或权利人在 issue 或 X（[@MagicQM](https://x.com/MagicQM)）提出，直接删，不问理由。

---

## License

MIT，见 [`LICENSE`](LICENSE)。推文原文不在 MIT 覆盖范围内，见 [`NOTICE.md`](NOTICE.md)。

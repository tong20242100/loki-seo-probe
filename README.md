[![门禁 CI](https://github.com/tong20242100/loki-seo-probe/actions/workflows/gate.yml/badge.svg)](https://github.com/tong20242100/loki-seo-probe/actions/workflows/gate.yml)
![MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3%2B-blue.svg)
![corpus](https://img.shields.io/badge/corpus-134%20tweets-blueviolet.svg)

# loki-seo-probe

用 [@loki_yan_seo](https://x.com/loki_yan_seo) 的口径，把一个网址诊断成能落地的动作——并且**结构上不能编**。

> **非官方实现，与作者无关联、未获授权、未获背书。** 判定规则以 @loki_yan_seo 的公开推文为源（见 `corpus.json`）；原始推文版权归原作者所有，MIT 仅覆盖本仓库代码与文档结构。完整版权与下架方式见 [NOTICE.md](NOTICE.md)。
>
> 这不是通用 SEO 手册：关键词密度、H1 塞目标词、外链建设、GEO 作业清单这类 commodity 建议，不在本口径的覆盖范围内（见 SKILL.md「明确不进」）。

---

## 三层结构

本仓库把一套 SEO 判断标准体系落成三层，每一层都能被程序验证：

| 层 | 文件 | 这一层负责什么 |
| --- | --- | --- |
| 🔬 **判断标准体系** | `SKILL.md` + `expert_claims.md` | 把一位 SEO 专家的 134 条判断标准整理成可查的规则库：每条都有判定条件、适用边界、反例、和原始推文出处；多条规则同时命中时按优先级决定顺序。 |
| 🧭 **事实采集** | `scripts/audit_url.py` | 不登录、纯公开请求抓取网站的客观事实：robots 协议、sitemap、伪装成正常的死链（软 404）、移动版子站、历史存档。输出带可信度标注的结果——**抓不到 ≠ 没问题**。 |
| 🚧 **防回归门禁** | `tests/confidence_gate.py` | 用自动化测试把上面的判断标准锁定：只要标准被改坏，测试立刻报错，不靠人肉审查。 |

## 安装

放进任何支持 `SKILL.md` 约定的 agent skills 目录：

```bash
git clone https://github.com/tong20242100/loki-seo-probe.git
cp -r loki-seo-probe ~/.workbuddy/skills/loki-seo      # ~/.claude/skills/、~/.grok/skills/ 同理
```

目录名要跟 `SKILL.md` frontmatter 里的 `name: loki-seo` 对齐，否则部分宿主认不出来。

**依赖**：Python 3 标准库即可运行（零第三方包）。所有外网抓取统一走 `fetch()`，对 502/503/504 与网络超时自动退避重试（最多 3 次，间隔 1s→2s→4s）；站点真 502 如实上报，不假装探测失败，也不会把单次代理抖动误判成「没抓到」。可选装 `curl_cffi` 作为抓取后端——用真实浏览器 TLS 指纹绕过 WAF / Cloudflare 对裸 `urllib` 的拦截，缺失时自动回退标准库。

---

## 使用

```bash
python3 scripts/audit_url.py https://example.com                   # 输出 JSON，并生成 <域名>_audit_report.md / .html 可读版
python3 scripts/audit_url.py https://example.com --diff prev.json   # 只打印变化项，复测比对
```

跑完得到两份产物：一份机器可读的 `JSON`（含 `status` / `run_confidence` / `diagnosis` / `agent`），一份可读的 `md` / `html` 报告。

- **人工查看**：直接读 `md` / `html` 报告，或对照 JSON 里的 `status` / `diagnosis`。
- **AI 集成**：只读取 JSON 里的 `agent` 块（`schema: loki-seo-agent/v1`）。它是结构化的机器接口，动作只计算一次，`md` / `html` 报告由它生成；`agent.actions[].verify.kind` 用三态（probe / human / collect）标明「哪些能自动复测、哪些需要人工确认、哪些缺少数据先停下」。完整接口定义见 SKILL.md「AI 闭环」一节。

## 可信度保证

判定语义不是靠模型自觉，而是由 `tests/` 下三道门禁强制锁定——任何回归都会让 CI 变红：

| 门禁 | 负责保证 |
| --- | --- |
| `confidence_gate.py` | 把每条判定规则的语义写成断言：置信度、判定优先级、采集状态区分、sitemap 结构差异、数据抖动不会误判为健康、移动端 / 历史存档 / 抽样 / 隐藏内容等边界、各探针超时路径 |
| `report_gate.py` | 报告用语清晰、结论表述直白、信息以表格清晰呈现、`md` 与 `JSON` 两份输出内容一致 |
| `fetch_retry_gate.py` | 抓取失败时按真实退避重试（而非仅检查代码字符串） |

门禁在每次 push / PR 的 CI 中自动跑；演进记录见 [CHANGELOG.md](CHANGELOG.md)。

## 仓库结构

| 文件 | 所属层 | 作用 |
|---|---|---|
| `SKILL.md` | 判断标准体系 | 使用说明：规则索引、规则优先级、输出结构、风险信号、判定规则全文 |
| `expert_claims.md` | 判断标准体系 | 134 条判定主张（每条标注来源推文 `#n`） |
| `corpus.json` | 判断标准体系（语料） | 134 条推文原文（`#n` 同序、日期、X 链接，可离线核验） |
| `scripts/audit_url.py` | 事实采集 | 纯标准库探针；运行后自动生成可读的 `md`/`html` 报告；支持 `--diff` 复测比对；抓取含 502/超时退避重试 |
| `tests/confidence_gate.py` | 防回归门禁 | 语义门禁 |
| `tests/report_gate.py` | 防回归门禁 | 报告质量门禁（用语清晰、结论直白、`md` 与 `JSON` 一致） |
| `tests/fetch_retry_gate.py` | 防回归门禁 | 抓取重试门禁 |
| `NOTICE.md` | 声明 | 语料归属、非官方声明、下架方式 |
| `LICENSE` | 声明 | MIT 许可证 |

---

## 语料与版权

- 收录的是 **@loki_yan_seo** 在 X 上**公开发布的推文原文**，目的是让每条判定规则可离线回源，不是转载传播。
- **134 条是筛选样本，不是全账号**：收录标准与不收录范围见 [NOTICE.md](NOTICE.md)。
- **原文版权归 @loki_yan_seo 所有**；MIT 仅覆盖本仓库的代码与文档结构，**不覆盖**推文原文。
- 有异议即下架：原作者或权利人在 issue 或 X（[@MagicQM](https://x.com/MagicQM)）提出，直接删，不问理由。

## License

MIT，见 [LICENSE](LICENSE)。推文原文不在 MIT 覆盖范围内，见 [NOTICE.md](NOTICE.md)。

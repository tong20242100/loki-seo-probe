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

## 和常见检测工具不一样

一般工具给你一堆分数和「待优化 127 项」，让你去修。这份诊断反过来：**先告诉你什么别做，再把结论与待办说清楚。**

- **不编数字。** 没有外链库就不写 DR，没有搜索量就不写「品牌词 800」。没抓到就写「无数据」，可信度写在结论前面。
- **把你当生意，不当网站。** 页面多、博客勤，它不会夸「内容丰富」——它会问：外人能不能一句话说清你是谁、成交发生在哪几页。
- **不替你发明关键词。** 每页只认一个外人会搜的词，空着让你填。说不清就写「这页说不出自己排什么」。
- **有一张「先停」清单。** 停改标题堆词、停追权重分数、停做「给 AI 看的作业包」、停用实验室分数冒充真实体验。成交页掉、博客涨，不等于站变好了。
- **分得清「它看见了」和「你得去后台看」。** 它只查公开页面；Search Console、整站扫描、处罚状态，一律甩给你，不把缺口包装成它的功劳。

适合已经有 Search Console / 整站扫描数据、需要有人拉住别乱做的人。不是新手油门，是给懂行的人用的刹车。

---

## 三分钟跑通

```bash
git clone https://github.com/tong20242100/loki-seo-probe.git
cd loki-seo-probe

# 1. 直接跑（零第三方依赖）
python3 scripts/audit_url.py https://example.com

# 2. 看报告
ls *_audit_report.*   # 同目录生成三件套
cat example.com_audit_report.md      # 给人看
cat example.com_audit_report.json | python3 -m json.tool | head -n 40  # 给机器/复测看
open example.com_audit_report.html   # 浏览器看表格版
```

真站示例（本仓库实测 `run_confidence=1.0`）：

```bash
python3 scripts/audit_url.py https://peercare.cn
# 产出 peercare.cn_audit_report.{json,md,html}
# peercare.cn: 444 页，75% 博客文章，verdict=needs-focus，无技术硬伤
```

> 生成物为探针本地产物，不入库（见 `.gitignore`：`*_audit_report.*`）。需要版本化请自行 `cp` 到别处。

---

## 你会得到什么

一次运行产出三件同源文件（文件名含域名）：

| 文件 | 给谁看 | 关键内容 |
|---|---|---|
| `*_audit_report.json` | 人 + 机器同源 | 完整数据与机器接口，含诊断与待办清单 |
| `*_audit_report.md` | 给人看 | 十节结构化报告（见下表），可直接贴给业务方 |
| `*_audit_report.html` | 给人看 | 同 `md` 的表格版，白底表格，适合转发 |

`md/html` 十节结构（固定顺序，空数据则整节不渲染）：

1. 现在的状态 2. 先做 3. 先停 4. 检测发现的问题 5. 每页要排哪个词 6. 哪些数据可信 7. 逐项核查结果 8. 需要你手动处理 9. 还需补充的数据 10. 最终决定权在你

`stdout` 同步打印 `json`（管道友好），`stderr` 提示落盘路径与 `status≠ok` 时的 `core_missing`。

---

## 报告怎么看

报告按结论→任务→核查→待办顺序展开，结构固定。字段含义与判定边界见 `SKILL.md`。

## 复测闭环

改一项、跑一次、对 diff：

```bash
# 第一次
python3 scripts/audit_url.py https://example.com  # 落盘 example.com_audit_report.json

# 改完站后再跑，对比
python3 scripts/audit_url.py https://example.com --diff example.com_audit_report.json
# 只打印 findings.rule/status + sitemap.n/prefixes 的变化
# na↔pass 抖动会标「可能是代理抖动，非真实修复」
```

`--diff` 仅对比关键字段，`na↔pass` 的抖动会标注，避免把网络抖动当成修复。

---

## 安装

**单机直接用（推荐先这样跑通）：** 零依赖，`git clone` 后 `python3 scripts/audit_url.py ...` 即可。

**装为 Agent Skill：** 放进任意支持 `SKILL.md` 的目录，目录名须与 `SKILL.md` frontmatter `name: loki-seo` 对齐：

```bash
git clone https://github.com/tong20242100/loki-seo-probe.git
cp -r loki-seo-probe ~/.workbuddy/skills/loki-seo   # ~/.claude/skills/、~/.grok/skills/ 同理
# 装到别处就用绝对路径跑探针：python3 /path/to/loki-seo/scripts/audit_url.py https://example.com
```

**依赖与网络：** Python 3 标准库即可；外网抓取走统一 `fetch()`，对 `502/503/504` 与网络超时自动退避重试 `3 次 1s→2s→4s`，站点真 `502` 如实报 `502`。可选 `pip install curl_cffi` 用真实浏览器 `TLS/JA3` 指纹（`impersonate=chrome`）绕过 `WAF/Cloudflare`，缺失自动回退 `urllib`，CI 默认走标准库。

---

## 三层结构

每层都能被程序验证，改坏即红：

| 层 | 文件 | 负责什么 |
|---|---|---|
| 🔬 判断标准体系 | `SKILL.md` + `expert_claims.md` + `corpus.json` | 134 条判定规则（判定条件/适用边界/反例/推文出处 `#n`），碰撞时按五档优先级取舍 |
| 🧭 事实采集 | `scripts/audit_url.py` | 零登录公开抓取：`robots/sitemap/llms.txt/软404/<main>/m站/Wayback/抽样原创度`，带可信度与降级状态机，自动落盘 `md/html` |
| 🚧 防回归门禁 | `tests/*_gate.py` | 三道门禁 + 形态检查，改坏即报错 |

---

## 可信度保证

三道门禁在 `CI` 每次 `push/PR` 自动跑，任一失败即阻断：

| 门禁 | 保证什么 |
|---|---|
| `confidence_gate.py` | 探针判定是否按规则执行，边界与超时是否正确处理 |
| `report_gate.py` | 报告与 `json` 是否同源一致，结论是否可直接使用 |
| `fetch_retry_gate.py` | 网络失败是否会重试，且真实错误不会被掩盖 |

演进见 `CHANGELOG.md`，完整规程见 `SKILL.md`。

---

## 仓库结构

| 文件 | 所属层 | 作用 |
|---|---|---|
| `SKILL.md` | 判断标准体系 | 判定规则与调用规程全文 |
| `expert_claims.md` | 判断标准体系 | 134 条主张表（`#n→tweet_id`） |
| `corpus.json` | 语料 | 134 条原文快照（同序、日期、`X` 链接，离线可核验） |
| `scripts/audit_url.py` | 事实采集 | 探针+渲染+`--diff`，`~1590 行`，含重试与隐身后端 |
| `tests/confidence_gate.py` | 门禁 | 语义门禁 `24 组 73 点` |
| `tests/report_gate.py` | 门禁 | 可读性+`agent↔md` 一致性 |
| `tests/fetch_retry_gate.py` | 门禁 | 重试行为 |
| `NOTICE.md` | 声明 | 语料归属/非官方/下架方式 |
| `LICENSE` | 声明 | MIT（不含推文原文） |

---

## 常见问题（只答工具，不答口径）

**报告落在哪？会污染仓库吗？** 同目录 `*_audit_report.{json,md,html}`，已在 `.gitignore`，不入库。需归档自行 `cp`。

**要什么环境？离线能跑吗？** `Python 3` 标准库即可，需联网抓目标站；`CI` 用 `3.13`，`import` 期不触网。

**抓取被 `WAF`/代理拦？** 先 `pip install curl_cffi` 再跑（`impersonate=chrome`），缺失自动回退 `urllib`；两路径在门禁均覆盖。仍失败看 `stderr` 的 `core_missing`。

**如何对比改动是否生效？** 用 `--diff`：`python3 scripts/audit_url.py https://example.com --diff prev.json`，只对 `findings/status` 与 `sitemap` 打 `diff`，`na↔pass` 抖动会标注。

**`md/html` 与 `json` 不一致？** 不应发生，若出现请提 `issue` 并附 `json`。

口径相关（`needs-focus/llms.txt/LinkedIn/partial` 含义）见 `SKILL.md`，不在此赘述。

---

## 语料与版权

- 收录的是 **@loki_yan_seo** 在 `X` 上**公开发布的推文原文**，为离线回源，非转载传播。
- **134 条是筛选样本，不是全账号**：标准与不收录范围见 `NOTICE.md`，窗口 `2026-02-11 ~ 2026-08-29`。
- **原文版权归 @loki_yan_seo 所有**；`MIT` 仅覆盖代码与文档结构，**不覆盖**推文原文。
- 有异议即下架：原作者或权利人在 `issue` 或 `X @MagicQM` 提出，直接删，不问理由。

## License

`MIT`，见 `LICENSE`。推文原文不在 `MIT` 覆盖范围内，见 `NOTICE.md`。

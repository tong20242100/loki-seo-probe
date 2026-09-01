# loki-seo-probe

> Loki Yan SEO 口径的可验证实现：探针（客观 HTTP 事实）＋ 研判（专家判定规则映射）＋ 语义门禁（回归即红）。
>
> **非官方蒸馏，无授权、无关联。** 本项目从 @loki_yan_seo 的公开推文蒸馏口径，未获本人授权或背书。语料是门禁切片（134 条 core×authored×strong），不是全账号；原文全文收录在 `corpus.json`（#n 与主张表同序，含 X 链接），可离线回源核对每条判定规则。原文版权归原作者所有。

这不是通用 SEO 手册。关键词密度、H1 塞目标词、外链建设、GEO 作业清单这类 commodity 建议，在本口径里是被明确顶回去的（见 SKILL.md「明确不进」）。

## 为什么不是又一份 prompt 合集

同类 skill（含市场里装机量最高的那批）普遍缺的不是知识，是**防编造的强制力**。本项目的差异在三层结构：

| 层 | 文件 | 作用 |
|---|---|---|
| 口径层 | `SKILL.md` + `expert_claims.md` | 134 条专家主张：判定规则、边界、反例、出处 tweet_id；碰撞表决定判定规则叠加顺序 |
| 探针层 | `scripts/audit_url.py` | 未登录 HTTP 事实采集：robots/sitemap/软404/`<main>`/m 站/Wayback，输出带置信度的 JSON。五值状态机 `na / seen / pass / warn / fail`：**没看到 ≠ 没问题** |
| 门禁层 | `tests/confidence_gate.py` | 24 组语义断言（含变异测试验证）：判定规则语义回归直接 exit 1，不靠模型阅读自觉。形态（函数 ≤40 行 / 嵌套 ≤3 / 纯 if ≤5）由作者仓库的 `shape_check.py` 管，**不随包发布**——它是本仓库的写作纪律；装技能的人要的是语义门禁 |

关键设计（都在门禁里钉着，回退必红）：

- **降级状态机**：首页 502 但 robots 可读时是 `partial` + exit 0——可用的降级诊断不整份丢弃；`verdict` 在 partial 且无 fail/warn 时输出 `insufficient`，不让「healthy」字面值骗下游。
- **网络抖动不翻结论**：探针超时（status=0）/5xx 一律 `na`（没看到），不落 warn——站点没变，抖动不该把结论从 pass 翻成 at-risk。唯一例外：robots 是下跌场景第一探针，非 200 一律 `warn`（门禁刻意钉死）。
- **禁编清单**：GSC Field CWV、DR/外链、品牌搜索量——探针核不到的项在 JSON 里显式挡（`cannot[]`），报告里只能标「无数据」。
- **`seen` 值**：title/h1 文案、JSON-LD 类型这类「材料已给但不自动打分」的事实，与「没看到」严格分开，判断权归输出合同。

## 安装

放进任何支持 SKILL.md 约定的 agent skills 目录（以 `.grok/skills/` 为例）：

```bash
git clone https://github.com/<你>/loki-seo-probe.git
cp -r loki-seo-probe ~/.grok/skills/loki-seo
```

依赖：Python 3 标准库，无第三方包。

## 使用

```bash
python3 scripts/audit_url.py https://example.com   # 输出探针 JSON
python3 tests/confidence_gate.py                   # 语义门禁，应全绿
```

agent 按 SKILL.md 的输出合同（任务类型 / 探针事实 / 先做先停 / 一页一词表 / 证据等级 / 下一步搜集）出报告。人肉使用也成立：跑探针，对着 JSON 里的 `status` / `run_confidence` / `diagnosis` 读。

## 验证声明

- `tests/confidence_gate.py`：24 组门禁全绿、73 个静态断言点（P0 置信度语义 / P1 研判排序 / P4 seen-na 拆分 / P7 sitemap 变体 / P8 发现层 / P9 抖动与假 healthy / P10 m-host 双义、Wayback 倒序、抽样活样本分母、display:none 与 robots 双条覆盖 / P11 robots 幽灵块、sitemap body 复用、NXDOMAIN 进置信、sitemap 超时走 na）。
- 变异测试：11 个变异（含 3 个诱导性变异：源码诱饵行、只 patch 被测函数、等价变异）逐个回退，10 个 CAUGHT；剩下 1 个是等价变异（`True`/`None` 在唯一调用点同归 `na`，行为无差别）。复原后 byte-identical 复绿。P11 又补 5 个变异（幽灵块 / body 二抓 / NXDOMAIN 置信 / sitemap 超时 warn / mix 只认 lost），逐个回退全 CAUGHT，复原 byte-identical 复绿。
- 实测：peercare.cn（本机出口链路间歇超时，探针 TIMEOUT=20s，序列中任一请求都可能撞上）下，`partial` 降级路径与 `insufficient` verdict 均按设计落盘。
- 发布前二轮实测另抓出三项并已修：Wayback `last200` 取到最早第 3 条（假数据，比真实最新早 10 个月）、m-host 靠 urllib 错误文本判 NXDOMAIN 致同一站点事实随代理环境出两种结论、抽样分母把死样本计入。详见 CHANGELOG 1.0.1。
- 发布前三轮重测又抓出四项并已修：robots 解析器幽灵空 * 块、well_known 已 200 的 sitemap 被 `sitemap_mix` 二抓（双次 fetch 撞抖动）、NXDOMAIN 判定层认而置信层不认、sitemap 探针超时装扮成「站点没有 sitemap」。详见 CHANGELOG 1.0.1。
- 门禁自身也被实测纠过两次错：只查源码字符串的断言会被**诱饵行**骗过；只 patch **被测函数自身**的断言会让该实现一行都跑不到。两条均已改为断言行为（断言实际发出的请求 URL / 只 patch 下一层）。

## 仓库结构

```
SKILL.md                    调用规程：路由表、碰撞表、输出合同、风险信号、判定规则全文
expert_claims.md            134 条主张表（含 #n → tweet_id 映射）
corpus.json                 134 条推文原文（#n 同序、日期、X 链接，可离线核验）
scripts/audit_url.py        探针（700 行，纯标准库）
tests/confidence_gate.py    语义门禁（692 行，compile 源码，绕过 pyc 缓存）
```

## License

MIT

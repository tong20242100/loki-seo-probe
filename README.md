# loki-seo-probe

> Loki Yan SEO 口径的可验证实现：探针（客观 HTTP 事实）＋ 研判（专家口诀映射）＋ 语义门禁（回归即红）。
>
> **非官方蒸馏，无授权、无关联。** 本项目从 @loki_yan_seo 的公开推文蒸馏口径，未获本人授权或背书。语料是门禁切片（134 条 core×authored×strong），不是全账号；每条口诀可按 `expert_claims.md` 文末的 tweet_id 回 X 核对原文。

这不是通用 SEO 手册。关键词密度、H1 塞目标词、外链建设、GEO 作业清单这类 commodity 建议，在本口径里是被明确顶回去的（见 SKILL.md「明确不进」）。

## 为什么不是又一份 prompt 合集

同类 skill（含市场里装机量最高的那批）普遍缺的不是知识，是**防编造的强制力**。本项目的差异在三层结构：

| 层 | 文件 | 作用 |
|---|---|---|
| 口径层 | `SKILL.md` + `expert_claims.md` | 134 条专家主张：口诀、边界、反例、出处 tweet_id；碰撞表决定口诀叠加顺序 |
| 探针层 | `scripts/audit_url.py` | 未登录 HTTP 事实采集：robots/sitemap/软404/`<main>`/m 站/Wayback，输出带置信度的 JSON。五值状态机 `na / seen / pass / warn / fail`：**没看到 ≠ 没问题** |
| 门禁层 | `tests/confidence_gate.py` | P0–P9 十组语义断言（含变异测试验证）：口诀语义回归直接 exit 1，不靠模型阅读自觉 |

关键设计（都在门禁里钉着，回退必红）：

- **降级状态机**：首页 502 但 robots 可读时是 `partial` + exit 0——可用的降级诊断不整份丢弃；`verdict` 在 partial 且无 fail/warn 时输出 `insufficient`，不让「healthy」字面值骗下游。
- **网络抖动不翻结论**：探针超时（status=0）/5xx 一律 `na`（没看到），不落 warn——站点没变，抖动不该把结论从 pass 翻成 at-risk。
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

- `tests/confidence_gate.py`：P0–P9 十组门禁全绿（P0 置信度语义 / P1 研判排序 / P4 seen-na 拆分 / P7 sitemap 变体 / P8 发现层 / P9 抖动与假 healthy），32 个静态断言点。
- 变异测试：逐个回退 P9 两处修复，门禁分别 CAUGHT；复原后 byte-identical 复绿。
- 实测：peercare.cn（本机到该服务器链路间歇超时 30–45s 的恶劣环境）下，`partial` 降级路径与 `insufficient` verdict 均按设计落盘。

## 仓库结构

```
SKILL.md                    调用规程：路由表、碰撞表、输出合同、红旗、口诀全文
expert_claims.md            134 条主张表（含 #n → tweet_id 映射，可回 X 核对）
scripts/audit_url.py        探针（592 行，纯标准库）
tests/confidence_gate.py    语义门禁（compile 源码，绕过 pyc 缓存）
```

## License

MIT

# Changelog

## 1.0.0 — 2026-09-01

首发。

- 口径层：SKILL.md（路由表 / 碰撞表 / 输出合同 / 风险信号 RF01–RF28 / 判定规则 1.x–7.x）+ expert_claims.md 134 条主张（窗口 2026-02-11 ~ 2026-08-29，dump 2025-07-11 起，门禁切片非全账号）。
- 探针层：audit_url.py——robots/sitemap（三路径变体）/软404/`<main>`/m 站/Wayback/抽样原创度；五值状态机 na/seen/pass/warn/fail；降级状态机 partial/inconclusive + run_confidence + core_missing。
- 门禁层：confidence_gate.py P0–P9（十组、32 个静态断言点）。P9 为本日补钉：探针网络失败(0/5xx)→na 不再抬 at-risk；partial 无 fail/warn → verdict=insufficient 不再字面 healthy。两项均经变异测试验证（回退必红、复原复绿）。
- 文档：expert_claims 语料边界声明、SKILL.md 发稿前自查（编造/进口/升格/传记/GEO 幻觉五查）、RF18 复核钉死（#125 在库、G7 判常识，不采用是审过非漏采）、附录B 风险信号清单自正文判定规则反推（不引外部来源）。
- 新增 corpus.json：134 条推文原文（#n 与索引表同序、full_text、日期、X 链接），回源核验不再依赖 X 平台可用性；README/SKILL.md/expert_claims.md 同步指向。

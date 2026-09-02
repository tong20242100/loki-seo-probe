#!/usr/bin/env bash
# 发布辅助脚本：把本仓库推到 GitHub，触发 .github/workflows/gate.yml 三道门禁。
# 本机无认证 gh、仓库默认无 remote，故需你本地已配置 SSH key（或已登录 gh）且
# GitHub 上已建好 tong20242100/loki-seo-probe 空仓库。脚本只做 remote 补全 + push，不改任何代码。
set -euo pipefail

REMOTE="git@github.com:tong20242100/loki-seo-probe.git"
BRANCH="main"

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "→ 本地无 origin，添加 remote: $REMOTE"
  git remote add origin "$REMOTE"
else
  echo "→ 已存在 origin: $(git remote get-url origin)"
fi

echo "→ 推送到 origin/$BRANCH"
git push -u origin "$BRANCH"

echo "完成。CI 将在 https://github.com/tong20242100/loki-seo-probe/actions 跑三道门禁（confidence / report / fetch-retry）。"

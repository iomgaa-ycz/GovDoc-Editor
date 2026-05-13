---
type: plan
node_id: plan:cicd-secrets
title: "CI/CD 密钥管理计划"
date: 2026-05-13
migrated_from: docs/superpowers/plans/2026-04-21-cicd-secrets.md
tags: ["migrated"]
---

# CI/CD 密钥管理：GitHub Secrets 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CI workflow 从 GitHub Secrets 动态生成 `.env.runtime`，彻底消除对服务器预置文件的依赖。

**Architecture:** workflow 新增一步将 `${{ secrets.* }}` 写入 `deploy/.env.runtime`，deploy.sh 恢复简单的文件存在检查。非敏感变量（NO_PROXY 等）硬编码在 workflow 中，敏感变量从 secrets 注入。

**Tech Stack:** GitHub Actions secrets, bash

---

## 文件变更概览

| 文件 | 操作 | 说明 |
|------|------|------|
| `.github/workflows/deploy.yml` | MODIFY | 添加生成 `.env.runtime` 的步骤 |
| `deploy/deploy.sh` | MODIFY | 移除 symlink hack，恢复简单检查 |

---

### Task 1: 修改 workflow 从 secrets 生成 .env.runtime

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: 替换 `.github/workflows/deploy.yml` 全部内容**

```yaml
name: Deploy

on:
  push:
    branches: [master]
    tags: ['v*']

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: self-hosted
    timeout-minutes: 15
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: 确定部署环境
        id: env
        run: |
          if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
            echo "target=stable" >> "$GITHUB_OUTPUT"
            echo ">>> 部署目标: 稳定版 (tag: $GITHUB_REF_NAME)"
          else
            echo "target=testing" >> "$GITHUB_OUTPUT"
            echo ">>> 部署目标: 测试版 (commit: ${GITHUB_SHA::8})"
          fi

      - name: 生成 .env.runtime
        run: |
          cat > deploy/.env.runtime <<'ENVEOF'
          ANTHROPIC_BASE_URL=${{ secrets.ANTHROPIC_BASE_URL }}
          ANTHROPIC_AUTH_TOKEN=${{ secrets.ANTHROPIC_AUTH_TOKEN }}
          NO_PROXY=110.42.53.85
          no_proxy=110.42.53.85
          SCRIVAI_DEFAULT_MODEL=glm-5.1
          SCRIVAI_DEFAULT_PROVIDER=glm
          LOCAL_RANK=2
          ENVEOF
          sed -i 's/^          //' deploy/.env.runtime

      - name: 执行部署
        run: bash deploy/deploy.sh ${{ steps.env.outputs.target }}

      - name: 健康检查
        run: |
          if [ "${{ steps.env.outputs.target }}" = "stable" ]; then
            PORT=8000
          else
            PORT=8001
          fi
          echo ">>> 检查 http://localhost:${PORT}/healthz ..."
          for i in $(seq 1 10); do
            if curl -sf "http://localhost:${PORT}/healthz" > /dev/null 2>&1; then
              echo ">>> 健康检查通过"
              exit 0
            fi
            echo "    等待后端启动... ($i/10)"
            sleep 3
          done
          echo ">>> 健康检查失败"
          exit 1

      - name: 清理 .env.runtime
        if: always()
        run: rm -f deploy/.env.runtime
```

关键点：
- `生成 .env.runtime` 步骤：从 GitHub Secrets 注入敏感变量，非敏感变量（NO_PROXY 等）硬编码
- heredoc 使用 `'ENVEOF'`（单引号）防止 shell 展开 `${{ }}` 之外的变量
- `sed -i 's/^          //'` 去掉 YAML 缩进导致的行首空格
- `清理 .env.runtime` 步骤：`if: always()` 确保即使部署失败也会清理密钥文件

- [ ] **Step 2: 验证 YAML 语法**

Run: `conda run -n govdoc-auditor-v3 python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml')); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: 提交**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: workflow 从 GitHub Secrets 生成 .env.runtime"
```

---

### Task 2: deploy.sh 恢复简单检查

**Files:**
- Modify: `deploy/deploy.sh`

- [ ] **Step 1: 替换 `deploy/deploy.sh` 全部内容**

```bash
#!/bin/bash
set -euo pipefail

TARGET=${1:?用法: deploy.sh <stable|testing>}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env.${TARGET}"
[ -f "$ENV_FILE" ] || { echo "错误: 找不到 $ENV_FILE"; exit 1; }
[ -f ".env.runtime" ] || { echo "错误: 找不到 .env.runtime（CI 应由 workflow 生成，本地请从 .env.runtime.example 复制）"; exit 1; }

echo ">>> [$(date '+%Y-%m-%d %H:%M:%S')] 开始部署 ${TARGET} 环境..."

echo ">>> 构建镜像..."
docker compose --env-file "$ENV_FILE" build

echo ">>> 启动容器..."
docker compose --env-file "$ENV_FILE" up -d --force-recreate

echo ">>> 清理旧镜像..."
docker image prune -f

echo ">>> [$(date '+%Y-%m-%d %H:%M:%S')] ${TARGET} 部署完成"

# 输出访问信息
source "$ENV_FILE"
echo "    后端: http://localhost:${BACKEND_PORT}/docs"
echo "    前端: http://localhost:${FRONTEND_PORT}"
```

变更：移除第 10-22 行的 symlink hack，恢复为一行简单检查。错误信息明确区分 CI 和本地两种场景。

- [ ] **Step 2: 验证脚本语法**

Run: `bash -n deploy/deploy.sh && echo "syntax ok"`
Expected: `syntax ok`

- [ ] **Step 3: 提交并推送**

```bash
git add deploy/deploy.sh
git commit -m "fix: deploy.sh 移除 symlink hack，恢复简单密钥文件检查"
git push origin master
```

推送后 GitHub Actions 会自动触发新一轮 CI（前提：GitHub Secrets 已配置）。

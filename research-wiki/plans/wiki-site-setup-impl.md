---
type: plan
node_id: plan:wiki-site-setup-impl
title: "Wiki-Site 渲染站点搭建实施计划"
date: 2026-05-13
---

# Wiki-Site 渲染站点搭建实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从模板项目完整复制 wiki-site 基础设施到 GovDoc-Auditor，仅修改端口（8687）和项目名称，使 research-wiki/ 中的实体可通过浏览器查阅。

**Architecture:** 两个目录：`tools/wiki-site/`（React 前端 + prompts）和 `tools/wiki_site/`（Python daemon）。daemon 用 watchdog 监控 wiki 变更，构建 manifest.json，启动 Vite dev server。LLM 渲染由 render-wiki-page skill 负责。

**Tech Stack:** Vite + React 19 + shadcn/ui + Tailwind CSS 4 + D3（前端）；watchdog + PyYAML（Python daemon）

---

## 文件结构

### 新增目录/文件

```
tools/
├── __init__.py                          # 空文件，使 tools 成为 Python 包
├── wiki-site/                           # React 前端 + prompts + 配置
│   ├── app/                             # Vite + React 应用
│   │   ├── index.html
│   │   ├── package.json
│   │   ├── package-lock.json
│   │   ├── vite.config.ts               # 端口 8687
│   │   ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
│   │   ├── eslint.config.js
│   │   ├── components.json
│   │   ├── .gitignore
│   │   ├── public/
│   │   │   ├── favicon.svg
│   │   │   ├── icons.svg
│   │   │   └── sql-wasm.wasm
│   │   └── src/
│   │       ├── main.tsx / App.tsx / index.css
│   │       ├── components/ (Sidebar, Dashboard, EntityLoader, KnowledgeGraph, DatabaseBrowser, TableDetail, ui/*)
│   │       ├── data/ (manifest.json, edges.json — 运行时生成)
│   │       ├── lib/ (config.ts, db.ts, utils.ts)
│   │       └── pages/ (LLM 渲染生成，初始为空)
│   ├── prompts/
│   │   ├── system.md
│   │   └── types/ (11 个实体类型 prompt)
│   ├── wiki-site.config.yaml
│   └── start-wiki-site.sh
└── wiki_site/                           # Python daemon 模块
    ├── __init__.py
    ├── renderer.py
    ├── manifest.py
    ├── _wiki_helpers.py
    └── wiki_site_config.py
```

### 修改的现有文件

| 文件 | 修改内容 |
|------|----------|
| `.claude/skills/render-wiki-page/SKILL.md` | 端口 8686 → 8687 |
| `.gitignore` | 添加 `.wiki-site/`、`tools/wiki-site/app/node_modules/`、`tools/wiki-site/app/src/pages/` |

---

### Task 1: 复制 React 前端应用

**Files:**
- Create: `tools/wiki-site/` (整个目录从模板复制)

- [ ] **Step 1: 复制 tools/wiki-site/ 目录**

```bash
cp -r /home/iomgaa/Projects/claude-project-template/tools/wiki-site/ tools/wiki-site/
```

- [ ] **Step 2: 删除模板的示例页面和缓存**

```bash
rm -rf tools/wiki-site/app/src/pages/designs/
rm -rf tools/wiki-site/app/src/pages/papers/
rm -rf tools/wiki-site/app/src/pages/plans/
rm -rf tools/wiki-site/app/.pytest_cache/
rm -f tools/wiki-site/app/public/harness.db
rm -f tools/wiki-site/app/README.md
```

- [ ] **Step 3: 修改 wiki-site.config.yaml**

将 `tools/wiki-site/wiki-site.config.yaml` 内容改为：

```yaml
project_name: "GovDoc Research Wiki"
primary_color: "#4c6ef5"
port: 8687
model: "claude-opus-4-6"
temperature: 0
debounce_seconds: 2
auto_shutdown_minutes: 30
max_retries_on_compile_error: 1
```

- [ ] **Step 4: 修改 vite.config.ts 端口**

将 `tools/wiki-site/app/vite.config.ts` 第 14 行 `port: 8686` → `port: 8687`。

- [ ] **Step 5: 修改 start-wiki-site.sh 端口提示**

将 `tools/wiki-site/start-wiki-site.sh` 最后一行 `http://localhost:8686` → `http://localhost:8687`。

- [ ] **Step 6: 重置 data 目录为空占位**

```bash
echo '[]' > tools/wiki-site/app/src/data/manifest.json
echo '{"nodes":[],"links":[]}' > tools/wiki-site/app/src/data/edges.json
```

- [ ] **Step 7: 确保 pages 目录存在但为空**

```bash
mkdir -p tools/wiki-site/app/src/pages
```

---

### Task 2: 复制 Python daemon 模块

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/wiki_site/__init__.py`
- Create: `tools/wiki_site/renderer.py`
- Create: `tools/wiki_site/manifest.py`
- Create: `tools/wiki_site/_wiki_helpers.py`
- Create: `tools/wiki_site/wiki_site_config.py`

- [ ] **Step 1: 创建 tools 包并复制模块**

```bash
mkdir -p tools/wiki_site
touch tools/__init__.py
cp /home/iomgaa/Projects/claude-project-template/tools/wiki_site/__init__.py tools/wiki_site/
cp /home/iomgaa/Projects/claude-project-template/tools/wiki_site/renderer.py tools/wiki_site/
cp /home/iomgaa/Projects/claude-project-template/tools/wiki_site/manifest.py tools/wiki_site/
cp /home/iomgaa/Projects/claude-project-template/tools/wiki_site/_wiki_helpers.py tools/wiki_site/
cp /home/iomgaa/Projects/claude-project-template/tools/wiki_site/wiki_site_config.py tools/wiki_site/
```

- [ ] **Step 2: 验证 Python 模块可导入**

```bash
conda run -n govdoc-auditor-v3 python -c "from tools.wiki_site.manifest import build_manifest; print('OK')"
```

Expected: `OK`

---

### Task 3: 安装 Python 依赖

- [ ] **Step 1: 安装 watchdog 和 pyyaml**

```bash
conda run -n govdoc-auditor-v3 pip install watchdog pyyaml
```

- [ ] **Step 2: 验证全链路导入**

```bash
conda run -n govdoc-auditor-v3 python -c "from tools.wiki_site.renderer import serve; print('renderer OK')"
```

Expected: `renderer OK`

---

### Task 4: 更新 .gitignore 和 render-wiki-page skill

**Files:**
- Modify: `.gitignore`
- Modify: `.claude/skills/render-wiki-page/SKILL.md`

- [ ] **Step 1: 追加 .gitignore 条目**

在 `.gitignore` 末尾追加：

```gitignore
# Wiki-Site
.wiki-site/
tools/wiki-site/app/node_modules/
tools/wiki-site/app/src/pages/
tools/wiki-site/app/public/harness.db
```

- [ ] **Step 2: 更新 render-wiki-page skill 端口**

将 `.claude/skills/render-wiki-page/SKILL.md` 第 71 行 `http://localhost:8686` → `http://localhost:8687`。

---

### Task 5: 安装前端依赖并验证启动

- [ ] **Step 1: 安装 npm 依赖**

```bash
cd tools/wiki-site/app && npm install && cd -
```

Expected: 无报错，生成 `node_modules/`

- [ ] **Step 2: 启动 daemon 并验证**

```bash
conda run -n govdoc-auditor-v3 python -m tools.wiki_site.renderer research-wiki &
DAEMON_PID=$!
sleep 5
```

Expected: 输出 `Wiki-Site 已启动: http://localhost:8687`

- [ ] **Step 3: 验证 manifest.json 已生成**

```bash
cat tools/wiki-site/app/src/data/manifest.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} entities')"
```

Expected: `13 entities`

- [ ] **Step 4: 验证 Vite dev server 可访问**

```bash
curl -s http://localhost:8687 | head -5
```

Expected: 返回 `<!doctype html>` 开头的 HTML

- [ ] **Step 5: 停止 daemon 并清理**

```bash
kill $DAEMON_PID 2>/dev/null
rm -f .wiki-site/.pid
```

---

### Task 6: 提交

- [ ] **Step 1: 暂存变更**

```bash
git add tools/ .gitignore .claude/skills/render-wiki-page/SKILL.md research-wiki/
```

- [ ] **Step 2: 提交**

```bash
git commit -m "feat: 从模板搭建 wiki-site 渲染站点（端口 8687）"
```

---

## 验收标准

| # | 标准 | 验证方式 |
|---|------|----------|
| 1 | `start-wiki-site.sh` 正常启动 | 运行脚本，检查 PID 文件和输出 |
| 2 | Dashboard 显示实体统计 + 知识图谱 | 浏览器访问 `http://localhost:8687` |
| 3 | Sidebar 列出 13 个实体 | 浏览器检查左侧导航 |
| 4 | 实体页面显示 EmptyState | 点击任意实体 |
| 5 | daemon 超时自动退出 | 检查 `auto_shutdown_minutes: 30` 配置 |
| 6 | `/render-wiki-page` 可渲染实体 | 手动触发 skill 渲染一个实体 |

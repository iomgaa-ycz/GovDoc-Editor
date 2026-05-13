---
type: design
node_id: design:wiki-site-setup
title: "Wiki-Site 渲染站点搭建"
date: 2026-05-13
status: approved
---

# Wiki-Site 渲染站点搭建

## 概述

为 GovDoc-Auditor 项目搭建 research-wiki 可视化站点，将 `research-wiki/` 中的 Markdown 实体渲染为可浏览的 HTML 网站。

**方案**：从模板项目 `/home/iomgaa/Projects/claude-project-template/tools/wiki-site/` 完整复制，仅调整 2 处配置。

## 与模板的差异

| 配置项 | 模板值 | GovDoc 值 |
|--------|--------|-----------|
| `project_name` | "Research Wiki" | "GovDoc Research Wiki" |
| `port` | 8686 | 8687 |

其余所有代码、组件、prompt、daemon 逻辑 100% 保持一致。

## 架构

```
research-wiki/*.md
    ↓ watchdog (2s debounce)
renderer.py → manifest.json + render-queue.json
    ↓
render-wiki-page skill (LLM → .tsx)
    ↓
tools/wiki-site/app/src/pages/<type>/<id>.tsx
    ↓ Vite HMR
浏览器 http://localhost:8687
```

## 包含的功能

| 功能 | 说明 |
|------|------|
| Dashboard | 实体统计 + 知识图谱（D3 force） |
| Sidebar 导航 | 按实体类型分组，颜色标识 |
| 实体页面 | LLM 渲染的 React + shadcn/ui 页面 |
| Database Browser | SQL.js 查询 harness.db（harness 就绪后可用） |
| 文件监控 | watchdog daemon 自动检测变更 |
| 自动关闭 | 30 分钟无活动后 daemon 自动退出 |

## 实体类型映射

| 类型 | 目录 | 颜色 |
|------|------|------|
| paper | papers/ | #4a6cf0 |
| plan | plans/ | #7a3ad4 |
| design | designs/ | #0d9dd8 |
| idea | ideas/ | #059bb8 |
| finding | findings/ | #5f62e0 |
| review | reviews/ | #8558d6 |
| claim | claims/ | #3a7ee0 |
| gap | gaps/ | #607080 |
| experiment | experiments/ | #0888a8 |
| schema | schemas/ | #6826c8 |
| metric | metrics/ | #2460d8 |

## 启动方式

```bash
./tools/wiki-site/start-wiki-site.sh
# → http://localhost:8687
```

## 否决的替代方案

| 方案 | 否决原因 |
|------|----------|
| 裁剪 DB Browser | 项目有 harness 基础设施，保留更合理 |
| 从零搭建 | 工作量 10 倍以上，且模板已生产验证 |
| 改端口以外的更多配置 | 无必要，保持与模板一致降低维护成本 |

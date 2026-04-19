# GovDoc Auditor V3

招标文书自动审查系统。输入招标文书 + 法律指引，输出包含逐条发现、严重程度、证据回溯、法条引用的**审查工作底稿（docx）**。

## 三层架构

```
GovDoc-Auditor（业务 Web app）
        │ import scrivai
        ▼
Scrivai（通用 Claude Agent 编排框架）
        │ import qmd
        ▼
qmd-py（混合检索引擎：SQLite + sqlite-vec + FTS5 + RRF + Reranker）
```

依赖方向恒定朝下，上层不知道下层之外的存在。

## 开发环境

```bash
cd /home/undergraduate/lhz/work/GovDoc_AuditorV3
conda activate govdoc-auditor-v3
pip install -e ./vendor/scrivai-src
pip install -e .
```

- **qmd-0.1.2**：自研 pypi 库，面向 Markdown 的本地混合检索引擎，不可修改
- **scrivai-0.1.3**：基于 Claude Agent SDK 的通用 agent 编排框架，仍在迭代中

## 启动

```bash
# 1. 安装依赖（首次）
conda activate govdoc-auditor-v3
pip install -e ./vendor/scrivai-src
pip install -e .
cd frontend && npm install && cd ..

# 2. 启动后端
uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000

# 3. 启动前端（新终端）
cd frontend && npx vite --host 0.0.0.0 --port 5173
```

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000/docs

## 文档

- `AGENTS.md` — Claude Code Agent 规约
- `工程md/GOVDOC_OVERVIEW(1).md` — 三项目速读（10-15 分钟人类版）
- `工程md/GovDoc-Auditor/` — GovDoc-Auditor 设计与任务文档
- `工程md/qmd/` — qmd 设计与任务文档
- `工程md/scrivai/` — Scrivai 设计与任务文档

## 核心概念

| 概念 | 说明 |
|---|---|
| **PES** | Plan-Execute-Summarize 三阶段编排；阶段间通过文件（plan.json / findings/ / output.json）交换状态 |
| **Workspace** | 一次 agent 运行的独立沙箱目录；含 skills 快照、data 快照、output、logs、meta.json |
| **Skill** | Claude Code 能力单元（SKILL.md），指导 agent 做某类事 |
| **Library** | Scrivai 对 qmd 的封装；固定 collection 名 rules / cases / templates |
| **EvoSkill** | 基于 trajectory 迭代 skill 的进化机制；至少 2 类指标同向提升才 promote |

## 设计守则

- 唯一架构基线：`docs/design.md`
- 唯一任务基线：`docs/TD.md`
- 业务代码只允许 `from scrivai import ...` 和 `from govdoc.schemas import ...`
- 禁止 `import qmd`、禁止 `qmd.connect(...)`、禁止 `import claude_agent_sdk`
- `V2` 只能作为 donor/reference，不得把 `V2` 的 JSON blob store、`ReviewProject` 体系或 HTML-only workpaper 直接搬入 `V3`

## 当前初始化状态

当前仓库已按 design 搭起以下骨架：

- `govdoc/api/`
- `govdoc/pipelines/`
- `govdoc/schemas/`
- `govdoc/parsers/`
- `govdoc/templates/`
- `govdoc/cli/`
- `govdoc/db/`
- `govdoc/storage/`
- `agents/`
- `skills/`
- `tests/unit|contract|integration|fixtures`

其中：

- runtime / schema / SQLModel / Alembic 骨架已就位
- parser / CLI 最小能力已实现
- API 仍是 design 对齐骨架
- pipelines 已补齐 MockPES 回放闭环，可写入 DB 并渲染测试用 docx
- `workpaper.docx` 正式模板需按 design 用 Word/LibreOffice 手工制作


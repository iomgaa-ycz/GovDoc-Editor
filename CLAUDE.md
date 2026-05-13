# CLAUDE.md

> [!URGENT]
> **工程性项目 (Engineering Project)**
> 1. 本项目为 MVP（最小可行性产品），严禁过度工程化。
> 2. 你的所有思考过程和回复必须使用 **简体中文**。

## 1. 项目元数据 (Metadata)

- **核心目标**: 招标文书自动审查系统。输入招标文书 + 法律/指引，输出包含逐条发现、严重程度、证据回溯、法条引用的**审查工作底稿（docx）**。
- **项目类型**: MVP / 工程性项目（业务 web app）
- **架构层级**: 三层依赖链，方向恒定朝下
  ```
  GovDoc-Auditor（业务 web app，本项目）
        │ import scrivai
        ▼
  Scrivai（通用 Claude Agent 编排框架，vendored）
        │ import qmd
        ▼
  qmd-py（混合检索引擎：SQLite + sqlite-vec + FTS5 + RRF + Reranker）
  ```
- **后端**: Python 3.11 / FastAPI / SQLModel / SQLite / docxtpl / Pydantic v2 / Alembic
- **前端**: Vite + React + TypeScript（MVP 可用 Swagger UI 替代）
- **版本管理**: Git（当前分支 `master`，开发分支约定 `feat/v3-p0-cleanup`）
- **Conda 环境**: `govdoc-auditor-v3` (Python 3.11)
- **LLM 后端**: 默认 glm-5.1（经私有网关 `http://110.42.53.85:11098`），经 Claude Agent SDK 走标准 `ANTHROPIC_*` env 自动识别

## 2. 常用命令 (Commands)

### 2.1 Conda 环境管理

> [!CRITICAL]
> **所有 Python 相关命令必须在 govdoc-auditor-v3 环境中执行**
> - 使用 `conda run -n govdoc-auditor-v3 <command>` 确保命令在正确环境中运行
> - 或在命令前显式添加 `source activate govdoc-auditor-v3 &&`
> - 敏感信息（API Key）放 `.env`，不提交 git
> - **涉及 LLM / 本地 API 调用时必须设置 NO_PROXY**（本机有 HTTP 代理 `127.0.0.1:7892`）：
>   ```bash
>   export no_proxy="localhost,127.0.0.1,${no_proxy:-}"
>   export NO_PROXY="localhost,127.0.0.1,${NO_PROXY:-}"
>   ```

```bash
# 激活项目环境（交互式 shell）
conda activate govdoc-auditor-v3

# 推荐：使用 conda run 执行命令（自动使用正确环境）
conda run -n govdoc-auditor-v3 pip install xxx
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/ -v
# 注意：不能 `conda run -n govdoc-auditor-v3 pytest`，这样不会调用环境内的 pytest
```

### 2.2 安装依赖（首次）

```bash
conda activate govdoc-auditor-v3
pip install -e ./vendor/scrivai-src    # 若本地有 vendored 源码
pip install -e .
cd frontend && npm install && cd ..
```

- **qmd-0.1.2**：自研 pypi 库，**不可修改**（如需改动先走 `工程md/INTEGRATION_ISSUES.md` 登记）
- **scrivai-0.1.x**：基于 Claude Agent SDK 的通用 agent 编排框架，vendored + editable

### 2.2.1 Worktree 软链接（未跟踪大文件）

> [!CRITICAL]
> 以下目录**未纳入 git 跟踪**（体积大 / 敏感数据），但测试和运行时依赖它们。
> **新建 worktree 后必须创建软链接**，否则测试会因缺文件而失败。

```bash
# 在 worktree 根目录执行（PROJECT_ROOT 为主仓库路径）
ln -s "$PROJECT_ROOT/real_data" real_data
ln -s "$PROJECT_ROOT/.env" .env
ln -s "$PROJECT_ROOT/data" data
ln -sf "$PROJECT_ROOT/.claude/skills" .claude/skills
```

| 目录/文件 | 大小 | 用途 | 依赖方 |
|-----------|------|------|--------|
| `real_data/` | ~171MB | 真实招标文书、审查点表格等测试数据 | `tests/unit/test_checkpoint_import.py`、`tests/e2e/conftest.py` |
| `.env` | <1KB | API Key 等敏感配置 | `govdoc/config.py` |
| `data/` | ~数MB | SQLite 数据库 + 文件存储 | `govdoc/db/session.py`、`govdoc/storage/` |
| `.claude/skills/` | <1MB | Claude Code skill 定义（harness-eval 等） | `/harness-eval`、`/brainstorming` 等 skill 调用 |

### 2.3 启动服务

```bash
# 后端（FastAPI）
conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000

# 前端（新终端，Vite 开发服务器）
cd frontend && npx vite --host 0.0.0.0 --port 5173
```

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000/docs（Swagger UI，MVP 可直接作为"前端"使用）

### 2.3.1 访问部署环境（4090-server）

部署目标为 4090-server (`yuchengzhang@100.83.164.94`)，通过 Tailscale 组网。

> [!IMPORTANT]
> 本地开发机需设置 **无代理** 才能直连 4090-server 的 HTTP 端口：
> ```bash
> export NO_PROXY=100.83.164.94
> export no_proxy=100.83.164.94
> ```
> 或在 curl/httpx 命令前添加：`NO_PROXY=100.83.164.94`

| 环境 | 后端 | 前端 | 用途 |
|------|------|------|------|
| testing | `http://100.83.164.94:8001/docs` | `http://100.83.164.94:5174` | master 分支自动部署 |
| stable | `http://100.83.164.94:8000/docs` | `http://100.83.164.94:5175` | tag `v*` 手动发布 |

### 2.4 数据库迁移（Alembic）

```bash
# 创建新迁移
conda run -n govdoc-auditor-v3 alembic revision --autogenerate -m "<msg>"

# 应用迁移
conda run -n govdoc-auditor-v3 alembic upgrade head
```

迁移脚本位于 `govdoc/db/migrations/`；sqlite 落盘 `./data/app.sqlite`。

### 2.5 业务 CLI（govdoc-cli）

```bash
conda run -n govdoc-auditor-v3 govdoc-cli <subcommand> [args...]
# 常用：parse-tender / locate-section / validate-checkpoint / render-workpaper
```

### 2.6 代码质量检查

```bash
# 代码格式化
conda run -n govdoc-auditor-v3 ruff format .

# 代码检查并自动修复
conda run -n govdoc-auditor-v3 ruff check . --fix
```

### 2.7 测试

```bash
# 单元测试
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/ -v

# 契约测试（与 Scrivai/qmd 的契约）
conda run -n govdoc-auditor-v3 python -m pytest tests/contract/ -v

# 集成测试（真 SDK + 真 qmd + fixture）
conda run -n govdoc-auditor-v3 python -m pytest tests/integration/ -v

# 覆盖率
conda run -n govdoc-auditor-v3 python -m pytest tests/ --cov=govdoc --cov-report=term-missing
```

## 3. 标准作业程序 (Standard Operating Procedure)

> **Agent 必须严格遵守以下生命周期执行任务：**

### Phase 1: 规划与设计 (Planning)
1. **查阅规格 (Read Specs) & 讨论**:
   - **必须**先查阅 `research-wiki/` 中相关的 designs / plans / findings，了解已有设计决策
   - **必须**用 GitNexus MCP (`gitnexus://repo/Explicit-Lora/context` 入口，见 `graphify-out/`) 理解最新代码结构
   - 对不清楚的设计意图，**必须**与人类多轮讨论，确保对齐
2. **计划 (Plan)**: 正式编码前，**必须**使用 plan 模式输出开发计划，严格包含：
   - **1.1 摘要 (Summary)**: 1-2 句话总结
   - **1.2 审查点 (User Review Required)**: 明确列出需要用户确认的部分。若无，请注明"无"
   - **1.3 拟议变更 (Proposed Changes)**:
     - 以 **文件名 + 修改内容** 的形式列出
     - 修改内容必须精确到 **函数/方法级别 (Function-level)**
     - 明确标识 `[NEW]` / `[MODIFY]` / `[DELETE]`
   - **1.4 验证计划 (Verification Plan)**: 具体描述如何验证（测试命令、预期输出等）
3. **等待 (Wait)**: **必须**暂停等待用户审核。用户批准后方可进入下一阶段。

### Phase 2: 执行与验证 (Execution & Verification)
1. **编码 (Coding)**: 按计划逐步实现
2. **验证 (Verify)**:
   - **环境检查**: 所有命令在 `govdoc-auditor-v3` 环境中执行
   - **运行测试**: 先单元测试 → 契约测试 → 集成测试
   - 失败 → 回到编码修复；成功 → 进入 Phase 3

### Phase 3: 收尾与交付 (Finalization)
1. **文档同步**: 若变更影响架构或契约，同步更新 `research-wiki/` 中对应的 design / plan 实体
2. **提交**: 按 Conventional Commits 规范（`feat:`/`fix:`/`docs:`/`refactor:`/`test:`）
   - **严禁** commit message 中添加 AI 标识

## 4. 核心规则 (Rules)

### 4.1 架构约束（不可违反）

> [!CRITICAL]
> 本项目是三层架构中的业务层，**依赖方向恒定朝下**。以下约束不可违反：

| 约束 | 说明 |
|---|---|
| ❌ `import qmd` | 业务代码**禁止**直接导入 qmd（`ChunkRef` 经 Scrivai re-export） |
| ❌ `qmd.connect(...)` | 使用 `scrivai.build_qmd_client_from_config` 取代 |
| ❌ `import claude_agent_sdk` | Claude Agent SDK 仅 Scrivai 内部依赖，业务层完全隐形 |
| ❌ 复制 V2 主线代码 | V2 已冻结；仅可作为 donor/reference，不得把 V2 的 JSON blob store、`ReviewProject` 体系、HTML-only workpaper 搬入 V3 |
| ✅ 业务导入白名单 | 只允许 `from scrivai import ...` 和 `from govdoc.schemas import ...` |
| ✅ 领域模型单一真相 | 业务领域 pydantic 只定义在 `govdoc/schemas/`，不依赖外部 contracts 包 |
| ✅ skills/ 与 agents/ 位置 | 放**项目根**（不放 `.claude/` 和 `govdoc/` 包内）；`.claude/skills` 是 symlink → `skills/`（EvoSkill 路径兼容，见 `INTEGRATION_ISSUES.md` ISSUE-001） |
| ✅ Scrivai 缺口收口 | scrivai 与 design 的缺口统一收在 `govdoc/runtime.py`，**不得**改成 V2 风格 |

### 4.2 代码开发规范 (Code Style)

- **类型系统**: 强制所有函数签名包含完整类型注解 (`Union`, `Dict`, `Optional` 等)
- **文档**: 所有模块、类、方法必须包含 **中文 Docstring**（功能、参数、返回值、关键实现细节）
- **MVP 原则**:
  - **必须** 在 `tests/` 下编写测试代码（最低覆盖率 80%）
  - **严禁** 用默认参数掩盖必需逻辑（关键参数显式传递）
  - **必须** 关键维度 / 设备一致性通过 assertion 或 if 验证
- **代码组织**:
  - 使用阶段化注释 (`# Phase 1`, `# Phase 2`) 组织复杂逻辑
  - 返回值应含完整诊断信息（输出 / 损失 / 统计），用条件标志控制
- **命名与依赖**:
  - 类名 `PascalCase`，变量描述性命名，私有变量前缀 `_`
  - 导入顺序：标准库 → 第三方库 → 项目内部
- **日志与错误处理**:
  - 禁用 `print()`；使用 Python `logging` 模块或 Scrivai 提供的 logger
  - 错误要抛具名异常，不吞错
- **功能修改**:
  - **不考虑向后兼容**，直接修改原文件；代码简洁性优先

### 4.3 配置管理规范

- **优先级**: CLI args > `.env` > `govdoc.yaml`
- **文件**:
  - `govdoc.yaml`：全量非敏感配置（app / model / qmd / workspace / evolution）
  - `.env`：敏感信息（API Key、私有网关 token），**不提交**
  - `.env.example`：模板（如缺失则新建）
- **读取入口**: `govdoc/config.py`（pydantic-settings）；`govdoc/runtime.py` 提供 `lru_cache` 单例

### 4.4 测试组织规范

| 目录 | 用途 | 规范 |
|------|------|------|
| `tests/unit/` | 纯函数/单类单测 | 无外部依赖，mock 必要的边界 |
| `tests/contract/` | Scrivai / qmd 契约测试 | 验证上游 API 满足业务假设 |
| `tests/integration/` | 真实 SDK + 真 qmd + fixture | 端到端小样本，生成 Markdown 报告到 `tests/outputs/` |
| `tests/fixtures/` | 共享 fixture | `guide_excerpt.md` / `tender_small.docx` / `checkpoints_golden.json` / `mock_agent_trajectories/` |

#### Agent 测试输出规范

涉及 Agent 执行的集成测试**必须**生成 Markdown 报告：

| 要素 | 规范 |
|------|------|
| **输出位置** | `tests/outputs/<test_module>/<test_name>_<timestamp>.md` |
| **内容** | 任务描述、每步 Agent 输入/输出/推理、工具调用、最终结果 |
| **格式** | 结构化 Markdown（标题/代码块/列表），人类可读 |
| **pytest 集成** | 用 fixture 或工具类自动保存，结束时输出文件路径 |

**示例结构**:
```markdown
# Agent 测试: <test_name>
## 任务: <task>
## Step 1: <AgentName>
- 输入: ...
- 输出: ...
- 推理: ...
## 最终结果: ...
```

### 4.5 Pipeline / Workspace 规范

- 管道 A/B **消费 `PESRun.final_output_path`**（读文件）；必要时才 fallback 到 `final_output` 内存对象
- 单 `AuditPointRun` 对应一个独立 Scrivai workspace（单审核点隔离）
- `govdoc/pipelines/pes_overrides.py` 提供对 `build_phase_prompt` / validator / recovery 的轻量覆盖，不改 Scrivai 源
- `govdoc/pipelines/output_utils.py` 提供 `relaxed_json_loads`（修复中文引号、尾部逗号、字符串内裸引号）+ 业务级 schema 校验
- `templates/workpaper.docx` 必须 Word/LibreOffice **手工制作**（docxtpl + python-docx 程序化生成会拆 `<w:r>` 导致解析失败，见 ISSUE-002）

## 5. 上下文获取与迷途指南 (Context & Navigation)

> [!WARNING]
> `Reference/`（若存在）和 `_archive/`（若存在）下的所有内容仅供参考，**不代表本项目代码**。

### 5.1 权威文档

| 需求 | 文档路径 | 说明 |
|------|----------|------|
| 项目目标与背景 | `README.md` | 三层架构 + 启动说明 + 核心概念 |
| Agent 规约 | `AGENTS.md` | Claude Code Agent 实施约束摘要 |
| 知识库（唯一来源） | `research-wiki/` | 所有设计、计划、发现、调查的统一存储 |
| 知识库索引 | `research-wiki/index.md` | 所有实体的分类索引 |

### 5.2 GitNexus MCP 索引

本项目已被 GitNexus 索引（`graphify-out/`）：523 节点 · 792 边 · 32 社区。

**使用流程**：
1. 先读 `gitnexus://repo/<name>/context` 获取代码概览 + 检查索引新鲜度
2. 按任务类型读对应 skill 文件（见 `.claude/skills/gitnexus/` 下的 SKILL.md）
3. 若索引过期，终端运行 `npx gitnexus analyze` 重建

| 任务类型 | Skill 文件 |
|---|---|
| 理解架构 / "X 怎么工作？" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| 影响分析 / "改 X 会坏什么？" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| 追 bug / "X 为什么挂？" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| 重构（rename/extract/split） | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| 工具/资源/schema 参考 | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |

### 5.3 核心模块速查

| 模块 | 路径 | 职责 |
|------|------|------|
| FastAPI 入口 | `govdoc/api/main.py` | 路由注册 + lifecycle |
| API 路由 | `govdoc/api/routes/` | projects / rules / checkpoints / audit / workpapers |
| 管道 A | `govdoc/pipelines/extract_rules.py` | 触发 `gov-extractor` agent |
| 管道 B | `govdoc/pipelines/audit_tender.py` | 触发 `gov-auditor` agent（多 AuditPointRun） |
| PES 覆盖 | `govdoc/pipelines/pes_overrides.py` | ExtractorPES / AuditorPES 子类 + validator/hook |
| 输出工具 | `govdoc/pipelines/output_utils.py` | relaxed JSON + schema 校验 |
| 定稿回灌 | `govdoc/pipelines/finalize.py` | 工作底稿 → CaseLibrary |
| 领域 schema | `govdoc/schemas/` | GovCheckpoint / Workpaper / GovFinding / LegalBasis |
| DB 模型 | `govdoc/db/models.py` | SQLModel（10 表，design §5）|
| DB Session | `govdoc/db/session.py` | `get_session()` 依赖 |
| 文档存储 | `govdoc/storage/files.py` | DocumentStore + 路径辅助 |
| TenderDoc 解析 | `govdoc/parsers/tender_doc.py` | 上传文书 → markdown |
| 配置 | `govdoc/config.py` | pydantic-settings 读 `govdoc.yaml` |
| Runtime | `govdoc/runtime.py` | lru_cache 单例 + PES builder（design §13） |
| CLI 入口 | `govdoc/cli/__main__.py` | `govdoc-cli` 子命令分发 |
| 业务 skill | `skills/gov-*/SKILL.md` | extract-checkpoint / audit-tender / locate-evidence / cite-legal-basis |
| 业务 agent | `agents/gov-*.yaml` | PESConfig（extractor / auditor） |
| 工作底稿模板 | `govdoc/templates/workpaper.docx` | docxtpl 手工模板（10 占位符） |

### 5.4 核心概念

| 概念 | 说明 |
|---|---|
| **PES** | Plan-Execute-Summarize 三阶段编排；阶段间通过文件（plan.json / findings/ / output.json）交换状态 |
| **Workspace** | 一次 agent 运行的独立沙箱目录；含 skills 快照、data 快照、output、logs、meta.json |
| **Skill** | Claude Code 能力单元（SKILL.md），指导 agent 做某类事 |
| **Library** | Scrivai 对 qmd 的封装；固定 collection 名 `rules` / `cases` / `templates` |
| **AuditRun / AuditPointRun** | 管道 B 的编排层 vs 单审核点执行；V2 教训：单 JSON 汇总 → V3 拆细 |
| **EvoSkill** | 基于 trajectory 迭代 skill 的进化机制；至少 2 类指标同向提升才 promote（M2 启用）|

### 5.5 里程碑对照

| 里程碑 | 交付 | 集成点 |
|---|---|---|
| **M0**（Week 1-2）| 领域 schema + DB + Fixture + PESConfig/skill 草稿 + CLI + MockPES 跑通 | I0：MockPES 跑通管道 A/B |
| **M1**（Week 3-5）| 真 Scrivai PES + 真 LLM + 小 fixture 端到端 + Web API 骨架 | I1：小 fixture 指标达标 |
| **M2**（Week 6-7）| 前端 + 专家修订 + 定稿回灌 + 真实文书 + EvoSkill 接入 | I2：3 份真实文书 + EvoSkill |
| **M3**（Week 8） | 全量数据 + Docker + 锁定 scrivai/qmd 版本 | I3：生产验收 |

## 6. 输出规范

### 6.1 语言要求
- 所有输出语言: **简体中文**

### 6.2 信息密度原则
- **优先使用**:
  - 简洁文本描述
  - 伪代码（而非完整代码）
  - 表格（对比 / 配置 / 参数说明）
  - 流程图（Mermaid）
  - 项目符号列表
- **避免使用**:
  - 大段完整代码（信息密度低，可读性差）
  - 冗长的自然语言解释
- **核心原则**: 用最少的字符传递最多的信息

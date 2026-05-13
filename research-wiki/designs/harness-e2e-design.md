---
type: design
node_id: design:harness-e2e-design
title: 端到端 Harness 评估基础设施设计
date: 2026-05-13
tags: ["harness", "testing", "evaluation"]
---

# 设计：端到端 Harness 评估基础设施

> 日期：2026-05-13
> 状态：草稿

## 1. 背景与目标

### 1.1 问题

当前 harness-eval skill（`.claude/skills/harness-eval/SKILL.md`）的 4 个前置条件全部缺失：

| 前置条件 | 状态 |
|----------|------|
| `research-wiki/schemas/` 中有 schema 实体 | ❌ 目录不存在 |
| `research-wiki/metrics/` 中有 metric 实体 | ❌ 目录不存在 |
| `results/harness.db` 存在且包含数据 | ❌ 目录不存在 |
| `scripts/*.sh` 实验脚本 | ❌ 目录不存在 |

### 1.2 目标

使用 `real_data/` 中的真实政府采购数据，构建端到端 harness 评估基础设施，覆盖：
- **管道可靠性**：成功率、异常率、耗时等硬性指标
- **LLM 输出质量**：按 DeepEval 风格细粒度语义评估（faithfulness / recall / hallucination 等）
- **全 FastAPI 端点**：API 契约、功能验证、性能

### 1.3 测试数据

使用 `real_data/` 中的两个完整项目：

| 项目 | 主要文件 | 用途 |
|------|---------|------|
| 从化医院采购 | 需求书 .docx (14KB) + 招标文件 .pdf (693KB) + 合同 + 投标文件 | 管道 B 输入 |
| 汕头河道项目 | 需求书 .docx (16KB) + 招标包 .zip | 管道 B 输入 |
| 四类违法违规指引 | .doc (8.2MB) | 管道 A 输入 |
| 处罚标准表 | .xls (33KB) | 审核点导入 |

## 2. 方案选择

### 2.1 评估过的方案

| 方案 | 描述 | 优势 | 劣势 |
|------|------|------|------|
| A: API 全栈驱动 | 全部通过 HTTP 端点调用 | 最真实 | 调试难、慢 |
| B: 管道直调 | 跳过 HTTP，直接调 Python 函数 | 快、细粒度 | 不覆盖 API 层 |
| **C: 分层架构** | L1 管道直调 + L2 API 契约，共写同一 harness.db | 模块化、完整 | 基础设施量最多 |

### 2.2 选定方案：C（分层架构）

两层都交付，不分期：

- **Layer 1（管道层）**：直接调用 `run_extract()` / `run_audit()` / `finalize_workpaper()`，含真 LLM 调用，用 HarnessLog 精细记录，用 HarnessJudge 做 16 维语义评估
- **Layer 2（API 层）**：httpx 调用全部 20 个 FastAPI 端点，验证契约正确性、功能完整性、性能指标

## 3. Schema 设计（harness.db 表结构）

除 HarnessLog 固定的 `_runs` / `_events` 表外，自定义以下表：

### 3.1 Layer 1 表

#### `pipeline_runs` — 管道执行汇总

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK → _runs.run_id |
| pipeline | TEXT | "A" 或 "B" |
| project_name | TEXT | 测试项目名 |
| input_file | TEXT | 输入文件路径 |
| status | TEXT | completed / failed |
| duration_s | REAL | 执行耗时（秒） |
| total_tokens | INTEGER | 总 token 用量 |
| error | TEXT | 失败时的错误信息 |

#### `phase_metrics` — 逐 Phase 指标

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK |
| pipeline | TEXT | "A" 或 "B" |
| phase | TEXT | plan / execute / summarize |
| duration_s | REAL | 阶段耗时 |
| tokens_in | INTEGER | 输入 token |
| tokens_out | INTEGER | 输出 token |
| status | TEXT | completed / failed |
| attempt_no | INTEGER | 重试次数 |

#### `extract_results` — 管道 A 逐审核点输出

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK |
| checkpoint_id | TEXT | 审核点 ID |
| title | TEXT | 审核点标题 |
| category | TEXT | 分类（四类之一） |
| has_legal_basis | INTEGER | 是否有法条引用 (0/1) |
| legal_basis_count | INTEGER | 法条引用数量 |

#### `audit_results` — 管道 B 逐审核点输出

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK |
| point_run_id | TEXT | AuditPointRun ID |
| checkpoint_id | TEXT | 对应审核点 |
| verdict | TEXT | 合规 / 不合规 / 存疑 |
| has_evidence | INTEGER | 是否有证据 (0/1) |
| evidence_count | INTEGER | 证据引用数 |
| has_case_refs | INTEGER | 是否有案例引用 (0/1) |
| duration_s | REAL | 单点耗时 |
| status | TEXT | completed / failed |

#### `quality_scores` — HarnessJudge 语义评估结果

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK |
| dimension | TEXT | 指标 ID（如 extract-faithfulness） |
| score | REAL | 0.0 - 1.0 |
| passed | INTEGER | 是否通过 (0/1) |
| judge_reasoning | TEXT | Judge 的推理过程 |

### 3.2 Layer 2 表

#### `api_calls` — HTTP 调用记录

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK |
| method | TEXT | GET / POST / PUT / DELETE |
| path | TEXT | 端点路径 |
| status_code | INTEGER | HTTP 状态码 |
| duration_ms | REAL | 响应时间 |
| request_size | INTEGER | 请求体大小 |
| response_size | INTEGER | 响应体大小 |
| error | TEXT | 异常信息 |

#### `api_contracts` — 契约检查结果

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK |
| endpoint | TEXT | 端点标识 |
| check_name | TEXT | 检查项名称 |
| passed | INTEGER | 0/1 |
| detail | TEXT | 详细信息 |

## 4. Metrics 定义

### 4.1 硬性指标（自动判定 pass/fail）

| ID | 名称 | 计算方式 | 阈值 | 层 |
|----|------|---------|------|---|
| `pipeline-a-success` | 管道 A 成功率 | `pipeline_runs WHERE pipeline='A'` 成功比 | ≥ 80% | L1 |
| `pipeline-b-success` | 管道 B 成功率 | `pipeline_runs WHERE pipeline='B'` 成功比 | ≥ 80% | L1 |
| `phase-no-crash` | Phase 零崩溃 | `phase_metrics` 中 failed 数 | = 0 | L1 |
| `extract-yield` | 审核点产出率 | 每法规产出的审核点数 | ≥ 5 | L1 |
| `audit-completion` | 审核点完成率 | 每次 audit run 的点位完成比 | ≥ 90% | L1 |
| `e2e-duration` | 端到端耗时 | 单项目全流程耗时 | ≤ 600s | L1 |
| `checkpoint-import-success` | 审核点导入成功率 | XLS 导入的成功数/总行数 | = 100% | L2 |
| `tender-parse-success` | 文书解析成功率 | docx→markdown 转换成功率 | = 100% | L2 |
| `workpaper-render` | 底稿渲染成功 | finalize → docx 生成是否成功 | = 100% | L2 |
| `docx-download` | DOCX 下载完整性 | 下载文件 > 0 且 python-docx 可打开 | pass | L2 |
| `compare-success` | 文档对比成功率 | 两份 docx 上传对比返回 200 | = 100% | L2 |
| `api-all-endpoints` | 全端点可达 | 逐端点调用，状态码符合预期 | = 100% | L2 |
| `api-contract-pass` | 响应 Schema 契约 | 响应 body 符合 Pydantic model | = 100% | L2 |
| `api-latency-p95` | API P95 延迟 | 排除异步触发后的 P95 | ≤ 2000ms | L2 |

### 4.2 语义指标（HarnessJudge 评判，DeepEval 风格）

#### 管道 A（规则提取）

| ID | 名称 | 对标 DeepEval | Rubric 要点 | 评判输入 |
|----|------|-------------|------------|---------|
| `extract-faithfulness` | 法条引用忠实度 | Faithfulness | `legal_basis[]` 中的法条在原文中可找到出处，不编造 | 审核点 JSON + 法规原文 |
| `extract-recall` | 审核点召回率 | Contextual Recall | "四类违法违规"的所有可审核维度被完整覆盖，无重大遗漏 | 审核点列表 + 法规原文 |
| `extract-precision` | 审核点精准率 | Contextual Precision | 每个审核点都有明确法规依据，无凭空推测 | 审核点列表 + 法规原文 |
| `extract-hallucination` | 幻觉检测 | Hallucination | 描述中不含法规未提及的内容或歪曲原意 | 审核点 JSON + 法规原文 |
| `extract-json-correctness` | 输出 Schema 合规 | JSON Correctness | 严格符合 `CheckpointListOutput` schema | output.json + schema |
| `extract-category-accuracy` | 分类准确性 | G-Eval | `category` 与审核点内容匹配 | 审核点 JSON |

#### 管道 B（招标审核）

| ID | 名称 | 对标 DeepEval | Rubric 要点 | 评判输入 |
|----|------|-------------|------------|---------|
| `audit-faithfulness` | 证据引用忠实度 | Faithfulness | `evidence_quotes[]` / `evidence_refs[]` 在招标文书中可找到 | finding JSON + 文书原文 |
| `audit-relevancy` | 发现与审核点相关性 | Answer Relevancy | GovFinding 内容紧扣 GovCheckpoint 审查维度 | finding + checkpoint |
| `audit-verdict-reasoning` | 判定推理自洽性 | G-Eval | verdict 与 rationale 逻辑自洽，证据支撑结论 | finding JSON |
| `audit-hallucination` | 幻觉检测 | Hallucination | 证据引用非虚构、未张冠李戴 | finding JSON + 文书原文 |
| `audit-completeness` | 审核覆盖完整性 | Contextual Recall | 所有审核点被审核，"存疑"合理而非敷衍 | 全部 findings + checkpoints |
| `audit-json-correctness` | 输出 Schema 合规 | JSON Correctness | 符合 `WorkpaperAuditOutput` schema | output.json + schema |

#### Agent 行为

| ID | 名称 | 对标 DeepEval | Rubric 要点 | 评判输入 |
|----|------|-------------|------------|---------|
| `agent-plan-quality` | 计划质量 | Plan Quality | plan.json 包含所有待处理项、有清晰执行策略 | plan.json |
| `agent-plan-adherence` | 计划遵循度 | Plan Adherence | execute 阶段按 plan 逐个执行，无跳过无增删 | plan.json + findings/ |
| `agent-step-efficiency` | 步骤效率 | Step Efficiency | 无不必要的重复操作、空读取、无效工具调用 | trajectory 日志 |
| `agent-task-completion` | 任务完成度 | Task Completion | 三个 phase 都产出预期文件 | workspace 文件列表 |

#### 工作底稿

| ID | 名称 | 对标 DeepEval | Rubric 要点 | 评判输入 |
|----|------|-------------|------------|---------|
| `workpaper-summarization` | 摘要质量 | Summarization | summary 准确概括所有 findings，无遗漏无歪曲 | WorkpaperDraft JSON |
| `workpaper-finding-coverage` | 发现覆盖率 | G-Eval | 底稿包含所有 completed 审核点的 finding | WorkpaperDraft vs AuditPointRuns |
| `workpaper-format-compliance` | 格式规范性 | Prompt Alignment | docx 遵循模板结构、字段完整、无空白占位符 | 生成的 docx |

#### API 层语义

| ID | 名称 | 对标 DeepEval | Rubric 要点 | 评判输入 |
|----|------|-------------|------------|---------|
| `checkpoint-import-fidelity` | 导入保真度 | G-Eval | 导入后字段内容与原始 XLS 一致，无截断/乱码 | 导入结果 vs XLS 原始数据 |

## 5. 实验脚本架构

### 5.1 目录结构

```
govdoc/harness/                 # Python 实现（已有模块，扩展）
├── __init__.py                 # 已有：导出 HarnessLog, HarnessJudge, Verdict, Diagnosis
├── log.py                      # 已有：HarnessLog
├── handler.py                  # 已有：SqliteHandler
├── judge.py                    # 已有：HarnessJudge
├── pipeline_eval.py            # [NEW] L1 管道评估逻辑
├── api_eval.py                 # [NEW] L2 API 评估逻辑
└── manifest.py                 # [NEW] 加载 harness_manifest.yaml

scripts/                        # Shell 入口（符合 harness-eval skill 约定）
├── harness_pipeline.sh         # L1：conda run ... python -m govdoc.harness.pipeline_eval
├── harness_api.sh              # L2：conda run ... python -m govdoc.harness.api_eval
└── harness_all.sh              # 总入口：串行调 L1 + L2

scripts/fixtures/
└── harness_manifest.yaml       # 测试数据清单

scripts/rubrics/                # 语义评估 rubric 文件（16 个）
├── extract_faithfulness.md
├── extract_recall.md
├── extract_precision.md
├── extract_hallucination.md
├── extract_json_correctness.md
├── extract_category_accuracy.md
├── audit_faithfulness.md
├── audit_relevancy.md
├── audit_verdict_reasoning.md
├── audit_hallucination.md
├── audit_completeness.md
├── audit_json_correctness.md
├── agent_plan_quality.md
├── agent_plan_adherence.md
├── agent_step_efficiency.md
├── agent_task_completion.md
├── workpaper_summarization.md
├── workpaper_finding_coverage.md
├── workpaper_format_compliance.md
└── checkpoint_import_fidelity.md
```

### 5.2 Layer 1 执行流程 (`govdoc.harness.pipeline_eval`)

```
1. 初始化
   HarnessLog(db_path="results/harness.db", run_id=<uuid>, git_sha=HEAD)
   configure_logging → SqliteHandler

2. Fixture 准备（per project in manifest）
   ├─ 法规文件 → DB RuleSource
   ├─ 招标文书 → TenderDoc（含 docx→md 解析）
   ├─ 审核点表 → CheckpointFinal
   └─ log_event("fixture_prepared", {...})

3. 管道 A（per 法规文件）
   ├─ run_extract(rule_source_id, session)
   ├─ 记录 pipeline_runs / phase_metrics / extract_results
   └─ HarnessJudge 语义评估（6 个维度）→ quality_scores

4. 管道 B（per 项目）
   ├─ run_audit(audit_run_id, session)
   ├─ 记录 pipeline_runs / phase_metrics / audit_results
   └─ HarnessJudge 语义评估（6 个维度）→ quality_scores

5. Agent 行为评估
   └─ 从 trajectory 读取，HarnessJudge 评估 4 个维度

6. 工作底稿评估
   ├─ finalize_workpaper(audit_run_id, partial=True)
   └─ HarnessJudge 评估 3 个维度

7. 关闭
   harness_log.close(status='completed')
```

### 5.3 Layer 2 执行流程 (`govdoc.harness.api_eval`)

```
前提：FastAPI 服务已启动（脚本自检，未启动则 subprocess 拉起）

1. 初始化
   HarnessLog（同一个 harness.db，新 run_id）
   httpx.AsyncClient(base_url="http://localhost:8000")

2. 全端点冒烟（20 个端点逐一调用）
   ├─ 健康检查：GET /healthz → 200
   ├─ 项目 CRUD：POST/GET /api/v1/projects
   ├─ 文书上传：POST /api/v1/projects/{id}/tender-doc
   ├─ 规则上传：POST /api/v1/rules/upload → 202（异步）
   ├─ 审核点导入：POST /api/v1/checkpoints/import
   ├─ 审核运行：POST /api/v1/audit/runs → 202 → 轮询 progress
   ├─ 工作底稿：GET draft → PUT draft → POST finalize
   ├─ DOCX 下载：GET /workpaper/final/docx
   ├─ 文档对比：POST /api/v1/compare
   └─ 每个端点记录 api_calls + api_contracts

3. 契约验证
   ├─ 响应 body vs Pydantic model 反序列化
   ├─ 异步端点 202 → 状态变迁正确性
   ├─ 错误场景：无效 ID → 404，缺必填字段 → 422
   └─ 审核点导入保真度（HarnessJudge）

4. 性能指标
   ├─ P95 延迟
   └─ 请求/响应 size

5. DOCX 完整性
   ├─ python-docx 可打开
   └─ 文档非空、含预期节标题

6. 关闭
```

### 5.4 `harness_manifest.yaml`

```yaml
projects:
  - name: "从化医院采购"
    tender_doc: "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx"
    supplementary_docs:
      - "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购的合同.pdf"

  - name: "汕头河道项目"
    tender_doc: "real_data/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目.docx"
    supplementary_docs: []

rules:
  - name: "四类违法违规指引"
    path: "real_data/2025年政府采购领域\"四类\"违法违规行为专项整治工作指引.doc"

checkpoints:
  - name: "处罚标准表"
    path: "real_data/附件9 处理处罚标准.xls"
```

## 6. 与 harness-eval skill 的集成

### 6.1 评估触发流程

```
用户/CI：
  tmux new-session -d -s harness-run "bash scripts/harness_all.sh; echo '=== DONE ==='; sleep 86400"

完成后：
  /harness-eval <run_id>
    │
    ├─ Phase 1: 读 research-wiki/schemas/ → 知道查哪些表
    ├─ Phase 2: 复用已有运行记录（git_sha 匹配时跳过重跑）
    ├─ Phase 3: 硬性指标 → SQL 查询 → 对比阈值
    ├─ Phase 4: 语义指标 → 从 quality_scores 读已有评估
    ├─ Phase 5: 综合判定
    ├─ Phase 6: 不通过时诊断 + 迭代建议
    └─ Phase 7: 写 research-wiki/findings/eval-<run_id>.md
```

### 6.2 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 语义评估时机 | 在 L1 脚本中完成 | 评估需要法规/文书原文作 evidence，运行时最易获取 |
| harness-eval 职责 | 聚合判定 + 诊断 | 读取已有 quality_scores，不重复调 HarnessJudge |
| rubric 管理 | 独立 .md 文件 | 修改评判标准不需改代码 |
| DB 共享 | 两层共写一个 harness.db | harness-eval 统一查询，不需跨 DB |
| 真实 LLM 调用 | L1 用真 LLM，L2 不涉及 LLM | L1 评估输出质量必须真跑；L2 只验 API 契约 |

## 7. 新增文件清单

### 7.1 代码文件

| 路径 | 标记 | 说明 |
|------|------|------|
| `govdoc/harness/pipeline_eval.py` | [NEW] | L1 管道评估主逻辑 |
| `govdoc/harness/api_eval.py` | [NEW] | L2 API 评估主逻辑 |
| `govdoc/harness/manifest.py` | [NEW] | 加载 harness_manifest.yaml |
| `scripts/harness_pipeline.sh` | [NEW] | L1 shell 入口 |
| `scripts/harness_api.sh` | [NEW] | L2 shell 入口 |
| `scripts/harness_all.sh` | [NEW] | 总入口 |
| `scripts/fixtures/harness_manifest.yaml` | [NEW] | 测试数据清单 |
| `scripts/rubrics/*.md` | [NEW] | 20 个语义评判 rubric 文件 |

### 7.2 research-wiki 实体

| 路径 | 类型 | 说明 |
|------|------|------|
| `research-wiki/schemas/harness-pipeline-runs.md` | schema | pipeline_runs 表定义 |
| `research-wiki/schemas/harness-phase-metrics.md` | schema | phase_metrics 表定义 |
| `research-wiki/schemas/harness-extract-results.md` | schema | extract_results 表定义 |
| `research-wiki/schemas/harness-audit-results.md` | schema | audit_results 表定义 |
| `research-wiki/schemas/harness-quality-scores.md` | schema | quality_scores 表定义 |
| `research-wiki/schemas/harness-api-calls.md` | schema | api_calls 表定义 |
| `research-wiki/schemas/harness-api-contracts.md` | schema | api_contracts 表定义 |
| `research-wiki/metrics/pipeline-a-success.md` ~ `api-latency-p95.md` | metric | 14 个硬性指标 |
| `research-wiki/metrics/extract-faithfulness.md` ~ `checkpoint-import-fidelity.md` | metric | 17 个语义指标 |

### 7.3 基础设施

| 路径 | 说明 |
|------|------|
| `results/` | 目录，存放 harness.db（.gitignore） |
| `scripts/` | 目录，存放实验脚本 |

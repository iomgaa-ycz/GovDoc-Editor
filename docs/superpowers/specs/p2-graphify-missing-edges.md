# P2 副产物：graphify 漏抽边 / 合理低耦合节点 / 已消失符号

本文档记录 P2 孤立节点审查的**非删除**部分：graphify 工具漏抽的真实调用边、保留的低耦合合理节点，以及因前置 P0/P1 重构已从代码库中消失的符号。

原始 CSV：`docs/superpowers/specs/p2-isolated-nodes-audit.csv`（83 行嫌疑 / 4 僵尸 / 30 漏抽 / 44 合理 / 5 已消失）

---

## 1. graphify 漏抽边（`classification=missing`）

这些节点在图谱里 degree≤1，但实际代码中有生产/测试调用。属于 graphify 抽取器的边丢失 —— **不删代码**，仅建议下次 `/graphify --update` 后复核。

### 1.1 Frontend（adapters / components / context / pages）

| 节点 | 文件 | 实际使用点 |
|---|---|---|
| `extractSummaryFromHtml()` | frontend/src/adapters/backendToUi.ts | V3WorkbenchContext.tsx:419 |
| `parseFindingJson()` | frontend/src/adapters/backendToUi.ts | AIReviewPage / AuditResultsPage / AuditProgressPanel / V3WorkbenchContext |
| `pointRunToLog()` | frontend/src/adapters/backendToUi.ts | V3WorkbenchContext.tsx:304 |
| `severityToRisk()` | frontend/src/adapters/backendToUi.ts | PointInsight.tsx:43 |
| `verdictLabel()` | frontend/src/adapters/backendToUi.ts | PointInsight.tsx:61 |
| `verdictToStatus()` | frontend/src/adapters/backendToUi.ts | PointInsight / AuditResultsPage / AuditProgressPanel |
| `AppShell()` | frontend/src/components/AppShell.tsx | App.tsx:3 Route 壳 |
| `Modal()` | frontend/src/components/Modal.tsx | AIReviewPage / AuditLibraryPage |
| `FileDropzone()` | frontend/src/components/Ui.tsx | TenderUploadPanel / AuditLibraryPage |
| `ProgressBar()` | frontend/src/components/Ui.tsx | AuditProgressPanel:60 |
| `SelectInput()` | frontend/src/components/Ui.tsx | WorkpaperPage / AuditResultsPage / TenderUploadPanel |
| `TextArea()` | frontend/src/components/Ui.tsx | AuditResultsPage / AuditLibraryPage |
| `WorkpaperEditor()` | frontend/src/components/WorkpaperEditor.tsx | WorkpaperPage.tsx:13 |
| `WorkbenchProvider()` | frontend/src/context/V3WorkbenchContext.tsx | main.tsx:17 App 根包裹 |
| `useWorkbench()` | frontend/src/context/V3WorkbenchContext.tsx | 5+ pages / hooks 消费 |
| `HomePage()` | frontend/src/pages/HomePage.tsx | App.tsx:4 Route |

### 1.2 Backend（api / cli / config / db / pipelines / storage / testing_support）

| 节点 | 文件 | 实际使用点 |
|---|---|---|
| `get_db_session()` | govdoc/api/deps.py | 5 个 route 文件 import |
| `create_app()` | govdoc/api/main.py | 同文件 L76 模块级 `app = create_app()` |
| `locate_section_command()` | govdoc/cli/tender.py | cli/__main__.py 子命令分发 |
| `parse_tender_command()` | govdoc/cli/tender.py | cli/__main__.py 子命令分发 |
| `validate_checkpoint_command()` | govdoc/cli/tender.py | cli/__main__.py 子命令分发 |
| `GovDocConfig.project_root` | govdoc/config.py | `resolve_path` / tests/unit/test_config.py / 下游 `cfg.project_root` |
| `uid()` | govdoc/db/models.py | 多个 SQLModel 表 `Field(default_factory=uid)` |
| `attach_workspace_output()` | govdoc/pipelines/common.py | extract_rules.py:95 + audit_tender.py:352 |
| `dump_phase_usage()` | govdoc/pipelines/common.py | extract_rules.py:96/136 + audit_tender.py:390 |
| `load_result_payload()` | govdoc/pipelines/common.py | extract_rules.py:100 + audit_tender.py:372 |
| `run_extract()` | govdoc/pipelines/extract_rules.py | routes/rules.py:69 后台任务 + 契约测试 |
| `DocumentStore.__init__()` | govdoc/storage/files.py | runtime.get_document_store 实例化 |
| `seed_working_tree()` | govdoc/testing_support.py | extract_rules.py:83 + audit_tender.py:333 |
| `MockReplayBundle.working_seed_dir` | govdoc/testing_support.py | extract_rules / audit_tender 读该属性 |

**根因推测**：graphify 当前版本对以下模式存在盲点：

1. **属性访问**（`cfg.project_root`、`replay.working_seed_dir`）
2. **默认工厂参数**（`Field(default_factory=uid)`）
3. **字符串里的 import**（`from X import Y` 写在函数体内）
4. **JSX 里的组件消费**（`<Modal>...</Modal>`、`<SelectInput />` 等）

**建议动作**：P2 merge 后重跑 `/graphify . --update`（目前跳过以避免重建成本），再跑 `scripts/audit_isolated_nodes.py` 复核这些节点应连入正常社区。

---

## 2. 合理低耦合节点（`classification=alive`）

这些节点 degree≤1 是因为它们由**框架直接调用**或是**组件内私有方法**，非图谱问题。**不删代码**。

### 2.1 FastAPI 路由处理器（framework-invoked，14 个）

`govdoc/api/routes/` 下全部 `@router.<verb>` 装饰的 async 函数：`create_audit_run` / `get_audit_run` / `get_audit_run_progress` / `list_audit_runs` / `retry_point_run` / `delete_checkpoint` / `create_project` / `get_project` / `list_projects` / `list_tender_docs` / `upload_tender_doc` / `get_extract_run_status` / `list_checkpoint_drafts` / `list_rule_sources` / `upload_rule` / `download_final_workpaper_docx` / `finalize_workpaper_endpoint` / `finalize_workpaper_partial` / `get_workpaper_draft` / `update_workpaper_draft`。

### 2.2 Alembic 迁移钩子（4 个）

`run_migrations_offline` / `run_migrations_online`（env.py）、`upgrade` / `downgrade`（0001_initial.py）—— 由 alembic CLI 调用。

### 2.3 React 组件内私有事件处理器（11 个）

这些都是 page 组件内部声明的 `function handleXxx(...)`，只在同组件 JSX 的 `onClick` / `onChange` 等 prop 里被引用。graphify 图里它们孤立，但实际"使用点"就是同文件 JSX 树：

- `AuditLibraryPage`: `confirmDelete` / `handleUpload` / `openEdit` / `saveEdit`
- `AuditResultsPage`: `getCheckpoint` / `handleRetry`
- `WorkpaperPage`: `handleExport` / `handleFinalize` / `handleSave` / `handleSelectRun`

### 2.4 pytest 测试（7 个）

`tests/` 下的测试函数由 pytest 自动收集运行，不需要被 Python 代码显式调用。同理测试模块级的文件节点。

### 2.5 Vite 工具链文件（2 个）

- `frontend/src/vite-env.d.ts`：Vite 三斜线类型引用，TypeScript 编译器直接读
- `frontend/vite.config.ts`：Vite CLI 启动/构建时直接加载

### 2.6 DocumentStore 对外暴露属性（1 个）

- `DocumentStore.storage_root` @property：V2 遗留接口的最小占位，当前 V3 生产代码未消费。可考虑在未来的清理 sprint 中评估是否真正需要保留；当前属于 MVP 容忍范围。

---

## 3. 已消失的符号（`classification=gone`，5 个）

这些节点在图谱快照里还存在，但因前置 P0/P1a/P1b 重构已从代码中删除 / 重定位。本次 P2 **无操作**（没有代码可改）。

| 节点 | 原位置 | 去向 |
|---|---|---|
| `getCheckpointForPointRun()` | frontend/src/pages/AIReviewPage.tsx | P1a 收敛：改为 JSX inline `finalCheckpoints.find(...)` |
| `handleCreateProject()` | frontend/src/pages/AIReviewPage.tsx | P1a 抽到 `hooks/useProjectWorkflow.ts` |
| `handleUploadTender()` | frontend/src/pages/AIReviewPage.tsx | P1a 抽到 `hooks/useProjectWorkflow.ts` |
| `handleStartAudit()` | frontend/src/pages/AIReviewPage.tsx | P1a 抽到 `hooks/useAuditRun.ts` |
| `toggleCheckpoint()` | frontend/src/pages/AIReviewPage.tsx | P1a 抽到 `hooks/useAuditRun.ts` |

这 5 个节点验证了：P2 在 P0/P1a/P1b/P1c 全部 merge **之后**执行是正确决策 —— 否则会误删 P1a 正在重构的代码。

---

## 4. Graphify 重跑建议（P2 合并后）

P2 合并进 umbrella 后建议执行：

```bash
/graphify . --update
conda run -n govdoc-auditor-v3 python scripts/audit_isolated_nodes.py /tmp/p2-verify.csv
wc -l /tmp/p2-verify.csv
```

**期望结果**：

1. 4 个已删除的 zombie 节点从图里消失
2. 5 个 `gone` 节点（P1a 旧版 AIReviewPage handlers）也消失
3. 30 个 `missing` 节点按实际调用边进入正常社区（degree > 1）
4. 剩下约 44 个 `alive` 节点（框架调用 + 组件私有方法 + Vite 工具链）仍会出现在嫌疑列表，但属于**可接受的 false positives**

本次跳过重跑 graphify 的原因：
- 全量 `/graphify --update` 成本高（需要 LLM 调用抽取）
- P2 本质是"代码清理 + 图谱盲点文档化"，重跑不是 DoD 的硬约束
- 类似 P1a smoke 声明模式：留作后续独立执行

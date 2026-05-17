# GovDoc_AuditorV3 技术债整理 · Umbrella Spec

**日期**：2026-04-19
**分支**：`feat/tech-debt-cleanup`（集成分支）
**目标**：一次性收齐由 graphify 图谱诊断出的 5 项结构性技术债，不改变系统行为。
**预估工作量**：3 波次，约 6-9 天

---

## 0. 依据

由 `graphify-out/GRAPH_REPORT.md`（601 节点 · 882 边 · 33 社区）交叉源码复核得出的"屎山热力图"。诊断结论：**这不是屎山，是 MVP 略粗糙 + 1 个上帝函数 + 文档社区过载**。真正需要处理的结构性问题集中在 5 项。

---

## 1. 四条不变式

贯穿全 spec，任何子项目违反其中任一条即阻塞 merge。

| # | 不变式 | 如何验证 |
|---|---|---|
| **I1** | **行为不变**：P0/P1a/P1b 后，对任意输入 fixture，最终 DB/文件/API 响应与拆分前一致 | P0/P1b 跑 golden 对比；P1a 跑 @testing-library render 断言 |
| **I2** | **测试先行**（适用 P0/P1a/P1b 重构项）：**先**合入护栏测试，**再**合入改动代码。P1c 本身即测试交付（自洽）；P2 为纯删除，护栏为 `grep -r <symbol>` 使用点核验 | P0/P1a/P1b 子分支至少两个 commit：先 `test:` 再 `refactor:`；P2 每次删除前需在 commit message 或 PR 描述附 grep 证据 |
| **I3** | **子 PR 可独立回滚**：任一子 PR revert 后，umbrella 分支仍能通过全部现有测试 | CI 在 umbrella 分支上跑全量；revert 演练进入验收清单 |
| **I4** | **契约零扩张**：不新增 API 端点、不改 SQLModel schema、不扩 pydantic 必填字段 | diff 审查 `routes/*.py`、`db/models.py`、`schemas/*.py` |

---

## 2. Umbrella 架构

### 2.1 分支拓扑

```
master
  └── feat/tech-debt-cleanup  (集成分支 · 长生命周期)
        ├── feat/p0-run-audit-split        → PR → umbrella
        ├── feat/p1a-aireview-split        → PR → umbrella
        ├── feat/p1b-output-utils-json5    → PR → umbrella
        ├── feat/p1c-v3-contract-tests     → PR → umbrella
        └── feat/p2-isolated-nodes-audit   → PR → umbrella
                                                ▼
                                       (全部 merge 后)
                                            umbrella → master (merge commit)
```

### 2.2 范围边界

**在范围内**：
- 5 项整理任务的设计 + 验收 + 顺序 + 风险
- 前端测试基建一次性引入（vitest + @testing-library/react + MSW）

**不在范围内**：
- Scrivai / qmd 上游的任何改动（如需涉及，登记到 `工程md/INTEGRATION_ISSUES.md`）
- V2 代码的任何清理
- 新业务功能
- EvoSkill 接入（属 M2 里程碑）

---

## 3. 五个子项目

### 3.1 P0 · `run_audit` 拆分

- **现状**：`govdoc/pipelines/audit_tender.py::run_audit` 214 行单函数（L204-418），一锅炖：qmd 索引 / DB 事务 / workspace 生命周期 / PES 调度 / 结果解析 / 错误恢复 / 清理。
- **目标**：拆为 orchestration（~50 行） + 5 个职责清晰 helper：
  - `_index_tender_doc(audit_run, tender_doc) -> str | None` — qmd collection 准备
  - `_resolve_point_runs(audit_run, selected_ids) -> list[AuditPointRun]` — 过滤待跑点
  - `_run_single_point(point_run, ctx) -> PESRun` — 单点 PES 调度
  - `_persist_point_result(point_run, pes_run)` — DB 写入 + Finding JSON 落盘
  - `_cleanup_tender_collection(collection_id)` — 资源清理
- **护栏**：
  - (B) 扩充 `tests/contract/test_pipeline_b_with_mocks.py::test_pipeline_b_with_mock_pes_replay`，断言 6 类终态（`AuditRun.status`、`AuditPointRun.status`、`GovFinding` 内容、`WorkpaperDraft` 存在、trajectory 落盘、tender collection 清理）
  - (A) 合入前跑一次 golden：采集 `audit_case_01` fixture 的 DB hash + 文件树 hash（排除时间戳字段），拆分后必须字节一致
- **风险**：高。管道 B 核心；`_ensure_tender_collection` 和 `_delete_trajectory_run` 的异常语义必须保真。

### 3.2 P1a · `AIReviewPage.tsx` 拆分

- **现状**：`frontend/src/pages/AIReviewPage.tsx` 315 行单组件，含 8+ useState、多个事件处理器、审核点列表 + 上传区 + 进度区同屏。
- **目标**：容器组件（~80 行） + 3 子组件 + 2 custom hook：
  - `TenderUploadPanel` — 招标文书上传 UI
  - `CheckpointPicker` — 审核点多选
  - `AuditProgressPanel` — 审计进度显示
  - `useProjectWorkflow()` — 创建项目 / 上传文书状态机
  - `useAuditRun()` — 启动审计 / 轮询进度
- **护栏**：
  - 依赖 P1c 已合入（MSW 基建就位）
  - 为容器组件写 5+ 个 render+interaction test：创建 → 上传 → 勾选 → 启动全链路
- **风险**：中。UI 行为回归靠 testing-library 断言；视觉回归靠手工 smoke（不做 visual snapshot）。

### 3.3 P1b · `output_utils.py` 混合重构

- **现状**：`govdoc/pipelines/output_utils.py` 225 行，三段混合：①预处理（中文引号 + 字符串内裸引号修复）/ ②宽松解析（尾逗号 + 单引号等）/ ③业务校验（GovFinding schema）。
- **目标**：
  - `_preprocess()` 保留（~60 行，处理 LLM 中文输出特有问题）
  - 中间段 ② 替换为 `import json5; json5.loads(...)`（删除 ~100 行手写代码）
  - `_validate_govfinding_schema()` 保留（~40 行）
  - 总体从 225 行降到 ~120 行
  - 新增 devDep：`json5>=0.9.14`
- **护栏**：
  - `tests/unit/test_output_utils.py` 从 2 case 扩到 12+ case，覆盖 6 类错误模式：中文引号、裸引号、尾逗号、单引号 key、结构正常、schema 违规
  - 从 `tests/fixtures/mock_agent_trajectories/` 采样至少 10 份真 LLM 输出做对比验证
- **风险**：中。json5 对某些结构的容错边界需要在 test 中固化。

### 3.4 P1c · `v3.ts::request()` 契约测试 + 前端测试基建

- **现状**：`frontend/src/api/v3.ts::request()` 是所有前端 API 调用的唯一出口（图谱 god node，22 条边），当前零测试；`frontend/package.json` 零测试基建。
- **目标**：
  - 一次性引入 devDeps：`vitest`、`@testing-library/react`、`@testing-library/jest-dom`、`msw`、`@testing-library/user-event`、`jsdom`
  - 配置 `frontend/vitest.config.ts` + `frontend/tests/setup.ts` + `frontend/tests/mocks/handlers.ts`
  - 为 `request()` 写 8-10 个 contract test：URL 拼接、query string、401/500 错误码、JSON parse、超时、fetch 失败、success path、空响应
  - 在 `package.json` 加 `"test": "vitest run"` 和 `"test:watch": "vitest"`
- **护栏**：**本项自身就是护栏**——必须先于 P1a 合入。
- **风险**：低。纯新增，不动现有代码。锁定 `msw@^2.x` 避免 API 不兼容。

### 3.5 P2 · 23 个真嫌疑孤立节点审查

- **现状**：图谱 158 个 ≤1 连接节点，其中 60% 是文档 rationale（非代码）、25% 是 module docstring（非代码）、**15%（~23 个）是真代码嫌疑**。
- **目标**：
  - 新增 `scripts/audit_isolated_nodes.py`，从 `graphify-out/graph.json` 过滤 `file_type=code AND degree≤1` 节点
  - 输出 `docs/superpowers/specs/p2-isolated-nodes-audit.csv`，含列：node_id / label / file / classification（待填）
  - 人工逐行标注为：僵尸（删）/ 漏抽边（graphify 配置问题）/ 活着（放过）
  - 每个"删"操作前强制 `grep -r <symbol>` 全仓确认无引用，删除独立 commit
- **护栏**：最后一波，P0/P1 全部合入后再扫，避免误删正在重构的代码。
- **风险**：低。操作粒度小，逐个 commit 评审。

---

## 4. 实施顺序

```
Wave 1（并行 · 约 3-5 天）
├── P0  feat/p0-run-audit-split          ─┐
├── P1b feat/p1b-output-utils-json5      ─┤ 互相无依赖，可同时推进
└── P1c feat/p1c-v3-contract-tests       ─┘

Wave 2（串行 · P1c merge 后启动 · 约 2-3 天）
└── P1a feat/p1a-aireview-split             依赖 P1c 的 MSW 基建

Wave 3（最后 · 约 1 天）
└── P2  feat/p2-isolated-nodes-audit       P0/P1 全部合入后再扫
```

**依赖理由**：
- P1a → P1c：`AIReviewPage` render test 需要 MSW mock fetch，MSW 在 P1c 里建
- P2 → all：P2 涉及"删僵尸"，如果 P0/P1 还在重构，可能误删"待重构但活着"的代码

---

## 5. 验收标准（Definition of Done）

| 项 | DoD（全部打勾才能 merge 到 umbrella）|
|---|---|
| **P0** | ① 集成测试 6 类终态断言全绿<br>② golden 对比零 diff<br>③ `run_audit` ≤ 70 行（不含 docstring）<br>④ `ruff check` 零新增 warning |
| **P1a** | ① `tests/pages/AIReviewPage.test.tsx` 5+ case 全绿<br>② 容器 `AIReviewPage.tsx` ≤ 120 行<br>③ 手工 smoke：创建 → 上传 → 勾选 → 启动，无 console.error<br>④ `tsc -b` 零新增 error |
| **P1b** | ① `test_output_utils.py` 12+ case 全绿<br>② 总行数 ≤ 140<br>③ 10 份真 LLM 样本 parse 成功率 100% |
| **P1c** | ① `tests/api/v3.test.ts` 8+ case 全绿<br>② `npm test` 可运行<br>③ `tests/mocks/handlers.ts` 可被 P1a 复用 |
| **P2** | ① 过滤脚本就位并产 CSV<br>② CSV 每行标注完成<br>③ 标为"僵尸"的代码删除<br>④ `graphify --update` 重跑后孤立节点数下降 |

---

## 6. Umbrella 合回 master 的验收门

```
所有子 PR 已 merge → umbrella 上执行：
  ✓ conda run -n govdoc-auditor-v3 python -m pytest tests/ 全绿
  ✓ conda run -n govdoc-auditor-v3 ruff check . 零 warning
  ✓ conda run -n govdoc-auditor-v3 ruff format --check . 无格式差异
  ✓ cd frontend && npm test 全绿
  ✓ cd frontend && tsc -b 零 error
  ✓ 手工端到端：后端启动 + 前端启动 + 真 fixture 跑一次完整审计
  ✓ umbrella rebase master 无冲突
→ 合回 master（merge commit，保留子 PR 历史）
```

---

## 7. 回滚策略

**子 PR 级回滚**（某个子项目合入后发现问题）：
- 在 umbrella 分支上 `git revert <merge-commit>`
- 触发 CI 确认 revert 后 umbrella 仍全绿（验证 I3）
- 修复后重新开子分支 PR

**umbrella 级回滚**（合回 master 后出问题）：
- 在 master 上 `git revert <umbrella-merge-commit>` 整体回滚
- merge commit 保留子 PR 历史，未来可只 cherry-pick 部分子项目

---

## 8. 关键风险清单

| 风险 | 可能性 | 缓解 |
|---|---|---|
| P0 golden 采集的 hash 含时间戳导致 flaky | 中 | 采集脚本显式排除 `created_at`/`updated_at` 字段 |
| json5 对生产 LLM 输出样本行为与手写代码不一致 | 中 | 从 `mock_agent_trajectories/` 至少采样 10 份真 LLM 输出做对比 |
| MSW 1.x vs 2.x API 变化导致 setup 踩坑 | 低 | 锁定 `msw@^2.x`（2023+ 稳定版本），参考官方 vitest example |
| P1a 拆出的 custom hook 在 React 18 strict mode 下 double-render 引发副作用 | 中 | render test 默认开启 strict mode；hook 内所有副作用走 `useEffect` |
| P2 误删仍在使用的代码 | 低 | 每个删除前强制 `grep -r <symbol>` 全仓验证 |

---

## 9. 附录：可追溯性

| 决策点 | 选项 | 理由概述 |
|---|---|---|
| 组织方式 | Umbrella spec | 一次性收齐技术债的节奏 |
| P0 护栏 | A+B 组合（integration + golden） | 开发快（每次 integration）+ 终局严（合入前 golden）|
| 前端测试基建 | vitest + testing-library + MSW | 业界标准，与 Vite 生态原生集成 |
| 分支策略 | Umbrella + 子分支 PR 链 | 粒度清晰、可逐项回滚、CI 独立 |
| P1b 边界 | 保留 ①③ + ② 换 json5 | 保留 LLM 特定容错 + 削减一半代码 |
| P2 范围 | 只审 23 个真嫌疑节点 | 158 里 85% 是图谱工具噪声，不是代码问题 |

---

**下一步**：此 spec 批准后，调用 `writing-plans` skill 产出具体可执行的 implementation plan（含 milestone、文件级变更、测试 case 清单、commit 顺序）。

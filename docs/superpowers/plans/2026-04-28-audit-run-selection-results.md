# 审核运行下拉与结果加载修复计划

> 日期：2026-04-28
> 分支：`fix/audit-run-selection-results`
> 目标：让工作底稿和审核点结果页的审核运行下拉对客户更友好，并修复审核点结果页切换历史审核运行后不加载内容的问题。

## 背景

当前工作底稿页和审核点结果页都通过全局 `auditRuns` 列表提供“选择审核运行”的下拉框。下拉项展示逻辑直接使用 `AuditRun.id` 前 8 位加状态：

- `frontend/src/pages/WorkpaperPage.tsx`
- `frontend/src/pages/AuditResultsPage.tsx`

这会让客户看到一串内部编号，无法判断对应项目、文书、审核时间和当前状态。

另外，审核点结果页的内容来源是 `auditProgress?.point_runs`。用户切换下拉时，目前只更新 `selectedAuditRunId`，没有主动请求所选运行的 `/api/v1/audit/runs/{id}/progress`，导致刷新页面后选择历史审核仍显示“暂无审核结果”。如果内存中保留了上一轮审核进度，还可能误展示旧运行的数据。

## 现象

- 工作底稿页下拉展示类似 `abc123ef... (draft_ready)`，对客户不友好。
- 审核点结果页下拉展示同样的内部编号。
- 审核点结果页选择某次审核运行后，左侧审核点列表不出现。
- 从 AI 审核页刚完成一次审核后进入结果页可能能看到内容，但这是依赖内存中的 `auditProgress`，不是稳定的历史加载能力。

## 根因

1. 下拉展示层没有格式化业务标签，只使用 `AuditRun.id` 和英文状态。
2. `V3WorkbenchContext` 没有提供“按 run id 加载审核进度”的公开方法。
3. `AuditResultsPage` 切换运行时没有调用 `getAuditRunProgress(runId)`。
4. `selectedPointRunId` 没有随审核运行切换重置，存在指向旧点位的风险。
5. 工作底稿编辑器存在延迟自动保存；切换运行时如果不取消 pending save，可能把旧底稿内容保存到新选中的运行。

## 产品口径

本次修复优先解决“能看懂、能加载、不错位”：

- 下拉首选展示项目名、主文书名、创建时间和状态。
- 结果页切换某次审核后必须加载该运行的审核点结果。
- 加载成功后默认选中第一个审核点，减少用户空点一次。
- 加载中、加载失败、无审核点三种状态要有明确反馈。
- 不在本轮扩展工作底稿 JSON schema，也不改变后端审核运行数据模型。

## 前端改动

### 1. 增加审核运行展示标签

新增独立工具函数：

```text
frontend/src/utils/auditRunLabel.ts
```

由这个 helper 用现有数据拼出客户可读标签，两个页面共用，方便单元测试：

- 项目名：通过 `run.project_id` 匹配 `projects`。
- 主文书名：通过 `run.tender_doc_id` 精确匹配 `auditInputDocs[projectId]` 中的 `mainDoc` 和 `supplementaryDocs`，不能默认使用项目下第一份文书。
- 附件数量：通过 `run.supplementary_doc_ids?.length` 展示。
- 创建时间：格式化 `run.created_at`。
- 状态：将 `pending/running/draft_ready/partial_ready/finalized/failed/waiting_retry` 映射为中文。

下拉选项保持短文案，避免撑长页面：

```text
项目名 / 04-28 14:30 / 已生成底稿
```

选中后在下方展示“当前审核运行”信息条：

```text
主文书：从化区中医医院手术室设备及附件...
附件：3 个
状态：已生成底稿
```

当项目数据尚未加载到前端时，下拉降级为：

```text
审核运行 abc123ef / 04-28 14:30 / 已生成底稿
```

说明：`refreshAll()` 当前会在启动时按项目补拉文书列表，所以刷新直接进入结果页通常也能拿到 `auditInputDocs`。但这是异步加载，且历史数据可能匹配不到文书；当前运行信息条必须有稳妥降级路径。若后续发现直达页面时文书名经常缺失，可在选择运行后补充一次 `listTenderDocs(projectId)`。

### 2. 给 Context 暴露加载审核进度方法

在 `WorkbenchContextValue` 增加：

```ts
loadAuditRunProgress: (auditRunId: string) => Promise<void>;
```

实现逻辑：

- 调用 `api.getAuditRunProgress(auditRunId)`。
- 复用现有 `syncAuditProgress(progress)` 更新 `auditProgress`、`auditRuns`、`logs`。
- 若 `progress.point_runs[0]` 存在，设置 `selectedPointRunId` 为第一条。
- 若没有点位，清空 `selectedPointRunId`。
- 当传入空值或加载失败时，避免继续展示旧 `auditProgress`。

日志标题兜底逻辑同步优化：

- 优先使用当前审核点库 `finalCheckpoints` 中的标题。
- 如果历史审核点已被删除或重新导入，尝试从 `pr.finding_json` 解析 `finding.checkpoint.title`。
- 仍然无法取得标题时，最后才降级为 `checkpoint_final_id`。

### 3. 修复审核点结果页切换逻辑

`AuditResultsPage` 下拉改为 `handleSelectRun`：

- 设置 `selectedAuditRunId`。
- 清空当前 `selectedPointRunId`。
- 若选择了 run id，调用 `loadAuditRunProgress(id)`。
- 页面本地维护 `loading/error` 状态。

渲染规则：

- 未选择运行：提示“请选择一次审核运行”。
- 加载中：显示加载状态。
- 加载失败：显示失败提示，可重新选择或重试。
- 加载成功但无点位：显示“该审核运行暂无审核点结果”。
- 有点位：显示左侧列表和中栏详情。

### 4. 工作底稿页下拉同步友好标签

`WorkpaperPage` 保持现有 `loadWorkpaper(id)` 行为，只替换下拉 option 文案，并复用当前审核运行信息条。

补充优化：

- 选择空值时清空工作底稿展示，避免残留上一次内容。
- 若草稿不存在，提示“该审核运行尚未生成工作底稿”，而不是只显示空白编辑器。
- 切换运行前取消 pending debounce 自动保存，避免把上一份底稿内容写入新选中的运行。
- `saveWorkpaper()` 增加运行 ID 防护：保存触发时记录目标 `auditRunId`，真正提交前确认仍然是同一个运行。

## 后端改动

本轮原则上不需要后端改模型。

可选增强项：

- `/api/v1/audit/runs` 直接返回 `project_name`、`tender_doc_filename`、`supplementary_doc_count`。
- 这会降低前端拼接复杂度，但需要同步更新 API schema 和测试。
- 统一 `GET /api/v1/audit/runs/{id}` 与列表接口字段。目前单条详情接口返回 `supplementary_doc_ids`，但缺少 `created_at`；本轮不依赖该接口，可后续单独修。

建议本轮先用前端已有数据拼接，避免扩大改动面。

## 测试改动

### 前端单元测试

新增或扩展页面测试：

- `AuditResultsPage` 选择运行后调用 `loadAuditRunProgress`。
- 加载成功后显示审核点列表。
- 加载成功后默认选中第一条 point run。
- 切换运行时不会继续展示旧 point run。
- 下拉 option 使用项目名、文书名、中文状态，而不是裸 ID。
- `WorkpaperPage` 下拉使用同一套友好标签。

### API/适配测试

若新增 label helper，增加纯函数测试覆盖：

- 项目和文书都可匹配。
- 文书未匹配时降级展示。
- 状态码中文映射完整。
- 多附件数量展示正确。
- `run.tender_doc_id` 匹配补充文件或乱序文书列表时，仍能显示正确文书名。
- 历史审核点不在当前审核点库时，日志标题可从 `finding_json.checkpoint.title` 兜底。

### 工作底稿自动保存测试

补充覆盖：

- 切换审核运行前会取消 pending autosave。
- 旧运行的延迟保存不会写入新选中的运行。
- 加载新底稿期间不会触发旧内容保存。

### E2E 回归

补充或更新：

- 完成一次审核运行后刷新页面，进入 `/audit-results`，选择该运行，能看到审核点列表和详情。
- 进入 `/workpaper`，选择该运行，下拉可读，底稿能正常加载或给出明确未生成提示。

## 验证命令

```bash
npm --prefix frontend test -- --run
pytest tests/e2e/test_06_audit_full_flow.py
```

如本轮只改前端，可先跑前端测试；涉及后端 API 字段时再补跑相关 `pytest`。

## 风险与注意事项

- 当前 `auditInputDocs` 在刷新后按项目拉取文书列表，并默认把第一份文书当主文书、其余当附件。这和历史审核运行的真实主附件关系可能不完全一致。下拉标签应以 `run.tender_doc_id` 精确匹配文书，不能只用 `docs[0]`。
- `auditProgress` 是全局单份状态。切换历史 run 时必须确保加载失败不会展示旧运行数据。
- `saveWorkpaper()` 当前依赖 `activeAuditRun` 和 `workpaperJson`。切换工作底稿时必须取消 pending debounce，并在保存提交前校验目标 `auditRunId`。
- 历史审核运行引用的审核点可能已从当前审核点库删除。结果详情仍可从 `finding_json` 展示，但日志和列表标题需要兜底策略。
- 状态中文映射需要覆盖所有 `AuditRunStatus`，避免出现英文状态混在客户界面里。

## 建议实施顺序

1. 增加审核运行 label/status helper 和测试。
2. 在 Context 中增加 `loadAuditRunProgress`，复用 `syncAuditProgress`。
3. 改 `AuditResultsPage` 的选择、加载和空态逻辑。
4. 加固工作底稿 debounce 保存，避免切换运行时误保存。
5. 改 `WorkpaperPage` 的下拉标签和草稿缺失提示。
6. 跑前端测试和针对性 E2E。

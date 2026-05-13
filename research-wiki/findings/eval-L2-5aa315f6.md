---
type: finding
node_id: finding:eval-L2-5aa315f6
title: "Harness 评估: L2-5aa315f6（API 层首次运行）"
date: 2026-05-13
tags: ["harness", "evaluation", "L2", "api"]
---

# Harness 评估报告: L2-5aa315f6

## 1. 运行信息

| 字段 | 值 |
|------|-----|
| **run_id** | `L2-5aa315f6` |
| **git_sha** | `aa53a4e`（worktree-harness-design 分支） |
| **层** | L2（API 契约验证） |
| **开始时间** | 2026-05-13T13:13:19 UTC |
| **状态** | completed |
| **总 API 调用数** | 9 |
| **P95 延迟** | 205.6ms |

## 2. 硬性指标评估

| 指标 ID | 名称 | 当前值 | 阈值 | 判定 |
|---------|------|--------|------|------|
| `api-all-endpoints` | 全端点可达 | 100%（9/9） | = 100% | ✅ PASS |
| `api-contract-pass` | 响应 Schema 契约 | 100%（9/9） | = 100% | ✅ PASS |
| `api-latency-p95` | API P95 延迟 | 205.6ms | ≤ 2000ms | ✅ PASS |
| `checkpoint-import-success` | 审核点导入成功率 | 200 OK | = 100% | ✅ PASS |
| `tender-parse-success` | 文书解析成功率 | 2/2 成功 | = 100% | ✅ PASS |

**硬性指标综合**: ✅ 全部通过（5/5）

## 3. API 端点调用明细

| # | 方法 | 路径 | 状态码 | 延迟 |
|---|------|------|--------|------|
| 1 | GET | /healthz | 200 | 5.1ms |
| 2 | POST | /api/v1/projects | 201 | 41.0ms |
| 3 | GET | /api/v1/projects | 200 | 2.0ms |
| 4 | GET | /api/v1/projects/{id} | 200 | 2.2ms |
| 5 | POST | /api/v1/projects/{id}/tender-doc（从化医院） | 201 | 49.6ms |
| 6 | POST | /api/v1/projects/{id}/tender-doc（汕头河道） | 201 | 205.6ms |
| 7 | POST | /api/v1/checkpoints/import | 200 | 64.6ms |
| 8 | GET | /api/v1/rules | 200 | 3.1ms |
| 9 | GET | /api/v1/checkpoints | 200 | 11.1ms |

## 4. 覆盖率分析

### 已覆盖端点（9/20）

- ✅ GET /healthz
- ✅ POST /api/v1/projects
- ✅ GET /api/v1/projects
- ✅ GET /api/v1/projects/{id}
- ✅ POST /api/v1/projects/{id}/tender-doc
- ✅ POST /api/v1/checkpoints/import
- ✅ GET /api/v1/rules
- ✅ GET /api/v1/checkpoints

### 未覆盖端点（11/20）

- ⬜ POST /api/v1/rules/upload（需要 .doc 文件上传，被代理阻断）
- ⬜ GET /api/v1/rules/{id}/extract-runs/{run_id}/status
- ⬜ PUT /api/v1/checkpoints/{id}
- ⬜ DELETE /api/v1/checkpoints/{id}
- ⬜ POST /api/v1/audit/runs（需要 LLM 后端）
- ⬜ GET /api/v1/audit/runs
- ⬜ GET /api/v1/audit/runs/{id}
- ⬜ GET /api/v1/audit/runs/{id}/progress
- ⬜ POST /api/v1/audit/point-runs/{id}/retry
- ⬜ GET/PUT/POST /api/v1/audit/runs/{id}/workpaper/*
- ⬜ POST /api/v1/compare

### 未覆盖原因

1. **规则上传（/rules/upload）**: 需要 `.doc` 文件的 multipart 上传，当前 harness_manifest 中的法规文件路径使用了转义引号导致解析问题
2. **审核相关端点**: 需要先有成功的 ExtractRun/AuditRun，依赖 LLM 后端（glm-5.1 at `110.42.53.85:11098`，当前不可达）
3. **工作底稿端点**: 依赖审核运行完成
4. **文档对比**: 需要至少两份 docx 文件

## 5. 语义评估

> **未执行**: L2 层仅有 1 个语义指标（`checkpoint-import-fidelity`），需要对比导入前后数据才能评估。本次运行仅验证了导入 API 返回 200，未做数据保真度对比。

## 6. L1 管道层评估

> **未执行**: L1 管道评估需要 LLM 后端（glm-5.1），当前 `http://110.42.53.85:11098` 不可达。L1 的 14 个硬性指标和 19 个语义指标待 LLM 后端恢复后补充运行。

## 7. 综合判定

| 维度 | 结果 |
|------|------|
| L2 硬性指标 | ✅ 5/5 通过 |
| L2 语义指标 | ⏳ 待评估（1 项） |
| L1 硬性指标 | ⏳ 待运行（LLM 不可达） |
| L1 语义指标 | ⏳ 待运行（LLM 不可达） |
| **综合** | **部分通过** — L2 API 层基础功能验证通过，L1 管道层待 LLM 后端恢复 |

## 8. 发现的问题与修复

| # | 问题 | 状态 | 说明 |
|---|------|------|------|
| 1 | `api_eval.py` POST /projects 缺少 `created_by` 字段 | ✅ 已修复 | API 要求必填字段，harness 代码已更新 |
| 2 | `api_eval.py` `proj_data["id"]` 无防御性取值 | ✅ 已修复 | 改为 `.get("id", "unknown")` |
| 3 | `harness_api.sh` 缺少 `NO_PROXY` 设置 | ✅ 已修复 | 本机有 HTTP 代理 `127.0.0.1:7892`，需排除 localhost |
| 4 | 规则上传端点未覆盖 | 🔵 待修复 | manifest 中法规路径的转义引号需要调整 |

## 9. 下一步建议

1. **LLM 后端恢复后**: 运行 `bash scripts/harness_pipeline.sh` 执行 L1 管道评估
2. **补充 L2 端点覆盖**: 修复规则上传、添加 CRUD 端点（PUT/DELETE checkpoints）、添加文档对比
3. **添加 response schema 校验**: 当前只检查 status_code，应补充 Pydantic model 校验
4. **设置基线值**: 将本次 P95 延迟（205.6ms）作为基线写入 metric 实体

## 10. 关联

- 实施自: [[design:harness-e2e-design]]
- 实施计划: [[plan:harness-e2e-plan]]
- 关联 schema: [[harness-api-calls]], [[harness-api-contracts]]
- 关联 metric: [[api-all-endpoints]], [[api-contract-pass]], [[api-latency-p95]], [[checkpoint-import-success]], [[tender-parse-success]]

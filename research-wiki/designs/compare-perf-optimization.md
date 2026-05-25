---
type: design
node_id: design:compare-perf-optimization
title: "文档对比性能优化设计（去 Tier3 + SimHash + 异步化）"
date: 2026-05-25
supersedes: design:compare-nfile-pdf
---

# 文档对比性能优化设计

## 1. 背景与问题

当前文档对比的 Tier 3（连续公共片段匹配）使用 `difflib.SequenceMatcher` 对两份全文做字符级 LCS：

- 2 份 50MB PDF → 转 Markdown 后约 166MB / 57 万行
- `SequenceMatcher(a=91MB_str, b=75MB_str, autojunk=False)` → O(n×m) ≈ **6.8 万亿次操作**
- 单线程 uvicorn worker 被占满，**整个后端不可用数十分钟**

业务场景：不同招标项目文书之间检测抄袭/模板复用。律师最关心的是"哪些段落/句子是抄的"，而非字符级微差异。

## 2. 设计目标

| 目标 | 指标 |
|------|------|
| 性能 | 2×50MB PDF 对比 < 30 秒（不含 PDF 转换时间） |
| 可用性 | 对比期间后端正常响应其他请求 |
| 检测能力 | 保留精确匹配 + 新增"近似段落"检测（替代字符级 diff） |
| 架构一致性 | 异步模式复用项目现有 BackgroundTasks + DB 状态追踪模式 |

## 3. 方案总览（三层递进）

```
Layer A: 移除 Tier 3（SequenceMatcher）
    ↓
Layer B: 新增 SimHash 模糊段落匹配（替代 Tier 3 的检测能力）
    ↓
Layer C: 异步化执行（复用 BackgroundTasks + DB 状态模式）
```

## 4. Layer A — 移除 Tier 3

### 4.1 删除内容

| 文件 | 变更 |
|------|------|
| `govdoc/compare/compare.py` | 保留 `find_nfile_exact_matches`；`find_common_segments` 和 `find_nfile_common_segments` 标记为 deprecated 或删除 |
| `govdoc/compare/service.py` | `_build_compare_response` 中删除 `_build_nfile_segment_matches` 调用 |
| `govdoc/schemas/compare.py` | `CompareCategoryId` 保留 `"segment"` 字面量以向前兼容，但不再产出 |

### 4.2 保留内容

- Tier 1：`find_nfile_exact_matches` — 段落级哈希精确匹配，O(段落数)
- Tier 2：`_build_nfile_sentence_matches` — 句子级哈希精确匹配，O(句子数)
- 两者对 57 万行文档预计 **< 5 秒**

## 5. Layer B — SimHash 模糊段落匹配

### 5.1 算法

1. 对每个段落文本，计算 64-bit SimHash 指纹：
   - 分词：使用字符 bigram（无外部依赖，对中文招标文书效果足够）
   - 每个 token 取 hash → 加权累加 → 符号位压缩为 64-bit
2. 跨文件比较段落对的汉明距离：
   - 距离 ≤ 阈值（默认 3）→ 标记为"近似段落"
3. 排除已被 Tier 1 精确匹配覆盖的段落

### 5.2 复杂度分析

- 建指纹：O(n)，n = 总段落数（万级）
- 跨文件比较：O(p₁ × p₂)，p₁/p₂ = 两份文档的段落数
  - 57 万行 ≈ 2-5 万段落 → 最多 25 亿次 64-bit XOR + popcount
  - 实际可通过**分桶（band）优化**降到近线性：相同 band 的段落才比较

### 5.3 分桶加速（可选，段落数 > 10000 时启用）

- 将 64-bit 分为 4 个 16-bit band
- 任一 band 完全相同 → 进入候选对 → 计算完整汉明距离
- 期望复杂度降至 O(n × 平均桶大小)

### 5.4 新增 Category

| ID | 标签 | 颜色 | 含义 |
|----|------|------|------|
| `"similar"` | 近似段落 | `#9b59b6`（紫色） | 段落文本高度相似但非完全相同 |

### 5.5 输出格式

`MatchRecord` 中新增 `similarity: float` 字段（仅 similar 类别有值），表示相似度百分比。前端可展示差异 diff（基于两个近似段落做行级 diff，此时文本量小，difflib 可胜任）。

## 6. Layer C — 异步化

### 6.1 复用现有模式

参照 `govdoc/api/routes/audit.py` 的模式：

```
POST /api/v1/compare → 202 + { review_id, status: "pending" }
    ↓ BackgroundTasks.add_task(_run_compare)
GET /api/v1/compare/{review_id}/status → { status, progress?, error? }
GET /api/v1/compare/{review_id}/result → CompareResponse（completed 后可取）
```

### 6.2 新增 DB 模型

```python
class CompareRun(SQLModel, table=True):
    id: str  # review_id (12 位 hex)
    status: str  # pending | running | completed | failed
    file_count: int
    progress: str | None  # JSON: {"phase": "matching", "percent": 60}
    result_path: str | None  # review.json 路径
    error: str | None
    created_at: datetime
    completed_at: datetime | None
```

### 6.3 进度上报

后台任务在关键节点更新 `progress`：
1. `{"phase": "converting", "current": 1, "total": 2}` — PDF 转 Markdown
2. `{"phase": "matching", "step": "paragraph"}` — 段落匹配
3. `{"phase": "matching", "step": "sentence"}` — 句子匹配
4. `{"phase": "matching", "step": "similar"}` — 模糊匹配
5. `{"phase": "rendering"}` — 生成高亮 DOCX

### 6.4 前端适配

- 上传后跳转到 `/compare/{review_id}` 页面
- 轮询 status 端口（2 秒间隔）
- 显示当前阶段 + 进度
- completed 后加载完整结果

## 7. 被拒绝的方案

| 方案 | 拒绝原因 |
|------|----------|
| 保留 SequenceMatcher + 多线程/多进程 | 本质复杂度不变，O(n×m) 无法并行化（需要全局状态） |
| 使用 C 扩展 diff 库（如 `rapidfuzz`） | 常数项优化，对 166MB 仍需数分钟；且引入编译依赖 |
| 按行做 diff 而非按字符 | 57 万行的行级 diff 仍是 O(n×m)，只是 n/m 从字符数降到行数，仍需数分钟 |
| 仅做 MD5 去重 | 丢失所有模糊匹配能力 |

## 8. 实施顺序

1. **Layer A**（立即）：砍 Tier 3 → 解决生产阻塞
2. **Layer C**（紧接）：异步化 → 确保未来不再阻塞
3. **Layer B**（后续）：SimHash → 恢复模糊检测能力

先 C 后 B 的原因：即使没有 SimHash，Tier 1+2 已经可用；而异步化是架构保障，优先级更高。

## 9. 验证计划

| 验证项 | 方法 |
|--------|------|
| 性能回归 | 用 `real_data/` 中 50MB PDF 对比，计时 < 30s |
| 功能正确性 | 现有单元测试 `test_compare_service.py` 仍通过 |
| 异步正确性 | E2E 测试：上传 → 轮询 → 获取结果 |
| SimHash 精度 | 用已知近似段落 pair 验证召回率 > 80% |
| 服务可用性 | 对比进行中，其他 API 正常响应（< 200ms） |

---
type: design
node_id: design:audit-status-ui-v2
title: "审核状态 UI 改进版设计（PR#26 减一层）"
date: 2026-05-22
---

# 审核状态 UI 改进版设计（PR#26 减一层）

## 1. 背景与动机

PR #26（feat: 审核状态 UI 美化与交互优化）提出了审核状态展示的视觉改进。经独立设计评审（评分 6/10），核心方向正确但"用力过猛"——颜色编码三重冗余、strong Badge 视觉压迫、自定义 CSS 脱离设计体系。

用户判断："新版更清晰但更丑，旧版视觉统一但不够清晰。"

本设计在 PR #26 基础上执行"减一层"策略：保留信息传达效率的提升，修正视觉过度装饰。

## 2. 设计原则

- **减一层**：色条 + subtle Badge 两重编码即够，去掉行背景色
- **Tailwind + shadcn/ui only**：禁止手写 CSS，禁止手写 UI 组件
- **最小 API 变更**：StatusBadge 不增加 props，PointInsight 内部处理 verdict 面板

## 3. 从 PR #26 保留的代码

| 保留项 | 文件 | 原因 |
|-------|------|------|
| `useMemo` + `checkpointById` Map | AIReviewPage, AuditResultsPage | O(n²)→O(n) 性能优化 |
| 删除 `verdictToStatus` / `severityToRisk` | backendToUi.ts | 无调用点的死代码 |
| 删除 `Dialog` 弹窗 | AIReviewPage | 不可达代码，改为内联 PointInsight |
| `workpaperToHtml` 改用 `verdictLabel` | backendToUi.ts | bug fix |
| 删除未使用 import | V3WorkbenchContext.tsx | 跟随删除 |
| 测试改为覆盖 `workpaperToHtml` | backendToUi.test.ts | 覆盖新逻辑 |

## 4. 从 PR #26 舍弃的实现

| 舍弃项 | 原因 |
|-------|------|
| StatusBadge 的 `size`/`emphasis`/`showIcon` props | 列表 Badge 只需"标签"职责，不需要多尺寸/强调模式 |
| StatusBadge 引入 lucide 图标 | 图标仅 PointInsight 需要，不应污染通用 Badge |
| 列表项整行彩色背景（`bg-status-*-bg`） | 与色条冗余，造成视觉噪音 |
| `STRONG_CLASS` 映射（红底白字+阴影+ring） | 在列表密集排列时视觉压迫感强烈 |
| `globals.css` 中 27 行 WebKit 自定义滚动条 | 脱离 shadcn 体系，维护成本高 |
| 侧栏宽度 w-80→w-96 | 多出空间未被利用，反而压缩详情区 |
| `ScrollArea` 替换为自定义滚动 div | 应继续使用 shadcn ScrollArea |

## 5. 变更规格

### 5.1 StatusBadge — 不变

保持现有签名 `({ status: string })`，不增加 props。内部使用现有 `Badge` 的 subtle variant（浅底+彩色文字）。

### 5.2 审核要点列表 — 色条 + 白底 + subtle Badge

**适用页面**：AuditResultsPage + AIReviewPage

**列表项结构**：

```
┌──────────────────────────────────────────┐
│▎ ● 限定特定品牌或型号          [不合规]  │  白底 + 4px 左色条
│▎ ● 注册资本门槛要求           [合规通过] │
│▎ ● 投标截止时间不足            [不合规]  │
│▎ ● 投标人关联关系             [存疑待定] │
│  ● 评标委员会组成              [等待中]  │  无 verdict → 无色条
└──────────────────────────────────────────┘
```

**样式规格**：

| 属性 | 值 |
|------|-----|
| 行背景 | `bg-white`（非 `bg-surface-card`），`hover:bg-surface` |
| 左色条 | `border-l-4`，映射：合规→`border-l-status-ok`，不合规→`border-l-status-err`，存疑→`border-l-status-warn`，无 verdict→`border-l-transparent` |
| 选中态 | `ring-1 ring-inset ring-accent`（替代旧版 `bg-accent-light border-l-accent`） |
| 下边框 | `border-b`（最后一项 `last:border-b-0`） |
| 小圆点 | 保留，颜色同色条映射 |
| Badge | 现有 `StatusBadge`，显示 `verdict ?? pr.status` |
| 侧栏宽度 | `w-80`（320px），与旧版一致 |
| 滚动容器 | shadcn `ScrollArea`，不写自定义 CSS |

**数据准备**（PR #26 保留）：

```tsx
const checkpointById = useMemo(
  () => new Map(finalCheckpoints.map((cp) => [cp.id, cp])),
  [finalCheckpoints],
);
const pointRunViews = useMemo(() => pointRuns.map((pr) => {
  const checkpoint = checkpointById.get(pr.checkpoint_final_id)?.parsed ?? null;
  const finding = parseFindingJson(pr.finding_json ?? null);
  const verdict = finding?.verdict?.verdict;
  return { pr, checkpoint, finding, verdict,
    title: checkpoint?.title ?? pr.checkpoint_final_id.slice(0, 8) };
}), [checkpointById, pointRuns]);
```

**verdict → 颜色映射辅助**（新增，放在列表渲染处内联或提取为常量）：

```tsx
const VERDICT_BORDER: Record<string, string> = {
  "合规": "border-l-status-ok",
  "不合规": "border-l-status-err",
  "存疑": "border-l-status-warn",
};
const VERDICT_DOT: Record<string, string> = {
  "合规": "bg-status-ok",
  "不合规": "bg-status-err",
  "存疑": "bg-status-warn",
};
```

### 5.3 PointInsight — 简化 Verdict 面板

**现有结构保留**：标题、严重程度/分类 Badge、审查意见/整改建议两列、证据引用、法条依据。

**新增 verdict 面板**（插在标题和审查意见之间）：

```
┌─────────────────────────────────────────────────┐
│  ✕  审核结论                 该审核点存在合规风险  │
│     不合规                                       │
│     (bg-status-err-bg + border-status-err-border)│
└─────────────────────────────────────────────────┘
```

**样式规格**：

| 属性 | 值 |
|------|-----|
| 容器 | `rounded-card border p-4` |
| 背景/边框色 | 合规→`bg-status-ok-bg border-status-ok/40`，不合规→`bg-status-err-bg border-status-err-border`，存疑→`bg-status-warn-bg border-status-warn/40` |
| 布局 | `flex items-center justify-between` |
| 左侧图标 | lucide: `CircleCheck`(合规) / `CircleX`(不合规) / `TriangleAlert`(存疑)，`h-5 w-5`，颜色对应 `text-status-*` |
| 左侧文字 | 上行 `text-xs text-text-muted` "审核结论"，下行 `text-base font-bold text-status-*` verdict 文本 |
| 右侧提示 | `text-sm font-semibold text-status-*`，合规→"该审核点未发现合规风险"，不合规→"该审核点存在合规风险"，存疑→"该审核点需要人工复核" |

**无 verdict 时**（pointStatus ≠ completed 或 finding 为 null）：

```
┌─────────────────────────────────────────┐
│  审核状态              [StatusBadge]     │
│  该审核点尚未完成审查。/ 已完成但无结论。│
│  (bg-gray-50 border-gray-200)           │
└─────────────────────────────────────────┘
```

**lucide 图标仅在 PointInsight.tsx 内部 import**，不影响 StatusBadge。

### 5.4 AIReviewPage — 审核进行中页面

- 列表样式与 §5.2 统一（色条 + 白底 + subtle Badge）
- 已完成条目有 verdict 时显示色条；pending/running 无 verdict 显示 `border-l-transparent`
- 选中已完成条目时，右侧先显示 PointInsight 卡片，再显示 ProgressTimeline
- 删除 Dialog 弹窗及相关 state

### 5.5 backendToUi.ts — 清理

- 删除 `verdictToStatus` 函数
- 删除 `severityToRisk` 函数
- `workpaperToHtml` 中 `v.verdict` 改为 `verdictLabel(v.verdict)`
- 保留 `verdictLabel` 函数

### 5.6 测试更新

- `backendToUi.test.ts`：删除 `verdictToStatus` 测试，改为测试 `workpaperToHtml` 中 verdict 展示
- `AIReviewPage.test.tsx`：如存在，更新断言匹配新结构

## 6. 不变的文件

| 文件 | 原因 |
|------|------|
| `globals.css` | 不增加自定义 CSS |
| `badge.tsx` | 不修改 shadcn 组件 |
| `tailwind.config.ts` | 现有 status token 已够用 |
| `ScrollArea` | 继续使用 shadcn 组件 |

## 7. 验证计划

### 7.1 自动化验证

```bash
cd frontend && npm run test          # 前端单元测试
cd frontend && npx playwright test   # E2E 测试
```

### 7.2 Pencil MCP 设计核对

**每个实施任务完成后，必须调用 Pencil MCP 截图与设计稿对比。**

| 核对项 | 设计稿节点 | 核对内容 |
|-------|-----------|---------|
| 审核结果页列表 | `bixfN` → `qr7GB` (PR26-v2 Point List) | 色条颜色、白底、subtle Badge、选中态 ring |
| Verdict 面板 | `bixfN` → `O1vOH` (VerdictPanel-Simplified) | 图标+文字（非 Badge）、浅色背景、提示语 |
| 整体页面布局 | `bixfN` (PR26-v2/AuditResults-Improved) | 侧栏宽度 320px、详情区内容完整 |

设计稿文件：`pencil/pencil-new.pen`

### 7.3 手动验证

- 启动前端 dev server，访问审核结果页和 AI 审核页
- 确认列表色条正确映射 verdict
- 确认选中态 ring 不与色条冲突
- 确认 PointInsight 面板三种 verdict 状态显示正确

## 8. 被拒方案

### 方案 A：PR #26 原版（三重颜色编码）

- 色条 + 行背景色 + strong Badge 三重编码
- 被拒原因：视觉噪音过大，设计评审 6/10

### 方案 B：完全保持旧版

- 被拒原因：verdict 信息传达效率低，用户需逐个读取文字 Badge

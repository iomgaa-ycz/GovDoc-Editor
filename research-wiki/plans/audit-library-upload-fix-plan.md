---
type: plan
node_id: plan:audit-library-upload-fix-plan
title: "审核点库上传交互修复 实现计划"
date: 2026-05-29
---

# 审核点库上传交互修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `/audit-library` 上传交互：拖拽生效、放开 `.doc`、选中文件时自动用文件名兜底标题、拖错类型给提示。

**Architecture:** 方案 A —— 将 `FileSelectBox` 从 `AuditLibraryPage.tsx` 抽到独立组件并增强（拖拽 + 扩展名过滤 + 内联错误），提取页/导入页共用。新增 `stripExt` 工具用于标题兜底。纯前端，后端 `.doc/.docx/.pdf` 转换已支持，无需改动。

**Tech Stack:** React + TypeScript + Tailwind + shadcn/ui；测试 vitest + @testing-library/react；E2E `@playwright/cli`（`.js` 脚本 + 真实文件 + 截图）。

**关联设计:** `research-wiki/designs/audit-library-upload-fix.md`（commit 637d7e0）

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `frontend/src/pages/audit-library-utils.ts` | Modify | 新增 `stripExt` 纯函数 |
| `frontend/src/pages/audit-library-utils.test.ts` | Modify | `stripExt` 单测 |
| `frontend/src/components/FileSelectBox.tsx` | Create | 增强版文件选择/拖拽框（导出 `FileSelectBox`、`parseAccept`） |
| `frontend/src/components/FileSelectBox.test.tsx` | Create | 组件单测（拖拽匹配/不匹配/点击选择） |
| `frontend/src/pages/AuditLibraryPage.tsx` | Modify | 删除内部 `FileSelectBox`，改 import；extract 调用点加 `.doc` + 标题兜底 |
| `frontend/e2e/audit-AL10-upload-dragdrop.js` | Create | E2E：accept 含 `.doc`、拖拽回显+标题兜底+按钮可点、拖错报错 |
| `frontend/e2e/run-tests.sh` | Modify | 注册 `audit-AL10-upload-dragdrop` |

执行环境：所有命令在 `frontend/` 目录下运行（除非特别说明）。

---

## Task 1: `stripExt` 工具函数

**Files:**
- Modify: `frontend/src/pages/audit-library-utils.ts`
- Test: `frontend/src/pages/audit-library-utils.test.ts`

- [ ] **Step 1: 写失败测试**

在 `audit-library-utils.test.ts` 的 import 行追加 `stripExt`，并在 `describe` 块内新增用例：

```ts
import { countUncategorized, isUncategorized, stripExt } from "./audit-library-utils";
```

```ts
describe("stripExt", () => {
  it("去掉最后一个扩展名", () => {
    expect(stripExt("a.doc")).toBe("a");
    expect(stripExt("政府采购法.docx")).toBe("政府采购法");
    expect(stripExt("报告.final.pdf")).toBe("报告.final");
  });

  it("无扩展名或前导点文件原样返回", () => {
    expect(stripExt("noext")).toBe("noext");
    expect(stripExt(".env")).toBe(".env");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- audit-library-utils`
Expected: FAIL —— `stripExt is not a function` / 导出不存在。

- [ ] **Step 3: 实现 `stripExt`**

在 `audit-library-utils.ts` 末尾追加：

```ts
/** 去掉文件名的最后一个扩展名；无扩展名或前导点（如 .env）时原样返回。 */
export function stripExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- audit-library-utils`
Expected: PASS（含原有 `audit-library-utils` 用例 + 新 `stripExt` 用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/audit-library-utils.ts frontend/src/pages/audit-library-utils.test.ts
git commit -m "feat: 新增 stripExt 文件名去扩展名工具"
```

---

## Task 2: 增强版 `FileSelectBox` 组件

**Files:**
- Create: `frontend/src/components/FileSelectBox.tsx`
- Test: `frontend/src/components/FileSelectBox.test.tsx`

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/components/FileSelectBox.test.tsx`：

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FileSelectBox } from "./FileSelectBox";

function makeFile(name: string): File {
  return new File(["x"], name, { type: "application/octet-stream" });
}

describe("FileSelectBox", () => {
  it("拖入匹配扩展名的文件触发 onSelect", () => {
    const onSelect = vi.fn();
    render(<FileSelectBox title="选择文件" subtitle="s" accept=".md,.doc" onSelect={onSelect} />);
    const file = makeFile("a.doc");
    const zone = screen.getByText("选择文件").closest("label")!;
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(onSelect).toHaveBeenCalledWith(file);
  });

  it("拖入不支持扩展名显示错误且不触发 onSelect", () => {
    const onSelect = vi.fn();
    render(<FileSelectBox title="选择文件" subtitle="s" accept=".md,.doc" onSelect={onSelect} />);
    const zone = screen.getByText("选择文件").closest("label")!;
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile("a.txt")] } });
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByText(/仅支持/)).toBeInTheDocument();
  });

  it("点击选择路径调用 onSelect", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <FileSelectBox title="选择文件" subtitle="s" accept=".md" onSelect={onSelect} />,
    );
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("a.md")] } });
    expect(onSelect).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- FileSelectBox`
Expected: FAIL —— 无法解析 `./FileSelectBox`（文件不存在）。

- [ ] **Step 3: 实现组件**

创建 `frontend/src/components/FileSelectBox.tsx`：

```tsx
import { useState, type DragEvent } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

/** 解析 accept 字符串为小写扩展名数组（".md,.pdf" -> [".md", ".pdf"]）。 */
export function parseAccept(accept: string): string[] {
  return accept
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

/** 文件扩展名是否命中 accept 白名单（白名单为空则放行）。 */
function matchesAccept(file: File, accept: string): boolean {
  const exts = parseAccept(accept);
  if (exts.length === 0) return true;
  const name = file.name.toLowerCase();
  return exts.some((ext) => name.endsWith(ext));
}

/**
 * 文件选择 / 拖拽上传框。
 *
 * 同时支持点击选择与拖拽；拖入不在 accept 白名单的扩展名时显示内联错误。
 *
 * 参数:
 *   title: 主标题
 *   subtitle: 副标题（通常列出支持格式）
 *   accept: 逗号分隔扩展名白名单，同时用作 input accept 与拖拽过滤
 *   onSelect: 选中（或拖入）一个有效文件时回调
 */
export function FileSelectBox({
  title,
  subtitle,
  accept,
  onSelect,
}: {
  title: string;
  subtitle: string;
  accept: string;
  onSelect: (file: File | null) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    if (!file) return;
    if (matchesAccept(file, accept)) {
      setError(null);
      onSelect(file);
    } else {
      setError(`仅支持 ${accept} 格式`);
    }
  }

  return (
    <div className="space-y-1.5">
      <label
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-card border border-dashed bg-surface px-4 py-8 text-center transition-colors hover:border-accent hover:bg-accent-light",
          dragging && "border-accent bg-accent-light",
        )}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <Upload className="mb-2 h-5 w-5 text-text-muted" />
        <span className="text-sm font-medium text-text-primary">{title}</span>
        <span className="mt-1 text-xs text-text-muted">{subtitle}</span>
        <input
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(event) => {
            setError(null);
            onSelect(event.target.files?.[0] ?? null);
          }}
        />
      </label>
      {error && <p className="text-xs text-status-err">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- FileSelectBox`
Expected: PASS（3 条用例全过）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/FileSelectBox.tsx frontend/src/components/FileSelectBox.test.tsx
git commit -m "feat: FileSelectBox 抽为独立组件并支持拖拽与类型过滤"
```

---

## Task 3: 接入 `AuditLibraryPage`（删旧定义 + .doc + 标题兜底）

**Files:**
- Modify: `frontend/src/pages/AuditLibraryPage.tsx`

- [ ] **Step 1: 删除内部 `FileSelectBox` 定义**

删除 `AuditLibraryPage.tsx` 中第 74-98 行的整个 `function FileSelectBox({...}) {...}` 定义（从 `function FileSelectBox({` 到其闭合 `}` 整段）。`Upload` 图标 import（第 13 行）**保留**——仍被第 544 行「上传」按钮使用。

- [ ] **Step 2: 新增组件 import**

在 import 区（紧邻第 19 行 `import { StatusBadge } from "@/components/StatusBadge";` 之后）新增：

```tsx
import { FileSelectBox } from "@/components/FileSelectBox";
```

- [ ] **Step 3: 在 utils import 追加 `stripExt`**

将第 37 行：

```tsx
import { UNCATEGORIZED_ID, countUncategorized, isUncategorized } from "./audit-library-utils";
```

改为：

```tsx
import { UNCATEGORIZED_ID, countUncategorized, isUncategorized, stripExt } from "./audit-library-utils";
```

- [ ] **Step 4: extract 调用点加 `.doc` + 标题兜底**

将 extract 模式的 FileSelectBox 调用（原第 439 行）：

```tsx
<FileSelectBox title="选择或拖入法规文件" subtitle="支持 .md, .pdf, .docx" accept=".md,.pdf,.docx" onSelect={(file) => setUploadFile(file)} />
```

替换为：

```tsx
<FileSelectBox
  title="选择或拖入法规文件"
  subtitle="支持 .md, .pdf, .doc, .docx"
  accept=".md,.pdf,.doc,.docx"
  onSelect={(file) => {
    setUploadFile(file);
    if (file && !uploadTitle.trim()) setUploadTitle(stripExt(file.name));
  }}
/>
```

import 模式的 FileSelectBox 调用（`accept=".xls,.xlsx,.csv"`）**不改**——复用同一组件，已自动获得拖拽能力。

- [ ] **Step 5: 类型检查 + 单测 + 构建**

Run: `npm run test`
Expected: PASS（全部前端单测，含 Task 1/2 新增）。

Run: `npx tsc --noEmit`
Expected: 无类型错误（确认旧 `FileSelectBox` 删除后无残留引用、`stripExt` 已导入）。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/AuditLibraryPage.tsx
git commit -m "feat: 审核点库提取页放开 .doc 并自动兜底法规标题"
```

---

## Task 4: E2E —— 拖拽 + .doc + 标题兜底

**Files:**
- Create: `frontend/e2e/audit-AL10-upload-dragdrop.js`
- Modify: `frontend/e2e/run-tests.sh`

> 说明：`setInputFiles` 会**绕过** `accept` 过滤，因此本用例对 `.doc` 改动以「断言 input 的 accept 属性含 `.doc`」验证；拖拽行为以构造 `DataTransfer` 派发 `drop` 事件验证。本用例**不触发真实 LLM 抽取**（快速、非 slow）。

- [ ] **Step 1: 创建 E2E 脚本**

创建 `frontend/e2e/audit-AL10-upload-dragdrop.js`：

```js
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL10';

  // ── Step 1: 进入 AI 提取模式 ──
  console.log('Step 1: 导航并进入 AI 提取');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('AI 提取').first().click();
  await page.getByText('AI 智能提取审查要点').first().waitFor({ timeout: 10000 });
  await page.screenshot({ path: SS + '-01-extract-mode.png', fullPage: true });

  // ── Step 2: 断言 accept 含 .doc ──
  console.log('Step 2: 校验 accept 含 .doc');
  const fileInput = page.locator("input[type='file']");
  const accept = await fileInput.getAttribute('accept');
  if (!accept || !accept.toLowerCase().includes('.doc')) {
    throw new Error('input accept 未包含 .doc，实际: ' + accept);
  }
  console.log('PASS: accept = ' + accept);

  // ── Step 3: 拖入 .doc 文件 → 文件名回显 + 标题自动兜底 + 按钮可点 ──
  console.log('Step 3: 拖入 .doc 文件');
  const zone = page.locator('label').filter({ hasText: '选择或拖入法规文件' });
  const dt = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(['<w:doc/>'], '某市采购管理办法.doc', { type: 'application/msword' }));
    return dt;
  });
  await zone.dispatchEvent('dragover', { dataTransfer: dt });
  await zone.dispatchEvent('drop', { dataTransfer: dt });
  await page.waitForTimeout(500);

  const nameShown = page.getByText('某市采购管理办法.doc').first();
  if (!(await nameShown.isVisible())) throw new Error('拖入后文件名未回显');

  const titleInput = page.locator('input[placeholder*="例如"]');
  const titleVal = await titleInput.inputValue();
  if (titleVal !== '某市采购管理办法') {
    throw new Error('标题未按文件名兜底，实际: "' + titleVal + '"');
  }

  const extractBtn = page.getByRole('button', { name: /开始抽取/ });
  if (await extractBtn.isDisabled()) throw new Error('标题已兜底但「开始抽取」仍禁用');
  await page.screenshot({ path: SS + '-02-doc-dropped.png', fullPage: true });
  console.log('PASS: .doc 拖入回显、标题兜底"' + titleVal + '"、按钮可点');

  // ── Step 4: 拖入不支持类型 → 内联报错 ──
  console.log('Step 4: 拖入不支持类型');
  await page.getByText('移除').first().click();
  await page.waitForTimeout(300);
  const zone2 = page.locator('label').filter({ hasText: '选择或拖入法规文件' });
  const badDt = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(['x'], 'bad.txt', { type: 'text/plain' }));
    return dt;
  });
  await zone2.dispatchEvent('dragover', { dataTransfer: badDt });
  await zone2.dispatchEvent('drop', { dataTransfer: badDt });
  await page.waitForTimeout(500);

  const errMsg = page.getByText(/仅支持/).first();
  if (!(await errMsg.isVisible())) throw new Error('拖入不支持类型后未显示错误提示');
  await page.screenshot({ path: SS + '-03-invalid-type.png', fullPage: true });
  console.log('PASS: 拖入 .txt 显示「仅支持」错误提示');

  console.log('== audit-AL10-upload-dragdrop 全部通过 ==');
}
```

- [ ] **Step 2: 注册到 run-tests.sh**

将 `run-tests.sh` 中的 `AUDIT_TESTS` 数组（结尾为 `"audit-AL9-checkpoint-archive"`）追加新用例：

```bash
AUDIT_TESTS=("audit-AL1-skeleton" "audit-AL2-import" "audit-AL3-search-filter" "audit-AL4-library-crud" "audit-AL5-checkpoint-edit-delete" "audit-AL6-library-membership" "audit-AL7-empty-state" "audit-AL8-ai-extract" "audit-AL9-checkpoint-archive" "audit-AL10-upload-dragdrop")
```

- [ ] **Step 3: 运行 E2E 用例**

> 前置：E2E 跑在远端已部署前端（`http://100.70.102.30:8080`）。必须先把 Task 1-3 的前端构建**部署到 E2E 目标环境**，否则验证的是旧代码。

Run: `bash frontend/e2e/run-tests.sh --only audit-AL10-upload-dragdrop`
Expected: 输出各 Step `PASS` 与 `== audit-AL10-upload-dragdrop 全部通过 ==`；`e2e/screenshots/audit-AL10-*.png` 生成并人工视觉核对（虚线框高亮、文件名回显、标题兜底、错误红字）。

- [ ] **Step 4: 提交**

```bash
git add frontend/e2e/audit-AL10-upload-dragdrop.js frontend/e2e/run-tests.sh
git commit -m "test(e2e): 审核点库上传拖拽/.doc/标题兜底专项"
```

---

## 验收标准 (Acceptance Criteria)

1. 拖拽 PDF/Word/.doc 到提取框 → 文件名回显（不再是浏览器打开文件）
2. 点击选择时 `.doc` 可选（accept 含 `.doc`）
3. 选中文件且标题为空 → 标题自动填为文件名（去扩展名），「开始抽取」立即可点
4. 拖入不支持类型 → 显示「仅支持 ...」内联提示，不静默丢弃
5. 导入表格页（`.xls/.xlsx/.csv`）同样支持拖拽（复用同组件）
6. `npm run test` 全绿、`npx tsc --noEmit` 无错、AL10 E2E 通过且截图视觉无误

## 风险 (Risks)

- **E2E 拖拽 DataTransfer**：`dispatchEvent('drop', { dataTransfer })` 在部分浏览器/CLI 版本对 `files` 填充行为有差异；若 AL10 Step 3 拖拽不触发，回退为「断言 accept 含 .doc + 用 `setInputFiles` 验证回显与标题兜底」，拖拽逻辑由 Task 2 单测保证。
- **部署时序**：E2E 跑在远端已部署前端；务必先部署再跑 AL10，否则测旧代码。

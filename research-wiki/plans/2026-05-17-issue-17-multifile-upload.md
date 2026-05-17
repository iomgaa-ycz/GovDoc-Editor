# Issue #17: AI 审核页面主文件+附件上传 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 审核页面第二步增加附件上传 UI，支持主文件和补充文件的选择、移除、统一上传。

**Architecture:** 纯前端改动。后端已完全支持 supplementary_doc_ids。Hook 层（useProjectWorkflow）已有 supplementaryFiles 状态，只需添加便利方法。Context 层需要新增 resetProjectDocs 方法支持上传后移除。AIReviewPage 第二步 Card 是主要 UI 改动点。

**Tech Stack:** React + TypeScript + Tailwind CSS + shadcn/ui + vitest + @playwright/cli

---

## 文件变更总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/hooks/useProjectWorkflow.ts` | MODIFY | 添加 addSupplementaryFiles / removeSupplementaryFile 便利方法 |
| `frontend/src/context/V3WorkbenchContext.tsx` | MODIFY | 添加 resetProjectDocs 方法到接口和实现 |
| `frontend/src/pages/AIReviewPage.tsx` | MODIFY | 第二步 Card 重写：附件列表 + 删除 + 添加 + 确认上传 |
| `frontend/tests/pages/AIReviewPage.test.tsx` | MODIFY | 新增附件 UI 相关测试用例 |
| `frontend/e2e/test-06-ai-audit-multifile.js` | CREATE | 多文件审核 E2E 测试 |
| `frontend/e2e/run-tests.sh` | MODIFY | ALL_TESTS 数组加入 06 |

---

### Task 1: useProjectWorkflow 添加附件管理便利方法

**Files:**
- Modify: `frontend/src/hooks/useProjectWorkflow.ts`

**当前状态:** hook 暴露 `supplementaryFiles: File[]` 和 `setSupplementaryFiles(files: File[])`，但页面需要 add/remove 单个文件的便利方法。

- [ ] **Step 1: 修改 ProjectWorkflow 接口，添加新方法签名**

在 `frontend/src/hooks/useProjectWorkflow.ts` 的 `ProjectWorkflow` 接口中，在 `setSupplementaryFiles` 后面追加：

```typescript
/** 追加一批附件到待上传列表 */
addSupplementaryFiles: (files: File[]) => void;
/** 按索引移除一个待上传附件 */
removeSupplementaryFile: (index: number) => void;
```

- [ ] **Step 2: 实现两个方法**

在 `useProjectWorkflow` 函数体中，`setMainTenderFile` 函数之后添加：

```typescript
function addSupplementaryFiles(files: File[]): void {
  setSupplementaryFiles((prev) => [...prev, ...files]);
}

function removeSupplementaryFile(index: number): void {
  setSupplementaryFiles((prev) => prev.filter((_, i) => i !== index));
}
```

注意：`setSupplementaryFiles` 当前用的是 `useState` 直接的 setter，需要改为函数式更新。把第 47 行的状态声明保持不变（useState 的 setter 本身支持函数式更新），但 `addSupplementaryFiles` / `removeSupplementaryFile` 内部直接调用 `setSupplementaryFiles` 并传入 updater function。

- [ ] **Step 3: 在 return 对象中暴露新方法**

```typescript
return {
  // ... 现有属性
  addSupplementaryFiles,
  removeSupplementaryFile,
};
```

- [ ] **Step 4: 运行类型检查**

Run: `cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useProjectWorkflow.ts
git commit -m "feat(hook): useProjectWorkflow 添加 addSupplementaryFiles/removeSupplementaryFile"
```

---

### Task 2: V3WorkbenchContext 添加 resetProjectDocs 方法

**Files:**
- Modify: `frontend/src/context/V3WorkbenchContext.tsx`

**目的:** 上传后用户点击"移除"主文件时，需要清空该项目的 auditInputDocs 记录，使步骤回退到 2。

- [ ] **Step 1: 在 WorkbenchContextValue 接口添加方法签名**

在 `frontend/src/context/V3WorkbenchContext.tsx` 的 `WorkbenchContextValue` 接口中，`auditInputDocs` 行之后添加：

```typescript
/** 清空指定项目的已上传文档状态（主文件+附件），回退到上传步骤 */
resetProjectDocs: (projectId: string) => void;
```

- [ ] **Step 2: 实现 resetProjectDocs**

在 `handleUploadAuditInputDocs` 函数之后添加：

```typescript
function resetProjectDocs(projectId: string): void {
  setAuditInputDocs((prev) => {
    const next = { ...prev };
    delete next[projectId];
    return next;
  });
  setTenderDocs((prev) => {
    const next = { ...prev };
    delete next[projectId];
    return next;
  });
}
```

- [ ] **Step 3: 在 value 对象中暴露**

在 context value 对象中（约第 575 行附近），`auditInputDocs` 之后添加：

```typescript
resetProjectDocs,
```

- [ ] **Step 4: 运行类型检查**

Run: `cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc --noEmit`
Expected: 无类型错误（测试文件中的 defaultValue 会报缺少属性，Task 4 中修复）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/context/V3WorkbenchContext.tsx
git commit -m "feat(context): 添加 resetProjectDocs 方法支持上传后移除文档"
```

---

### Task 3: 重写 AIReviewPage 第二步 Card

**Files:**
- Modify: `frontend/src/pages/AIReviewPage.tsx:1-222`

**设计稿参考:** `pencil/pencil-new.pen` 中的 `View/UploadCard-FilesAttached`（节点 u4Y9wh）和 `View/Supp-ManyFiles`（节点 Gci4c）。

**核心交互逻辑:**
- 主文件选择前：显示 FileDropzone
- 主文件选择后、上传前：显示文件名 + 移除按钮 + 附件区域 + 确认上传
- 上传后：显示绿色已上传状态 + 移除按钮（调 resetProjectDocs 回退）
- 附件区域：已选文件列表（每个带删除按钮） + 添加更多 FileDropzone
- 确认上传按钮：统一上传主文件 + 所有附件

- [ ] **Step 1: 添加新的 import**

在 `AIReviewPage.tsx` 顶部 import 区域，`lucide-react` 导入中添加 `FileText, X, Upload, Paperclip`：

```typescript
import { Check, ChevronRight, FileText, Loader2, Paperclip, Plus, Upload, X } from "lucide-react";
```

从 context 中解构 `resetProjectDocs`：

```typescript
const {
  projects, activeProject, selectedProjectId, setSelectedProjectId,
  auditInputDocs, finalCheckpoints, auditProgress, retryPointRun,
  resetProjectDocs,
} = useWorkbench();
```

- [ ] **Step 2: 添加 supplementaryDocs 变量**

在 `const mainDoc = inputDocs?.mainDoc;` 之后添加：

```typescript
const supplementaryDocs = inputDocs?.supplementaryDocs ?? [];
```

- [ ] **Step 3: 替换第二步 Card 内容（第 166-188 行）**

将 `{activeProject && (` 到对应的 `)}` 之间的整个 Card 替换为：

```tsx
{activeProject && (
  <Card>
    <CardHeader><CardTitle>第二步：上传招标文件</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      {/* ── 主招标文书 ── */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-text-secondary">主招标文书</label>
        {mainDoc ? (
          <div className="flex items-center gap-2 rounded-card border border-green-300 bg-green-50 p-3">
            <Check className="h-4 w-4 shrink-0 text-green-600" />
            <span className="min-w-0 flex-1 truncate text-sm">{mainDoc.filename}</span>
            <button type="button" className="text-xs text-red-500 hover:text-red-700" onClick={() => resetProjectDocs(activeProject.id)}>移除</button>
          </div>
        ) : wf.mainTenderFile ? (
          <div className="flex items-center gap-2 rounded-card border p-3">
            <FileText className="h-4 w-4 shrink-0 text-text-muted" />
            <span className="min-w-0 flex-1 truncate text-sm">{wf.mainTenderFile.name}</span>
            <button type="button" className="text-xs text-red-500 hover:text-red-700" onClick={() => wf.setMainTenderFile(null)}>移除</button>
          </div>
        ) : (
          <FileDropzone title="点击选择或拖入招标文书" subtitle="支持 .docx, .pdf" accept=".docx,.pdf" onSelect={(files) => { if (files[0]) wf.setMainTenderFile(files[0]); }} />
        )}
      </div>

      {/* ── 补充文件（主文件选择后才显示） ── */}
      {(wf.mainTenderFile || mainDoc) && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-text-secondary">补充文件（可选）</label>
            {(wf.supplementaryFiles.length > 0 || supplementaryDocs.length > 0) && (
              <span className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                <Paperclip className="h-3 w-3" />
                {wf.supplementaryFiles.length + supplementaryDocs.length} 个文件
              </span>
            )}
          </div>
          <p className="text-xs text-text-muted">变更公告、答疑纪要、补充通知等</p>

          {/* 已上传的附件（上传后状态） */}
          {supplementaryDocs.map((doc) => (
            <div key={doc.id} className="flex items-center gap-2 rounded-card border bg-gray-50 px-3 py-2">
              <FileText className="h-4 w-4 shrink-0 text-text-muted" />
              <span className="min-w-0 flex-1 truncate text-sm">{doc.filename}</span>
            </div>
          ))}

          {/* 待上传的附件列表 */}
          {wf.supplementaryFiles.map((f, i) => (
            <div key={`pending-${i}`} className="flex items-center gap-2 rounded-card border bg-gray-50 px-3 py-2">
              <FileText className="h-4 w-4 shrink-0 text-text-muted" />
              <span className="min-w-0 flex-1 truncate text-sm">{f.name}</span>
              <button type="button" className="text-text-muted hover:text-red-500" onClick={() => wf.removeSupplementaryFile(i)}>
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}

          {/* 添加更多附件 */}
          {!mainDoc && (
            <FileDropzone title="添加补充文件" subtitle="支持 .docx, .pdf，可多选" accept=".docx,.pdf" multiple onSelect={(files) => wf.addSupplementaryFiles(files)} />
          )}
        </div>
      )}

      {/* ── 确认上传按钮（上传前） ── */}
      {wf.mainTenderFile && !mainDoc && (
        <Button className="w-full" disabled={wf.uploadingTender} onClick={wf.handleUploadTender}>
          {wf.uploadingTender ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          确认上传{wf.supplementaryFiles.length > 0 ? `（含 ${wf.supplementaryFiles.length} 个附件）` : ""}
        </Button>
      )}
      {wf.uploadError && <p className="text-sm text-status-err">{wf.uploadError}</p>}
    </CardContent>
  </Card>
)}
```

- [ ] **Step 4: 运行类型检查**

Run: `cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc --noEmit`
Expected: PASS（或仅 test 文件报 resetProjectDocs 缺失，Task 4 修复）

- [ ] **Step 5: 手动验证**

启动前端开发服务器：
```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx vite --host 0.0.0.0 --port 5173
```

在浏览器中验证：
1. 进入 /ai-review，选择/创建项目
2. 选择主文件 → 出现文件名 + 移除按钮 + 补充文件区域 + 确认上传按钮
3. 点击"移除"主文件 → 回到 FileDropzone 状态
4. 重新选择主文件 → 添加 2-3 个补充文件 → 看到文件列表
5. 删除某个补充文件 → 列表更新
6. 点击"确认上传" → 上传完成后进入步骤 3
7. 步骤 3 中主文件显示绿色已上传 → 点击"移除" → 回退到步骤 2

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/AIReviewPage.tsx
git commit -m "feat(ui): AI 审核页第二步支持附件上传、文件移除"
```

---

### Task 4: 单元测试

**Files:**
- Modify: `frontend/tests/pages/AIReviewPage.test.tsx`

- [ ] **Step 1: 在 defaultValue() 中添加 resetProjectDocs mock**

在 `frontend/tests/pages/AIReviewPage.test.tsx` 的 `defaultValue()` 函数中，`auditInputDocs: {},` 行之后添加：

```typescript
resetProjectDocs: vi.fn(),
```

- [ ] **Step 2: 添加附件相关测试用例**

在 `describe("AIReviewPage · Setup 模式", () => {` 块末尾、`});` 之前添加：

```typescript
it("有 activeProject + 无 mainDoc 时渲染第二步上传卡片含主招标文书 label", () => {
  renderPage({
    projects: [sampleProject],
    activeProject: sampleProject,
    selectedProjectId: sampleProject.id,
  });
  expect(screen.getByText("第二步：上传招标文件")).toBeInTheDocument();
  expect(screen.getByText("主招标文书")).toBeInTheDocument();
});

it("mainDoc 已上传时显示绿色状态和「移除」按钮", () => {
  renderPage({
    projects: [sampleProject],
    activeProject: sampleProject,
    selectedProjectId: sampleProject.id,
    auditInputDocs: {
      [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] },
    },
  });
  expect(screen.getByText("tender.docx")).toBeInTheDocument();
  expect(screen.getByText("移除")).toBeInTheDocument();
});

it("点击已上传主文件的「移除」调用 resetProjectDocs", async () => {
  const resetProjectDocs = vi.fn();
  renderPage({
    projects: [sampleProject],
    activeProject: sampleProject,
    selectedProjectId: sampleProject.id,
    auditInputDocs: {
      [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] },
    },
    resetProjectDocs,
  });
  await userEvent.click(screen.getByText("移除"));
  expect(resetProjectDocs).toHaveBeenCalledWith(sampleProject.id);
});

it("mainDoc 已上传 + supplementaryDocs 非空时显示附件文件名", () => {
  const suppDoc: TenderDoc = { id: "td-s1", project_id: "p-1", filename: "合同.pdf", markdown_path: "/tmp/s1.md" };
  renderPage({
    projects: [sampleProject],
    activeProject: sampleProject,
    selectedProjectId: sampleProject.id,
    auditInputDocs: {
      [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [suppDoc] },
    },
  });
  expect(screen.getByText("合同.pdf")).toBeInTheDocument();
  expect(screen.getByText("补充文件（可选）")).toBeInTheDocument();
});
```

- [ ] **Step 3: 运行测试**

Run: `cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx vitest run tests/pages/AIReviewPage.test.tsx`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/pages/AIReviewPage.test.tsx
git commit -m "test: AIReviewPage 附件上传 UI 单元测试"
```

---

### Task 5: E2E test-06 多文件审核测试

**Files:**
- Create: `frontend/e2e/test-06-ai-audit-multifile.js`
- Modify: `frontend/e2e/run-tests.sh:42`

**说明:** test-05 保持单文件审核不变。test-06 测试多文件上传流程（主文件 + 1个附件），验证附件 UI 显示、删除、确认上传。不启动真实审核（避免长时间等待），只验证到上传完成进入步骤 3。

- [ ] **Step 1: 创建 test-06-ai-audit-multifile.js**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const TENDER_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf';
  const SUPP_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/广州市从化区中医医院从化区中医医院手术室设备及附件、病房护理及医院设备采购的合同.pdf';

  // Step 1: 进入 AI 审核页面
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入 AI 审核页面');

  // Step 2: 创建新项目
  const projName = 'E2E-多文件-' + Date.now().toString().slice(-6);
  await page.getByPlaceholder('输入项目名称').fill(projName);
  await page.getByRole('button', { name: /创建/ }).click();
  await page.waitForTimeout(2000);
  console.log('Step 2: 创建项目 ' + projName);

  // Step 3: 上传主招标文书
  const fileInputs = page.locator("input[type='file']");
  await fileInputs.first().setInputFiles(TENDER_PDF);
  await page.waitForTimeout(500);
  console.log('Step 3: 选择主招标文书');
  await page.screenshot({ path: 'e2e/screenshots/06-main-selected.png' });

  // Step 4: 验证附件区域出现
  await page.getByText('补充文件（可选）').waitFor({ timeout: 5000 });
  console.log('Step 4: 附件区域已出现');

  // Step 5: 添加补充文件
  const suppInput = fileInputs.last();
  await suppInput.setInputFiles(SUPP_PDF);
  await page.waitForTimeout(500);
  console.log('Step 5: 添加 1 个补充文件');
  await page.screenshot({ path: 'e2e/screenshots/06-supp-added.png' });

  // Step 6: 验证补充文件列表显示
  const suppFileText = page.getByText(/合同/);
  await suppFileText.waitFor({ timeout: 5000 });
  console.log('Step 6: 补充文件名显示正确');

  // Step 7: 验证确认上传按钮文案含附件数量
  const uploadBtn = page.getByRole('button', { name: /确认上传/ });
  await uploadBtn.waitFor({ timeout: 5000 });
  const btnText = await uploadBtn.textContent();
  if (!btnText.includes('附件')) throw new Error('确认上传按钮未显示附件数量: ' + btnText);
  console.log('Step 7: 确认上传按钮: ' + btnText);

  // Step 8: 点击确认上传
  await uploadBtn.click();
  console.log('Step 8: 开始上传');

  // Step 9: 等待上传完成（主文件绿色状态出现）
  const uploadedIndicator = page.locator('.border-green-300');
  await uploadedIndicator.waitFor({ timeout: 180000 });
  console.log('Step 9: 上传完成');
  await page.screenshot({ path: 'e2e/screenshots/06-uploaded.png' });

  // Step 10: 验证移除按钮存在
  const removeBtn = page.getByText('移除');
  await removeBtn.waitFor({ timeout: 5000 });
  console.log('Step 10: 移除按钮存在');

  // Step 11: 测试移除主文件 → 回退到上传步骤
  await removeBtn.click();
  await page.waitForTimeout(500);
  const dropzone = page.getByText('点击选择或拖入招标文书');
  await dropzone.waitFor({ timeout: 5000 });
  console.log('Step 11: 移除后回退到上传步骤');
  await page.screenshot({ path: 'e2e/screenshots/06-removed.png' });

  // Step 12: 最终截图
  await page.screenshot({ path: 'e2e/screenshots/06-final.png', fullPage: true });
  console.log('== test-06-ai-audit-multifile 全部通过 ==');
}
```

- [ ] **Step 2: 更新 run-tests.sh 的 ALL_TESTS 数组**

在 `frontend/e2e/run-tests.sh` 第 42 行，把：

```bash
ALL_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "04-ai-extract" "05-ai-audit")
```

改为：

```bash
ALL_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "04-ai-extract" "05-ai-audit" "06-ai-audit-multifile")
```

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/test-06-ai-audit-multifile.js frontend/e2e/run-tests.sh
git commit -m "test(e2e): 添加 test-06 多文件审核上传 E2E 测试"
```

---

### Task 6: 部署到 testing 并运行全部 E2E 测试（01-06）

**前置条件:** Task 1-5 全部完成并提交。

- [ ] **Step 1: 运行全部前端单元测试确保无回归**

Run: `cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx vitest run`
Expected: 全部 PASS

- [ ] **Step 2: 使用 deploy skill 部署到 testing 环境**

调用 `/deploy --target testing`，将前端和后端都部署到 testing 环境：
- 后端: `http://100.83.164.94:8001`
- 前端: `http://175.178.131.134:8080`

- [ ] **Step 3: 运行全部 E2E 测试（01-06）**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && bash e2e/run-tests.sh
```

Expected: 6 passed, 0 failed, 0 skipped

- [ ] **Step 4: 如果有失败，定位原因并修复**

检查 `e2e/screenshots/FAIL-*.png` 截图，根据失败原因回到对应 Task 修复。

---

## 验证清单

| 验证项 | 方法 | 预期结果 |
|--------|------|----------|
| 类型检查 | `npx tsc --noEmit` | 无错误 |
| 单元测试 | `npx vitest run` | 全部 PASS |
| 主文件选择 | 手动 - 选择文件 | 显示文件名 + 移除按钮 + 补充文件区域 |
| 主文件移除（上传前） | 手动 - 点击移除 | 回到 FileDropzone |
| 附件添加 | 手动 - 拖入多个文件 | 文件列表显示，计数更新 |
| 附件删除 | 手动 - 点击 X | 文件从列表消失 |
| 确认上传 | 手动 - 点击按钮 | 主文件 + 附件上传，进入步骤 3 |
| 上传后移除 | 手动 - 点击移除 | 回退到步骤 2 初始状态 |
| E2E 01-06 | `bash e2e/run-tests.sh` | 6 passed |
| testing 环境 | 部署后浏览器访问 | 功能正常 |

# 审核点库页面 E2E 测试 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `/audit-library` 页面编写 8 个 E2E 测试脚本（AL1~AL8），覆盖页面骨架、导入、搜索筛选、库 CRUD、审核点编辑删除、库成员关系、空状态、AI 提取全链路。

**Architecture:** 每个测试是独立的 `async page => {}` 裸函数，由 `@playwright/cli` 的 `run-code` 执行。测试按编号顺序执行（AL1→AL8），后续测试可依赖前序测试创建的数据。截图保存到 `e2e/screenshots/audit-AL*` 供人工视觉审查。

**Tech Stack:** @playwright/cli, JavaScript (async page => {} 格式), real_data/ 下的真实文件

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|---|---|---|
| Create | `frontend/e2e/audit-AL1-skeleton.js` | 页面骨架验证 |
| Create | `frontend/e2e/audit-AL2-import.js` | 导入审查点表格 |
| Create | `frontend/e2e/audit-AL3-search-filter.js` | 搜索与分类筛选 |
| Create | `frontend/e2e/audit-AL4-library-crud.js` | 库的增删改 |
| Create | `frontend/e2e/audit-AL5-checkpoint-edit-delete.js` | 审核点编辑与删除 |
| Create | `frontend/e2e/audit-AL6-library-membership.js` | 库与审核点关联 |
| Create | `frontend/e2e/audit-AL7-empty-state.js` | 空状态与边界 |
| Create | `frontend/e2e/audit-AL8-ai-extract.js` | AI 智能提取 |
| Modify | `frontend/e2e/run-tests.sh:41-44` | 注册 AUDIT_TESTS 数组 + 添加 `--page audit` 支持 |

## 约定

- **截图前缀**：`e2e/screenshots/audit-AL{N}-{step}.png`
- **BASE URL**：从 `page.url()` 动态取，兼容 testing/local
- **真实数据路径**：`/home/iomgaa/Projects/GovDoc_Editor/real_data/`
  - 导入用 xls：`附件9 处理处罚标准.xls`
  - AI 提取用 doc：`2025年政府采购领域"四类"违法违规行为专项整治工作指引.doc`
- **每步必须截图**（`fullPage: true`），失败抛 `throw new Error`，警告用 `console.log('WARN:')`
- **依赖关系**：AL2（导入）为 AL3/AL5/AL6 提供数据，AL4（建库）为 AL6 提供库。测试按编号顺序执行。

---

### Task 1: AL1-skeleton — 页面骨架验证

**Files:**
- Create: `frontend/e2e/audit-AL1-skeleton.js`

**测试逻辑：** 进入 `/audit-library`，验证所有静态 UI 元素存在且可见。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL1';

  // Step 1: 进入审核点库页
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // Step 2: 页面标题
  const title = page.locator('header').getByText('审核点库');
  if (!(await title.isVisible())) throw new Error('页面标题"审核点库"不可见');
  console.log('PASS: 页面标题可见');

  // Step 3: "新建库" 按钮
  const newLibBtn = page.getByRole('button', { name: '新建库' });
  if (!(await newLibBtn.isVisible())) throw new Error('"新建库"按钮不可见');
  console.log('PASS: "新建库"按钮可见');

  // Step 4: "上传" 下拉按钮
  const uploadBtn = page.getByRole('button', { name: '上传' });
  if (!(await uploadBtn.isVisible())) throw new Error('"上传"按钮不可见');
  console.log('PASS: "上传"按钮可见');

  // Step 5: 左侧栏 — "全部审核点" 入口
  const allEntry = page.getByText('全部审核点').first();
  if (!(await allEntry.isVisible())) throw new Error('"全部审核点"入口不可见');
  console.log('PASS: 左侧栏"全部审核点"可见');

  // Step 6: 搜索框
  const searchInput = page.getByPlaceholder('搜索审查要点...');
  if (!(await searchInput.isVisible())) throw new Error('搜索框不可见');
  console.log('PASS: 搜索框可见');

  // Step 7: "全部分类" 筛选按钮
  const catBtn = page.getByRole('button', { name: '全部分类' });
  if (!(await catBtn.isVisible())) throw new Error('"全部分类"按钮不可见');
  console.log('PASS: "全部分类"筛选按钮可见');

  // Step 8: 表格列头
  const expectedColumns = ['审查要点', '分类', '严重程度', '状态', '操作'];
  for (const col of expectedColumns) {
    const th = page.locator('th').getByText(col).first();
    if (!(await th.isVisible())) throw new Error('表格列头缺失: ' + col);
  }
  console.log('PASS: 表格列头完整（' + expectedColumns.join('/') + '）');

  // Step 9: 全选 checkbox
  const selectAllCheckbox = page.locator('thead input[type="checkbox"]');
  if (!(await selectAllCheckbox.isVisible())) throw new Error('全选 checkbox 不可见');
  console.log('PASS: 全选 checkbox 可见');

  // Step 10: "上传" 下拉菜单展开验证
  await uploadBtn.click();
  await page.waitForTimeout(500);
  const aiExtractItem = page.getByText('AI 提取');
  const importItem = page.getByText('导入审查点表格');
  if (!(await aiExtractItem.isVisible())) throw new Error('"AI 提取"菜单项不可见');
  if (!(await importItem.isVisible())) throw new Error('"导入审查点表格"菜单项不可见');
  await page.screenshot({ path: SS + '-02-upload-dropdown.png', fullPage: true });
  console.log('PASS: 上传下拉菜单（AI 提取 / 导入审查点表格）');

  // 关闭下拉
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  // Step 11: 全页截图
  await page.screenshot({ path: SS + '-03-full-page.png', fullPage: true });

  console.log('== audit-AL1-skeleton 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**

```bash
cd frontend && NO_PROXY="100.70.102.30,100.82.33.121" npx playwright-cli -s=e2e open "http://100.70.102.30:8080/audit-library" --config=.playwright/cli.config.json && npx playwright-cli -s=e2e run-code --filename=e2e/audit-AL1-skeleton.js
```

预期：所有 `PASS` 输出，无 Error。

- [ ] **Step 3: 审查截图**

检查 `e2e/screenshots/audit-AL1-*.png`，确认页面元素位置、样式、无遮挡。

---

### Task 2: AL2-import — 导入审查点表格

**Files:**
- Create: `frontend/e2e/audit-AL2-import.js`

**测试逻辑：** 通过"上传 → 导入审查点表格"流程导入 `附件9 处理处罚标准.xls`，为后续测试提供审核点数据。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL2';
  const XLS_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/附件9 处理处罚标准.xls';

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  // 记录初始审核点数
  const initCountText = await page.getByText('全部审核点').first().locator('..').textContent() || '';
  console.log('初始状态: ' + initCountText.trim());
  await page.screenshot({ path: SS + '-01-before-import.png', fullPage: true });

  // ── Step 1: 打开"上传"下拉 → 点击"导入审查点表格" ──
  console.log('Step 1: 进入导入模式');
  await page.getByRole('button', { name: '上传' }).click();
  await page.waitForTimeout(500);
  await page.getByText('导入审查点表格').click();
  await page.waitForTimeout(1000);

  // 验证进入 import 模式
  const importTitle = page.getByText('批量导入').first();
  await importTitle.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-02-import-mode.png', fullPage: true });
  console.log('PASS: 进入导入模式');

  // ── Step 2: 上传 xls 文件 ──
  console.log('Step 2: 上传 xls 文件');
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(XLS_PATH);
  await page.waitForTimeout(1000);

  // 验证文件名显示
  const fileName = page.getByText('处理处罚标准').first();
  if (!(await fileName.isVisible())) throw new Error('上传后文件名不可见');
  await page.screenshot({ path: SS + '-03-file-uploaded.png', fullPage: true });
  console.log('PASS: 文件上传成功');

  // ── Step 3: 点击"解析预览" ──
  console.log('Step 3: 解析预览');
  const previewBtn = page.getByRole('button', { name: '解析预览' });
  await previewBtn.click();

  // 等待预览结果（新增/复用/重复/跳过 计数卡片出现）
  const metricLabel = page.getByText('新增').first();
  await metricLabel.waitFor({ timeout: 30000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-04-preview-result.png', fullPage: true });

  // 验证 4 个指标全部可见
  for (const label of ['新增', '复用', '重复', '跳过']) {
    const el = page.getByText(label).first();
    if (!(await el.isVisible())) throw new Error('预览指标缺失: ' + label);
  }
  console.log('PASS: 预览指标完整（新增/复用/重复/跳过）');

  // ── Step 4: 点击"确认入库" ──
  console.log('Step 4: 确认入库');
  const importBtn = page.getByRole('button', { name: '确认入库' });
  await importBtn.click();

  // 等待成功提示
  const successMsg = page.getByText(/新增.*条/).first();
  await successMsg.waitFor({ timeout: 30000 });
  await page.screenshot({ path: SS + '-05-import-success.png', fullPage: true });
  const resultText = await successMsg.textContent() || '';
  console.log('PASS: 入库成功 — ' + resultText.trim());

  // ── Step 5: 返回列表，验证数据出现 ──
  console.log('Step 5: 返回列表验证');
  const backBtn = page.getByRole('button', { name: '返回列表' });
  await backBtn.click();
  await page.waitForTimeout(2000);

  // 验证表格中有数据行
  const rows = page.locator('table tbody tr');
  const rowCount = await rows.count();
  if (rowCount === 0) throw new Error('返回列表后表格仍为空');
  await page.screenshot({ path: SS + '-06-list-with-data.png', fullPage: true });
  console.log('PASS: 列表已有 ' + rowCount + ' 条审核点');

  // ── Step 6: 验证严重程度 badge 显示 ──
  const severityBadges = ['严重', '重要', '一般'];
  let foundBadge = false;
  for (const badge of severityBadges) {
    const el = page.getByText(badge).first();
    if (await el.isVisible().catch(() => false)) {
      foundBadge = true;
      break;
    }
  }
  if (foundBadge) {
    console.log('PASS: 严重程度 badge 可见');
  } else {
    console.log('WARN: 未发现严重程度 badge（截图供检查）');
  }

  await page.screenshot({ path: SS + '-07-final.png', fullPage: true });
  console.log('== audit-AL2-import 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 3: AL3-search-filter — 搜索与分类筛选

**Files:**
- Create: `frontend/e2e/audit-AL3-search-filter.js`

**前置依赖：** AL2 已导入审核点数据。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL3';

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  // 前置：确保有数据
  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 审核点为空，无法测试搜索筛选');
    return;
  }
  console.log('初始审核点数: ' + initialCount);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 1: 搜索框 — 输入已存在的审查要点关键词 ──
  const firstTitle = await rows.first().locator('td').nth(1).locator('p').first().textContent() || '';
  const searchKey = firstTitle.trim().slice(0, 4);
  console.log('Step 1: 搜索关键词 "' + searchKey + '"');

  const searchInput = page.getByPlaceholder('搜索审查要点...');
  await searchInput.fill(searchKey);
  await page.waitForTimeout(500);
  const filteredCount = await rows.count();
  if (filteredCount === 0) throw new Error('搜索 "' + searchKey + '" 后无结果');
  if (filteredCount > initialCount) throw new Error('搜索后行数反而增多');
  await page.screenshot({ path: SS + '-02-search-result.png', fullPage: true });
  console.log('PASS: 搜索过滤（' + initialCount + ' → ' + filteredCount + '）');

  // ── Step 2: 清空搜索 → 恢复 ──
  await searchInput.fill('');
  await page.waitForTimeout(500);
  const restoredCount = await rows.count();
  if (restoredCount !== initialCount) {
    throw new Error('清空搜索后行数未恢复: ' + restoredCount + ' vs ' + initialCount);
  }
  console.log('PASS: 清空搜索恢复（' + restoredCount + ' 行）');

  // ── Step 3: 分类筛选 ──
  console.log('Step 3: 分类筛选');
  // 收集所有分类 pill（排除"全部分类"）
  const categoryPills = page.locator('button.rounded-full').filter({ hasNot: page.getByText('全部分类') });
  const catCount = await categoryPills.count();
  if (catCount === 0) {
    console.log('SKIP: 无分类 pill，跳过分类筛选');
  } else {
    // 点击第一个分类
    const firstCatText = (await categoryPills.first().textContent() || '').trim();
    console.log('  点击分类: "' + firstCatText + '"');
    await categoryPills.first().click();
    await page.waitForTimeout(500);
    const catFiltered = await rows.count();
    await page.screenshot({ path: SS + '-03-category-filter.png', fullPage: true });
    console.log('PASS: 分类筛选"' + firstCatText + '"（' + catFiltered + ' 行）');

    // 验证筛选后每行的分类列都包含该分类
    for (let i = 0; i < Math.min(catFiltered, 5); i++) {
      const rowText = await rows.nth(i).textContent() || '';
      if (!rowText.includes(firstCatText)) {
        throw new Error('分类筛选后第 ' + i + ' 行不含"' + firstCatText + '"');
      }
    }
    console.log('PASS: 分类筛选内容正确');

    // 恢复到全部分类
    await page.getByRole('button', { name: '全部分类' }).click();
    await page.waitForTimeout(500);
    const allCount = await rows.count();
    if (allCount !== initialCount) {
      throw new Error('点击"全部分类"后行数未恢复: ' + allCount + ' vs ' + initialCount);
    }
    console.log('PASS: 点击"全部分类"恢复（' + allCount + ' 行）');
  }

  // ── Step 4: 组合搜索 + 分类筛选 ──
  if (catCount > 0) {
    console.log('Step 4: 组合筛选');
    await categoryPills.first().click();
    await page.waitForTimeout(300);
    await searchInput.fill(searchKey);
    await page.waitForTimeout(500);
    const combinedCount = await rows.count();
    await page.screenshot({ path: SS + '-04-combined-filter.png', fullPage: true });
    console.log('PASS: 组合筛选（' + combinedCount + ' 行）');

    // 复位
    await searchInput.fill('');
    await page.getByRole('button', { name: '全部分类' }).click();
    await page.waitForTimeout(300);
  }

  // ── Step 5: 全选 checkbox ──
  console.log('Step 5: 全选 checkbox');
  const selectAll = page.locator('thead input[type="checkbox"]');
  await selectAll.click();
  await page.waitForTimeout(300);

  // 验证"已选择 N 个" badge
  const selectedBadge = page.getByText(/已选择/).first();
  if (!(await selectedBadge.isVisible())) throw new Error('"已选择"badge 不可见');
  await page.screenshot({ path: SS + '-05-select-all.png', fullPage: true });
  console.log('PASS: 全选后"已选择"badge 可见');

  // 验证"加入库"按钮启用
  const addToLibBtn = page.getByRole('button', { name: '加入库' });
  if (await addToLibBtn.isDisabled()) throw new Error('全选后"加入库"按钮仍禁用');
  console.log('PASS: "加入库"按钮已启用');

  // 取消全选
  await selectAll.click();
  await page.waitForTimeout(300);

  console.log('== audit-AL3-search-filter 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 4: AL4-library-crud — 库的增删改

**Files:**
- Create: `frontend/e2e/audit-AL4-library-crud.js`

**测试逻辑：** 新建库 → 编辑库 → 删除库，完整验证库 CRUD 流程。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL4';
  const LIB_NAME = 'E2E测试库' + Date.now().toString().slice(-4);
  const LIB_DESC = 'E2E 自动化测试创建';
  const LIB_NAME_EDITED = LIB_NAME + '-已编辑';

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 1: 点击"新建库"按钮 ──
  console.log('Step 1: 新建库');
  await page.getByRole('button', { name: '新建库' }).click();
  await page.waitForTimeout(500);

  // 验证弹窗出现
  const dialog = page.locator('[role="dialog"]').filter({ hasText: '新建审核点库' });
  await dialog.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-02-new-lib-dialog.png', fullPage: true });
  console.log('PASS: 新建库弹窗已打开');

  // ── Step 2: 填写库名称和描述 → 创建 ──
  console.log('Step 2: 填写并创建');
  await dialog.locator('input[placeholder="库名称"]').fill(LIB_NAME);
  await dialog.locator('textarea[placeholder*="说明"]').fill(LIB_DESC);
  await page.screenshot({ path: SS + '-03-form-filled.png', fullPage: true });

  await dialog.getByRole('button', { name: '创建' }).click();
  await page.waitForTimeout(2000);

  // 验证弹窗关闭
  if (await dialog.isVisible().catch(() => false)) throw new Error('创建后弹窗未关闭');

  // 验证左侧栏出现新库
  const newLibEntry = page.getByText(LIB_NAME).first();
  if (!(await newLibEntry.isVisible())) throw new Error('新库未出现在左侧栏');
  await page.screenshot({ path: SS + '-04-lib-created.png', fullPage: true });
  console.log('PASS: 新库"' + LIB_NAME + '"已创建');

  // ── Step 3: 切换到新库视图 ──
  console.log('Step 3: 切换到新库视图');
  await newLibEntry.click();
  await page.waitForTimeout(1000);

  // 验证主区域标题变为库名
  const mainTitle = page.locator('h2').getByText(LIB_NAME).first();
  if (!(await mainTitle.isVisible())) throw new Error('主区域标题未变为库名');
  await page.screenshot({ path: SS + '-05-lib-view.png', fullPage: true });
  console.log('PASS: 已切换到库视图');

  // 验证库视图特有按钮（编辑库/删除库/移出当前库）
  const editLibBtn = page.getByRole('button', { name: '编辑库' });
  const deleteLibBtn = page.getByRole('button', { name: '删除库' });
  if (!(await editLibBtn.isVisible())) throw new Error('"编辑库"按钮不可见');
  if (!(await deleteLibBtn.isVisible())) throw new Error('"删除库"按钮不可见');
  console.log('PASS: 库视图特有按钮可见（编辑库/删除库）');

  // ── Step 4: 编辑库 ──
  console.log('Step 4: 编辑库');
  await editLibBtn.click();
  await page.waitForTimeout(500);

  const editDialog = page.locator('[role="dialog"]').filter({ hasText: '编辑审核点库' });
  await editDialog.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-06-edit-dialog.png', fullPage: true });

  // 验证表单回填了原始值
  const nameInput = editDialog.locator('input').first();
  const nameValue = await nameInput.inputValue();
  if (!nameValue.includes(LIB_NAME)) throw new Error('编辑弹窗库名未回填');
  console.log('PASS: 编辑弹窗已回填原始值');

  // 修改库名
  await nameInput.fill(LIB_NAME_EDITED);
  await editDialog.getByRole('button', { name: '保存' }).click();
  await page.waitForTimeout(2000);

  // 验证左侧栏库名更新
  const editedEntry = page.getByText(LIB_NAME_EDITED).first();
  if (!(await editedEntry.isVisible())) throw new Error('编辑后库名未更新');
  await page.screenshot({ path: SS + '-07-lib-edited.png', fullPage: true });
  console.log('PASS: 库名已更新为"' + LIB_NAME_EDITED + '"');

  // ── Step 5: 删除库 ──
  console.log('Step 5: 删除库');
  await page.getByRole('button', { name: '删除库' }).click();
  await page.waitForTimeout(500);

  const deleteDialog = page.locator('[role="dialog"]').filter({ hasText: '删除审核点库' });
  await deleteDialog.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-08-delete-dialog.png', fullPage: true });

  // 验证确认文案包含库名
  const dialogText = await deleteDialog.textContent() || '';
  if (!dialogText.includes(LIB_NAME_EDITED)) throw new Error('删除确认弹窗未显示库名');
  console.log('PASS: 删除确认弹窗已显示库名');

  // 确认删除
  await deleteDialog.getByRole('button', { name: '确认删除' }).click();
  await page.waitForTimeout(2000);

  // 验证回到"全部审核点"
  const allTitle = page.locator('h2').getByText('全部审核点').first();
  if (!(await allTitle.isVisible())) throw new Error('删除后未回到"全部审核点"');

  // 验证左侧栏库已消失
  const goneEntry = page.getByText(LIB_NAME_EDITED);
  if (await goneEntry.isVisible().catch(() => false)) throw new Error('删除后库仍在左侧栏');
  await page.screenshot({ path: SS + '-09-lib-deleted.png', fullPage: true });
  console.log('PASS: 库已删除，回到全部审核点');

  console.log('== audit-AL4-library-crud 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 5: AL5-checkpoint-edit-delete — 审核点编辑与删除

**Files:**
- Create: `frontend/e2e/audit-AL5-checkpoint-edit-delete.js`

**前置依赖：** AL2 已导入审核点数据。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL5';

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 审核点为空');
    return;
  }
  console.log('初始审核点数: ' + initialCount);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 1: 编辑审核点 ──
  console.log('Step 1: 编辑审核点');
  const firstRow = rows.first();
  const origTitle = (await firstRow.locator('td').nth(1).locator('p').first().textContent() || '').trim();
  console.log('  原始标题: ' + origTitle.slice(0, 30));

  // 点击编辑按钮（铅笔图标）
  const editBtn = firstRow.locator('td').last().locator('button').first();
  await editBtn.click();
  await page.waitForTimeout(500);

  // 验证编辑弹窗
  const editDialog = page.locator('[role="dialog"]').filter({ hasText: '编辑审查要点' });
  await editDialog.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-02-edit-dialog.png', fullPage: true });
  console.log('PASS: 编辑弹窗已打开');

  // 验证标题和描述回填
  const titleInput = editDialog.locator('input').first();
  const titleValue = await titleInput.inputValue();
  if (!titleValue) throw new Error('编辑弹窗标题未回填');
  console.log('PASS: 标题已回填');

  const descTextarea = editDialog.locator('textarea').first();
  const descValue = await descTextarea.inputValue();
  console.log('  描述回填: ' + (descValue ? '是' : '否'));

  // 修改标题
  const editedTitle = titleValue + '[E2E已编辑]';
  await titleInput.fill(editedTitle);
  await page.screenshot({ path: SS + '-03-edit-filled.png', fullPage: true });

  // 保存
  await editDialog.getByRole('button', { name: '保存修改' }).click();
  await page.waitForTimeout(2000);

  // 验证弹窗关闭
  if (await editDialog.isVisible().catch(() => false)) throw new Error('保存后弹窗未关闭');

  // 验证表格中标题已更新
  const updatedTitle = page.getByText('[E2E已编辑]').first();
  if (!(await updatedTitle.isVisible())) throw new Error('编辑后标题未在表格中更新');
  await page.screenshot({ path: SS + '-04-edit-saved.png', fullPage: true });
  console.log('PASS: 审核点标题已更新');

  // ── Step 2: 还原标题（避免污染后续测试） ──
  console.log('Step 2: 还原标题');
  await firstRow.locator('td').last().locator('button').first().click();
  await page.waitForTimeout(500);
  const restoreDialog = page.locator('[role="dialog"]').filter({ hasText: '编辑审查要点' });
  await restoreDialog.waitFor({ timeout: 5000 });
  await restoreDialog.locator('input').first().fill(titleValue);
  await restoreDialog.getByRole('button', { name: '保存修改' }).click();
  await page.waitForTimeout(2000);
  console.log('PASS: 标题已还原');

  // ── Step 3: 删除审核点 — 先取消 ──
  console.log('Step 3: 删除审核点（取消）');
  const lastRow = rows.last();
  const delTarget = (await lastRow.locator('td').nth(1).locator('p').first().textContent() || '').trim();
  console.log('  删除目标: ' + delTarget.slice(0, 30));

  // 点击删除按钮（垃圾桶图标）
  const deleteBtn = lastRow.locator('td').last().locator('button').last();
  await deleteBtn.click();
  await page.waitForTimeout(500);

  // 验证删除确认弹窗
  const deleteDialog = page.locator('[role="dialog"]').filter({ hasText: '确认删除' });
  await deleteDialog.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-05-delete-dialog.png', fullPage: true });

  // 验证不可撤销警告
  const warning = deleteDialog.getByText('此操作不可撤销');
  if (!(await warning.isVisible())) throw new Error('不可撤销警告不可见');
  console.log('PASS: 不可撤销警告可见');

  // 验证审核点名称显示
  const cpName = await deleteDialog.textContent() || '';
  if (!cpName.includes(delTarget.slice(0, 10))) {
    console.log('WARN: 删除确认弹窗可能未显示审核点名称');
  }

  // 取消删除
  await deleteDialog.getByRole('button', { name: '取消' }).click();
  await page.waitForTimeout(500);

  const afterCancelCount = await rows.count();
  if (afterCancelCount !== initialCount) {
    throw new Error('取消删除后行数变化: ' + initialCount + ' → ' + afterCancelCount);
  }
  console.log('PASS: 取消删除，行数不变（' + afterCancelCount + '）');

  // ── Step 4: 删除审核点 — 确认 ──
  console.log('Step 4: 删除审核点（确认）');
  await deleteBtn.click();
  await page.waitForTimeout(500);
  const deleteDialog2 = page.locator('[role="dialog"]').filter({ hasText: '确认删除' });
  await deleteDialog2.waitFor({ timeout: 5000 });

  await deleteDialog2.getByRole('button', { name: '确认删除' }).click();
  await page.waitForTimeout(2000);

  const afterDeleteCount = await rows.count();
  if (afterDeleteCount >= initialCount) {
    throw new Error('确认删除后行数未减少: ' + initialCount + ' → ' + afterDeleteCount);
  }
  await page.screenshot({ path: SS + '-06-after-delete.png', fullPage: true });
  console.log('PASS: 确认删除，行数减少（' + initialCount + ' → ' + afterDeleteCount + '）');

  console.log('== audit-AL5-checkpoint-edit-delete 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 6: AL6-library-membership — 库与审核点关联

**Files:**
- Create: `frontend/e2e/audit-AL6-library-membership.js`

**测试逻辑：** 新建库 → 勾选审核点 → 加入库 → 切换库视图验证 → 移出 → 清理。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL6';
  const LIB_NAME = 'E2E关联测试库' + Date.now().toString().slice(-4);

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount < 2) {
    console.log('⏭ 跳过: 审核点不足 2 条，无法测试库关联');
    return;
  }
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 1: 勾选前 2 个审核点 ──
  console.log('Step 1: 勾选 2 个审核点');
  const cb1 = rows.nth(0).locator('input[type="checkbox"]');
  const cb2 = rows.nth(1).locator('input[type="checkbox"]');
  await cb1.click();
  await page.waitForTimeout(200);
  await cb2.click();
  await page.waitForTimeout(200);

  const selectedBadge = page.getByText(/已选择 2/).first();
  if (!(await selectedBadge.isVisible())) throw new Error('"已选择 2"badge 不可见');
  await page.screenshot({ path: SS + '-02-selected.png', fullPage: true });
  console.log('PASS: 已勾选 2 个审核点');

  // ── Step 2: 点击"加入库" → 弹窗 ──
  console.log('Step 2: 打开"加入库"弹窗');
  await page.getByRole('button', { name: '加入库' }).click();
  await page.waitForTimeout(500);

  const addDialog = page.locator('[role="dialog"]').filter({ hasText: '加入审核点库' });
  await addDialog.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-03-add-dialog.png', fullPage: true });
  console.log('PASS: "加入库"弹窗已打开');

  // ── Step 3: 在弹窗中输入新库名称（内联创建） ──
  console.log('Step 3: 内联创建新库');
  const inlineInput = addDialog.locator('input[placeholder*="新库名称"]');
  await inlineInput.fill(LIB_NAME);
  await page.screenshot({ path: SS + '-04-inline-new-lib.png', fullPage: true });

  // 确认加入
  await addDialog.getByRole('button', { name: '确认加入' }).click();
  await page.waitForTimeout(3000);

  // 验证弹窗关闭
  if (await addDialog.isVisible().catch(() => false)) throw new Error('确认后弹窗未关闭');
  console.log('PASS: 审核点已加入新库');

  // ── Step 4: 在左侧栏找到新库并切换 ──
  console.log('Step 4: 切换到新库视图');
  const libEntry = page.getByText(LIB_NAME).first();
  if (!(await libEntry.isVisible())) throw new Error('新库未出现在左侧栏');
  await libEntry.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-05-lib-view.png', fullPage: true });

  // 验证库内有 2 条审核点
  const libRows = page.locator('table tbody tr');
  const libRowCount = await libRows.count();
  if (libRowCount < 2) throw new Error('库内审核点数不足: 期望 ≥2，实际 ' + libRowCount);
  console.log('PASS: 库内有 ' + libRowCount + ' 条审核点');

  // ── Step 5: 勾选第一条 → "移出当前库" ──
  console.log('Step 5: 移出审核点');
  const libCb1 = libRows.first().locator('input[type="checkbox"]');
  await libCb1.click();
  await page.waitForTimeout(200);

  const removeBtn = page.getByRole('button', { name: '移出当前库' });
  if (!(await removeBtn.isVisible())) throw new Error('"移出当前库"按钮不可见');
  await removeBtn.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-06-after-remove.png', fullPage: true });

  const afterRemoveCount = await libRows.count();
  if (afterRemoveCount >= libRowCount) {
    throw new Error('移出后行数未减少: ' + libRowCount + ' → ' + afterRemoveCount);
  }
  console.log('PASS: 移出成功（' + libRowCount + ' → ' + afterRemoveCount + '）');

  // ── Step 6: 清理 — 删除测试库 ──
  console.log('Step 6: 清理测试库');
  await page.getByRole('button', { name: '删除库' }).click();
  await page.waitForTimeout(500);
  const delDialog = page.locator('[role="dialog"]').filter({ hasText: '删除审核点库' });
  await delDialog.waitFor({ timeout: 5000 });
  await delDialog.getByRole('button', { name: '确认删除' }).click();
  await page.waitForTimeout(2000);

  // 验证回到全部审核点
  const allTitle = page.locator('h2').getByText('全部审核点').first();
  if (!(await allTitle.isVisible())) throw new Error('删除库后未回到全部审核点');
  console.log('PASS: 测试库已清理');

  await page.screenshot({ path: SS + '-07-final.png', fullPage: true });
  console.log('== audit-AL6-library-membership 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 7: AL7-empty-state — 空状态与边界

**Files:**
- Create: `frontend/e2e/audit-AL7-empty-state.js`

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL7';

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  const rows = page.locator('table tbody tr');

  // ── Step 1: 搜索不存在的关键词 ──
  console.log('Step 1: 搜索不存在的关键词');
  const searchInput = page.getByPlaceholder('搜索审查要点...');
  await searchInput.fill('ZZZXXX_绝对不存在的审查要点_12345');
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-02-no-match.png', fullPage: true });

  const bodyText = await page.locator('table').textContent() || '';
  if (bodyText.includes('暂无') || bodyText.includes('请点击')) {
    console.log('PASS: 搜索无结果显示空状态提示');
  } else {
    const rowCount = await rows.count();
    if (rowCount === 0) {
      console.log('PASS: 搜索无结果（0 行）');
    } else {
      throw new Error('搜索无结果后仍有 ' + rowCount + ' 行');
    }
  }

  // 清空
  await searchInput.fill('');
  await page.waitForTimeout(500);

  // ── Step 2: 空库视图 ──
  console.log('Step 2: 空库视图');
  // 创建一个空库
  await page.getByRole('button', { name: '新建库' }).click();
  await page.waitForTimeout(500);
  const dialog = page.locator('[role="dialog"]').filter({ hasText: '新建审核点库' });
  await dialog.waitFor({ timeout: 5000 });
  const emptyLibName = 'E2E空库测试' + Date.now().toString().slice(-4);
  await dialog.locator('input[placeholder="库名称"]').fill(emptyLibName);
  await dialog.getByRole('button', { name: '创建' }).click();
  await page.waitForTimeout(2000);

  // 切换到空库
  await page.getByText(emptyLibName).first().click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: SS + '-03-empty-lib.png', fullPage: true });

  // 验证空状态
  const emptyHint = page.getByText('暂无审核点').first();
  if (await emptyHint.isVisible().catch(() => false)) {
    console.log('PASS: 空库显示"暂无审核点"');
  } else {
    const libRowCount = await rows.count();
    console.log('空库行数: ' + libRowCount + '（截图供检查）');
  }

  // 清理空库
  await page.getByRole('button', { name: '删除库' }).click();
  await page.waitForTimeout(500);
  const delDialog = page.locator('[role="dialog"]').filter({ hasText: '删除审核点库' });
  await delDialog.waitFor({ timeout: 5000 });
  await delDialog.getByRole('button', { name: '确认删除' }).click();
  await page.waitForTimeout(2000);
  console.log('PASS: 空库已清理');

  // ── Step 3: "加入库"按钮初始禁用 ──
  console.log('Step 3: "加入库"按钮初始禁用');
  const addBtn = page.getByRole('button', { name: '加入库' });
  if (!(await addBtn.isDisabled())) throw new Error('未选中审核点时"加入库"按钮未禁用');
  console.log('PASS: "加入库"按钮初始禁用');

  // ── Step 4: 加载状态截图 ──
  console.log('Step 4: 刷新捕获加载状态');
  await page.goto(BASE + '/audit-library');
  await page.screenshot({ path: SS + '-04-loading-state.png', fullPage: true });
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-05-loaded-state.png', fullPage: true });
  console.log('PASS: 加载状态截图已保存');

  console.log('== audit-AL7-empty-state 全部通过 ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 8: AL8-ai-extract — AI 智能提取

**Files:**
- Create: `frontend/e2e/audit-AL8-ai-extract.js`

**测试逻辑：** 上传真实法规文件 → AI 提取 → 等待三阶段完成 → 返回列表验证新审核点。这是长时间运行的端到端测试。

- [ ] **Step 1: 编写测试脚本**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL8';
  const DOC_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2025年政府采购领域"四类"违法违规行为专项整治工作指引.doc';
  const RULE_TITLE = '政府采购四类违规行为专项整治工作指引';

  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  // 记录初始审核点数
  const initRows = page.locator('table tbody tr');
  const initCount = await initRows.count();
  console.log('初始审核点数: ' + initCount);
  await page.screenshot({ path: SS + '-01-before-extract.png', fullPage: true });

  // ── Step 1: 进入 AI 提取模式 ──
  console.log('Step 1: 进入 AI 提取模式');
  await page.getByRole('button', { name: '上传' }).click();
  await page.waitForTimeout(500);
  await page.getByText('AI 提取').click();
  await page.waitForTimeout(1000);

  // 验证进入 extract 模式
  const extractTitle = page.getByText('AI 智能提取审查要点').first();
  await extractTitle.waitFor({ timeout: 5000 });
  await page.screenshot({ path: SS + '-02-extract-mode.png', fullPage: true });
  console.log('PASS: 进入 AI 提取模式');

  // ── Step 2: 填写法规标题 ──
  console.log('Step 2: 填写法规标题');
  const titleInput = page.getByPlaceholder('例如：政府采购法实施条例');
  await titleInput.fill(RULE_TITLE);

  // ── Step 3: 上传法规文件 ──
  console.log('Step 3: 上传法规文件（7.8MB）');
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(DOC_PATH);
  await page.waitForTimeout(1000);

  // 验证文件名显示
  const fileName = page.getByText('四类').first();
  if (!(await fileName.isVisible())) throw new Error('上传后文件名不可见');
  await page.screenshot({ path: SS + '-03-file-uploaded.png', fullPage: true });
  console.log('PASS: 法规文件已上传');

  // ── Step 4: 点击"开始抽取" ──
  console.log('Step 4: 开始抽取');
  const extractBtn = page.getByRole('button', { name: '开始抽取' });
  if (await extractBtn.isDisabled()) throw new Error('"开始抽取"按钮仍禁用');
  await extractBtn.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-04-extracting.png', fullPage: true });

  // ── Step 5: 验证进度卡片出现 ──
  console.log('Step 5: 验证进度卡片');
  const progressCard = page.getByText('提取进度').first();
  if (await progressCard.isVisible().catch(() => false)) {
    console.log('PASS: 提取进度卡片可见');

    // 验证三阶段标签
    const phases = ['分析法规结构', '逐条提取审查要点', '汇总并入库'];
    for (const phase of phases) {
      const el = page.getByText(phase).first();
      if (!(await el.isVisible().catch(() => false))) {
        console.log('WARN: 进度阶段"' + phase + '"不可见');
      }
    }
    await page.screenshot({ path: SS + '-05-progress-card.png', fullPage: true });
    console.log('PASS: 进度卡片三阶段标签已验证');
  } else {
    console.log('WARN: 进度卡片未出现（截图供检查）');
  }

  // ── Step 6: 等待提取完成（最长 30 分钟） ──
  console.log('Step 6: 等待提取完成（最长 30 分钟）...');
  var startTime = Date.now();
  var completed = false;
  var failed = false;
  var lastLog = 0;

  while (Date.now() - startTime < 1800000) {
    // 检查成功
    var successMsg = page.getByText('提取完成').first();
    if (await successMsg.isVisible().catch(function() { return false; })) {
      completed = true;
      break;
    }

    // 检查失败
    var failMsg = page.getByText('处理失败').first();
    if (await failMsg.isVisible().catch(function() { return false; })) {
      failed = true;
      break;
    }

    // 每分钟截图 + 日志
    var elapsed = Date.now() - startTime;
    if (elapsed - lastLog > 60000) {
      var mins = Math.floor(elapsed / 60000);
      await page.screenshot({ path: SS + '-progress-' + mins + 'min.png', fullPage: true });
      console.log('... 等待中 (' + mins + ' 分钟)');
      lastLog = elapsed;
    }
    await page.waitForTimeout(5000);
  }

  var secs = Math.floor((Date.now() - startTime) / 1000);

  if (failed) {
    await page.screenshot({ path: SS + '-06-failed.png', fullPage: true });
    var errEl = page.locator('.text-status-err').first();
    var errText = await errEl.textContent().catch(function() { return ''; });
    throw new Error('AI 提取失败 (' + secs + 's): ' + (errText || '').slice(0, 200));
  }

  if (!completed) {
    await page.screenshot({ path: SS + '-06-timeout.png', fullPage: true });
    throw new Error('AI 提取超时（30 分钟）');
  }

  await page.screenshot({ path: SS + '-06-completed.png', fullPage: true });
  console.log('PASS: AI 提取完成 (' + secs + 's)');

  // ── Step 7: 返回列表验证新审核点 ──
  console.log('Step 7: 返回列表验证');
  var backBtn = page.getByRole('button', { name: '返回列表' });
  await backBtn.click();
  await page.waitForTimeout(2000);

  var afterRows = page.locator('table tbody tr');
  var afterCount = await afterRows.count();
  if (afterCount <= initCount) {
    throw new Error('提取后审核点数未增加: ' + initCount + ' → ' + afterCount);
  }
  await page.screenshot({ path: SS + '-07-list-after-extract.png', fullPage: true });
  console.log('PASS: 审核点数增加（' + initCount + ' → ' + afterCount + '）');

  console.log('== audit-AL8-ai-extract 全部通过 (' + secs + 's) ==');
}
```

- [ ] **Step 2: 运行测试验证**
- [ ] **Step 3: 审查截图**

---

### Task 9: 注册测试到 run-tests.sh

**Files:**
- Modify: `frontend/e2e/run-tests.sh:41-44`

- [ ] **Step 1: 添加 AUDIT_TESTS 数组和 `--page audit` 支持**

在 `run-tests.sh` 的测试清单区域（第 41-44 行），在 `COMPARE_TESTS` 后面添加：

```bash
AUDIT_TESTS=("audit-AL1-skeleton" "audit-AL2-import" "audit-AL3-search-filter" "audit-AL4-library-crud" "audit-AL5-checkpoint-edit-delete" "audit-AL6-library-membership" "audit-AL7-empty-state" "audit-AL8-ai-extract")
```

修改 `ALL_TESTS` 行为：

```bash
ALL_TESTS=("${FILES_TESTS[@]}" "${COMPARE_TESTS[@]}" "${AUDIT_TESTS[@]}")
```

在 `case "$PAGE"` 区域添加 audit 分支：

```bash
audit) TESTS=("${AUDIT_TESTS[@]}") ;;
```

- [ ] **Step 2: 验证脚本语法**

```bash
bash -n frontend/e2e/run-tests.sh && echo "语法正确"
```

- [ ] **Step 3: 试运行单个测试**

```bash
bash frontend/e2e/run-tests.sh --only audit-AL1-skeleton
```

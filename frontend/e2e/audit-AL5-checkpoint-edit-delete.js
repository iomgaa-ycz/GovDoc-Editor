async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL5';

  // Step 1: 进入审核点库页，确认有数据
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 审核点库为空（AL2 未导入数据），无法测试编辑/删除');
    return;
  }
  console.log('初始行数: ' + initialCount);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 2: 编辑审查要点 ──
  const firstRow = rows.first();
  const firstRowActions = firstRow.locator('td').last();
  const editBtn = firstRowActions.locator('button').first();
  await editBtn.click();

  const editDialog = page.locator('[role="dialog"]');
  await editDialog.waitFor({ state: 'visible', timeout: 5000 });
  const editTitle = editDialog.getByText('编辑审查要点');
  if (!(await editTitle.isVisible())) throw new Error('编辑对话框标题"编辑审查要点"不可见');
  console.log('PASS: 编辑对话框弹出');

  // 验证标题 input 已预填（非空）
  const titleInput = editDialog.locator('input').first();
  const originalTitle = await titleInput.inputValue();
  if (!originalTitle || originalTitle.trim().length === 0) {
    throw new Error('编辑对话框标题 input 为空，未预填');
  }
  console.log('PASS: 标题已预填: "' + originalTitle.slice(0, 30) + '..."');

  // 验证 textarea 存在
  const textarea = editDialog.locator('textarea');
  if (!(await textarea.isVisible())) throw new Error('编辑对话框 textarea 不可见');
  console.log('PASS: textarea 可见');

  // 追加 "[E2E已编辑]" 到标题
  const editedTitle = originalTitle + '[E2E已编辑]';
  await titleInput.fill(editedTitle);
  await page.screenshot({ path: SS + '-02-edit-form.png', fullPage: true });

  // 点击保存修改
  const saveBtn = editDialog.getByRole('button', { name: '保存修改' });
  await saveBtn.click();
  await page.waitForTimeout(2000);

  // 验证对话框关闭
  if (await editDialog.isVisible()) throw new Error('保存后编辑对话框未关闭');
  console.log('PASS: 编辑对话框已关闭');

  // 验证表格中包含 "[E2E已编辑]"
  const editedText = page.getByText('[E2E已编辑]').first();
  if (!(await editedText.isVisible())) throw new Error('表格中未找到 "[E2E已编辑]" 文本');
  await page.screenshot({ path: SS + '-03-after-edit.png', fullPage: true });
  console.log('PASS: 表格已显示编辑后的标题');

  // ── Step 3: 恢复原标题 ──
  const editBtn2 = rows.first().locator('td').last().locator('button').first();
  await editBtn2.click();
  await editDialog.waitFor({ state: 'visible', timeout: 5000 });

  const titleInput2 = editDialog.locator('input').first();
  await titleInput2.fill(originalTitle);
  const saveBtn2 = editDialog.getByRole('button', { name: '保存修改' });
  await saveBtn2.click();
  await page.waitForTimeout(2000);

  if (await editDialog.isVisible()) throw new Error('恢复标题后对话框未关闭');
  console.log('PASS: 标题已恢复为原始值');

  // ── Step 4: 删除 — 取消 ──
  const lastRow = rows.last();
  const lastRowActions = lastRow.locator('td').last();
  const deleteBtn = lastRowActions.locator('button').last();
  await deleteBtn.click();

  const deleteDialog = page.locator('[role="dialog"]');
  await deleteDialog.waitFor({ state: 'visible', timeout: 5000 });
  const deleteTitle = deleteDialog.getByText('确认删除');
  if (!(await deleteTitle.isVisible())) throw new Error('删除对话框标题"确认删除"不可见');

  // 验证 "此操作不可撤销" 警告
  const warningText = deleteDialog.getByText('此操作不可撤销');
  if (!(await warningText.isVisible())) throw new Error('删除对话框"此操作不可撤销"警告不可见');
  console.log('PASS: 删除确认对话框显示正确');
  await page.screenshot({ path: SS + '-04-delete-confirm.png', fullPage: true });

  // 点击取消
  const cancelBtn = deleteDialog.getByRole('button', { name: '取消' });
  await cancelBtn.click();
  await page.waitForTimeout(500);

  // 验证行数不变
  const afterCancelCount = await rows.count();
  if (afterCancelCount !== initialCount) {
    throw new Error('取消删除后行数变化: ' + initialCount + ' → ' + afterCancelCount);
  }
  console.log('PASS: 取消删除，行数不变（' + afterCancelCount + '）');

  // ── Step 5: 删除 — 确认 ──
  const deleteBtn2 = rows.last().locator('td').last().locator('button').last();
  await deleteBtn2.click();
  await deleteDialog.waitFor({ state: 'visible', timeout: 5000 });

  const confirmDeleteBtn = deleteDialog.getByRole('button', { name: '确认删除' });
  await confirmDeleteBtn.click();
  await page.waitForTimeout(2000);

  // 验证行数减少
  const afterDeleteCount = await rows.count();
  if (afterDeleteCount >= initialCount) {
    throw new Error('确认删除后行数未减少: ' + initialCount + ' → ' + afterDeleteCount);
  }
  await page.screenshot({ path: SS + '-05-after-delete.png', fullPage: true });
  console.log('PASS: 确认删除，行数减少（' + initialCount + ' → ' + afterDeleteCount + '）');

  console.log('== audit-AL5-checkpoint-edit-delete 全部通过 ==');
}

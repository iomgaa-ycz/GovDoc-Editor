async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL4';
  const libName = 'E2E测试库' + Date.now().toString().slice(-4);

  // Step 1: 进入审核点库页
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });
  console.log('PASS: 审核点库页加载完成');

  // Step 2: 新建库
  const createBtn = page.getByRole('button', { name: '新建库' });
  if (!(await createBtn.isVisible())) throw new Error('"新建库"按钮不可见');
  await createBtn.click();

  const createDialog = page.locator('[role="dialog"]');
  await createDialog.waitFor({ state: 'visible', timeout: 5000 });
  const createTitle = createDialog.getByText('新建审核点库');
  if (!(await createTitle.isVisible())) throw new Error('新建对话框标题"新建审核点库"不可见');
  console.log('PASS: 新建库对话框弹出');

  // 填写名称和说明（等待 input 渲染完成，Radix Dialog 有进入动画）
  const nameInput = createDialog.locator('input[placeholder="库名称"]');
  await nameInput.waitFor({ state: 'visible', timeout: 5000 });
  await nameInput.fill(libName);
  const descTextarea = createDialog.locator('textarea[placeholder*="说明"]');
  await descTextarea.fill('E2E 自动化测试创建的审核点库');
  await page.screenshot({ path: SS + '-02-create-form.png', fullPage: true });

  // 点击创建
  const confirmCreateBtn = createDialog.getByRole('button', { name: '创建' });
  await confirmCreateBtn.click();
  await page.waitForTimeout(2000);

  // 验证对话框关闭
  if (await createDialog.isVisible()) throw new Error('创建后对话框未关闭');
  console.log('PASS: 创建对话框已关闭');

  // 验证侧栏可见
  const sidebarEntry = page.getByText(libName).first();
  if (!(await sidebarEntry.isVisible())) throw new Error('侧栏未显示新库: ' + libName);
  await page.screenshot({ path: SS + '-03-after-create.png', fullPage: true });
  console.log('PASS: 新库"' + libName + '"已出现在侧栏');

  // Step 3: 切换到库视图
  await sidebarEntry.click();
  await page.waitForTimeout(1000);

  const heading = page.locator('h2').getByText(libName);
  if (!(await heading.isVisible())) throw new Error('库视图 h2 未显示库名: ' + libName);

  const editBtn = page.getByRole('button', { name: '编辑库' });
  const deleteBtn = page.getByRole('button', { name: '删除库' });
  if (!(await editBtn.isVisible())) throw new Error('"编辑库"按钮不可见');
  if (!(await deleteBtn.isVisible())) throw new Error('"删除库"按钮不可见');
  await page.screenshot({ path: SS + '-04-library-view.png', fullPage: true });
  console.log('PASS: 库视图显示正确，编辑/删除按钮可见');

  // Step 4: 编辑库
  await editBtn.click();
  const editDialog = page.locator('[role="dialog"]');
  await editDialog.waitFor({ state: 'visible', timeout: 5000 });
  const editTitle = editDialog.getByText('编辑审核点库');
  if (!(await editTitle.isVisible())) throw new Error('编辑对话框标题"编辑审核点库"不可见');

  // 验证名称已预填（编辑对话框 Input 无 placeholder，label 也未用 htmlFor 关联，直接取第一个 input）
  const editNameInput = editDialog.locator('input').first();
  const prefilledValue = await editNameInput.inputValue();
  if (prefilledValue !== libName) throw new Error('编辑对话框名称未预填: 期望"' + libName + '"，实际"' + prefilledValue + '"');
  console.log('PASS: 编辑对话框名称已预填');

  // 修改名称
  const editedName = libName + '-已编辑';
  await editNameInput.fill(editedName);
  const saveBtn = editDialog.getByRole('button', { name: '保存' });
  await saveBtn.click();
  await page.waitForTimeout(2000);

  // 验证侧栏显示更新后的名称
  const updatedEntry = page.getByText(editedName).first();
  if (!(await updatedEntry.isVisible())) throw new Error('侧栏未显示更新后的库名: ' + editedName);
  await page.screenshot({ path: SS + '-05-after-edit.png', fullPage: true });
  console.log('PASS: 库名已更新为"' + editedName + '"');

  // Step 5: 删除库
  const deleteBtn2 = page.getByRole('button', { name: '删除库' });
  await deleteBtn2.click();
  const deleteDialog = page.locator('[role="dialog"]');
  await deleteDialog.waitFor({ state: 'visible', timeout: 5000 });
  const deleteTitle = deleteDialog.getByText('删除审核点库');
  if (!(await deleteTitle.isVisible())) throw new Error('删除对话框标题"删除审核点库"不可见');

  // 验证对话框文本包含库名
  const dialogText = await deleteDialog.textContent();
  if (!dialogText.includes(editedName)) throw new Error('删除对话框未包含库名"' + editedName + '"');
  await page.screenshot({ path: SS + '-06-delete-confirm.png', fullPage: true });
  console.log('PASS: 删除确认对话框显示正确');

  // 确认删除
  const confirmDeleteBtn = deleteDialog.getByRole('button', { name: '确认删除' });
  await confirmDeleteBtn.click();
  await page.waitForTimeout(2000);

  // 验证回到"全部审核点"视图
  const allPointsHeading = page.locator('h2').getByText('全部审核点');
  if (!(await allPointsHeading.isVisible())) throw new Error('删除后未回到"全部审核点"视图');
  console.log('PASS: 已回到"全部审核点"视图');

  // 验证已删除的库不在侧栏
  const deletedEntry = page.getByText(editedName);
  if (await deletedEntry.isVisible()) throw new Error('删除后侧栏仍显示已删除的库: ' + editedName);
  await page.screenshot({ path: SS + '-07-after-delete.png', fullPage: true });
  console.log('PASS: 已删除的库不再出现在侧栏');

  console.log('== audit-AL4-library-crud 全部通过 ==');
}

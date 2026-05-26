async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C3';

  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');

  // 辅助：从文件库选择 N 个文件
  async function pickFiles(n) {
    await page.getByRole('button', { name: /从文件库添加|从文件库选择文件/ }).first().click();
    const modal = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' });
    await modal.waitFor({ timeout: 10000 });
    const items = modal.locator('.overflow-y-auto button.w-full');
    for (let retry = 0; retry < 20; retry++) {
      if (await items.count() > 0) break;
      await page.waitForTimeout(500);
    }
    const available = await items.count();
    const toSelect = Math.min(n, available);
    for (let i = 0; i < toSelect; i++) {
      await items.nth(i).click();
      await page.waitForTimeout(200);
    }
    await modal.getByRole('button', { name: '确认选择' }).click();
    await page.waitForTimeout(500);
    return toSelect;
  }

  // Step 1: 选择 2 个文件
  console.log('Step 1: 选择 2 个文件');
  const picked = await pickFiles(2);
  if (picked < 2) throw new Error('文件库不足 2 个已转换文件');
  await page.screenshot({ path: SS + '-01-two-files.png', fullPage: true });

  // 验证 badge
  const badge = page.getByText(/已选 \d+ 个文件/);
  if (!(await badge.isVisible())) throw new Error('文件数 badge 不可见');
  const badgeText = await badge.textContent() || '';
  console.log('PASS: badge 显示 "' + badgeText.trim() + '"');

  // 验证卡片 — 显示文件名和大小
  const removeButtons = page.locator('button[aria-label*="移除"]');
  const initialCards = await removeButtons.count();
  if (initialCards < 2) throw new Error('文件卡片不足 2 个: ' + initialCards);
  console.log('PASS: ' + initialCards + ' 个文件卡片');

  // 验证 "开始对比" 按钮启用
  const compareBtn = page.getByRole('button', { name: /开始对比/ });
  if (await compareBtn.isDisabled()) throw new Error('2 个文件时"开始对比"按钮仍禁用');
  console.log('PASS: 2 个文件时"开始对比"按钮启用');

  // Step 2: 移除 1 个文件
  console.log('Step 2: 移除 1 个文件');
  await removeButtons.first().click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: SS + '-02-one-removed.png', fullPage: true });

  const afterRemoveCards = await page.locator('button[aria-label*="移除"]').count();
  if (afterRemoveCards !== initialCards - 1) {
    throw new Error('移除后卡片数异常: ' + initialCards + ' → ' + afterRemoveCards);
  }
  console.log('PASS: 移除成功（' + initialCards + ' → ' + afterRemoveCards + '）');

  // "开始对比" 按钮应回到禁用（只剩 1 个文件）
  if (!(await compareBtn.isDisabled())) throw new Error('1 个文件时"开始对比"按钮未禁用');
  console.log('PASS: 1 个文件时"开始对比"按钮禁用');

  // Step 3: 再次打开 picker 追加文件
  console.log('Step 3: 追加文件');
  const added = await pickFiles(1);
  if (added < 1) throw new Error('追加文件失败');
  await page.screenshot({ path: SS + '-03-added-back.png', fullPage: true });

  const afterAddCards = await page.locator('button[aria-label*="移除"]').count();
  if (afterAddCards < 2) throw new Error('追加后卡片不足 2: ' + afterAddCards);
  if (await compareBtn.isDisabled()) throw new Error('追加后"开始对比"按钮仍禁用');
  console.log('PASS: 追加后卡片 ' + afterAddCards + ' 个，按钮启用');

  // Step 4: 移除全部文件 → 空状态
  console.log('Step 4: 移除全部文件');
  let remaining = await page.locator('button[aria-label*="移除"]').count();
  while (remaining > 0) {
    await page.locator('button[aria-label*="移除"]').first().click();
    await page.waitForTimeout(200);
    remaining = await page.locator('button[aria-label*="移除"]').count();
  }
  await page.screenshot({ path: SS + '-04-empty-state.png', fullPage: true });

  // 验证空状态
  const emptyHint = page.getByText('从文件库选择已转换完成的文件').first();
  if (!(await emptyHint.isVisible())) throw new Error('移除全部后空状态未恢复');
  if (!(await compareBtn.isDisabled())) throw new Error('空状态时"开始对比"按钮未禁用');
  console.log('PASS: 空状态恢复，按钮禁用');

  console.log('== compare-C3-selection-manage 全部通过 ==');
}

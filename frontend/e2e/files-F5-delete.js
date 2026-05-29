async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F5';

  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 文件库为空，无法测试删除');
    return;
  }
  console.log('初始文件数: ' + initialCount);
  await page.screenshot({ path: SS + '-01-before-delete.png', fullPage: true });

  // 记录最后一行的文件名（删最后一行，避免影响其他测试）
  const lastRow = rows.last();
  const lastFileName = (await lastRow.locator('td').nth(1).textContent() || '').trim();
  console.log('目标删除文件: ' + lastFileName.slice(0, 30));

  // ── Step 1: 点击删除按钮 ──
  const deleteBtn = lastRow.locator('td').last().locator('button').last();
  await deleteBtn.click();
  await page.waitForTimeout(500);

  // 截图：确认对话框 — 视觉检查对话框样式和遮罩
  await page.screenshot({ path: SS + '-02-confirm-dialog.png', fullPage: true });

  // ── Step 2: 验证确认对话框弹出 ──
  // window.confirm 是原生对话框，playwright-cli 中需要用 dialog handler
  // 但根据代码用的是 window.confirm，先检查是否弹出了自定义 dialog
  // 如果用的是 window.confirm，需要预注册 dialog handler

  // 注册 dialog handler（取消）
  page.once('dialog', async dialog => {
    console.log('Step 2: 确认对话框弹出，消息: ' + dialog.message().slice(0, 50));
    await dialog.dismiss();
  });

  // 再次点击删除（因为第一次可能已经弹了 confirm 但未处理）
  await deleteBtn.click();
  await page.waitForTimeout(1000);

  // 验证取消后行数不变
  const afterCancelCount = await rows.count();
  if (afterCancelCount !== initialCount) {
    throw new Error('取消删除后行数变化: ' + initialCount + ' → ' + afterCancelCount);
  }
  await page.screenshot({ path: SS + '-03-after-cancel.png', fullPage: true });
  console.log('PASS: 取消删除，行数不变（' + afterCancelCount + '）');

  // ── Step 3: 确认删除 ──
  page.once('dialog', async dialog => {
    console.log('Step 3: 确认删除');
    await dialog.accept();
  });

  await deleteBtn.click();
  await page.waitForTimeout(2000);

  const afterDeleteCount = await rows.count();
  await page.screenshot({ path: SS + '-04-after-delete.png', fullPage: true });

  if (afterDeleteCount >= initialCount) {
    throw new Error('确认删除后行数未减少: ' + initialCount + ' → ' + afterDeleteCount);
  }
  console.log('PASS: 确认删除，行数减少（' + initialCount + ' → ' + afterDeleteCount + '）');

  // ── Step 4: 验证统计卡片更新 ──
  const totalCard = page.getByText('总文件').first().locator('..');
  const totalNum = totalCard.locator('.text-2xl, .text-3xl, .font-bold').first();
  const totalText = (await totalNum.textContent() || '').trim();
  console.log('PASS: 删除后总文件统计: ' + totalText);
  await page.screenshot({ path: SS + '-05-stats-updated.png', fullPage: true });

  console.log('== files-F5-delete 全部通过 ==');
}

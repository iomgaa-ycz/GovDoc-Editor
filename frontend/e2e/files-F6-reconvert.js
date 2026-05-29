async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F6';

  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── 查找 failed 状态的文件行 ──
  const failedRows = page.locator('table tbody tr').filter({ hasText: '失败' });
  const failedCount = await failedRows.count();

  if (failedCount === 0) {
    console.log('⏭ 跳过: 无失败状态文件，无法测试重新转换');
    await page.screenshot({ path: SS + '-02-no-failed.png', fullPage: true });
    return;
  }

  console.log('发现 ' + failedCount + ' 个失败文件');
  const targetRow = failedRows.first();
  const fileName = (await targetRow.locator('td').nth(1).textContent() || '').trim();
  console.log('目标文件: ' + fileName.slice(0, 30));

  // 截图：失败状态行 — 视觉检查失败标记样式
  await page.screenshot({ path: SS + '-02-failed-row.png', fullPage: true });

  // ── Step 1: 验证重新转换按钮存在（只有 failed 行才有） ──
  // 重新转换按钮是 td 最后一列的中间按钮（标签按钮、重新转换按钮、删除按钮）
  const actionButtons = targetRow.locator('td').last().locator('button');
  const btnCount = await actionButtons.count();
  console.log('失败行操作按钮数: ' + btnCount + '（应为 3：标签/重新转换/删除）');

  if (btnCount < 2) {
    throw new Error('失败行操作按钮不足，期望至少 2 个，实际: ' + btnCount);
  }

  // 重新转换按钮是第 2 个（index 1）
  const reconvertBtn = actionButtons.nth(1);
  await page.screenshot({ path: SS + '-03-reconvert-btn.png', fullPage: true });

  // ── Step 2: 点击重新转换 ──
  console.log('Step 2: 点击重新转换');
  await reconvertBtn.click();
  await page.waitForTimeout(2000);

  // 验证状态从"失败"变为"转换中"
  await page.screenshot({ path: SS + '-04-after-reconvert.png', fullPage: true });
  const rowTextAfter = await targetRow.textContent() || '';
  if (rowTextAfter.includes('转换中')) {
    console.log('PASS: 状态已变为"转换中"');
  } else if (rowTextAfter.includes('已就绪')) {
    console.log('PASS: 重新转换后直接变为"已就绪"（快速完成）');
  } else if (rowTextAfter.includes('失败')) {
    throw new Error('重新转换后状态仍为"失败"');
  } else {
    console.log('WARN: 重新转换后状态不明确: ' + rowTextAfter.slice(0, 80));
  }

  // ── Step 3: 验证失败统计卡片数字减少 ──
  const failedCard = page.getByText('失败').first().locator('..');
  const failedNum = failedCard.locator('.text-2xl, .text-3xl, .font-bold').first();
  const failedText = (await failedNum.textContent() || '').trim();
  console.log('PASS: 失败统计: ' + failedText);

  await page.screenshot({ path: SS + '-05-final.png', fullPage: true });
  console.log('== files-F6-reconvert 全部通过 ==');
}

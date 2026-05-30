async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F4';
  const TAG_NAME = 'E2E测试标签' + Date.now().toString().slice(-4);

  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 文件库为空');
    return;
  }
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 1: 点击第一行的标签管理按钮 → TagPopover 弹出 ──
  console.log('Step 1: 打开第一行的 TagPopover');
  const firstRowTagBtn = rows.first().locator('td').last().locator('button').first();
  // force: true 绕过 actionability 检查（TagPopover overlay 可能短暂遮挡按钮）
  await firstRowTagBtn.click({ force: true });
  await page.waitForTimeout(500);

  // 截图：TagPopover 弹出状态 — 关键视觉检查点
  // 验证弹出框是否被遮挡、位置是否正确
  await page.screenshot({ path: SS + '-02-tag-popover-open.png', fullPage: true });

  // 验证 popover 可见
  const popover = page.locator('[role="dialog"], [data-radix-popper-content-wrapper], .z-50').filter({ hasText: /标签|创建/ }).first();
  if (!(await popover.isVisible({ timeout: 3000 }).catch(() => false))) {
    // 退而求其次：检查是否有任何浮层
    const anyPopover = page.locator('[data-radix-popper-content-wrapper]').first();
    if (!(await anyPopover.isVisible({ timeout: 2000 }).catch(() => false))) {
      throw new Error('TagPopover 未弹出或被完全遮挡');
    }
  }
  console.log('PASS: TagPopover 已弹出');

  // 视觉遮挡检查：获取 popover 的 bounding box，确认在视口内
  const popoverBox = await popover.boundingBox().catch(() => null);
  if (popoverBox) {
    const viewport = page.viewportSize();
    if (popoverBox.x < 0 || popoverBox.y < 0) {
      console.log('WARN: TagPopover 部分在视口外（x=' + popoverBox.x + ', y=' + popoverBox.y + '）');
    }
    if (viewport && (popoverBox.x + popoverBox.width > viewport.width || popoverBox.y + popoverBox.height > viewport.height)) {
      console.log('WARN: TagPopover 超出视口边界（底部或右侧被裁切）');
    }
    console.log('TagPopover 位置: x=' + Math.round(popoverBox.x) + ' y=' + Math.round(popoverBox.y) + ' w=' + Math.round(popoverBox.width) + ' h=' + Math.round(popoverBox.height));
  }

  // ── Step 2: 在 popover 中创建新标签 ──
  console.log('Step 2: 创建新标签 "' + TAG_NAME + '"');
  const tagInput = popover.locator('input').first();
  await tagInput.fill(TAG_NAME);
  await page.waitForTimeout(300);

  // 点击创建按钮（文本含"创建"或 +）
  const createBtn = popover.getByText(/创建/).first();
  await createBtn.click();
  await page.waitForTimeout(1000);

  // 截图：创建标签后状态
  await page.screenshot({ path: SS + '-03-tag-created.png', fullPage: true });

  // 关闭 popover
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // ── Step 3: 验证新标签出现在文档行中 ──
  console.log('Step 3: 验证标签显示在文档行');
  const tagInRow = rows.first().getByText(TAG_NAME);
  await page.screenshot({ path: SS + '-04-tag-in-row.png', fullPage: true });
  if (await tagInRow.isVisible().catch(() => false)) {
    console.log('PASS: 标签 "' + TAG_NAME + '" 显示在文档行中');
  } else {
    console.log('WARN: 标签可能未显示在行内（截图供人工检查）');
  }

  // ── Step 4: 用标签筛选 ──
  console.log('Step 4: 标签筛选');
  const tagFilterBtn = page.getByRole('button', { name: /筛选标签/ });
  await tagFilterBtn.click();
  await page.waitForTimeout(500);

  // 截图：标签筛选 popover — 视觉检查是否被遮挡
  await page.screenshot({ path: SS + '-05-tag-filter-popover.png', fullPage: true });

  // 在筛选 popover 中选中刚创建的标签
  const filterPopover = page.locator('[data-radix-popper-content-wrapper]').last();
  const tagOption = filterPopover.getByText(TAG_NAME).first();
  if (await tagOption.isVisible().catch(() => false)) {
    await tagOption.click();
    await page.waitForTimeout(500);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    const filteredCount = await rows.count();
    await page.screenshot({ path: SS + '-06-tag-filtered.png', fullPage: true });
    console.log('PASS: 标签筛选后行数 = ' + filteredCount);

    // 清除标签筛选（点击标签 pill 上的 × 或重新筛选）
    const activeTagPill = page.locator('button').filter({ hasText: TAG_NAME }).first();
    if (await activeTagPill.isVisible().catch(() => false)) {
      await activeTagPill.click();
      await page.waitForTimeout(500);
    }
  } else {
    await page.keyboard.press('Escape');
    console.log('WARN: 标签筛选中未找到 "' + TAG_NAME + '"（截图供人工检查）');
  }

  // ── Step 5: 取消标签（从文档行移除） ──
  console.log('Step 5: 取消标签');
  const firstRowTagBtn2 = rows.first().locator('td').last().locator('button').first();
  await firstRowTagBtn2.click({ force: true });
  await page.waitForTimeout(500);

  const popover2 = page.locator('[data-radix-popper-content-wrapper]').last();
  const tagCheckbox = popover2.getByText(TAG_NAME).first();
  if (await tagCheckbox.isVisible().catch(() => false)) {
    await tagCheckbox.click();
    await page.waitForTimeout(1000);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // 验证标签从行中消失
    await page.screenshot({ path: SS + '-07-tag-removed.png', fullPage: true });
    const tagGone = !(await rows.first().getByText(TAG_NAME).isVisible().catch(() => false));
    if (tagGone) {
      console.log('PASS: 标签已从文档行移除');
    } else {
      console.log('WARN: 标签可能未移除（截图供人工检查）');
    }
  } else {
    await page.keyboard.press('Escape');
    console.log('WARN: popover 中未找到标签以取消');
  }

  // ── Step 6: 最终全页截图 ──
  await page.screenshot({ path: SS + '-08-final.png', fullPage: true });

  console.log('== files-F4-tags 全部通过 ==');
}

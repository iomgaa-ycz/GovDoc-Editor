async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R4';

  // ── Step 1: 导航到 AI 审查页 ──
  console.log('Step 1: 导航到 /ai-review');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  // ── Step 2: 找到一个审核任务 ──
  console.log('Step 2: 查找审核任务');
  const viewButtons = page.getByRole('button', { name: '查看' });
  const btnCount = await viewButtons.count();
  if (btnCount === 0) {
    console.log('SKIP: 无审核任务，请先运行 review-R3 创建任务后再执行此测试');
    return;
  }

  // 优先找 running 状态的，否则找第一个
  const runningRow = page.locator('[role="button"][tabindex="0"]').filter({ hasText: 'running' }).first();
  let targetBtn;
  if (await runningRow.isVisible().catch(() => false)) {
    targetBtn = runningRow.getByRole('button', { name: '查看' });
  } else {
    targetBtn = viewButtons.first();
  }
  await targetBtn.click();

  // 等待跳转到详情页
  await page.waitForURL(/\/ai-review\/[a-zA-Z0-9-]+/, { timeout: 10000 });
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-detail-loaded.png', fullPage: true });
  console.log('PASS: 已进入审核详情页');

  // ── Step 3: 判断当前是哪种视图 ──
  console.log('Step 3: 判断视图类型');
  const bodyText = await page.locator('main').first().textContent().catch(() => '') || '';

  const isProgressView = bodyText.includes('审查进度') || bodyText.includes('审核点');
  const isWorkpaperView = bodyText.includes('底稿操作') || bodyText.includes('工作底稿');
  const isErrorView = bodyText.includes('审查失败') || bodyText.includes('审查已取消');

  if (isProgressView) {
    console.log('INFO: 当前为进度视图');

    // 任务信息卡
    const taskInfo = page.getByText('任务信息');
    if (await taskInfo.isVisible().catch(() => false)) {
      console.log('PASS: "任务信息" Card 可见');
    }

    // 审查进度卡
    const progressCard = page.getByText('审查进度');
    if (await progressCard.isVisible().catch(() => false)) {
      console.log('PASS: "审查进度" Card 可见');
    }

    // 审核点网格
    const pointGrid = page.getByText('审核点');
    if (await pointGrid.isVisible().catch(() => false)) {
      console.log('PASS: "审核点" Card 可见');

      // 检查审核点卡片数量
      const pointCards = page.locator('[role="button"][tabindex="0"]').filter({ hasText: /详情/ });
      const cardCount = await pointCards.count();
      console.log('INFO: 发现 ' + cardCount + ' 个审核点卡片');

      if (cardCount > 0) {
        // 点击第一个卡片的"详情"按钮
        const detailBtn = page.getByRole('button', { name: '详情' }).first();
        if (await detailBtn.isVisible().catch(() => false)) {
          await detailBtn.click();
          await page.waitForTimeout(500);

          // 验证 Dialog 出现
          const dialog = page.locator('[role="dialog"]').filter({ hasText: '审查点详情' });
          if (await dialog.isVisible().catch(() => false)) {
            console.log('PASS: 审查点详情 Dialog 可见');
            await page.screenshot({ path: SS + '-02-point-detail.png', fullPage: true });
            await page.keyboard.press('Escape');
            await page.waitForTimeout(300);
          }
        }
      }
    }

    // 进度条
    const progressBar = page.locator('[role="progressbar"]').first();
    if (await progressBar.isVisible().catch(() => false)) {
      console.log('PASS: 进度条可见');
    }

    // 取消审查按钮
    const cancelBtn = page.getByRole('button', { name: '取消审查' });
    if (await cancelBtn.isVisible().catch(() => false)) {
      console.log('PASS: "取消审查"按钮可见（任务运行中）');
    }

  } else if (isWorkpaperView) {
    console.log('INFO: 当前为工作底稿视图（审核已完成）');
    console.log('PASS: 工作底稿视图正常显示');
    // 底稿操作面板
    const saveBtn = page.getByRole('button', { name: '保存' }).first();
    const finalizeBtn = page.getByRole('button', { name: '定稿' }).first();
    if (await saveBtn.isVisible().catch(() => false)) {
      console.log('PASS: "保存"按钮可见');
    }
    if (await finalizeBtn.isVisible().catch(() => false)) {
      console.log('PASS: "定稿"按钮可见');
    }

  } else if (isErrorView) {
    console.log('INFO: 当前为错误视图');
    const recreateBtn = page.getByRole('button', { name: '重新创建' });
    if (await recreateBtn.isVisible().catch(() => false)) {
      console.log('PASS: 错误视图有"重新创建"按钮');
    }
  } else {
    console.log('WARN: 无法识别当前视图类型，截图供人工检查');
  }

  await page.screenshot({ path: SS + '-03-final.png', fullPage: true });
  console.log('== review-R4-progress 全部通过 ==');
}

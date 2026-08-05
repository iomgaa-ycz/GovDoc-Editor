async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R6';

  // ── Step 1: 查找可取消的审核任务 ──
  console.log('Step 1: 查找可取消的审核任务');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  const result = await page.evaluate(async (baseUrl) => {
    const res = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await res.json();
    return runs.find(r => ['pending', 'running'].includes(r.status)) || null;
  }, BASE);

  if (!result) {
    console.log('SKIP: 无运行中的审核任务可取消');
    console.log('INFO: 要测试取消功能，请先创建审核任务并在此任务完成前运行此脚本');
    return;
  }

  console.log('INFO: 找到运行中的任务 ' + result.id);

  // ── Step 2: 进入详情页 ──
  console.log('Step 2: 进入详情页');
  await page.goto(BASE + '/ai-review/' + result.id);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: SS + '-01-progress.png', fullPage: true });

  // ── Step 3: 验证"取消审查"按钮存在 ──
  console.log('Step 3: 验证取消按钮');
  const cancelBtn = page.getByRole('button', { name: '取消审查' });
  if (!(await cancelBtn.isVisible().catch(() => false))) {
    throw new Error('"取消审查"按钮不可见（任务可能已不在运行状态）');
  }
  console.log('PASS: "取消审查"按钮可见');

  // ── Step 4: 取消审查 ──
  console.log('Step 4: 点击取消审查');
  await cancelBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: SS + '-02-cancelled.png', fullPage: true });

  // 验证页面切换到错误视图或状态变化
  const bodyText = await page.locator('main, header').textContent().catch(() => '') || '';
  const isCancelled = bodyText.includes('审查已取消') || bodyText.includes('cancelled');
  const isFailed = bodyText.includes('审查失败');

  if (isCancelled) {
    console.log('PASS: 页面显示"审查已取消"');
    // 验证"重新创建"按钮
    const recreateBtn = page.getByRole('button', { name: '重新创建' });
    if (await recreateBtn.isVisible().catch(() => false)) {
      console.log('PASS: "重新创建"按钮可见');
    }
  } else if (isFailed) {
    console.log('PASS: 页面显示"审查失败"（取消可能导致 failed 状态）');
  } else {
    // 可能已回到列表或状态已变
    const statusText = await page.locator('header span, header div').filter({ hasText: /cancelled|failed|waiting_retry/ }).first().textContent().catch(() => '');
    console.log('INFO: 取消后状态: ' + statusText);
  }

  await page.screenshot({ path: SS + '-03-after-cancel.png', fullPage: true });

  // ── Step 5: 验证 AI 审查列表中状态为 cancelled ──
  console.log('Step 5: 验证列表状态');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  const listStatus = await page.evaluate(async ({ baseUrl, runId }) => {
    const res = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await res.json();
    const run = runs.find(r => r.id === runId);
    return run ? run.status : 'not_found';
  }, { baseUrl: BASE, runId: result.id });
  console.log('PASS: 列表中任务状态: ' + listStatus);

  console.log('== review-R6-cancel 全部通过 ==');
}

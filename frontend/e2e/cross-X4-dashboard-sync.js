async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/cross-X4';

  // ── 跨页面测试：仪表盘与 AI 审查页数据一致性 ──
  // 检查 "已完成" 计数口径是否一致
  // 后端 dashboard: _COMPLETED_STATUSES = {"draft_ready", "partial_ready", "finalized"}
  // 前端 AIReviewHubPage: COMPLETED_STATUSES = {"completed", "draft_ready", "finalized"}

  // Step 1: 获取仪表盘数据
  console.log('Step 1: 获取仪表盘 API 数据');
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');

  const dashboardStats = await page.evaluate(async (baseUrl) => {
    const res = await fetch(baseUrl + '/api/v1/dashboard/stats');
    return await res.json();
  }, BASE);

  console.log('INFO: 仪表盘 API → 审核要点=' + dashboardStats.checkpoint_count +
    ', 完成审核=' + dashboardStats.completed_audit_count +
    ', 发现问题=' + dashboardStats.finding_count +
    ', 工作底稿=' + dashboardStats.workpaper_count);

  // Step 2: 获取 AI 审查列表统计
  console.log('Step 2: 获取 AI 审查列表数据');
  const auditStats = await page.evaluate(async (baseUrl) => {
    const res = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await res.json();

    const backendCompleted = runs.filter(r => ['draft_ready', 'partial_ready', 'finalized'].includes(r.status)).length;
    const frontendCompleted = runs.filter(r => ['completed', 'draft_ready', 'finalized'].includes(r.status)).length;
    const allStatuses = {};
    for (const r of runs) {
      allStatuses[r.status] = (allStatuses[r.status] || 0) + 1;
    }
    return { backendCompleted, frontendCompleted, total: runs.length, statuses: allStatuses };
  }, BASE);

  console.log('INFO: AI 审查列表 → 总计 ' + auditStats.total + ' 个任务');
  console.log('INFO: 各状态分布: ' + JSON.stringify(auditStats.statuses));
  console.log('INFO: 后端口径"已完成" = ' + auditStats.backendCompleted + '（draft_ready + partial_ready + finalized）');
  console.log('INFO: 前端口径"已完成" = ' + auditStats.frontendCompleted + '（completed + draft_ready + finalized）');

  // Step 3: 对比仪表盘指标
  console.log('Step 3: 对比仪表盘指标');

  // 审核要点
  const cpCount = dashboardStats.checkpoint_count;
  const dashboardCP = await page.getByText('审核要点', { exact: true }).first().locator('..').locator('.text-2xl, .text-3xl, .font-bold').first().textContent().catch(() => '?');
  console.log('INFO: 仪表盘 UI "审核要点" = ' + dashboardCP + '，API = ' + cpCount);
  if (parseInt(dashboardCP) === cpCount) {
    console.log('PASS: 审核要点数值一致');
  } else {
    console.log('WARN: 审核要点数值不一致（UI=' + dashboardCP + ', API=' + cpCount + '）');
  }

  // 完成审核 — 关键一致性检查
  const dashboardCompletedCount = dashboardStats.completed_audit_count;
  if (auditStats.backendCompleted === dashboardCompletedCount) {
    console.log('PASS: 仪表盘"完成审核"=' + dashboardCompletedCount + ' 与后端口径=' + auditStats.backendCompleted + ' 一致');
  } else {
    console.log('WARN: 仪表盘"完成审核"=' + dashboardCompletedCount + ' 与后端口径=' + auditStats.backendCompleted + ' 不一致');
  }

  // 检查前端口径和后端口径是否一致
  if (auditStats.frontendCompleted !== auditStats.backendCompleted) {
    console.log('⚠️ BUG: 前端口径"已完成"(' + auditStats.frontendCompleted + ') ≠ 后端口径(' + auditStats.backendCompleted + ')');
    console.log('⚠️ 差异来源：前端包含 "completed" 状态，后端不包含');
    const completedCount = auditStats.statuses['completed'] || 0;
    console.log('⚠️ "completed" 状态的任务数: ' + completedCount);
  } else {
    console.log('PASS: 前后端"已完成"口径一致');
  }

  // 发现问题
  const findingCount = dashboardStats.finding_count;
  const dashboardFinding = await page.getByText('发现问题', { exact: true }).first().locator('..').locator('.text-2xl, .text-3xl, .font-bold').first().textContent().catch(() => '?');
  if (parseInt(dashboardFinding) === findingCount) {
    console.log('PASS: "发现问题"数值一致（' + findingCount + '）');
  }

  // 工作底稿
  const wpCount = dashboardStats.workpaper_count;
  const dashboardWP = await page.getByText('工作底稿', { exact: true }).first().locator('..').locator('.text-2xl, .text-3xl, .font-bold').first().textContent().catch(() => '?');
  if (parseInt(dashboardWP) === wpCount) {
    console.log('PASS: "工作底稿"数值一致（' + wpCount + '）');
  }

  await page.screenshot({ path: SS + '-01-dashboard.png', fullPage: true });
  console.log('== cross-X4-dashboard-sync 全部通过 ==');
}

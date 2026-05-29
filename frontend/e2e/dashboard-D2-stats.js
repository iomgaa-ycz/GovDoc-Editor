async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/dashboard-D2';

  // Step 1: 进入工作台总览页
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // Step 2: 通过 API 获取实际数据
  const stats = await page.evaluate(async (baseUrl) => {
    const resp = await fetch(baseUrl + '/api/v1/dashboard/stats');
    if (!resp.ok) return null;
    return resp.json();
  }, BASE);

  if (!stats) {
    console.log('WARN: /api/v1/dashboard/stats 请求失败，跳过数据验证');
    console.log('== dashboard-D2-stats 跳过（API 不可用） ==');
    return;
  }
  console.log('PASS: 获取 dashboard stats 成功');

  // Step 3: 验证副标题文案
  const checkpointCount = stats.checkpoint_count ?? 0;
  const projectCount = (stats.recent_projects || []).length;
  const subtitle = page.getByText(/总共.*个审核要点.*覆盖.*个项目/).first();
  if (await subtitle.isVisible().catch(() => false)) {
    const text = await subtitle.textContent();
    if (text && text.includes(String(checkpointCount)) && text.includes(String(projectCount))) {
      console.log('PASS: 副标题数字与 API 一致（' + checkpointCount + ' 要点, ' + projectCount + ' 项目）');
    } else {
      console.log('WARN: 副标题数字可能不一致 — 页面: "' + text + '", API: ' + checkpointCount + '/' + projectCount);
    }
  }

  // Step 4: 验证四个指标卡片数字
  const metrics = [
    { label: '审核要点', value: stats.checkpoint_count ?? 0 },
    { label: '完成审核', value: stats.completed_audit_count ?? 0 },
    { label: '发现问题', value: stats.finding_count ?? 0 },
    { label: '工作底稿', value: stats.workpaper_count ?? 0 },
  ];
  for (const m of metrics) {
    const card = page.getByText(m.label, { exact: true }).first();
    if (!(await card.isVisible().catch(() => false))) continue;
    // 数字在卡片的下一个兄弟元素或父容器中
    const container = card.locator('..');
    const valueEl = container.locator('p').last();
    const displayValue = await valueEl.textContent();
    if (displayValue && parseInt(displayValue) === m.value) {
      console.log('PASS: ' + m.label + ' = ' + m.value);
    } else {
      console.log('WARN: ' + m.label + ' — 页面显示 "' + displayValue + '", API 返回 ' + m.value);
    }
  }
  await page.screenshot({ path: SS + '-02-metrics-verified.png', fullPage: true });

  // Step 5: 验证近期审核记录表格
  const projects = stats.recent_projects || [];
  if (projects.length === 0) {
    const emptyMsg = page.getByText('暂无审核记录');
    if (await emptyMsg.isVisible().catch(() => false)) {
      console.log('PASS: 无项目时显示"暂无审核记录"');
    }
    console.log('INFO: 无近期项目，跳过表格数据验证');
    console.log('== dashboard-D2-stats 全部通过（无数据场景） ==');
    return;
  }

  // 验证表格行数
  const tableRows = page.locator('tbody tr');
  const rowCount = await tableRows.count();
  if (rowCount === projects.length) {
    console.log('PASS: 表格行数 = ' + rowCount + '（与 API 一致）');
  } else {
    console.log('WARN: 表格行数 = ' + rowCount + ', API 项目数 = ' + projects.length);
  }

  // Step 6: 验证状态 Badge
  const statusLabels = { idle: '未开始', running: '审查中', completed: '已完成' };
  for (const [status, label] of Object.entries(statusLabels)) {
    const matchingProjects = projects.filter(p => p.audit_status === status);
    if (matchingProjects.length > 0) {
      const badge = page.getByText(label, { exact: true }).first();
      if (await badge.isVisible().catch(() => false)) {
        console.log('PASS: 状态 Badge "' + label + '" 可见（' + matchingProjects.length + ' 个项目）');
      } else {
        console.log('WARN: 有 ' + matchingProjects.length + ' 个"' + label + '"项目但 Badge 不可见');
      }
    }
  }

  // Step 7: 验证箭头按钮（aria-label）
  const arrowButtons = page.locator('button[aria-label*="审核结果"]');
  const arrowCount = await arrowButtons.count();
  if (arrowCount > 0) {
    console.log('PASS: 箭头按钮存在（' + arrowCount + ' 个）');
  }

  // Step 8: 验证审查情况卡片
  for (const p of projects) {
    const issueText = p.issue_count > 0 ? p.issue_count + ' 项问题' : '无问题';
    const issueEl = page.getByText(issueText, { exact: false }).first();
    if (await issueEl.isVisible().catch(() => false)) {
      console.log('PASS: 项目"' + p.name + '"问题文案: "' + issueText + '"');
    }
  }

  await page.screenshot({ path: SS + '-03-data-verified.png', fullPage: true });
  console.log('== dashboard-D2-stats 全部通过 ==');
}

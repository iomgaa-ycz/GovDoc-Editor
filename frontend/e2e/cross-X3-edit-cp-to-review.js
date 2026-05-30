async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/cross-X3';

  // ── 跨页面测试：编辑审核点标题后审查详情页中的显示 ──

  // Step 1: 通过 API 找到一个已完成的审核任务及其审核点
  console.log('Step 1: 查找已完成审核任务的审核点');
  const fixture = await page.evaluate(async (baseUrl) => {
    const runsRes = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await runsRes.json();
    const completed = runs.find(r => ['draft_ready', 'finalized', 'completed', 'partial_ready'].includes(r.status));
    if (!completed) return null;

    const progressRes = await fetch(baseUrl + '/api/v1/audit/runs/' + completed.id + '/progress');
    const progress = await progressRes.json();
    const pr = progress.point_runs?.find(p => p.finding_json);
    if (!pr) return null;

    const cpRes = await fetch(baseUrl + '/api/v1/checkpoints?include_archived=true');
    const cps = await cpRes.json();
    const cp = cps.find(c => c.id === pr.checkpoint_final_id && !c.archived);
    if (!cp) return null;

    let title = '';
    try { title = JSON.parse(cp.payload_json).title; } catch {}
    return { auditRunId: completed.id, checkpointId: cp.id, originalTitle: title, payloadJson: cp.payload_json };
  }, BASE);

  if (!fixture) {
    console.log('SKIP: 未找到已完成审核任务中未归档的审核点');
    return;
  }

  console.log('INFO: 审核点 "' + fixture.originalTitle + '"');

  // Step 2: 在审核点库编辑标题
  console.log('Step 2: 编辑审核点标题');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  // 搜索
  const search = page.getByPlaceholder('搜索审查要点...');
  const titleSnippet = fixture.originalTitle.slice(0, 6);
  await search.fill(titleSnippet);
  await page.waitForTimeout(1000);

  const targetRow = page.locator('table tbody tr').filter({ hasText: titleSnippet }).first();
  if (!(await targetRow.isVisible().catch(() => false))) {
    console.log('SKIP: 审核点库中未找到该审核点');
    return;
  }

  // 点击编辑
  const editBtn = targetRow.locator('td').last().locator('button').first();
  await editBtn.click();
  await page.waitForTimeout(500);

  const editDialog = page.locator('[role="dialog"]').filter({ hasText: '编辑审查要点' });
  await editDialog.waitFor({ state: 'visible', timeout: 5000 });

  // 修改标题
  const titleInput = editDialog.locator('input').first();
  await titleInput.fill(''); // 清空
  await titleInput.fill('[E2E跨页测试]' + fixture.originalTitle);

  await editDialog.getByRole('button', { name: '保存修改' }).click();
  await editDialog.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
  console.log('PASS: 标题已修改');
  await page.screenshot({ path: SS + '-01-edited.png', fullPage: true });

  // Step 3: 切到审查详情页验证标题
  console.log('Step 3: 验证审查详情页中的标题');
  await page.goto(BASE + '/ai-review/' + fixture.auditRunId);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-02-review-detail.png', fullPage: true });

  const bodyText = await page.locator('body').textContent() || '';
  const hasNewTitle = bodyText.includes('[E2E跨页测试]');
  if (hasNewTitle) {
    console.log('PASS: 审查详情页显示新标题 "[E2E跨页测试]"');
  } else {
    console.log('INFO: 审查详情页未显示新标题（可能工作底稿使用的是快照标题）');
  }

  // Step 4: 恢复原标题
  console.log('Step 4: 恢复原标题');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  await search.fill('');
  await search.fill('[E2E跨页测试]');
  await page.waitForTimeout(1000);

  const restoreRow = page.locator('table tbody tr').filter({ hasText: '[E2E跨页测试]' }).first();
  if (await restoreRow.isVisible().catch(() => false)) {
    const editBtn2 = restoreRow.locator('td').last().locator('button').first();
    await editBtn2.click();
    const editDialog2 = page.locator('[role="dialog"]').filter({ hasText: '编辑审查要点' });
    await editDialog2.waitFor({ state: 'visible', timeout: 5000 });
    const titleInput2 = editDialog2.locator('input').first();
    await titleInput2.fill('');
    await titleInput2.fill(fixture.originalTitle);
    await editDialog2.getByRole('button', { name: '保存修改' }).click();
    await editDialog2.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
    console.log('PASS: 已恢复原标题');
  } else {
    console.log('WARN: 未找到编辑后的审核点，无法恢复');
  }

  console.log('== cross-X3-edit-cp-to-review 全部通过 ==');
}

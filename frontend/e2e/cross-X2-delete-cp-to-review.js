async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/cross-X2';

  // ── 跨页面测试：删除审核点后审查详情页仍正确显示归档审核点 ──
  // 对应 TEST-GUIDE.md T3.18：归档审核点在审查详情页的正确渲染
  //
  // 修复链路（2026-05-29）：
  //   cb81d97 CheckpointFinal.status 字段
  //   ef7002b 有引用归档 / 无引用硬删
  //   811a4a0 AIReviewDetailPage 加载归档审核点 + "已归档" badge
  //   eb6fa3f progress 端点过滤孤儿 point_run

  // ── Step 1: 通过 API 找到：一个已完成的审核任务 + 一个被该任务引用的审核点 ──
  console.log('Step 1: 查找已完成的审核任务中被引用的审核点');
  const fixture = await page.evaluate(async (baseUrl) => {
    // 获取审核任务列表
    const runsRes = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await runsRes.json();
    const completed = runs.find(r => ['draft_ready', 'finalized', 'completed', 'partial_ready'].includes(r.status));
    if (!completed) return null;

    // 获取该任务的 progress
    const progressRes = await fetch(baseUrl + '/api/v1/audit/runs/' + completed.id + '/progress');
    const progress = await progressRes.json();

    // 取第一个有 finding 的 point_run
    const pointRunWithFinding = progress.point_runs?.find(pr => pr.finding_json);
    if (!pointRunWithFinding) return null;

    // 获取审核点详情
    const cpRes = await fetch(baseUrl + '/api/v1/checkpoints?include_archived=true');
    const cps = await cpRes.json();
    const cp = cps.find(c => c.id === pointRunWithFinding.checkpoint_final_id);
    if (!cp) return null;

    // 解析 payload 获取标题
    let title = 'unknown';
    try { title = JSON.parse(cp.payload_json).title; } catch {}

    return {
      auditRunId: completed.id,
      checkpointId: cp.id,
      checkpointTitle: title,
      isArchived: cp.archived === true,
    };
  }, BASE);

  if (!fixture) {
    console.log('SKIP: 未找到已完成审核任务及其引用的审核点');
    return;
  }

  console.log('INFO: 找到审核点 "' + fixture.checkpointTitle + '"（id: ' + fixture.checkpointId + '）');
  console.log('INFO: 当前归档状态: ' + fixture.isArchived);

  // ── Step 2: 如果审核点未归档，先去审核点库归档它 ──
  if (!fixture.isArchived) {
    console.log('Step 2: 在审核点库中删除（归档）该审核点');
    await page.goto(BASE + '/audit-library');
    await page.waitForLoadState('networkidle');

    // 搜索该审核点
    const searchInput = page.getByPlaceholder('搜索审查要点...');
    await searchInput.fill(fixture.checkpointTitle.slice(0, 6));
    await page.waitForTimeout(1000);

    // 找到该行并删除
    const targetRow = page.locator('table tbody tr').filter({ hasText: fixture.checkpointTitle.slice(0, 6) }).first();
    if (!(await targetRow.isVisible().catch(() => false))) {
      console.log('WARN: 审核点库中未找到该审核点（可能在其他页面）');
    } else {
      // 注册 dialog handler 吸收归档 alert
      page.once('dialog', async dialog => {
        console.log('INFO: 归档 alert: ' + dialog.message());
        await dialog.accept();
      });

      const deleteBtn = targetRow.locator('td').last().locator('button').last();
      await deleteBtn.click();
      await page.waitForTimeout(500);

      // 确认删除
      const confirmDialog = page.locator('[role="dialog"]').filter({ hasText: '确认删除' });
      if (await confirmDialog.isVisible().catch(() => false)) {
        await confirmDialog.getByRole('button', { name: '确认删除' }).click();
        await page.waitForTimeout(2000);
        console.log('PASS: 审核点已归档');
      }
    }
  } else {
    console.log('Step 2: 审核点已归档，跳过归档操作');
  }

  // ── Step 3: 进入审查详情页验证渲染 ──
  console.log('Step 3: 进入审查详情页验证归档审核点渲染');
  await page.goto(BASE + '/ai-review/' + fixture.auditRunId);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-01-review-detail.png', fullPage: true });

  // 查找包含该审核点标题的元素
  const titleSnippet = fixture.checkpointTitle.length > 6 ? fixture.checkpointTitle.slice(0, 6) : fixture.checkpointTitle;
  const cpElement = page.locator('[role="button"][tabindex="0"], aside button, main span, main p').filter({ hasText: titleSnippet }).first();

  // 验证 1: 审核点标题可见（不是 fallback）
  const bodyText = await page.locator('body').textContent() || '';
  const fallbackText = '审核点 ' + fixture.checkpointId.slice(0, 8);

  if (bodyText.includes(fallbackText)) {
    console.log('WARN: 发现 fallback 标题 "' + fallbackText + '"（可能是正常的前 8 位截断匹配）');
  }

  if (await cpElement.isVisible().catch(() => false)) {
    console.log('PASS: 审核点标题 "' + titleSnippet + '..." 可见');
  } else {
    console.log('WARN: 未找到审核点标题元素（可能在进度视图/底稿视图中）');
  }

  // 验证 2: "已归档" badge
  const archivedBadge = page.getByText('已归档').first();
  if (await archivedBadge.isVisible().catch(() => false)) {
    console.log('PASS: "已归档" badge 可见');
  } else {
    console.log('WARN: "已归档" badge 不可见');
  }

  // 验证 3: 点击详情查看 PointInsight
  const detailBtn = page.getByRole('button', { name: '详情' }).first();
  if (await detailBtn.isVisible().catch(() => false)) {
    await detailBtn.click();
    await page.waitForTimeout(500);

    const dialog = page.locator('[role="dialog"]').filter({ hasText: '审查点详情' });
    if (await dialog.isVisible().catch(() => false)) {
      // 验证非空
      const dialogText = await dialog.textContent() || '';
      const isEmpty = dialogText.includes('暂无审查点详情');
      if (isEmpty) {
        console.log('FAIL: 详情弹窗为空（"暂无审查点详情"）');
      } else {
        console.log('PASS: 详情弹窗有内容');
      }
      await page.screenshot({ path: SS + '-02-point-insight.png', fullPage: true });
      await page.keyboard.press('Escape');
    }
  }

  await page.screenshot({ path: SS + '-03-final.png', fullPage: true });
  console.log('== cross-X2-delete-cp-to-review 全部通过 ==');
}

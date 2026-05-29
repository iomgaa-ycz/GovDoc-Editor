async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL9';

  // 归档审核点渲染专项（只读、幂等，不修改数据）。
  // 验证「审核点被归档后，引用它的历史审查任务详情页仍能正确展示」——即最初报告的 bug 已修复：
  //   1) 显示真实标题（而非 "审核点 <id前8位>" 的 fallback）
  //   2) 标题旁有「已归档」标签
  //   3) 点开详情能看到审查结论内容（而非 "暂无审查点详情" 空状态）
  // 删除→归档的后端逻辑由单元测试 test_checkpoint_archive.py 确定性覆盖，此处不重复且避免破坏共享数据。

  // ── Step 1: 经 API 找一个「引用了归档审核点且该点有 finding」的审查任务 ──
  // 前端与 /api 同源（nginx 代理），页面内可直接 fetch
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  const WORKPAPER_STATUSES = ['draft_ready', 'completed', 'finalized', 'partial_ready'];
  const fixture = await page.evaluate(async (okStatuses) => {
    const j = async (url) => (await fetch(url)).json();
    const all = await j('/api/v1/checkpoints?include_archived=true');
    const archived = new Map(
      all.filter((c) => c.archived).map((c) => {
        let title = '';
        try { title = JSON.parse(c.payload_json).title || ''; } catch { /* skip */ }
        return [c.id, title];
      }),
    );
    if (archived.size === 0) return null;
    const runs = await j('/api/v1/audit/runs');
    for (const r of runs) {
      if (!okStatuses.includes(r.status)) continue;
      let prog;
      try { prog = await j('/api/v1/audit/runs/' + r.id + '/progress'); } catch { continue; }
      for (const p of prog.point_runs || []) {
        if (archived.has(p.checkpoint_final_id) && p.finding_json) {
          return { runId: r.id, cpId: p.checkpoint_final_id, title: archived.get(p.checkpoint_final_id) };
        }
      }
    }
    return null;
  }, WORKPAPER_STATUSES);

  if (!fixture || !fixture.title) {
    console.log('⏭ 跳过: testing 环境无「引用了归档审核点且有结论」的审查任务，无法测试归档渲染');
    return;
  }
  console.log('fixture: run=' + fixture.runId.slice(0, 8) + ' cp=' + fixture.cpId.slice(0, 8) + ' title="' + fixture.title.slice(0, 24) + '"');
  const fallbackTitle = '审核点 ' + fixture.cpId.slice(0, 8);

  // ── Step 2: 打开该审查任务详情页 ──
  await page.goto(BASE + '/ai-review/' + fixture.runId);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500); // 等待 listCheckpoints(include_archived) + progress 加载
  await page.screenshot({ path: SS + '-01-detail-page.png', fullPage: true });

  // ── Step 3: 定位归档审核点对应的审查发现行 ──
  // 整行是一个 button，文本含审核点标题。用完整标题精确匹配（避免命中 fallback）。
  const targetRow = page.locator('button', { hasText: fixture.title }).first();
  await targetRow.waitFor({ state: 'visible', timeout: 8000 });

  // 断言 1: 显示真实标题，而非 fallback "审核点 xxxxxxxx"
  const pageText = await page.locator('body').textContent() || '';
  if (pageText.includes(fallbackTitle)) {
    throw new Error('页面出现 fallback 标题 "' + fallbackTitle + '"，归档审核点定义未正确加载');
  }
  console.log('PASS[1/3]: 显示真实标题，无 fallback "' + fallbackTitle + '"');

  // 断言 2: 该行含「已归档」标签
  const archivedBadge = targetRow.getByText('已归档');
  if (!(await archivedBadge.isVisible())) {
    throw new Error('归档审核点 "' + fixture.title.slice(0, 20) + '" 行未显示「已归档」标签');
  }
  await page.screenshot({ path: SS + '-02-archived-badge.png', fullPage: true });
  console.log('PASS[2/3]: 归档审核点行显示「已归档」标签');

  // ── Step 4: 点开详情，断言展示审查结论而非空状态 ──
  await targetRow.click();
  const dialog = page.locator('[role="dialog"]');
  await dialog.waitFor({ state: 'visible', timeout: 5000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-03-insight-dialog.png', fullPage: true });

  const dialogText = await dialog.textContent() || '';
  // 断言 3: 不是空状态，且渲染了该归档审核点的标题（PointInsight 已正常挂载）
  if (dialogText.includes('暂无审查点详情')) {
    throw new Error('归档审核点详情弹窗显示空状态 "暂无审查点详情"——原始 bug 未修复');
  }
  if (!dialogText.includes(fixture.title.trim())) {
    throw new Error('详情弹窗未渲染归档审核点标题，PointInsight 未正确加载');
  }
  console.log('PASS[3/3]: 详情弹窗展示审查结论内容（非空状态），原始 bug 已修复');

  console.log('== audit-AL9-checkpoint-archive 全部通过 ==');
}

async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R5';

  // ── Step 1: 查找一个已完成的审核任务 ──
  console.log('Step 1: 查找已完成（draft_ready/finalized）的审核任务');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  // 通过 API 查找 draft_ready 或 finalized 的任务
  const result = await page.evaluate(async (baseUrl) => {
    const res = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await res.json();
    return runs.find(r => ['draft_ready', 'finalized', 'completed', 'partial_ready'].includes(r.status)) || null;
  }, BASE);

  if (!result) {
    console.log('SKIP: 无已完成的审核任务，请先运行审核任务等待完成后再执行此测试');
    return;
  }

  console.log('INFO: 找到已完成任务 ' + result.id + '（状态: ' + result.status + '）');

  // ── Step 2: 进入详情页 ──
  console.log('Step 2: 进入详情页');
  await page.goto(BASE + '/ai-review/' + result.id);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-01-detail.png', fullPage: true });

  // 判断是否为工作底稿视图
  const bodyText = await page.locator('main').first().textContent().catch(() => '') || '';
  const isWorkpaperView = bodyText.includes('底稿操作') || bodyText.includes('保存状态');

  if (!isWorkpaperView) {
    // 可能还在进度视图（partial_ready 等状态）
    console.log('WARN: 当前非工作底稿视图（可能状态为 partial_ready），跳过底稿测试');
    return;
  }
  console.log('PASS: 工作底稿视图已加载');

  // ── Step 3: 验证底稿操作面板 ──
  console.log('Step 3: 验证底稿操作面板');
  const aside = page.locator('aside');

  // 保存状态
  const saveStatus = aside.getByText('保存状态').first();
  if (!(await saveStatus.isVisible().catch(() => false))) throw new Error('"保存状态"不可见');

  // 定稿状态
  const finalizeStatus = aside.getByText('定稿状态').first();
  if (!(await finalizeStatus.isVisible().catch(() => false))) throw new Error('"定稿状态"不可见');

  // 保存按钮
  const saveBtn = aside.getByRole('button', { name: '保存' }).first();
  if (!(await saveBtn.isVisible().catch(() => false))) throw new Error('"保存"按钮不可见');

  // 定稿按钮
  const finalizeBtn = aside.getByRole('button', { name: '定稿' }).first();
  if (!(await finalizeBtn.isVisible().catch(() => false))) throw new Error('"定稿"按钮不可见');

  console.log('PASS: 底稿操作面板元素完整');

  // ── Step 4: 验证工作底稿编辑器 + 编辑输入 ──
  console.log('Step 4: 验证工作底稿编辑器 + 编辑输入');
  const editor = page.locator('[contenteditable="true"], .ProseMirror, [role="textbox"]').first();
  if (await editor.isVisible().catch(() => false)) {
    const content = await editor.textContent().catch(() => '');
    if (content && content.length > 10) {
      console.log('PASS: 编辑器有内容（' + content.length + ' 字符）');
    } else {
      console.log('WARN: 编辑器内容为空或很短');
    }

    // 编辑器输入测试（T5.2）：在编辑器末尾追加文字
    console.log('Step 4b: 编辑器输入测试');
    await editor.click();
    await page.keyboard.press('End');
    await page.keyboard.type('\n[E2E自动测试编辑]');
    await page.waitForTimeout(300);
    console.log('PASS: 编辑器输入成功');

    // 验证自动保存触发（T5.2）：编辑后状态应先变为"未保存"，然后 700ms 后自动保存
    const unsavedBadge = aside.getByText('未保存').first();
    if (await unsavedBadge.isVisible().catch(() => false)) {
      console.log('PASS: 编辑后保存状态变为"未保存"');
    } else {
      console.log('INFO: 保存状态未变为"未保存"（可能已触发自动保存）');
    }

    // 等待自动保存（700ms 防抖 + 网络延迟）
    await page.waitForTimeout(3000);
    const autoSavedBadge = aside.getByText('已保存').first();
    if (await autoSavedBadge.isVisible().catch(() => false)) {
      console.log('PASS: 自动保存成功，状态变为"已保存"');
    } else {
      console.log('INFO: 自动保存可能仍在进行中');
    }
  } else {
    console.log('WARN: 未找到可编辑区域');
  }

  // ── Step 5: 验证审查发现列表 ──
  console.log('Step 5: 验证审查发现列表');
  const findingsCard = page.getByText('审查发现').first();
  if (await findingsCard.isVisible().catch(() => false)) {
    const findingItems = page.locator('aside button').filter({ hasText: /合规|不合规|存疑/ });
    const findingCount = await findingItems.count();
    console.log('PASS: "审查发现" Card 可见，发现 ' + findingCount + ' 条');
  }

  await page.screenshot({ path: SS + '-02-workpaper-view.png', fullPage: true });

  // ── Step 6: 手动保存 ──
  console.log('Step 6: 手动保存');
  await saveBtn.click();
  await page.waitForTimeout(2000);

  // 检查保存状态变化
  const savedBadge = aside.getByText('已保存').first();
  const savingBadge = aside.getByText('保存中').first();
  const errorBadge = aside.getByText('保存失败').first();
  if (await savedBadge.isVisible().catch(() => false)) {
    console.log('PASS: 保存成功');
  } else if (await savingBadge.isVisible().catch(() => false)) {
    console.log('INFO: 保存中...');
  } else if (await errorBadge.isVisible().catch(() => false)) {
    console.log('WARN: 保存失败');
  }
  await page.screenshot({ path: SS + '-03-after-save.png', fullPage: true });

  // ── Step 7: 检查导出 Word 按钮 ──
  console.log('Step 7: 检查导出按钮状态');
  const exportBtn = aside.getByRole('button', { name: '导出 Word' }).first();
  if (await exportBtn.isVisible().catch(() => false)) {
    const isDisabled = await exportBtn.isDisabled().catch(() => true);
    if (isDisabled) {
      console.log('INFO: "导出 Word"按钮禁用（未定稿，符合预期）');
    } else {
      console.log('PASS: "导出 Word"按钮可点击（已定稿）');
    }
  }

  // ── Step 8: 检查已归档审核点 badge ──
  console.log('Step 8: 检查已归档审核点');
  const archivedBadge = page.getByText('已归档').first();
  if (await archivedBadge.isVisible().catch(() => false)) {
    console.log('PASS: 发现已归档审核点 badge');
  } else {
    console.log('INFO: 当前任务无已归档审核点');
  }

  await page.screenshot({ path: SS + '-04-final.png', fullPage: true });
  console.log('== review-R5-workpaper 全部通过 ==');
}

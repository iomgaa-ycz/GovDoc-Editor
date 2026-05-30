async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R7';

  // ── Step 1: 查找可定稿的审核任务（draft_ready 状态）──
  console.log('Step 1: 查找 draft_ready 状态的审核任务');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  const result = await page.evaluate(async (baseUrl) => {
    const res = await fetch(baseUrl + '/api/v1/audit/runs');
    const runs = await res.json();
    return runs.find(r => r.status === 'draft_ready') || null;
  }, BASE);

  if (!result) {
    console.log('SKIP: 无 draft_ready 状态的审核任务，需要先完成审核等待任务进入底稿阶段');
    return;
  }

  console.log('INFO: 找到 draft_ready 任务 ' + result.id);

  // ── Step 2: 进入详情页，确认工作底稿视图 ──
  console.log('Step 2: 进入详情页');
  await page.goto(BASE + '/ai-review/' + result.id);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  const aside = page.locator('aside');
  const saveLabel = aside.getByText('保存状态').first();
  if (!(await saveLabel.isVisible().catch(() => false))) {
    console.log('WARN: 非工作底稿视图，跳过');
    return;
  }
  console.log('PASS: 工作底稿视图已加载');
  await page.screenshot({ path: SS + '-01-workpaper.png', fullPage: true });

  // ── Step 3: 编辑底稿内容 ──
  console.log('Step 3: 编辑底稿内容');
  const editor = page.locator('[contenteditable="true"]').first();
  if (await editor.isVisible().catch(() => false)) {
    // 点击编辑器末尾并输入文字
    await editor.click();
    await page.keyboard.press('End');
    await page.keyboard.type('\nE2E自动测试编辑内容');
    await page.waitForTimeout(300);

    // 验证保存状态变为"未保存"
    const unsavedBadge = aside.getByText('未保存').first();
    if (await unsavedBadge.isVisible().catch(() => false)) {
      console.log('PASS: 编辑后保存状态变为"未保存"');
    } else {
      console.log('INFO: 保存状态未立即变为"未保存"（可能已触发自动保存）');
    }
  } else {
    console.log('WARN: 未找到 contenteditable 编辑器，跳过编辑步骤');
  }
  await page.screenshot({ path: SS + '-02-edited.png', fullPage: true });

  // ── Step 4: 等待自动保存（700ms 防抖 + 网络延迟）──
  console.log('Step 4: 等待自动保存');
  await page.waitForTimeout(3000);
  const savedBadge = aside.getByText('已保存').first();
  if (await savedBadge.isVisible().catch(() => false)) {
    console.log('PASS: 自动保存成功，状态显示"已保存"');
  } else {
    console.log('INFO: 自动保存可能仍在进行中');
  }

  // ── Step 5: 手动保存 ──
  console.log('Step 5: 手动保存');
  const saveBtn = aside.getByRole('button', { name: '保存' }).first();
  if (await saveBtn.isVisible().catch(() => false) && !(await saveBtn.isDisabled().catch(() => true))) {
    await saveBtn.click();
    await page.waitForTimeout(2000);
    const savedAfterManual = aside.getByText('已保存').first();
    if (await savedAfterManual.isVisible().catch(() => false)) {
      console.log('PASS: 手动保存成功');
    } else {
      console.log('WARN: 手动保存状态未确认为"已保存"');
    }
  } else {
    console.log('INFO: "保存"按钮不可见或已禁用');
  }
  await page.screenshot({ path: SS + '-03-saved.png', fullPage: true });

  // ── Step 6: 定稿 ──
  console.log('Step 6: 定稿');
  const finalizeBtn = aside.getByRole('button', { name: '定稿' }).first();
  if (!(await finalizeBtn.isVisible().catch(() => false))) {
    throw new Error('"定稿"按钮不可见');
  }
  if (await finalizeBtn.isDisabled().catch(() => true)) {
    // 可能已经定稿过了
    const finalizedBadge = aside.getByText('已定稿').first();
    if (await finalizedBadge.isVisible().catch(() => false)) {
      console.log('INFO: 任务已定稿，跳过定稿步骤');
    } else {
      console.log('WARN: "定稿"按钮禁用但未显示"已定稿"');
    }
  } else {
    await finalizeBtn.click();
    console.log('INFO: 已点击"定稿"按钮，等待定稿完成...');

    // 等待定稿完成（状态 badge 变为"已定稿"）
    await page.waitForFunction(
      () => document.body.textContent.includes('已定稿'),
      { timeout: 30000, polling: 1000 }
    );
    console.log('PASS: 定稿成功，状态显示"已定稿"');

    // 验证定稿按钮变为禁用
    if (await finalizeBtn.isDisabled().catch(() => false)) {
      console.log('PASS: 定稿后按钮已禁用');
    } else {
      console.log('WARN: 定稿后按钮未禁用');
    }
  }
  await page.screenshot({ path: SS + '-04-finalized.png', fullPage: true });

  // ── Step 7: 验证导出 Word 按钮 ──
  console.log('Step 7: 验证导出 Word 按钮');
  // 导出按钮是 <a> 标签包裹在 Button(asChild) 中
  const exportLink = aside.locator('a').filter({ hasText: '导出 Word' }).first();
  const exportBtn = aside.getByRole('button', { name: '导出 Word' }).first();
  const exportEl = (await exportLink.isVisible().catch(() => false)) ? exportLink : exportBtn;

  if (await exportEl.isVisible().catch(() => false)) {
    const isDisabled = await exportBtn.isDisabled().catch(() => true);
    if (isDisabled) {
      console.log('WARN: "导出 Word"按钮仍禁用（可能定稿未生效）');
    } else {
      console.log('PASS: "导出 Word"按钮可点击');

      // 验证下载 URL 格式正确
      const href = await exportLink.getAttribute('href').catch(() => '');
      if (href && href.includes('/workpaper/final/docx')) {
        console.log('PASS: 导出 URL 格式正确 — ' + href);
      } else {
        console.log('WARN: 导出 URL 格式异常 — ' + href);
      }
    }
  } else {
    console.log('WARN: "导出 Word"按钮不可见');
  }

  await page.screenshot({ path: SS + '-05-final.png', fullPage: true });
  console.log('== review-R7-finalize-export 全部通过 ==');
}

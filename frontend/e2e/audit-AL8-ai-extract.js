async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL8';
  const FILE_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc';
  const TITLE = '政府采购四类违规行为专项整治工作指引';
  const MAX_WAIT_MS = 30 * 60 * 1000; // 30 minutes

  // ── Step 1: 导航到审核点库页面，记录初始行数 ──
  console.log('Step 1: 导航到 /audit-library');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  var initialRows = await page.locator('table tbody tr').count();
  console.log('初始表格行数: ' + initialRows);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });
  console.log('PASS: 审核点库页面加载完成');

  // ── Step 2: 进入 AI 提取模式 ──
  console.log('Step 2: 进入 AI 提取模式');
  const uploadBtn = page.getByRole('button', { name: /上传/ });
  await uploadBtn.click();

  const aiExtractOption = page.getByText('AI 提取').first();
  await aiExtractOption.waitFor({ timeout: 5000 });
  await aiExtractOption.click();

  const extractHeading = page.getByText('AI 智能提取审查要点').first();
  await extractHeading.waitFor({ timeout: 10000 });
  await page.screenshot({ path: SS + '-02-extract-mode.png', fullPage: true });
  console.log('PASS: 进入 AI 提取模式，标题"AI 智能提取审查要点"可见');

  // ── Step 3: 填写标题 ──
  console.log('Step 3: 填写标题');
  const titleInput = page.locator('input[placeholder*="例如"]');
  await titleInput.fill(TITLE);
  console.log('PASS: 标题已填写"' + TITLE + '"');

  // ── Step 4: 上传文件 ──
  console.log('Step 4: 上传文件');
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(FILE_PATH);
  await page.waitForTimeout(1000);

  const fileNameFragment = page.getByText('四类').first();
  if (!(await fileNameFragment.isVisible())) throw new Error('上传后文件名片段"四类"不可见');
  await page.screenshot({ path: SS + '-03-file-uploaded.png', fullPage: true });
  console.log('PASS: 文件上传成功，文件名片段"四类"可见');

  // ── Step 5: 点击"开始抽取" ──
  console.log('Step 5: 点击"开始抽取"');
  const extractBtn = page.getByRole('button', { name: /开始抽取/ });
  const isDisabled = await extractBtn.isDisabled();
  if (isDisabled) throw new Error('"开始抽取"按钮为禁用状态');
  console.log('PASS: "开始抽取"按钮可用');

  await extractBtn.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-04-extract-started.png', fullPage: true });
  console.log('PASS: 已点击"开始抽取"');

  // ── Step 6: 验证进度卡片 ──
  console.log('Step 6: 验证进度卡片');
  const progressCard = page.getByText('提取进度').first();
  if (await progressCard.isVisible().catch(function() { return false; })) {
    console.log('PASS: "提取进度"卡片可见');

    var phases = ['分析法规结构', '逐条提取审查要点', '汇总并入库'];
    var visiblePhases = 0;
    for (var pi = 0; pi < phases.length; pi++) {
      var phaseEl = page.getByText(phases[pi]).first();
      if (await phaseEl.isVisible().catch(function() { return false; })) visiblePhases++;
    }
    console.log('进度阶段可见: ' + visiblePhases + '/3（' + phases.join(', ') + '）');
  } else {
    console.log('INFO: "提取进度"卡片暂未可见（可能快速跳过或延迟出现）');
  }
  await page.screenshot({ path: SS + '-05-progress-card.png', fullPage: true });

  // ── Step 7: 等待完成（最长 30 分钟） ──
  console.log('Step 7: 等待提取完成（最长 30 分钟）...');
  var startTime = Date.now();
  var completed = false;
  var failed = false;
  var lastScreenshot = 0;

  while (Date.now() - startTime < MAX_WAIT_MS) {
    // 检查成功
    var successEl = page.getByText('提取完成').first();
    if (await successEl.isVisible().catch(function() { return false; })) {
      completed = true;
      break;
    }

    // 检查失败
    var failEl = page.getByText('处理失败').first();
    if (await failEl.isVisible().catch(function() { return false; })) {
      failed = true;
      break;
    }

    // 每 60 秒截图记录进度
    var elapsed = Date.now() - startTime;
    if (elapsed - lastScreenshot >= 60000) {
      var mins = Math.floor(elapsed / 60000);
      await page.screenshot({ path: SS + '-06-progress-' + mins + 'min.png', fullPage: true });
      console.log('... 等待中（' + mins + ' 分钟）');
      lastScreenshot = elapsed;
    }

    await page.waitForTimeout(5000);
  }

  var totalSecs = Math.floor((Date.now() - startTime) / 1000);

  if (failed) {
    await page.screenshot({ path: SS + '-07-failed.png', fullPage: true });
    var errorBox = page.locator('.bg-red-50, .text-red-600, .text-destructive').first();
    var errorText = await errorBox.textContent().catch(function() { return '(无法读取)'; });
    throw new Error('AI 提取失败（' + totalSecs + 's）: ' + (errorText || '').slice(0, 300));
  }

  if (!completed) {
    await page.screenshot({ path: SS + '-07-timeout.png', fullPage: true });
    throw new Error('AI 提取超时（30 分钟未完成）');
  }

  await page.screenshot({ path: SS + '-07-success.png', fullPage: true });
  console.log('PASS: AI 提取完成（耗时 ' + totalSecs + 's）');

  // ── Step 8: 返回列表，验证行数增加 ──
  console.log('Step 8: 返回列表');
  const backBtn = page.getByText('返回列表').first();
  await backBtn.click();
  await page.waitForTimeout(2000);

  var finalRows = await page.locator('table tbody tr').count();
  if (finalRows <= initialRows) {
    throw new Error('返回列表后行数未增加（初始: ' + initialRows + ', 当前: ' + finalRows + '）');
  }
  await page.screenshot({ path: SS + '-08-back-to-list.png', fullPage: true });
  console.log('PASS: 返回列表成功，行数从 ' + initialRows + ' 增加到 ' + finalRows);

  console.log('== audit-AL8-ai-extract 全部通过 (' + totalSecs + 's) ==');
}

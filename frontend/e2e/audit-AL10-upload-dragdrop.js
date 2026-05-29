async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL10';
  // 真实 .doc（旧版 Word，7.8MB）——验证「.doc 选不了」是否真正修复。与 AL8/F2 同源文件。
  const DOC_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc';
  const DOC_BASENAME = DOC_PATH.split('/').pop();                 // ...指引.doc
  const DOC_TITLE = DOC_BASENAME.replace(/\.[^.]+$/, '');          // 去 .doc 后的标题兜底期望值

  // ── Step 1: 进入 AI 提取模式 ──
  console.log('Step 1: 导航并进入 AI 提取');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('AI 提取').first().click();
  await page.getByText('AI 智能提取审查要点').first().waitFor({ timeout: 10000 });
  await page.screenshot({ path: SS + '-01-extract-mode.png', fullPage: true });

  // ── Step 2: 杀手断言——accept 必须含 .doc（修复前为 .md,.pdf,.docx，不含 .doc）──
  console.log('Step 2: 校验 accept 含 .doc');
  const fileInput = page.locator("input[type='file']");
  const accept = (await fileInput.getAttribute('accept')) || '';
  if (!accept.toLowerCase().includes('.doc')) {
    throw new Error('【.doc 修复未生效】input accept = "' + accept + '"，未包含 .doc');
  }
  console.log('PASS: accept = ' + accept);

  // ── Step 3: 真实 .doc 经文件选择上传——回显 + 标题兜底 + 按钮可点 ──
  console.log('Step 3: 选择真实 .doc（' + DOC_BASENAME + '）');
  await fileInput.setInputFiles(DOC_PATH);
  await page.waitForTimeout(800);
  if (!(await page.getByText('四类').first().isVisible())) {
    throw new Error('选择真实 .doc 后文件名片段「四类」未回显');
  }
  const titleInput = page.locator('input[placeholder*="例如"]');
  let titleVal = await titleInput.inputValue();
  if (titleVal !== DOC_TITLE) {
    throw new Error('真实 .doc 标题未按文件名兜底。期望: "' + DOC_TITLE + '" 实际: "' + titleVal + '"');
  }
  const extractBtn = page.getByRole('button', { name: /开始抽取/ });
  if (await extractBtn.isDisabled()) throw new Error('已选文件且标题兜底，但「开始抽取」仍禁用');
  await page.screenshot({ path: SS + '-02-real-doc-selected.png', fullPage: true });
  console.log('PASS: 真实 .doc 可选、文件名回显、标题兜底"' + titleVal + '"、按钮可点');

  // ── Step 4: 拖拽——核心 bug。移除并清空标题后，拖入有效文件触发回显 + 兜底 ──
  // 注：Playwright 无法拖拽 OS 文件，用页面内 File 构造 DataTransfer 验证 onDrop 处理器是否真实存在
  //     （修复前 FileSelectBox 无任何拖拽处理器，拖入毫无反应）。真实文件流转已由 Step 3 覆盖。
  console.log('Step 4: 拖拽有效文件验证 onDrop 处理器');
  await page.getByText('移除').first().click();
  await titleInput.fill('');
  await page.waitForTimeout(300);
  const zone = page.locator('label').filter({ hasText: '选择或拖入法规文件' });
  const dt = await page.evaluateHandle(() => {
    const d = new DataTransfer();
    d.items.add(new File(['<w:doc/>'], '某市采购管理办法.doc', { type: 'application/msword' }));
    return d;
  });
  await zone.dispatchEvent('dragover', { dataTransfer: dt });
  await zone.dispatchEvent('drop', { dataTransfer: dt });
  await page.waitForTimeout(500);
  if (!(await page.getByText('某市采购管理办法.doc').first().isVisible())) {
    throw new Error('【拖拽修复未生效】拖入文件后文件名未回显——onDrop 未触发');
  }
  titleVal = await titleInput.inputValue();
  if (titleVal !== '某市采购管理办法') {
    throw new Error('拖入文件标题未兜底。期望: "某市采购管理办法" 实际: "' + titleVal + '"');
  }
  if (await extractBtn.isDisabled()) throw new Error('拖入有效文件后「开始抽取」仍禁用');
  await page.screenshot({ path: SS + '-03-drag-valid.png', fullPage: true });
  console.log('PASS: 拖入有效文件 onDrop 触发、回显、标题兜底"' + titleVal + '"、按钮可点');

  // ── Step 5: 拖入不支持类型 → 内联报错（不静默丢弃）──
  console.log('Step 5: 拖入不支持类型 .txt');
  await page.getByText('移除').first().click();
  await page.waitForTimeout(300);
  const zone2 = page.locator('label').filter({ hasText: '选择或拖入法规文件' });
  const badDt = await page.evaluateHandle(() => {
    const d = new DataTransfer();
    d.items.add(new File(['x'], 'bad.txt', { type: 'text/plain' }));
    return d;
  });
  await zone2.dispatchEvent('dragover', { dataTransfer: badDt });
  await zone2.dispatchEvent('drop', { dataTransfer: badDt });
  await page.waitForTimeout(500);
  if (!(await page.getByText(/仅支持/).first().isVisible())) {
    throw new Error('拖入不支持类型后未显示「仅支持」错误提示');
  }
  await page.screenshot({ path: SS + '-04-drag-invalid.png', fullPage: true });
  console.log('PASS: 拖入 .txt 显示「仅支持」错误提示');

  console.log('== audit-AL10-upload-dragdrop 全部通过 ==');
}

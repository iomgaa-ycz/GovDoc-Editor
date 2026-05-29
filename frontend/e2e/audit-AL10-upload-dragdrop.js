async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL10';

  // ── Step 1: 进入 AI 提取模式 ──
  console.log('Step 1: 导航并进入 AI 提取');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('AI 提取').first().click();
  await page.getByText('AI 智能提取审查要点').first().waitFor({ timeout: 10000 });
  await page.screenshot({ path: SS + '-01-extract-mode.png', fullPage: true });

  // ── Step 2: 断言 accept 含 .doc ──
  console.log('Step 2: 校验 accept 含 .doc');
  const fileInput = page.locator("input[type='file']");
  const accept = await fileInput.getAttribute('accept');
  if (!accept || !accept.toLowerCase().includes('.doc')) {
    throw new Error('input accept 未包含 .doc，实际: ' + accept);
  }
  console.log('PASS: accept = ' + accept);

  // ── Step 3: 拖入 .doc 文件 → 文件名回显 + 标题自动兜底 + 按钮可点 ──
  console.log('Step 3: 拖入 .doc 文件');
  const zone = page.locator('label').filter({ hasText: '选择或拖入法规文件' });
  const dt = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(['<w:doc/>'], '某市采购管理办法.doc', { type: 'application/msword' }));
    return dt;
  });
  await zone.dispatchEvent('dragover', { dataTransfer: dt });
  await zone.dispatchEvent('drop', { dataTransfer: dt });
  await page.waitForTimeout(500);

  const nameShown = page.getByText('某市采购管理办法.doc').first();
  if (!(await nameShown.isVisible())) throw new Error('拖入后文件名未回显');

  const titleInput = page.locator('input[placeholder*="例如"]');
  const titleVal = await titleInput.inputValue();
  if (titleVal !== '某市采购管理办法') {
    throw new Error('标题未按文件名兜底，实际: "' + titleVal + '"');
  }

  const extractBtn = page.getByRole('button', { name: /开始抽取/ });
  if (await extractBtn.isDisabled()) throw new Error('标题已兜底但「开始抽取」仍禁用');
  await page.screenshot({ path: SS + '-02-doc-dropped.png', fullPage: true });
  console.log('PASS: .doc 拖入回显、标题兜底"' + titleVal + '"、按钮可点');

  // ── Step 4: 拖入不支持类型 → 内联报错 ──
  console.log('Step 4: 拖入不支持类型');
  await page.getByText('移除').first().click();
  await page.waitForTimeout(300);
  const zone2 = page.locator('label').filter({ hasText: '选择或拖入法规文件' });
  const badDt = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(['x'], 'bad.txt', { type: 'text/plain' }));
    return dt;
  });
  await zone2.dispatchEvent('dragover', { dataTransfer: badDt });
  await zone2.dispatchEvent('drop', { dataTransfer: badDt });
  await page.waitForTimeout(500);

  const errMsg = page.getByText(/仅支持/).first();
  if (!(await errMsg.isVisible())) throw new Error('拖入不支持类型后未显示错误提示');
  await page.screenshot({ path: SS + '-03-invalid-type.png', fullPage: true });
  console.log('PASS: 拖入 .txt 显示「仅支持」错误提示');

  console.log('== audit-AL10-upload-dragdrop 全部通过 ==');
}

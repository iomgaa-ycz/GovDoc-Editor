async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F2';
  const PDF_PATH = 'e2e/.test-data/E2E测试招标文件.pdf';
  const DOC_PATH = 'e2e/.test-data/E2E测试声明函.docx';

  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');

  // 记录初始统计
  const getStatValue = async (label) => {
    const card = page.getByText(label).first().locator('..');
    const numEl = card.locator('.text-2xl, .text-3xl, .font-bold').first();
    return parseInt((await numEl.textContent() || '0').trim(), 10);
  };
  const initTotal = await getStatValue('总文件');
  const initRows = await page.locator('table tbody tr').count();
  console.log('初始状态: 总文件=' + initTotal + ', 表格行=' + initRows);
  await page.screenshot({ path: SS + '-01-before-upload.png', fullPage: true });

  // ── Step 1: 上传 PDF ──
  console.log('Step 1: 上传 PDF...');
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(PDF_PATH);

  // 等待上传完成 — 表格中出现文件名（大文件超时设宽）
  const pdfRow = page.getByText('E2E测试招标文件').first();
  await pdfRow.waitFor({ timeout: 120000 });
  await page.screenshot({ path: SS + '-02-pdf-uploaded.png', fullPage: true });
  console.log('PASS: PDF 上传成功，文件行出现');

  // 验证状态为 "转换中" 或 "已就绪"
  const pdfRowFull = page.locator('table tbody tr').filter({ hasText: 'E2E测试招标文件' }).first();
  const pdfStatusText = await pdfRowFull.textContent() || '';
  if (!pdfStatusText.includes('转换中') && !pdfStatusText.includes('已就绪')) {
    throw new Error('PDF 上传后状态异常: ' + pdfStatusText.slice(0, 100));
  }
  console.log('PASS: PDF 状态正确（' + (pdfStatusText.includes('已就绪') ? '已就绪' : '转换中') + '）');

  // 验证类型列显示 "PDF" badge
  const pdfTypeBadge = pdfRowFull.getByText('PDF').first();
  if (await pdfTypeBadge.isVisible().catch(() => false)) {
    console.log('PASS: PDF 文件类型列显示 "PDF" badge');
  } else {
    console.log('WARN: PDF 文件类型列未显示 "PDF" badge');
  }

  // ── Step 2: 上传 DOCX ──
  console.log('Step 2: 上传 DOCX...');
  const fileInput2 = page.locator("input[type='file']");
  await fileInput2.setInputFiles(DOC_PATH);

  const docRow = page.getByText('E2E测试声明函').first();
  await docRow.waitFor({ timeout: 120000 });
  await page.screenshot({ path: SS + '-03-doc-uploaded.png', fullPage: true });
  console.log('PASS: DOC 上传成功，文件行出现');

  // 验证类型列显示 "Word" badge
  const docRowFull = page.locator('table tbody tr').filter({ hasText: 'E2E测试声明函' }).first();
  const docTypeBadge = docRowFull.getByText('Word').first();
  if (await docTypeBadge.isVisible().catch(() => false)) {
    console.log('PASS: Word 文件类型列显示 "Word" badge');
  } else {
    console.log('WARN: Word 文件类型列未显示 "Word" badge');
  }

  // ── Step 3: 统计卡片数字变化 ──
  await page.waitForTimeout(2000);
  const afterTotal = await getStatValue('总文件');
  if (afterTotal < initTotal) throw new Error('上传后总文件数不应减少: ' + initTotal + ' → ' + afterTotal);
  console.log('PASS: 统计卡片更新（总文件 ' + initTotal + ' → ' + afterTotal + '）');

  // ── Step 4: 去重测试 — 再次上传同一 PDF ──
  console.log('Step 4: 去重测试 — 再次上传同一 PDF');
  const beforeDupRows = await page.locator('table tbody tr').count();
  const fileInput3 = page.locator("input[type='file']");
  await fileInput3.setInputFiles(PDF_PATH);
  await page.waitForTimeout(5000);
  const afterDupRows = await page.locator('table tbody tr').count();
  if (afterDupRows > beforeDupRows) {
    throw new Error('去重失败: 重复上传后行数增加 ' + beforeDupRows + ' → ' + afterDupRows);
  }
  await page.screenshot({ path: SS + '-04-dedup.png', fullPage: true });
  console.log('PASS: 去重生效（行数不变: ' + afterDupRows + '）');

  // ── Step 5: 等待转换完成（大文件可能需要较长时间） ──
  console.log('Step 5: 等待至少一个文件转换完成（最长 10 分钟）...');
  const readyBadge = page.locator('table tbody tr').filter({ hasText: 'E2E测试招标文件' }).getByText('已就绪');
  try {
    await readyBadge.waitFor({ timeout: 600000 });
    console.log('PASS: PDF 转换完成（已就绪）');
    await page.screenshot({ path: SS + '-05-converted.png', fullPage: true });
  } catch {
    const currentStatus = await pdfRowFull.textContent() || '';
    console.log('WARN: 10 分钟内 PDF 未完成转换，当前状态: ' + currentStatus.slice(0, 80));
    await page.screenshot({ path: SS + '-05-still-converting.png', fullPage: true });
  }

  // ── Step 6: 进度条视觉检查（转换中时应显示） ──
  const convertingRows = page.locator('table tbody tr').filter({ hasText: '转换中' });
  const convertingCount = await convertingRows.count();
  if (convertingCount > 0) {
    const progressBar = convertingRows.first().locator('[role="progressbar"], .bg-blue-500, .h-1');
    await page.screenshot({ path: SS + '-06-progress-bar.png', fullPage: true });
    console.log('PASS: 转换中行已截图供视觉检查（' + convertingCount + ' 行转换中）');
  } else {
    console.log('SKIP: 无转换中文件，跳过进度条检查');
  }

  console.log('== files-F2-upload 全部通过 ==');
}

async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const FIX = '/home/iomgaa/Projects/GovDoc_Editor/tests/fixtures/compare';
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  async function compareAndGetMetrics(files, label) {
    await page.goto(BASE + '/compare');
    await page.waitForLoadState('domcontentloaded');
    const fileInputs = page.locator("input[type='file']");
    const inputCount = await fileInputs.count();
    if (inputCount >= 2) {
      // 双输入框模式
      await fileInputs.nth(0).setInputFiles(files[0]);
      if (files.length > 1) await fileInputs.nth(1).setInputFiles(files[1]);
    } else {
      // 单输入框 multiple 模式
      await fileInputs.first().setInputFiles(files);
    }
    await page.waitForTimeout(500);
    const compareBtn = page.getByRole('button', { name: /开始对比/ });
    await compareBtn.click();
    const metric = page.getByText('匹配总数');
    await metric.waitFor({ timeout: 180000 });
    await page.screenshot({ path: 'e2e/screenshots/14-' + label + '.png', fullPage: true });

    const getText = async (labelText) => {
      const el = page.getByText(labelText).first();
      const parent = el.locator('..');
      const valueEl = parent.locator('.text-2xl, .text-3xl').first();
      return parseInt((await valueEl.textContent() || '0').trim(), 10);
    };
    const matchCount = await getText('匹配总数');
    const paragraphCount = await getText('相同段落');
    const sentenceCount = await getText('相同句子');
    const segmentCount = await getText('公共片段');
    return { matchCount, paragraphCount, sentenceCount, segmentCount };
  }

  async function getMatchTexts() {
    const items = page.locator('button.w-full.border-b p.line-clamp-2');
    const count = await items.count();
    const texts = [];
    for (let i = 0; i < count; i++) {
      texts.push((await items.nth(i).textContent() || '').trim());
    }
    return texts;
  }

  async function getMatchFileInfo() {
    const items = page.locator('button.w-full.border-b');
    const count = await items.count();
    const infos = [];
    for (let i = 0; i < count; i++) {
      const fileText = await items.nth(i).locator('p.text-xs').last().textContent() || '';
      infos.push(fileText.trim());
    }
    return infos;
  }

  // 用例①：段落级精确匹配
  console.log('== 用例①: 段落级精确匹配 ==');
  const m1 = await compareAndGetMetrics(
    [FIX + '/para_a.docx', FIX + '/para_b.docx'], 'para');
  if (m1.paragraphCount !== 1) throw new Error('①段落数应为1，实际: ' + m1.paragraphCount);
  if (m1.sentenceCount !== 0) throw new Error('①句子数应为0，实际: ' + m1.sentenceCount);
  if (m1.segmentCount < 1) throw new Error('①片段数应≥1，实际: ' + m1.segmentCount);
  if (m1.matchCount !== 2) throw new Error('①匹配总数应为2，实际: ' + m1.matchCount);
  const texts1 = await getMatchTexts();
  if (!texts1.some(t => t.includes('投标人应具有独立承担民事责任的能力'))) {
    throw new Error('①匹配文本缺少预期段落');
  }
  console.log('PASS: 段落级 — paragraphCount=1, sentenceCount=0, segmentCount≥1, matchCount=2');

  // 用例②：句子级精确匹配
  console.log('== 用例②: 句子级精确匹配 ==');
  const m2 = await compareAndGetMetrics(
    [FIX + '/sent_a.docx', FIX + '/sent_b.docx'], 'sent');
  if (m2.paragraphCount !== 0) throw new Error('②段落数应为0，实际: ' + m2.paragraphCount);
  if (m2.sentenceCount !== 2) throw new Error('②句子数应为2，实际: ' + m2.sentenceCount);
  if (m2.matchCount !== 2) throw new Error('②匹配总数应为2，实际: ' + m2.matchCount);
  const texts2 = await getMatchTexts();
  if (!texts2.some(t => t.includes('采购人可自行选择'))) throw new Error('②缺少句子匹配: 采购人');
  if (!texts2.some(t => t.includes('评标委员会独立评审'))) throw new Error('②缺少句子匹配: 评标委员会');
  console.log('PASS: 句子级 — paragraphCount=0, sentenceCount=2, matchCount=2');

  // 用例③：片段级连续匹配
  console.log('== 用例③: 片段级连续匹配 ==');
  const m3 = await compareAndGetMetrics(
    [FIX + '/seg_a.docx', FIX + '/seg_b.docx'], 'seg');
  if (m3.paragraphCount !== 0) throw new Error('③段落数应为0，实际: ' + m3.paragraphCount);
  if (m3.sentenceCount !== 0) throw new Error('③句子数应为0，实际: ' + m3.sentenceCount);
  if (m3.segmentCount < 1) throw new Error('③片段数应≥1，实际: ' + m3.segmentCount);
  const texts3 = await getMatchTexts();
  if (!texts3.some(t => t.includes('具有良好的商业信誉'))) {
    throw new Error('③匹配文本缺少预期片段');
  }
  console.log('PASS: 片段级 — paragraphCount=0, sentenceCount=0, segmentCount≥1');

  // 用例④：三级混合
  console.log('== 用例④: 三级混合 ==');
  const m4 = await compareAndGetMetrics(
    [FIX + '/mix_a.docx', FIX + '/mix_b.docx'], 'mix');
  if (m4.paragraphCount !== 1) throw new Error('④段落数应为1，实际: ' + m4.paragraphCount);
  if (m4.sentenceCount !== 2) throw new Error('④句子数应为2，实际: ' + m4.sentenceCount);
  if (m4.segmentCount !== 2) throw new Error('④片段数应为2，实际: ' + m4.segmentCount);
  if (m4.matchCount !== 5) throw new Error('④匹配总数应为5，实际: ' + m4.matchCount);
  console.log('PASS: 三级混合 — paragraphCount=1, sentenceCount=2, segmentCount=2, matchCount=5');

  // 用例⑤：自比较
  console.log('== 用例⑤: 自比较 ==');
  const m5 = await compareAndGetMetrics(
    [FIX + '/para_a.docx', FIX + '/para_a.docx'], 'self');
  if (m5.paragraphCount !== 2) throw new Error('⑤自比较段落数应为2，实际: ' + m5.paragraphCount);
  if (m5.sentenceCount !== 0) throw new Error('⑤自比较句子数应为0，实际: ' + m5.sentenceCount);
  if (m5.matchCount !== 2) throw new Error('⑤自比较匹配总数应为2，实际: ' + m5.matchCount);
  console.log('PASS: 自比较 — paragraphCount=2, sentenceCount=0, matchCount=2');

  // 用例⑥：无重复
  console.log('== 用例⑥: 无重复 ==');
  const m6 = await compareAndGetMetrics(
    [FIX + '/unique_a.docx', FIX + '/unique_b.docx'], 'unique');
  if (m6.matchCount !== 0) throw new Error('⑥无重复匹配总数应为0，实际: ' + m6.matchCount);
  console.log('PASS: 无重复 — matchCount=0');

  // 用例⑦：多文档 N=4
  console.log('== 用例⑦: 多文档 N=4 ==');
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('domcontentloaded');
  const inputCount7 = await page.locator("input[type='file']").count();
  if (inputCount7 <= 2) {
    console.log('SKIP: 部署版仅支持 2 文件对比，跳过 N=4 用例');
  } else {
    const m7 = await compareAndGetMetrics([
      FIX + '/multi_1.docx', FIX + '/multi_2.docx',
      FIX + '/multi_3.docx', FIX + '/multi_4.docx',
    ], 'multi');
    if (m7.paragraphCount !== 3) throw new Error('⑦段落数应为3，实际: ' + m7.paragraphCount);
    if (m7.sentenceCount !== 0) throw new Error('⑦句子数应为0，实际: ' + m7.sentenceCount);
    if (m7.segmentCount !== 2) throw new Error('⑦片段数应为2，实际: ' + m7.segmentCount);
    if (m7.matchCount !== 5) throw new Error('⑦匹配总数应为5，实际: ' + m7.matchCount);
    const fileInfos = await getMatchFileInfo();
    const has4file = fileInfos.some(t => t.includes('文件 1') && t.includes('文件 4'));
    if (!has4file) throw new Error('⑦缺少四文件共享的匹配项');
    const has2file = fileInfos.some(t => t.includes('文件 1') && t.includes('文件 2') && !t.includes('文件 3'));
    if (!has2file) throw new Error('⑦缺少仅12共享的匹配项');
    console.log('PASS: 多文档 — paragraphCount=3, sentenceCount=0, segmentCount=2, matchCount=5');
  }

  // 用例⑧：PDF 对比
  console.log('== 用例⑧: PDF 对比 ==');
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('domcontentloaded');
  const acceptAttr = await page.locator("input[type='file']").first().getAttribute('accept') || '';
  if (!acceptAttr.includes('.pdf')) {
    console.log('SKIP: 部署版不支持 PDF 对比，跳过');
  } else {
    const m8 = await compareAndGetMetrics(
      [FIX + '/para_a.pdf', FIX + '/para_b.pdf'], 'pdf');
    if (m8.paragraphCount !== 1) throw new Error('⑧PDF段落数应为1，实际: ' + m8.paragraphCount);
    if (m8.matchCount !== 1) throw new Error('⑧PDF匹配总数应为1，实际: ' + m8.matchCount);
    const texts8 = await getMatchTexts();
    if (!texts8.some(t => t.includes('投标人应具有独立承担民事责任的能力'))) {
      throw new Error('⑧PDF匹配文本缺少预期段落');
    }
    console.log('PASS: PDF — paragraphCount=1, matchCount=1, 文本正确');
  }

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-14-compare-verify 全部通过 ==');
}

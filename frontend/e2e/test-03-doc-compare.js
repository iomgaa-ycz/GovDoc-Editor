async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const DOC_A = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx';
  const DOC_B = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目.docx';

  // Step 1: 进入文档对比页
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入文档对比页');
  await page.screenshot({ path: 'e2e/screenshots/03-compare-empty.png' });

  // Step 2: 上传多份文档
  const fileInput = page.locator("input[type='file']").first();
  await fileInput.setInputFiles([DOC_A, DOC_B]);
  console.log('Step 2: 已上传 2 份 DOCX 文件');

  // Step 3: 点击「开始对比」
  const compareBtn = page.getByRole('button', { name: /开始对比/ });
  await compareBtn.click();
  console.log('Step 3: 点击开始对比');

  // Step 4: 等待对比结果
  const metric = page.getByText('匹配总数');
  await metric.waitFor({ timeout: 120000 });
  console.log('Step 4: 对比结果已返回');
  await page.screenshot({ path: 'e2e/screenshots/03-compare-result.png', fullPage: true });

  // Step 5: 验证结果内容 — 用指标卡的数值容器验证
  const metricCards = page.locator('.border-l-4');
  const metricCount = await metricCards.count();
  if (metricCount < 3) throw new Error('指标卡不足: ' + metricCount);
  console.log('Step 5: ' + metricCount + ' 个指标卡正确显示');

  // Step 6: 验证匹配清单区域存在
  const matchList = page.getByText('匹配清单').first();
  if (!(await matchList.isVisible())) throw new Error('缺少匹配清单');
  console.log('Step 6: 匹配清单存在');

  // Step 7: 验证文件栏存在（适配不同 UI 版本的标题格式）
  const mainContent = page.locator('main');
  const mainText = await mainContent.textContent() || '';
  const hasFileCol = mainText.includes('文件 1') || mainText.includes('文档 A') || mainText.includes('.docx');
  if (!hasFileCol) throw new Error('缺少文件栏');
  console.log('Step 7: 文件栏存在');

  // Step 8: 验证指标卡数值非空
  const metricLabels = ['匹配总数', '相同段落', '相同句子', '公共片段'];
  for (const label of metricLabels) {
    const el = page.getByText(label).first();
    const parent = el.locator('..');
    const valueEl = parent.locator('.text-2xl, .text-3xl').first();
    const val = (await valueEl.textContent() || '').trim();
    if (!val || val === '') throw new Error('指标卡 "' + label + '" 数值为空');
  }
  console.log('Step 8: 4 个指标卡数值非空');

  // Step 9: 验证匹配清单至少 1 项
  const matchItems = page.locator('button.w-full.border-b');
  const matchItemCount = await matchItems.count();
  if (matchItemCount < 1) throw new Error('匹配清单为空');
  console.log('Step 9: 匹配清单有 ' + matchItemCount + ' 项');

  // Step 10: 验证匹配文本含中文
  const chineseRegex = /[一-鿿]/;
  let hasChinese = false;
  for (let i = 0; i < Math.min(matchItemCount, 3); i++) {
    const text = (await matchItems.nth(i).textContent() || '');
    if (chineseRegex.test(text)) { hasChinese = true; break; }
  }
  if (!hasChinese) throw new Error('匹配文本中未检测到中文');
  console.log('Step 10: 匹配文本含中文字符');

  console.log('== test-03-doc-compare 全部通过 ==');
}

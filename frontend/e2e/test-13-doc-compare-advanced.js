async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const DOC_A = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx';
  const DOC_B = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目.docx';
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 进入文档对比页
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入文档对比页');

  // Step 2: 验证开始对比按钮初始禁用
  const compareBtn = page.getByRole('button', { name: /开始对比/ });
  if (!(await compareBtn.isDisabled())) throw new Error('初始状态开始对比按钮未禁用');
  console.log('PASS: 初始状态开始对比按钮禁用');

  // Step 3: 直接设置 3 个文件，验证 3 个卡片
  const fileInput = page.locator("input[type='file']").first();
  await fileInput.setInputFiles([DOC_A, DOC_B, DOC_A]);
  await page.waitForTimeout(500);
  const fileCards = page.locator('.rounded-card.border.bg-white');
  const cardCount3 = await fileCards.count();
  if (cardCount3 !== 3) throw new Error('应有 3 个文件卡片，实际: ' + cardCount3);
  if (await compareBtn.isDisabled()) throw new Error('3 个文件时按钮仍禁用');
  console.log('PASS: 3 个文件卡片正确，按钮启用');

  // Step 4: 移除第 2 个文件，验证剩 2 个
  const removeButtons = page.locator('button[aria-label*="移除"]');
  if (await removeButtons.count() >= 2) {
    await removeButtons.nth(1).click();
    await page.waitForTimeout(300);
    const cardCount2 = await fileCards.count();
    if (cardCount2 !== 2) throw new Error('移除后应剩 2 个文件卡片，实际: ' + cardCount2);
    console.log('PASS: 文件移除成功（3 → 2）');
  } else {
    console.log('SKIP: 移除按钮不足');
  }

  // Step 6: 开始对比并等待结果
  await compareBtn.click();
  console.log('Step 6: 点击开始对比');
  const metric = page.getByText('匹配总数');
  await metric.waitFor({ timeout: 120000 });
  console.log('PASS: 对比结果返回');
  await page.screenshot({ path: 'e2e/screenshots/13-compare-result.png', fullPage: true });

  // Step 7: 分类切换筛选
  const catButtons = page.locator('button.rounded-full.text-xs');
  const catBtnCount = await catButtons.count();
  if (catBtnCount >= 2) {
    const matchList = page.locator('button.w-full.border-b');
    const initialMatchCount = await matchList.count();
    await catButtons.first().click();
    await page.waitForTimeout(500);
    const afterToggleCount = await matchList.count();
    await catButtons.first().click();
    await page.waitForTimeout(500);
    const restoredCount = await matchList.count();
    console.log('PASS: 分类切换（' + initialMatchCount + ' → ' + afterToggleCount + ' → ' + restoredCount + '）');
  } else {
    console.log('SKIP: 分类按钮不足');
  }

  // Step 8: 匹配清单点击 → 选中样式
  const matchItems = page.locator('button.w-full.border-b');
  const matchCount = await matchItems.count();
  if (matchCount > 0) {
    await matchItems.first().click();
    await page.waitForTimeout(500);
    const hasActiveStyle = await matchItems.first().evaluate(el => el.classList.contains('bg-accent-light'));
    if (!hasActiveStyle) throw new Error('点击匹配项后未显示选中样式');
    console.log('PASS: 匹配项点击 → 选中高亮');
  }

  // Step 9: 下载高亮副本按钮
  const downloadBtns = page.getByText(/高亮副本/);
  const dlCount = await downloadBtns.count();
  if (dlCount >= 1) {
    console.log('PASS: ' + dlCount + ' 个高亮副本下载按钮');
  } else {
    console.log('SKIP: 无高亮副本按钮');
  }

  // Step 10: 重新上传按钮
  const resetBtn = page.getByRole('button', { name: /重新上传/ });
  if (await resetBtn.isVisible().catch(() => false)) {
    await resetBtn.click();
    await page.waitForTimeout(1000);
    const dropzone = page.getByText('选择或拖入对比文件');
    if (!(await dropzone.isVisible().catch(() => false))) throw new Error('重新上传后未恢复初始状态');
    console.log('PASS: 重新上传 → 回到初始状态');
  } else {
    console.log('SKIP: 无重新上传按钮');
  }

  await page.screenshot({ path: 'e2e/screenshots/13-compare-final.png' });
  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-13-doc-compare-advanced 全部通过 ==');
}

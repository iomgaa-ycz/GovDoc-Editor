async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const TENDER_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf';
  const SUPP_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/广州市从化区中医医院从化区中医医院手术室设备及附件、病房护理及医院设备采购的合同.pdf';

  // Step 1: 进入 AI 审核页面
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');
  console.log('Step 1: 进入 AI 审核页面');

  // Step 2: 创建新项目
  const projName = 'E2E-多文件-' + Date.now().toString().slice(-6);
  await page.getByPlaceholder('输入项目名称').fill(projName);
  await page.getByRole('button', { name: /创建/ }).click();
  await page.getByText('主招标文书').waitFor({ timeout: 10000 });
  console.log('Step 2: 创建项目 ' + projName);

  // Step 3: 选择主招标文书
  const mainFileInput = page.locator("input[type='file']").first();
  await mainFileInput.waitFor({ state: 'attached', timeout: 10000 });
  await mainFileInput.setInputFiles(TENDER_PDF);
  console.log('Step 3: 选择主招标文书');

  // Step 4: 验证附件区域和主文件"移除"按钮出现
  await page.getByText('补充文件（可选）').waitFor({ timeout: 5000 });
  const removeMainBtn = page.getByText('移除').first();
  await removeMainBtn.waitFor({ timeout: 5000 });
  console.log('Step 4: 附件区域 + 移除按钮已出现');

  // Step 5: 测试移除主文件（上传前）→ 回退到 FileDropzone
  await removeMainBtn.click();
  const dropzone = page.getByText('点击选择或拖入招标文书');
  await dropzone.waitFor({ timeout: 5000 });
  console.log('Step 5: 移除主文件后回退到选择状态');
  await page.screenshot({ path: 'e2e/screenshots/06-removed-before-upload.png' });

  // Step 6: 重新选择主文件
  const mainInput2 = page.locator("input[type='file']").first();
  await mainInput2.waitFor({ state: 'attached', timeout: 5000 });
  await mainInput2.setInputFiles(TENDER_PDF);
  await page.getByText('补充文件（可选）').waitFor({ timeout: 5000 });
  console.log('Step 6: 重新选择主招标文书');

  // Step 7: 添加补充文件
  const suppInput = page.locator("input[type='file']").last();
  await suppInput.waitFor({ state: 'attached', timeout: 5000 });
  await suppInput.setInputFiles(SUPP_PDF);
  await page.getByText(/合同/).waitFor({ timeout: 5000 });
  console.log('Step 7: 添加 1 个补充文件');

  // Step 8: 测试删除补充文件（上传前）→ X 按钮
  const suppDeleteBtn = page.locator('button.text-text-muted');
  if (await suppDeleteBtn.count() > 0) {
    await suppDeleteBtn.first().click();
    await page.waitForTimeout(300);
    console.log('Step 8: 删除补充文件');
  } else {
    console.log('Step 8: 跳过 — 未找到删除按钮');
  }

  // Step 9: 重新添加补充文件
  const suppInput2 = page.locator("input[type='file']").last();
  await suppInput2.waitFor({ state: 'attached', timeout: 5000 });
  await suppInput2.setInputFiles(SUPP_PDF);
  await page.getByText(/合同/).waitFor({ timeout: 5000 });
  console.log('Step 9: 重新添加补充文件');
  await page.screenshot({ path: 'e2e/screenshots/06-supp-added.png' });

  // Step 10: 验证确认上传按钮显示附件数量
  const uploadBtn = page.getByRole('button', { name: /确认上传/ });
  await uploadBtn.waitFor({ timeout: 5000 });
  const btnText = await uploadBtn.textContent();
  if (!btnText.includes('附件')) throw new Error('确认上传按钮未显示附件数量: ' + btnText);
  console.log('Step 10: 确认上传按钮: ' + btnText);

  // Step 11: 点击确认上传，等待上传完成
  await uploadBtn.click();
  console.log('Step 11: 开始上传');
  const uploadedIndicator = page.locator('.border-green-300');
  await uploadedIndicator.waitFor({ timeout: 180000 });
  console.log('Step 11: 上传完成');
  await page.screenshot({ path: 'e2e/screenshots/06-uploaded.png' });

  // Step 12: 选择审核点并启动审核
  const checkboxes = page.locator("input[type='checkbox']");
  await checkboxes.first().waitFor({ timeout: 10000 });
  const cpCount = await checkboxes.count();
  const selectCount = Math.min(cpCount, 2);
  for (let i = 0; i < selectCount; i++) await checkboxes.nth(i).check();

  const startBtn = page.getByRole('button', { name: /开始审核/ });
  await startBtn.click();
  console.log('Step 12: 启动审核（' + selectCount + ' 个审核点）');

  const running = page.getByText('审核进行中');
  await running.waitFor({ timeout: 30000 });

  // Step 13: 等待至少一个审核点完成
  console.log('Step 13: 等待审核点完成（最长 60 分钟）...');
  const completedBadge = page.locator('main').getByText('已完成').first();
  await completedBadge.waitFor({ timeout: 3600000 });
  console.log('Step 13: 至少一个审核点已完成');

  // Step 14: 验证质量
  console.log('Step 14: 验证审核结论质量');
  const VALID_VERDICTS = ['合规', '不合规', '存疑'];
  const pointBtns = page.locator('main button.border-l-4');
  const pointBtnCount = await pointBtns.count();
  let qualityVerified = 0;

  for (let i = 0; i < pointBtnCount; i++) {
    const btn = pointBtns.nth(i);
    const btnText = (await btn.textContent() || '');
    if (!btnText.includes('已完成') && !VALID_VERDICTS.some(v => btnText.includes(v))) continue;

    await btn.click();
    await page.waitForTimeout(1000);

    const hasVerdict = await page.getByText('审核结论').isVisible().catch(() => false);
    if (!hasVerdict) continue;

    const verdictPanel = page.locator('.rounded-card.border.p-4').first();
    const verdictText = (await verdictPanel.textContent() || '');
    const foundVerdict = VALID_VERDICTS.find(v => verdictText.includes(v));
    if (!foundVerdict) throw new Error('审核点 ' + i + ' verdict 无效');

    const rationale = page.getByText('审查意见').locator('..').locator('p').first();
    const rText = (await rationale.textContent().catch(() => '') || '').trim();
    if (rText.length <= 20) throw new Error('审核点 ' + i + ' 审查意见过短: ' + rText.length);

    qualityVerified++;
    console.log('Step 14: 审核点 ' + i + ' — verdict=' + foundVerdict + ', ok');
  }
  console.log('Step 14: 验证 ' + qualityVerified + ' 个审核点质量通过');

  // Step 15: 最终截图
  await page.screenshot({ path: 'e2e/screenshots/06-final.png', fullPage: true });
  console.log('== test-06-ai-audit-multifile 全部通过 ==');
}

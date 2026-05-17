async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const TENDER_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf';
  const SUPP_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/广州市从化区中医医院从化区中医医院手术室设备及附件、病房护理及医院设备采购的合同.pdf';

  // Step 1: 进入 AI 审核页面
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入 AI 审核页面');

  // Step 2: 创建新项目
  const projName = 'E2E-多文件-' + Date.now().toString().slice(-6);
  await page.getByPlaceholder('输入项目名称').fill(projName);
  await page.getByRole('button', { name: /创建/ }).click();
  await page.waitForTimeout(2000);
  console.log('Step 2: 创建项目 ' + projName);

  // Step 3: 上传主招标文书
  const fileInputs = page.locator("input[type='file']");
  await fileInputs.first().setInputFiles(TENDER_PDF);
  await page.waitForTimeout(500);
  console.log('Step 3: 选择主招标文书');
  await page.screenshot({ path: 'e2e/screenshots/06-main-selected.png' });

  // Step 4: 验证附件区域出现
  await page.getByText('补充文件（可选）').waitFor({ timeout: 5000 });
  console.log('Step 4: 附件区域已出现');

  // Step 5: 添加补充文件
  const suppInput = fileInputs.last();
  await suppInput.setInputFiles(SUPP_PDF);
  await page.waitForTimeout(500);
  console.log('Step 5: 添加 1 个补充文件');
  await page.screenshot({ path: 'e2e/screenshots/06-supp-added.png' });

  // Step 6: 验证补充文件列表显示
  const suppFileText = page.getByText(/合同/);
  await suppFileText.waitFor({ timeout: 5000 });
  console.log('Step 6: 补充文件名显示正确');

  // Step 7: 验证确认上传按钮文案含附件数量
  const uploadBtn = page.getByRole('button', { name: /确认上传/ });
  await uploadBtn.waitFor({ timeout: 5000 });
  const btnText = await uploadBtn.textContent();
  if (!btnText.includes('附件')) throw new Error('确认上传按钮未显示附件数量: ' + btnText);
  console.log('Step 7: 确认上传按钮: ' + btnText);

  // Step 8: 点击确认上传
  await uploadBtn.click();
  console.log('Step 8: 开始上传');

  // Step 9: 等待上传完成（主文件绿色状态出现）
  const uploadedIndicator = page.locator('.border-green-300');
  await uploadedIndicator.waitFor({ timeout: 180000 });
  console.log('Step 9: 上传完成');
  await page.screenshot({ path: 'e2e/screenshots/06-uploaded.png' });

  // Step 10: 验证移除按钮存在
  const removeBtn = page.getByText('移除');
  await removeBtn.waitFor({ timeout: 5000 });
  console.log('Step 10: 移除按钮存在');

  // Step 11: 测试移除主文件 → 回退到上传步骤
  await removeBtn.click();
  await page.waitForTimeout(500);
  const dropzone = page.getByText('点击选择或拖入招标文书');
  await dropzone.waitFor({ timeout: 5000 });
  console.log('Step 11: 移除后回退到上传步骤');
  await page.screenshot({ path: 'e2e/screenshots/06-removed.png' });

  // Step 12: 最终截图
  await page.screenshot({ path: 'e2e/screenshots/06-final.png', fullPage: true });
  console.log('== test-06-ai-audit-multifile 全部通过 ==');
}

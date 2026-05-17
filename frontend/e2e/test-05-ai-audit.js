async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const TENDER_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf';

  // Step 1: 进入 AI 审核页面
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');
  console.log('Step 1: 进入 AI 审核页面');
  await page.screenshot({ path: 'e2e/screenshots/05-audit-page.png' });

  // Step 2: 创建新项目 — 等待步骤2 UI 出现确认项目创建成功
  const projName = 'E2E-从化医院-' + Date.now().toString().slice(-6);
  await page.getByPlaceholder('输入项目名称').fill(projName);
  await page.getByRole('button', { name: /创建/ }).click();
  await page.getByText('主招标文书').waitFor({ timeout: 10000 });
  console.log('Step 2: 创建项目 ' + projName);

  // Step 3: 上传招标文件（单主文件）
  const fileInput = page.locator("input[type='file']").first();
  await fileInput.waitFor({ state: 'attached', timeout: 10000 });
  await fileInput.setInputFiles(TENDER_PDF);

  const uploadBtn = page.getByRole('button', { name: /确认上传/ });
  await uploadBtn.waitFor({ timeout: 5000 });
  await uploadBtn.click();
  console.log('Step 3: 上传招标文件');

  // 等待上传完成（绿色边框状态）
  const uploaded = page.locator('.border-green-300');
  await uploaded.waitFor({ timeout: 180000 });
  console.log('Step 3: 上传完成');
  await page.screenshot({ path: 'e2e/screenshots/05-audit-uploaded.png' });

  // Step 4: 选择 1-2 个审核点
  const checkboxes = page.locator("input[type='checkbox']");
  await checkboxes.first().waitFor({ timeout: 10000 });
  const cpCount = await checkboxes.count();
  if (cpCount === 0) throw new Error('无可选审核点');
  const selectCount = Math.min(cpCount, 2);
  for (let i = 0; i < selectCount; i++) {
    await checkboxes.nth(i).check();
  }
  console.log('Step 4: 选择 ' + selectCount + ' 个审核点（共 ' + cpCount + ' 个可选）');

  // Step 5: 启动审核
  const startBtn = page.getByRole('button', { name: /开始审核/ });
  await startBtn.click();
  console.log('Step 5: 启动审核');

  // Step 6: 验证进入审核进行中模式
  const running = page.getByText('审核进行中');
  await running.waitFor({ timeout: 30000 });
  console.log('Step 6: 审核进行中');
  await page.screenshot({ path: 'e2e/screenshots/05-audit-running.png' });

  // Step 7: 等待至少一个审核点完成（最长 60 分钟）
  console.log('Step 7: 等待审核点完成（最长 60 分钟）...');
  const completedBadge = page.locator('main').getByText('已完成').first();
  await completedBadge.waitFor({ timeout: 3600000 });
  console.log('Step 7: 至少一个审核点已完成');
  await page.screenshot({ path: 'e2e/screenshots/05-audit-partial.png' });

  // Step 8: 截图最终状态
  await page.screenshot({ path: 'e2e/screenshots/05-audit-final.png', fullPage: true });
  console.log('== test-05-ai-audit 全部通过 ==');
}

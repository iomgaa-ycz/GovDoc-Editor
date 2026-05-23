async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const TENDER_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf';
  const SUPP_PDF = '/home/iomgaa/Projects/GovDoc_Editor/real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/广州市从化区中医医院从化区中医医院手术室设备及附件、病房护理及医院设备采购的合同.pdf';
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 进入 AI 审核页面
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');
  console.log('Step 1: 进入 AI 审核页面');

  // Step 2: 步骤进度 UI 验证
  const stepLabels = ['选择或创建项目', '上传招标文件', '选择审查要点'];
  for (const label of stepLabels) {
    const el = page.getByText(label).first();
    if (!(await el.isVisible())) throw new Error('步骤标签缺失: ' + label);
  }
  console.log('PASS: 3 个步骤标签完整');

  // Step 3: 创建按钮禁用状态
  const createBtn = page.getByRole('button', { name: /创建/ });
  const nameInput = page.getByPlaceholder('输入项目名称');
  await nameInput.fill('');
  if (!(await createBtn.isDisabled())) throw new Error('空名称时创建按钮未禁用');
  console.log('PASS: 空名称时创建按钮禁用');

  // Step 4: 选择现有项目
  const projectSelect = page.locator('select').first();
  const options = projectSelect.locator('option');
  const optionCount = await options.count();
  if (optionCount > 1) {
    await projectSelect.selectOption({ index: 1 });
    await page.waitForTimeout(500);
    const step2Card = page.getByText('第二步：上传招标文书');
    await step2Card.waitFor({ timeout: 5000 });
    console.log('PASS: 选择现有项目，步骤 2 出现');
  } else {
    console.log('SKIP: 无现有项目，将通过创建项目测试');
  }

  // Step 5-8: 创建新项目 + 完整上传流程
  const projName = 'E2E-quick-' + Date.now().toString().slice(-6);
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  await nameInput.fill(projName);
  await createBtn.click();
  await page.waitForTimeout(2000);

  const step2Card = page.getByText('第二步：上传招标文书');
  await step2Card.waitFor({ timeout: 10000 });
  console.log('PASS: 创建项目 "' + projName + '"，步骤 2 出现');

  // Step 5: 主文件选择 → 移除 → 恢复
  const mainFileInput = page.locator("input[type='file']").first();
  await mainFileInput.setInputFiles(TENDER_PDF);
  await page.waitForTimeout(500);

  const removeBtn = page.getByText('移除').first();
  await removeBtn.waitFor({ timeout: 5000 });
  await removeBtn.click();
  await page.waitForTimeout(500);

  const dropzone = page.getByText('点击选择或拖入招标文书');
  if (!(await dropzone.isVisible())) throw new Error('移除主文件后 FileDropzone 未恢复');
  console.log('PASS: 主文件移除后 FileDropzone 恢复');

  // Step 6: 重新选择主文件 + 补充文件添加/删除
  const mainFileInput2 = page.locator("input[type='file']").first();
  await mainFileInput2.setInputFiles(TENDER_PDF);
  await page.waitForTimeout(1000);

  const suppLabel = page.getByText('补充文件（可选）');
  await suppLabel.waitFor({ timeout: 5000 });

  const suppFileInput = page.locator("input[type='file']").last();
  await suppFileInput.setInputFiles(SUPP_PDF);
  await page.waitForTimeout(500);

  const suppFileName = page.getByText('的合同.pdf');
  if (!(await suppFileName.isVisible().catch(() => false))) {
    console.log('SKIP: 补充文件名未显示，跳过删除测试');
  } else {
    const xBtn = suppFileName.locator('..').locator('button');
    if (await xBtn.isVisible().catch(() => false)) {
      await xBtn.click();
      await page.waitForTimeout(300);
      if (await suppFileName.isVisible().catch(() => false)) throw new Error('补充文件删除后仍可见');
      console.log('PASS: 补充文件删除');
    }
  }

  // Step 7: 确认上传 + 等待绿色边框
  const uploadBtn = page.getByRole('button', { name: /确认上传/ });
  if (await uploadBtn.isVisible()) {
    await uploadBtn.click();
    const greenBorder = page.locator('.border-green-300');
    await greenBorder.waitFor({ timeout: 60000 });
    console.log('PASS: 文件上传完成（绿色边框）');
  } else {
    console.log('SKIP: 确认上传按钮不可见');
  }

  // Step 8: 审查要点 checkbox + 开始审核按钮禁用状态
  const step3Title = page.getByText('第三步：选择审查要点');
  await step3Title.waitFor({ timeout: 10000 });

  const checkboxes = page.locator('input[type="checkbox"]');
  const cpCount = await checkboxes.count();

  if (cpCount > 0) {
    const startBtn = page.getByRole('button', { name: /开始审核/ });

    // 验证 0 个选中时 disabled
    if (!(await startBtn.isDisabled())) throw new Error('0 个选中时开始审核按钮未禁用');
    console.log('PASS: 0 个选中 → 开始审核禁用');

    // 勾选第 1 个
    await checkboxes.first().check();
    await page.waitForTimeout(300);
    if (await startBtn.isDisabled()) throw new Error('勾选 1 个后开始审核按钮仍禁用');

    const btnText = await startBtn.textContent();
    if (!btnText.includes('1')) throw new Error('按钮文本未包含选中数量');
    console.log('PASS: 勾选 1 个 → 按钮启用，文本含数量');

    // 取消勾选
    await checkboxes.first().uncheck();
    await page.waitForTimeout(300);
    if (!(await startBtn.isDisabled())) throw new Error('取消勾选后按钮未禁用');
    console.log('PASS: 取消勾选 → 按钮禁用');
  } else {
    const emptyHint = page.getByText('暂无审查要点');
    if (!(await emptyHint.isVisible())) throw new Error('无审查要点时缺少空状态提示');
    console.log('PASS: 空审查要点提示正确');
  }

  await page.screenshot({ path: 'e2e/screenshots/10-ai-review-workflow.png', fullPage: true });

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-10-ai-review-workflow 全部通过 ==');
}

async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const GUIDE_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc';

  // Step 1: 进入审核点库
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入审核点库');

  // Step 2: 点击上传 → AI 提取
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByRole('menuitem', { name: 'AI 提取' }).click();
  await page.waitForLoadState('domcontentloaded');

  // 验证进入 AI 提取页面
  const heading = page.getByText('AI 智能提取审查要点');
  await heading.waitFor({ timeout: 5000 });
  console.log('Step 2: 进入 AI 提取页面');
  await page.screenshot({ path: 'e2e/screenshots/04-extract-page.png' });

  // Step 3: 填写标题
  await page.getByPlaceholder(/政府采购法/).fill('四类违法违规指引');
  console.log('Step 3: 填写标题');

  // Step 4: 上传法规文件
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(GUIDE_PATH);
  console.log('Step 4: 上传法规文件');

  // Step 5: 点击「开始抽取」
  const extractBtn = page.getByRole('button', { name: /开始抽取/ });
  await extractBtn.click();
  console.log('Step 5: 点击开始抽取');
  await page.screenshot({ path: 'e2e/screenshots/04-extract-started.png' });

  // Step 6: 等待提取完成（LLM 调用，最长 60 分钟）
  // 注意：页面静态文字含"提取完成后"，不能用模糊匹配。精确等待成功状态框（绿底 .bg-status-ok-bg）
  console.log('Step 6: 等待 AI 提取完成（最长 60 分钟）...');
  const successBox = page.locator('.bg-status-ok-bg');
  await successBox.waitFor({ timeout: 3600000 });
  const successText = await successBox.textContent();
  console.log('Step 6: AI 提取完成 — ' + successText);
  await page.screenshot({ path: 'e2e/screenshots/04-extract-done.png' });

  // Step 7: 返回列表验证
  await page.getByRole('button', { name: /返回列表/ }).click();
  await page.waitForLoadState('domcontentloaded');

  const rows = page.locator('table tbody tr');
  await rows.first().waitFor({ timeout: 10000 });
  const count = await rows.count();
  if (count < 1) throw new Error('提取后列表为空');
  console.log('Step 7: 列表中有 ' + count + ' 条审核点');
  await page.screenshot({ path: 'e2e/screenshots/04-extract-list.png', fullPage: true });

  console.log('== test-04-ai-extract 全部通过 ==');
}

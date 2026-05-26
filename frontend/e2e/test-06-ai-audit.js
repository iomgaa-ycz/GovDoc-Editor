async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');

  // Step 1: 进入 AI 审查页面
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入 AI 审查页面');
  await page.locator('header').getByText(/AI 审查|AI 审核/).waitFor({ timeout: 10000 });

  // Step 2: 打开新建审查抽屉
  await page.getByRole('button', { name: /新建审查|新建审核/ }).first().click();
  const drawer = page.locator('form').filter({ hasText: '新建审查任务' }).first();
  await drawer.getByText('新建审查任务').waitFor({ timeout: 10000 });
  console.log('Step 2: 新建审查抽屉已打开');

  // Step 3: 验证并点击选择招标文书按钮
  const selectMainDocBtn = drawer.getByRole('button', { name: /选择招标文书/ });
  await selectMainDocBtn.waitFor({ timeout: 10000 });
  console.log('Step 3: 选择招标文书按钮可见');
  await selectMainDocBtn.click();

  // Step 4: 验证 FilePickerModal 弹出
  const modal = page.locator('.fixed.inset-0.z-50.flex.items-center.justify-center').filter({ hasText: '选择文件' }).first();
  await modal.getByText('选择文件').waitFor({ timeout: 10000 });
  console.log('Step 4: FilePickerModal 已弹出');

  // Step 5: 如果文件库有文件，选择 1 个并确认
  const fileRows = modal.locator('div.flex-1.overflow-y-auto button');
  let fileCount = 0;
  for (let i = 0; i < 10; i++) {
    fileCount = await fileRows.count();
    if (fileCount > 0) break;
    await page.waitForTimeout(500);
  }
  if (fileCount >= 1) {
    await fileRows.nth(0).click();
    await modal.getByRole('button', { name: '确认选择' }).click();
    await drawer.getByText('更换').waitFor({ timeout: 10000 });
    await drawer.locator('.text-green-950').first().waitFor({ timeout: 10000 });
    console.log('Step 5: 已选择招标文书并显示绿色文件卡片');
  } else {
    await modal.getByRole('button', { name: '取消' }).click();
    await modal.getByText('选择文件').waitFor({ state: 'hidden', timeout: 10000 });
    console.log('Step 5: 文件库为空，跳过招标文书选择分支');
  }

  // Step 6: 验证补充文件区域
  await drawer.getByText(/补充文件/).waitFor({ timeout: 10000 });
  await drawer.getByRole('button', { name: /从文件库添加/ }).waitFor({ timeout: 10000 });
  console.log('Step 6: 补充文件区域文件库入口可见');

  // Step 7: 验证审查要点列表区域
  await drawer.getByRole('heading', { name: '审查要点' }).waitFor({ timeout: 10000 });
  const checkpointAreaText = await drawer.textContent().catch(() => '') || '';
  if (!checkpointAreaText.includes('审查要点')) throw new Error('缺少审查要点区域');
  console.log('Step 7: 审查要点列表区域存在');

  // Step 8: 验证开始审查按钮
  await drawer.getByRole('button', { name: /开始审查/ }).waitFor({ timeout: 10000 });
  console.log('Step 8: 开始审查按钮存在');

  // Step 9: 验证提示条含文件管理字样
  await drawer.getByText(/文件管理/).waitFor({ timeout: 10000 });
  console.log('Step 9: 文件管理提示条存在');

  await page.screenshot({ path: 'e2e/screenshots/06-ai-audit.png', fullPage: true });
  console.log('== test-06-ai-audit 全部通过 ==');
}

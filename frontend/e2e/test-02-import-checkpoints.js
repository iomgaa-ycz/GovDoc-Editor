async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const XLS_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/附件9 处理处罚标准.xls';

  // Step 1: 进入审核点库
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入审核点库');

  // Step 2: 点击「上传」下拉菜单 → 选择「导入审查点表格」
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('导入审查点表格').click();
  await page.waitForLoadState('domcontentloaded');

  // 验证进入导入子页面
  const heading = page.getByText('导入审查点表格').first();
  if (!(await heading.isVisible())) throw new Error('未进入导入页面');
  console.log('Step 2: 进入导入子页面');
  await page.screenshot({ path: 'e2e/screenshots/02-import-page.png' });

  // Step 3: 上传 XLS 文件
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(XLS_PATH);
  console.log('Step 3: 已选择 XLS 文件');

  // Step 4: 点击「启动解析并导入库」
  const importBtn = page.getByRole('button', { name: /启动解析|导入/ });
  await importBtn.click();
  console.log('Step 4: 点击导入按钮');

  // Step 5: 等待成功提示
  const success = page.getByText(/成功导入/);
  await success.waitFor({ timeout: 60000 });
  const successText = await success.textContent();
  console.log('Step 5: ' + successText);
  await page.screenshot({ path: 'e2e/screenshots/02-import-success.png' });

  // Step 6: 返回列表，验证有审核点
  await page.getByRole('button', { name: /返回列表/ }).click();
  await page.waitForLoadState('domcontentloaded');

  const rows = page.locator('table tbody tr');
  await rows.first().waitFor({ timeout: 10000 });
  const count = await rows.count();
  if (count < 1) throw new Error('导入后列表为空');
  console.log('Step 6: 列表中有 ' + count + ' 条审核点');
  await page.screenshot({ path: 'e2e/screenshots/02-import-list.png', fullPage: true });

  // Step 7: 再次导入同一 XLS，验证不会继续新增审核点
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('导入审查点表格').click();
  await page.waitForLoadState('domcontentloaded');

  const secondFileInput = page.locator("input[type='file']");
  await secondFileInput.setInputFiles(XLS_PATH);
  const secondImportBtn = page.getByRole('button', { name: /启动解析|导入/ });
  await secondImportBtn.click();

  const secondSuccess = page.getByText(/成功导入/);
  await secondSuccess.waitFor({ timeout: 60000 });
  const secondSuccessText = await secondSuccess.textContent();
  console.log('Step 7: ' + secondSuccessText);

  await page.getByRole('button', { name: /返回列表/ }).click();
  await page.waitForLoadState('domcontentloaded');

  const rowsAfterSecondImport = page.locator('table tbody tr');
  await rowsAfterSecondImport.first().waitFor({ timeout: 10000 });
  const countAfterSecondImport = await rowsAfterSecondImport.count();
  if (countAfterSecondImport !== count) {
    throw new Error('重复导入后列表数量发生变化：' + count + ' -> ' + countAfterSecondImport);
  }

  const importedCountMatch = secondSuccessText.match(/成功导入\s*(\d+)\s*条/);
  if (importedCountMatch && Number(importedCountMatch[1]) !== 0) {
    throw new Error('重复导入应成功导入 0 条，实际提示：' + secondSuccessText);
  }

  await page.screenshot({ path: 'e2e/screenshots/02-import-dedup.png', fullPage: true });

  console.log('== test-02-import-checkpoints 全部通过 ==');
}

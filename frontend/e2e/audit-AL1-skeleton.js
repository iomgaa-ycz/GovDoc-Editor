async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL1';

  // Step 1: 进入审核点库页
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // Step 2: 页面标题
  const title = page.locator('header').getByText('审核点库');
  if (!(await title.isVisible())) throw new Error('页面标题"审核点库"不可见');
  console.log('PASS: 页面标题可见');

  // Step 3: 新建库按钮
  const createBtn = page.getByRole('button', { name: '新建库' });
  if (!(await createBtn.isVisible())) throw new Error('"新建库"按钮不可见');
  console.log('PASS: "新建库"按钮可见');

  // Step 4: 上传按钮
  const uploadBtn = page.getByRole('button', { name: '上传' });
  if (!(await uploadBtn.isVisible())) throw new Error('"上传"按钮不可见');
  console.log('PASS: "上传"按钮可见');

  // Step 5: 左侧栏"全部审核点"
  const allPoints = page.getByText('全部审核点').first();
  if (!(await allPoints.isVisible())) throw new Error('左侧栏"全部审核点"不可见');
  console.log('PASS: 左侧栏"全部审核点"可见');

  // Step 6: 搜索框
  const searchInput = page.getByPlaceholder('搜索审查要点...');
  if (!(await searchInput.isVisible())) throw new Error('搜索框不可见');
  console.log('PASS: 搜索框可见');

  // Step 7: 全部分类按钮
  const categoryBtn = page.getByRole('button', { name: '全部分类' });
  if (!(await categoryBtn.isVisible())) throw new Error('"全部分类"按钮不可见');
  console.log('PASS: "全部分类"按钮可见');

  // Step 8: 表格列头
  const expectedColumns = ['审查要点', '分类', '严重程度', '状态', '操作'];
  for (const col of expectedColumns) {
    const th = page.locator('th, thead').getByText(col).first();
    if (!(await th.isVisible())) throw new Error('表格列头缺失: ' + col);
  }
  console.log('PASS: 表格列头完整（' + expectedColumns.join('/') + '）');

  // Step 9: 全选 checkbox
  const selectAllCheckbox = page.locator('thead input[type="checkbox"]');
  if (!(await selectAllCheckbox.isVisible())) throw new Error('全选 checkbox 不可见');
  console.log('PASS: 全选 checkbox 可见');

  // Step 10: 上传下拉菜单
  await uploadBtn.click();
  await page.waitForTimeout(300);
  const aiExtract = page.getByText('AI 提取').first();
  const importSheet = page.getByText('导入审查点表格').first();
  if (!(await aiExtract.isVisible())) throw new Error('下拉菜单"AI 提取"不可见');
  if (!(await importSheet.isVisible())) throw new Error('下拉菜单"导入审查点表格"不可见');
  await page.screenshot({ path: SS + '-02-upload-dropdown.png', fullPage: true });
  console.log('PASS: 上传下拉菜单包含"AI 提取"和"导入审查点表格"');
  await page.keyboard.press('Escape');

  // Step 11: 最终全页截图
  await page.screenshot({ path: SS + '-03-full-page.png', fullPage: true });

  console.log('== audit-AL1-skeleton 全部通过 ==');
}

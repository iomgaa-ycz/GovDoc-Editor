async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C4-pdf-doc';

  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');

  // 打开 picker
  await page.getByRole('button', { name: /从文件库添加|从文件库选择文件/ }).first().click();
  const modal = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' });
  await modal.waitFor({ timeout: 10000 });

  const items = modal.locator('.overflow-y-auto button.w-full');
  for (let retry = 0; retry < 20; retry++) {
    if (await items.count() > 0) break;
    await page.waitForTimeout(500);
  }

  // 列出所有文件
  var count = await items.count();
  for (var i = 0; i < count; i++) {
    var text = await items.nth(i).textContent();
    console.log('文件 ' + (i + 1) + ': ' + (text || '').trim().slice(0, 80));
  }

  // 找 "广东宏业" PDF 和 "四类" Word
  var pdfIdx = -1, wordIdx = -1;
  for (var j = 0; j < count; j++) {
    var t = (await items.nth(j).textContent()) || '';
    if (t.includes('广东宏业') && pdfIdx === -1) pdfIdx = j;
    if (t.includes('四类') && wordIdx === -1) wordIdx = j;
  }
  console.log('PDF(广东宏业) idx=' + pdfIdx + ', Word(四类) idx=' + wordIdx);

  if (pdfIdx === -1 || wordIdx === -1) {
    await page.screenshot({ path: SS + '-skip.png', fullPage: true });
    throw new Error('未找到目标文件: PDF=' + pdfIdx + ' Word=' + wordIdx);
  }

  // 选择
  await items.nth(pdfIdx).click();
  await page.waitForTimeout(200);
  await items.nth(wordIdx).click();
  await page.waitForTimeout(200);
  await page.screenshot({ path: SS + '-01-selected.png', fullPage: true });

  await modal.getByRole('button', { name: '确认选择' }).click();
  await page.waitForTimeout(500);

  // 开始对比
  var compareBtn = page.getByRole('button', { name: /开始对比/ });
  await compareBtn.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-02-submitting.png', fullPage: true });

  // 等待跳转
  await page.waitForURL(/\/compare\/[a-zA-Z0-9-]+/, { timeout: 30000 });
  console.log('已跳转: ' + page.url());

  // 等待完成（最长 30 分钟）
  var startTime = Date.now();
  var completed = false;
  var failed = false;
  var lastLog = 0;

  while (Date.now() - startTime < 1800000) {
    var result = page.getByText('文档对比结果').first();
    if (await result.isVisible().catch(function() { return false; })) { completed = true; break; }
    var fail = page.getByText('对比失败').first();
    if (await fail.isVisible().catch(function() { return false; })) { failed = true; break; }

    var elapsed = Date.now() - startTime;
    if (elapsed - lastLog > 60000) {
      var mins = Math.floor(elapsed / 60000);
      await page.screenshot({ path: SS + '-progress-' + mins + 'min.png', fullPage: true });
      console.log('... 等待中 (' + mins + ' 分钟)');
      lastLog = elapsed;
    }
    await page.waitForTimeout(5000);
  }

  var secs = Math.floor((Date.now() - startTime) / 1000);
  if (failed) {
    await page.screenshot({ path: SS + '-03-failed.png', fullPage: true });
    var errEl = page.locator('.bg-red-50').first();
    var errText = await errEl.textContent().catch(function() { return ''; });
    throw new Error('对比失败 (' + secs + 's): ' + (errText || '').slice(0, 200));
  }
  if (!completed) {
    await page.screenshot({ path: SS + '-03-timeout.png', fullPage: true });
    throw new Error('对比超时（30 分钟）');
  }

  await page.screenshot({ path: SS + '-03-completed.png', fullPage: true });
  console.log('PASS: PDF+大Word 对比完成 (' + secs + 's)');
  console.log('== compare-C4-pdf-doc 通过 ==');
}

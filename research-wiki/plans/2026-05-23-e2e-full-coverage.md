# E2E 测试全覆盖实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 E2E 测试覆盖，造数据做精确对比断言，增强 LLM 测试质量验证，加严现有测试。

**Architecture:** 用 python-docx 程序化生成 fixture DOCX（内容完全可控，真值已知），手工转 PDF。新增 test-14（精确对比验证）和 test-15（审核结果质量验证），增强 test-03/04/05/06/07 的断言。

**Tech Stack:** python-docx（造数据）、@playwright/cli（E2E）、LibreOffice CLI（DOCX→PDF 转换）

---

### Task 1: 生成对比 fixture DOCX 文件

**Files:**
- Create: `tests/fixtures/compare/gen_fixtures.py`
- Create: `tests/fixtures/compare/para_a.docx` (及其他 13 个 DOCX)

- [ ] **Step 1: 创建 fixture 生成脚本**

```python
"""生成对比 E2E 测试用的 fixture DOCX 文件。"""

from pathlib import Path
from docx import Document

OUT = Path(__file__).parent


def _write(name: str, paragraphs: list[str]) -> None:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(OUT / name)


def gen() -> None:
    # ① 段落级精确匹配
    _write("para_a.docx", [
        "投标人应具有独立承担民事责任的能力。",
        "文件A独有的第二段内容。",
    ])
    _write("para_b.docx", [
        "投标人应具有独立承担民事责任的能力。",
        "文件B独有的第二段内容。",
    ])

    # ② 句子级精确匹配
    _write("sent_a.docx", [
        "采购人可自行选择。供应商不得串通。评标委员会独立评审。",
    ])
    _write("sent_b.docx", [
        "采购人可自行选择。代理机构按规定。评标委员会独立评审。",
    ])

    # ③ 片段级连续匹配
    _write("seg_a.docx", [
        "甲方根据具有良好的商业信誉和健全的财务会计制度的要求执行。",
    ])
    _write("seg_b.docx", [
        "乙方应当具有良好的商业信誉和健全的财务会计制度并提交证明。",
    ])

    # ④ 三级混合
    _write("mix_a.docx", [
        "完全相同的第一段落。",
        "第一句共享。第二句不同A。第三句共享。",
        "前缀具有良好的商业信誉和健全的财务会计制度后缀A。",
        "独有段落A。",
    ])
    _write("mix_b.docx", [
        "完全相同的第一段落。",
        "第一句共享。第二句不同B。第三句共享。",
        "开头具有良好的商业信誉和健全的财务会计制度尾部B。",
        "独有段落B。",
    ])

    # ⑥ 无重复
    _write("unique_a.docx", ["甲方内容。"])
    _write("unique_b.docx", ["乙方内容。"])

    # ⑦ 多文档 N=4
    _write("multi_1.docx", [
        "四文件共享段落。",
        "仅12共享段落。",
        "仅1独有段落。",
    ])
    _write("multi_2.docx", [
        "四文件共享段落。",
        "仅12共享段落。",
        "仅2独有段落。",
    ])
    _write("multi_3.docx", [
        "四文件共享段落。",
        "仅34共享段落。",
        "仅3独有段落。",
    ])
    _write("multi_4.docx", [
        "四文件共享段落。",
        "仅34共享段落。",
        "仅4独有段落。",
    ])

    print(f"已生成 14 个 fixture DOCX 文件到 {OUT}")


if __name__ == "__main__":
    gen()
```

- [ ] **Step 2: 运行脚本生成文件**

```bash
source activate govdoc-auditor-v3 && python tests/fixtures/compare/gen_fixtures.py
```

Expected: 在 `tests/fixtures/compare/` 下生成 14 个 `.docx` 文件。

- [ ] **Step 3: 验证文件可被后端正确解析**

```bash
source activate govdoc-auditor-v3 && python -c "
from govdoc.compare.extractor import extract_docx_paragraphs
from pathlib import Path
root = Path('tests/fixtures/compare')
for f in sorted(root.glob('*.docx')):
    paras = extract_docx_paragraphs(f)
    print(f'{f.name}: {paras}')
"
```

Expected: 每个文件输出其段落列表，内容与脚本中写入的完全一致。

---

### Task 2: 将 fixture DOCX 转为 PDF

**Files:**
- Create: `tests/fixtures/compare/para_a.pdf`
- Create: `tests/fixtures/compare/para_b.pdf`

- [ ] **Step 1: 用 LibreOffice 转换**

```bash
cd tests/fixtures/compare
libreoffice --headless --convert-to pdf para_a.docx para_b.docx
```

如果没有 `libreoffice`，用 python：

```bash
source activate govdoc-auditor-v3 && pip install docx2pdf 2>/dev/null || true
# 或者手动用 WPS/Word 打开 para_a.docx 另存为 para_a.pdf
```

- [ ] **Step 2: 验证 PDF 文件存在**

```bash
ls -la tests/fixtures/compare/para_a.pdf tests/fixtures/compare/para_b.pdf
```

Expected: 两个 PDF 文件存在，大小 > 0。

---

### Task 3: 重写 test-14-compare-verify.js

**Files:**
- Rewrite: `frontend/e2e/test-14-pdf-compare-verify.js` → rename to `frontend/e2e/test-14-compare-verify.js`

- [ ] **Step 1: 删除旧文件，创建新文件**

删除 `frontend/e2e/test-14-pdf-compare-verify.js`，创建 `frontend/e2e/test-14-compare-verify.js`：

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const FIX = '/home/iomgaa/Projects/GovDoc_Editor/tests/fixtures/compare';
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // 辅助函数：上传文件 → 对比 → 返回指标
  async function compareAndGetMetrics(files, label) {
    await page.goto(BASE + '/compare');
    await page.waitForLoadState('domcontentloaded');
    const fileInput = page.locator("input[type='file']");
    await fileInput.setInputFiles(files);
    await page.waitForTimeout(500);
    const compareBtn = page.getByRole('button', { name: /开始对比/ });
    await compareBtn.click();
    const metric = page.getByText('匹配总数');
    await metric.waitFor({ timeout: 180000 });
    await page.screenshot({ path: 'e2e/screenshots/14-' + label + '.png', fullPage: true });

    // 提取 4 个指标值
    const getText = async (labelText) => {
      const el = page.getByText(labelText).first();
      const parent = el.locator('..');
      const valueEl = parent.locator('.text-2xl, .text-3xl').first();
      return parseInt((await valueEl.textContent() || '0').trim(), 10);
    };
    const matchCount = await getText('匹配总数');
    const paragraphCount = await getText('相同段落');
    const sentenceCount = await getText('相同句子');
    const segmentCount = await getText('公共片段');
    return { matchCount, paragraphCount, sentenceCount, segmentCount };
  }

  // 辅助函数：获取匹配清单中的匹配文本列表
  async function getMatchTexts() {
    const items = page.locator('button.w-full.border-b p.line-clamp-2');
    const count = await items.count();
    const texts = [];
    for (let i = 0; i < count; i++) {
      texts.push((await items.nth(i).textContent() || '').trim());
    }
    return texts;
  }

  // 辅助函数：获取匹配清单中每项的 fileIndices 信息
  async function getMatchFileInfo() {
    const items = page.locator('button.w-full.border-b');
    const count = await items.count();
    const infos = [];
    for (let i = 0; i < count; i++) {
      const fileText = await items.nth(i).locator('p.text-xs').last().textContent() || '';
      infos.push(fileText.trim());
    }
    return infos;
  }

  // ═══════════════════════════════════════════════════
  // 用例①：段落级精确匹配
  // ═══════════════════════════════════════════════════
  console.log('== 用例①: 段落级精确匹配 ==');
  const m1 = await compareAndGetMetrics(
    [FIX + '/para_a.docx', FIX + '/para_b.docx'], 'para');
  if (m1.paragraphCount !== 1) throw new Error('①段落数应为1，实际: ' + m1.paragraphCount);
  if (m1.sentenceCount !== 0) throw new Error('①句子数应为0，实际: ' + m1.sentenceCount);
  if (m1.matchCount !== 1) throw new Error('①匹配总数应为1，实际: ' + m1.matchCount);
  const texts1 = await getMatchTexts();
  if (!texts1.some(t => t.includes('投标人应具有独立承担民事责任的能力'))) {
    throw new Error('①匹配文本缺少预期段落');
  }
  console.log('PASS: 段落级 — paragraphCount=1, sentenceCount=0, matchCount=1');

  // ═══════════════════════════════════════════════════
  // 用例②：句子级精确匹配
  // ═══════════════════════════════════════════════════
  console.log('== 用例②: 句子级精确匹配 ==');
  const m2 = await compareAndGetMetrics(
    [FIX + '/sent_a.docx', FIX + '/sent_b.docx'], 'sent');
  if (m2.paragraphCount !== 0) throw new Error('②段落数应为0，实际: ' + m2.paragraphCount);
  if (m2.sentenceCount !== 2) throw new Error('②句子数应为2，实际: ' + m2.sentenceCount);
  if (m2.matchCount !== 2) throw new Error('②匹配总数应为2，实际: ' + m2.matchCount);
  const texts2 = await getMatchTexts();
  if (!texts2.some(t => t.includes('采购人可自行选择'))) throw new Error('②缺少句子匹配: 采购人');
  if (!texts2.some(t => t.includes('评标委员会独立评审'))) throw new Error('②缺少句子匹配: 评标委员会');
  console.log('PASS: 句子级 — paragraphCount=0, sentenceCount=2, matchCount=2');

  // ═══════════════════════════════════════════════════
  // 用例③：片段级连续匹配
  // ═══════════════════════════════════════════════════
  console.log('== 用例③: 片段级连续匹配 ==');
  const m3 = await compareAndGetMetrics(
    [FIX + '/seg_a.docx', FIX + '/seg_b.docx'], 'seg');
  if (m3.paragraphCount !== 0) throw new Error('③段落数应为0，实际: ' + m3.paragraphCount);
  if (m3.sentenceCount !== 0) throw new Error('③句子数应为0，实际: ' + m3.sentenceCount);
  if (m3.segmentCount < 1) throw new Error('③片段数应≥1，实际: ' + m3.segmentCount);
  const texts3 = await getMatchTexts();
  if (!texts3.some(t => t.includes('具有良好的商业信誉'))) {
    throw new Error('③匹配文本缺少预期片段');
  }
  console.log('PASS: 片段级 — paragraphCount=0, sentenceCount=0, segmentCount≥1');

  // ═══════════════════════════════════════════════════
  // 用例④：三级混合
  // ═══════════════════════════════════════════════════
  console.log('== 用例④: 三级混合 ==');
  const m4 = await compareAndGetMetrics(
    [FIX + '/mix_a.docx', FIX + '/mix_b.docx'], 'mix');
  if (m4.paragraphCount !== 1) throw new Error('④段落数应为1，实际: ' + m4.paragraphCount);
  if (m4.sentenceCount !== 2) throw new Error('④句子数应为2，实际: ' + m4.sentenceCount);
  if (m4.segmentCount < 1) throw new Error('④片段数应≥1，实际: ' + m4.segmentCount);
  if (m4.matchCount < 4) throw new Error('④匹配总数应≥4，实际: ' + m4.matchCount);
  console.log('PASS: 三级混合 — paragraphCount=1, sentenceCount=2, segmentCount≥1, matchCount≥4');

  // ═══════════════════════════════════════════════════
  // 用例⑤：自比较
  // ═══════════════════════════════════════════════════
  console.log('== 用例⑤: 自比较 ==');
  const m5 = await compareAndGetMetrics(
    [FIX + '/para_a.docx', FIX + '/para_a.docx'], 'self');
  if (m5.paragraphCount !== 2) throw new Error('⑤自比较段落数应为2，实际: ' + m5.paragraphCount);
  console.log('PASS: 自比较 — paragraphCount=2');

  // ═══════════════════════════════════════════════════
  // 用例⑥：无重复
  // ═══════════════════════════════════════════════════
  console.log('== 用例⑥: 无重复 ==');
  const m6 = await compareAndGetMetrics(
    [FIX + '/unique_a.docx', FIX + '/unique_b.docx'], 'unique');
  if (m6.matchCount !== 0) throw new Error('⑥无重复匹配总数应为0，实际: ' + m6.matchCount);
  console.log('PASS: 无重复 — matchCount=0');

  // ═══════════════════════════════════════════════════
  // 用例⑦：多文档 N=4
  // ═══════════════════════════════════════════════════
  console.log('== 用例⑦: 多文档 N=4 ==');
  const m7 = await compareAndGetMetrics([
    FIX + '/multi_1.docx', FIX + '/multi_2.docx',
    FIX + '/multi_3.docx', FIX + '/multi_4.docx',
  ], 'multi');
  if (m7.paragraphCount !== 3) throw new Error('⑦段落数应为3，实际: ' + m7.paragraphCount);
  // 验证 fileIndices：四文件共享 → "文件 1、文件 2、文件 3、文件 4"
  const fileInfos = await getMatchFileInfo();
  const has4file = fileInfos.some(t => t.includes('文件 1') && t.includes('文件 4'));
  if (!has4file) throw new Error('⑦缺少四文件共享的匹配项');
  const has2file = fileInfos.some(t => t.includes('文件 1') && t.includes('文件 2') && !t.includes('文件 3'));
  if (!has2file) throw new Error('⑦缺少仅12共享的匹配项');
  console.log('PASS: 多文档 — paragraphCount=3, fileIndices 正确');

  // ═══════════════════════════════════════════════════
  // 用例⑧：PDF 对比（真值与 DOCX 相同）
  // ═══════════════════════════════════════════════════
  console.log('== 用例⑧: PDF 对比 ==');
  const m8 = await compareAndGetMetrics(
    [FIX + '/para_a.pdf', FIX + '/para_b.pdf'], 'pdf');
  if (m8.paragraphCount !== 1) throw new Error('⑧PDF段落数应为1，实际: ' + m8.paragraphCount);
  if (m8.matchCount !== 1) throw new Error('⑧PDF匹配总数应为1，实际: ' + m8.matchCount);
  const texts8 = await getMatchTexts();
  if (!texts8.some(t => t.includes('投标人应具有独立承担民事责任的能力'))) {
    throw new Error('⑧PDF匹配文本缺少预期段落');
  }
  console.log('PASS: PDF — paragraphCount=1, matchCount=1, 文本正确');

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-14-compare-verify 全部通过 ==');
}
```

- [ ] **Step 2: 确认文件已替换旧版本**

```bash
ls frontend/e2e/test-14-*.js
```

Expected: 只有 `test-14-compare-verify.js`，旧的 `test-14-pdf-compare-verify.js` 已删除。

---

### Task 4: 新增 test-15-result-quality.js

**Files:**
- Create: `frontend/e2e/test-15-result-quality.js`

- [ ] **Step 1: 创建测试文件**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  const VALID_VERDICTS = ['合规', '不合规', '存疑'];

  // ═══════════════════════════════════════════════════
  // Part A: 审核结果质量验证
  // ═══════════════════════════════════════════════════
  console.log('== Part A: 审核结果质量验证 ==');

  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  const firstRow = page.locator('table tbody tr').first();
  await firstRow.waitFor({ timeout: 15000 });

  // 从 Dashboard 找一个有审核结果的项目
  const arrowButtons = page.locator('table tbody tr td:last-child button');
  let firstEnabled = -1;
  for (let i = 0; i < await arrowButtons.count(); i++) {
    if (!(await arrowButtons.nth(i).isDisabled())) { firstEnabled = i; break; }
  }
  if (firstEnabled === -1) throw new Error('无可查看的审核运行');
  await arrowButtons.nth(firstEnabled).click();
  await page.waitForURL('**/audit-results', { timeout: 10000 });

  await page.waitForTimeout(3000);
  const leftPanel = page.locator('.w-80').first();
  const pointButtons = leftPanel.locator('button');
  const pointCount = await pointButtons.count();
  if (pointCount === 0) throw new Error('左侧审核要点列表为空');

  let verifiedCount = 0;
  for (let i = 0; i < pointCount; i++) {
    await pointButtons.nth(i).click();
    await page.waitForTimeout(1000);

    // 检查是否有 verdict
    const hasVerdict = await page.getByText('审核结论').isVisible().catch(() => false);
    if (!hasVerdict) continue;

    // 验证 verdict 值
    const verdictPanel = page.locator('.rounded-card.border.p-4').first();
    const verdictText = (await verdictPanel.textContent() || '');
    const foundVerdict = VALID_VERDICTS.find(v => verdictText.includes(v));
    if (!foundVerdict) throw new Error('审核点 ' + i + ' verdict 不在有效值中: ' + verdictText.slice(0, 50));

    // 验证审查意见
    const rationaleTitle = page.getByText('审查意见');
    if (!(await rationaleTitle.isVisible().catch(() => false))) throw new Error('审核点 ' + i + ' 缺少审查意见');
    const rationaleBlock = rationaleTitle.locator('..').locator('p').first();
    const rationaleText = (await rationaleBlock.textContent() || '').trim();
    if (rationaleText.length <= 20) throw new Error('审核点 ' + i + ' 审查意见过短(' + rationaleText.length + '字): ' + rationaleText);

    // 验证整改建议
    const suggestionTitle = page.getByText('整改建议');
    if (!(await suggestionTitle.isVisible().catch(() => false))) throw new Error('审核点 ' + i + ' 缺少整改建议');
    const suggestionBlock = suggestionTitle.locator('..').locator('p').first();
    const suggestionText = (await suggestionBlock.textContent() || '').trim();
    if (suggestionText.length <= 10) throw new Error('审核点 ' + i + ' 整改建议过短(' + suggestionText.length + '字): ' + suggestionText);

    // 验证原文引用（不合规/存疑时必须有）
    if (foundVerdict === '不合规' || foundVerdict === '存疑') {
      const evidenceTitle = page.getByText('原文引用');
      if (!(await evidenceTitle.isVisible().catch(() => false))) {
        throw new Error('审核点 ' + i + ' verdict=' + foundVerdict + ' 但缺少原文引用');
      }
    }

    verifiedCount++;
    console.log('PASS: 审核点 ' + i + ' — verdict=' + foundVerdict + ', rationale=' + rationaleText.length + '字, suggestion=' + suggestionText.length + '字');
  }
  if (verifiedCount === 0) throw new Error('没有任何 completed 的审核点可验证');
  console.log('Part A 完成: 验证 ' + verifiedCount + ' 个审核点质量');

  // ═══════════════════════════════════════════════════
  // Part B: 工作底稿质量验证
  // ═══════════════════════════════════════════════════
  console.log('');
  console.log('== Part B: 工作底稿质量验证 ==');

  await page.goto(BASE + '/workpaper');
  await page.waitForLoadState('networkidle');

  const emptyState = page.getByText('暂无工作底稿');
  if (await emptyState.isVisible().catch(() => false)) {
    console.log('SKIP: 无工作底稿数据');
  } else {
    // 等待编辑器加载
    const editor = page.locator('[contenteditable="true"]');
    await editor.waitFor({ timeout: 10000 }).catch(() => {});

    if (await editor.isVisible().catch(() => false)) {
      const html = await editor.innerHTML();
      if (html.length < 50) throw new Error('工作底稿 HTML 内容过短: ' + html.length + '字符');

      const keywords = ['审查', '意见', '建议'];
      const foundKw = keywords.filter(kw => html.includes(kw));
      if (foundKw.length === 0) {
        console.log('WARN: 工作底稿 HTML 未包含关键词 (审查/意见/建议)，可能内容异常');
      } else {
        console.log('PASS: 底稿含关键词: ' + foundKw.join(', '));
      }

      // 验证 findings 数量
      const findingsLabel = page.getByText('发现数量');
      if (await findingsLabel.isVisible().catch(() => false)) {
        const findingsRow = findingsLabel.locator('..');
        const findingsText = (await findingsRow.textContent() || '');
        const findingsMatch = findingsText.match(/(\d+)\s*条/);
        if (findingsMatch) {
          const count = parseInt(findingsMatch[1], 10);
          if (count < 1) throw new Error('findings 数量为 0');
          console.log('PASS: findings = ' + count + ' 条');
        }
      }
    } else {
      console.log('SKIP: 编辑器不可见，未加载工作底稿');
    }
  }

  await page.screenshot({ path: 'e2e/screenshots/15-result-quality.png', fullPage: true });

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-15-result-quality 全部通过 ==');
}
```

---

### Task 5: 增强 test-04 尾部质量断言

**Files:**
- Modify: `frontend/e2e/test-04-ai-extract.js`

- [ ] **Step 1: 在 test-04 末尾（Step 7 之后）追加质量验证**

在 `console.log('Step 7: 列表中有 ' + count + ' 条审核点');` 之后、最终 `console.log('== test-04')` 之前，插入：

```javascript
  // Step 8: 验证提取出的审核点质量
  console.log('Step 8: 验证审核点内容质量');
  let qualityChecked = 0;
  for (let i = 0; i < Math.min(count, 5); i++) {
    const row = rows.nth(i);
    const titleEl = row.locator('p.font-medium').first();
    const titleText = (await titleEl.textContent() || '').trim();
    if (titleText.length <= 2) throw new Error('审核点 ' + i + ' 标题过短: ' + titleText);

    const descEl = row.locator('p.text-xs').first();
    const descText = (await descEl.textContent() || '').trim();
    if (descText.length <= 10) throw new Error('审核点 ' + i + ' 描述过短: ' + descText);

    const categoryBadge = row.locator('td').nth(1).textContent();
    if (!(await categoryBadge)) throw new Error('审核点 ' + i + ' 缺少分类');

    const severityBadge = row.locator('td').nth(2).textContent();
    const sevText = (await severityBadge || '').trim();
    const validSeverities = ['严重', '重要', '一般'];
    if (!validSeverities.some(s => sevText.includes(s))) {
      throw new Error('审核点 ' + i + ' 严重程度异常: ' + sevText);
    }
    qualityChecked++;
  }
  console.log('Step 8: 验证 ' + qualityChecked + ' 个审核点质量通过');
```

---

### Task 6: 增强 test-05 尾部质量断言

**Files:**
- Modify: `frontend/e2e/test-05-ai-audit.js`

- [ ] **Step 1: 在 test-05 末尾（Step 8 之前）追加质量验证**

在 `console.log('Step 7: 至少一个审核点已完成');` 之后插入：

```javascript
  // Step 8: 验证已完成审核点的结果质量
  console.log('Step 8: 验证审核结论质量');
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
    if (!foundVerdict) throw new Error('审核点 ' + i + ' verdict 无效: ' + verdictText.slice(0, 50));

    const rationale = page.getByText('审查意见').locator('..').locator('p').first();
    const rText = (await rationale.textContent().catch(() => '') || '').trim();
    if (rText.length <= 20) throw new Error('审核点 ' + i + ' 审查意见过短: ' + rText.length);

    const suggestion = page.getByText('整改建议').locator('..').locator('p').first();
    const sText = (await suggestion.textContent().catch(() => '') || '').trim();
    if (sText.length <= 10) throw new Error('审核点 ' + i + ' 整改建议过短: ' + sText.length);

    qualityVerified++;
    console.log('Step 8: 审核点 ' + i + ' — verdict=' + foundVerdict + ', ok');
  }
  if (qualityVerified === 0) console.log('Step 8: WARN — 无 completed 审核点可验证质量');
  else console.log('Step 8: 验证 ' + qualityVerified + ' 个审核点质量通过');
```

然后将原来的 Step 8 截图改为 Step 9。

---

### Task 7: 增强 test-06 尾部质量断言

**Files:**
- Modify: `frontend/e2e/test-06-ai-audit-multifile.js`

- [ ] **Step 1: test-06 当前在 Step 11 上传完成后就结束了，没有启动审核。追加启动审核 + 等待 + 质量验证**

在 `console.log('Step 11: 上传完成');` 之后插入：

```javascript
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

  // Step 14: 验证质量（同 test-05 Step 8 逻辑）
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
```

然后将原来的 Step 12 截图改为 Step 15。

---

### Task 8: 加严 test-03 断言

**Files:**
- Modify: `frontend/e2e/test-03-doc-compare.js`

- [ ] **Step 1: 在 Step 7 之后追加严格断言**

在 `console.log('Step 7: 多文件栏存在');` 之后、最终 `console.log('== test-03')` 之前插入：

```javascript
  // Step 8: 验证指标卡数值非空
  const metricLabels = ['匹配总数', '相同段落', '相同句子', '公共片段'];
  for (const label of metricLabels) {
    const el = page.getByText(label).first();
    const parent = el.locator('..');
    const valueEl = parent.locator('.text-2xl, .text-3xl').first();
    const val = (await valueEl.textContent() || '').trim();
    if (!val || val === '') throw new Error('指标卡 "' + label + '" 数值为空');
  }
  console.log('Step 8: 4 个指标卡数值非空');

  // Step 9: 验证匹配清单至少 1 项
  const matchItems = page.locator('button.w-full.border-b');
  const matchItemCount = await matchItems.count();
  if (matchItemCount < 1) throw new Error('匹配清单为空');
  console.log('Step 9: 匹配清单有 ' + matchItemCount + ' 项');

  // Step 10: 验证匹配文本含中文
  const chineseRegex = /[一-鿿]/;
  let hasChinese = false;
  for (let i = 0; i < Math.min(matchItemCount, 3); i++) {
    const text = (await matchItems.nth(i).textContent() || '');
    if (chineseRegex.test(text)) { hasChinese = true; break; }
  }
  if (!hasChinese) throw new Error('匹配文本中未检测到中文');
  console.log('Step 10: 匹配文本含中文字符');
```

---

### Task 9: 加严 test-07 断言

**Files:**
- Modify: `frontend/e2e/test-07-audit-results-history.js`

- [ ] **Step 1: 在 Step 4（验证 point_runs 加载后）追加 PointInsight 验证**

在 `console.log('Step 4: 左侧已加载 ' + pointButtonCount + ' 个审核点');` 之后插入：

```javascript
  // Step 4b: 点击审核点验证右侧 PointInsight 显示
  console.log('Step 4b: 点击审核点验证 PointInsight');
  await pointButtons.first().click();
  await page.waitForTimeout(1500);
  const hasVerdict = await page.getByText('审核结论').isVisible().catch(() => false);
  const hasStatus = await page.getByText('审核状态').isVisible().catch(() => false);
  if (!hasVerdict && !hasStatus) throw new Error('点击审核点后右侧未显示 PointInsight');
  console.log('Step 4b: PointInsight 显示正确（' + (hasVerdict ? '有结论' : '有状态') + '）');
```

---

### Task 10: 更新 run-tests.sh

**Files:**
- Modify: `frontend/e2e/run-tests.sh`

- [ ] **Step 1: 更新 ALL_TESTS 和 QUICK_TESTS 数组**

将第 42-43 行替换为：

```bash
ALL_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "04-ai-extract" "05-ai-audit" "06-ai-audit-multifile" "07-audit-results-history" "08-dashboard-details" "09-audit-library-crud" "10-ai-review-workflow" "11-audit-results-interactions" "12-workpaper-page" "13-doc-compare-advanced" "14-compare-verify" "15-result-quality")
QUICK_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "08-dashboard-details" "09-audit-library-crud" "10-ai-review-workflow" "11-audit-results-interactions" "12-workpaper-page" "13-doc-compare-advanced" "15-result-quality")
```

- [ ] **Step 2: 更新注释**

将第 7 行改为：
```bash
#   bash frontend/e2e/run-tests.sh                    # 运行全部 15 个测试（含 LLM）
#   bash frontend/e2e/run-tests.sh --quick            # 仅运行非 LLM 测试（01-03, 08-13, 15）
```

---

### Task 11: 运行全部 E2E 测试并报告

**Files:** 无文件变更，纯验证。

- [ ] **Step 1: 运行全部 quick 模式 E2E 测试**

```bash
bash frontend/e2e/run-tests.sh --quick
```

Expected: 所有 quick 测试通过。如有失败，**不直接修改代码**，以报告形式阐述：
- 哪个测试失败
- 失败的 step 和错误信息
- 截图路径
- 可能的根因分析

- [ ] **Step 2: 运行 test-14（精确对比验证，需要后端）**

```bash
bash frontend/e2e/run-tests.sh --only 14-compare-verify
```

Expected: 全部 8 个用例通过。

- [ ] **Step 3: 汇总测试报告**

输出格式：
```
========================================
E2E 测试报告
========================================
总计: X 个测试
通过: Y 个
失败: Z 个

失败详情:
  - test-XX-name: [错误信息]
    根因: [分析]
    截图: e2e/screenshots/FAIL-XX-name.png
========================================
```

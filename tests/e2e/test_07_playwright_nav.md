# Playwright E2E: 导航 + 审核点库

## 环境

- 前端地址: http://100.83.164.94:5174
- 浏览器: Chromium

## P01: 首页加载

1. 打开 http://100.83.164.94:5174/
2. 等待页面加载完成
3. 验证: 文本 "政务智能审查工作台" 可见
4. 验证: 两个 entry-card 存在（"创建审核点库" 和 "AI审核"）
5. 截图: `reports/p01_homepage.png`

## P02: 导航到审核点库

1. 点击 "创建审核点库" 卡片（链接到 /audit-library）
2. 等待 URL 变为 /audit-library
3. 验证: 页面正常加载，无白屏
4. 截图: `reports/p02_audit_library.png`

## P03: 导航到 AI 审核

1. 点击侧边栏 "AI审核" 导航项（或返回首页点击 "AI审核" 卡片）
2. 等待 URL 变为 /ai-review
3. 验证: "项目审核" 标题可见
4. 截图: `reports/p03_ai_review.png`

## P04: 侧边栏全页面遍历

1. 依次点击侧边栏：首页 → 审核点库 → AI审核 → 审核结果 → 文档对比
2. 每个页面验证: 无 404 / 无白屏 / 无 console error
3. 截图: 每个页面一张 `reports/p04_nav_{name}.png`

## P05: 审核点库 — 查看列表

1. 打开 /audit-library
2. 等待审核点列表加载
3. 验证: 终审/草稿计数卡片存在
4. 截图: `reports/p05_checkpoint_list.png`

## P06: 审核点库 — 批量导入 XLS

1. 在审核点库页面找到导入功能
2. 上传文件: tests/e2e/data/附件9 处理处罚标准.xls
3. 等待导入完成
4. 验证: 显示导入成功数量
5. 截图: `reports/p06_import_result.png`

## P07: 审核点库 — 上传法规提取

1. 找到上传法规的表单
2. 填写标题: "E2E-专项整治指引"
3. 上传文件: tests/e2e/data/2025年政府采购领域"四类"违法违规行为专项整治工作指引.docx
4. 点击提交
5. 等待状态变化（pending → running → draft_ready）
6. 验证: 草稿审核点出现在列表中
7. 截图: `reports/p07_extract_result.png`
（注: 此步骤涉及 LLM，可能需要等待 1-5 分钟）

## P08: 审核点库 — 编辑审核点

1. 找到列表中某个审核点
2. 点击编辑图标/按钮
3. 修改标题为 "E2E 编辑测试"
4. 点击保存
5. 验证: Modal 关闭，列表中标题已更新
6. 截图: `reports/p08_edit_checkpoint.png`

## P09: 审核点库 — 删除审核点

1. 找到列表中某个审核点（非关键数据）
2. 点击删除图标/按钮
3. 确认删除
4. 验证: 审核点从列表消失
5. 截图: `reports/p09_delete_checkpoint.png`

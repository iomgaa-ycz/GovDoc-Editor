# Playwright E2E: AI 审核完整流程

## 环境

- 前端地址: http://100.83.164.94:5174
- 后端地址: http://100.83.164.94:8001
- 浏览器: Chromium
- 前置: 审核点库中已有 final 审核点（由 P06 / P07 产生）

## P10: 创建新项目

1. 打开 /ai-review
2. 在"新项目名称"输入框填入 "E2E浏览器测试项目"
3. 点击"新建"按钮
4. 等待创建完成
5. 验证: 项目下拉框出现新项目，被自动选中
6. 截图: `reports/p10_new_project.png`

## P11: 上传主文书（DOCX）

1. 在"上传主招标文书"区域
2. 上传文件: tests/e2e/data/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx
3. 验证: file-chip 显示文件名和大小
4. 截图: `reports/p11_main_doc_selected.png`

## P12: 上传补充文件

1. 在"上传补充文件"区域
2. 上传文件: tests/e2e/data/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf
3. 验证: 补充文件列表显示文件名
4. 截图: `reports/p12_supp_file_selected.png`

## P13: 上传文书到服务器

1. 点击"上传文书"按钮
2. 等待上传完成
3. 验证: InlineNotice(success) 显示 "文书已上传: ..."
4. 验证: 如有 warning（PDF 降级），应显示 InlineNotice(warning)
5. 截图: `reports/p13_upload_complete.png`

## P14: 上传错误反馈

1. 新建另一个项目
2. 尝试上传一个损坏/不支持的文件
3. 验证: InlineNotice(error) 显示错误信息，页面不崩溃
4. 截图: `reports/p14_upload_error.png`

## P15: 选择审核点

1. 等待 CheckpointPicker 出现（mainDoc 上传后 + 无 auditProgress 时显示）
2. 勾选所有可用审核点
3. 验证: "启动审核 (N 个审核点)" 按钮变为可用，N 匹配选中数
4. 截图: `reports/p15_checkpoints_selected.png`

## P16: 启动审核（完整流程）

1. 点击"启动审核"按钮
2. 验证: AuditProgressPanel 出现在中/右列
3. 观察进度条从 0% 开始增长
4. 每 10 秒截图: `reports/p16_progress_{n}.png`
5. 等待状态变为 draft_ready / partial_ready（最长 10 分钟）
6. 验证: 审核点列表中至少有一个 completed
7. 最终截图: `reports/p16_audit_complete.png`

## P17: 查看审核点详情弹窗

1. 点击已完成（completed）的审核点行
2. 验证: Modal 弹出，标题为"审核点详情"
3. 验证: PointInsight 组件显示 verdict / evidence / legal_basis
4. 截图: `reports/p17_point_detail.png`
5. 关闭 Modal

## P18: failed 审核点样式

1. 如有 failed 状态审核点
2. 验证: 该行显示 failed 样式（红色背景 / 错误图标）
3. 截图: `reports/p18_failed_style.png`

## P19: uncertain 状态展示

1. 如有 uncertain/存疑 状态审核点
2. 验证: 显示独立的存疑标签样式
3. 截图: `reports/p19_uncertain_style.png`

## P20: 重试失败审核点

1. 如有 failed 审核点
2. 点击该行的"重试"按钮
3. 验证: 状态重置为 pending → 重新执行
4. 等待完成
5. 截图: `reports/p20_retry_result.png`

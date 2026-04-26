# Playwright E2E: 文档对比 + 审核结果

## 环境

- 前端地址: http://100.83.164.94:5174
- 浏览器: Chromium

## P21-P26: 文档对比页面

### P21: 上传两个文档

1. 打开 /compare
2. 验证: 两侧 FileDropzone 可见
3. 上传文档 A: tests/e2e/data/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx
4. 上传文档 B: tests/e2e/data/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx（同文件自对比）
5. 验证: 两侧显示文件名和大小
6. 截图: `reports/p21_files_uploaded.png`

### P22: 执行对比

1. 点击对比按钮
2. 等待对比完成
3. 验证: 匹配指标区域出现（MetricCard 显示 match_count 等）
4. 截图: `reports/p22_compare_result.png`

### P23: 双栏对比视图

1. 查看对比结果
2. 验证: 左右两栏显示段落，匹配文本高亮
3. 验证: 段落有序号索引
4. 截图: `reports/p23_dual_view.png`

### P24: 分类筛选

1. 依次切换 toggle: paragraph → sentence → segment
2. 每次切换后验证: 高亮内容变化，匹配数对应分类计数
3. 截图: `reports/p24_filter_paragraph.png`, `reports/p24_filter_sentence.png`, `reports/p24_filter_segment.png`

### P25: 匹配列表交互

1. 点击右侧匹配列表中的某项
2. 验证: 左右文档滚动到对应位置
3. 验证: 对应匹配文本被突出显示
4. 截图: `reports/p25_match_click.png`

### P26: 下载高亮文档

1. 点击"下载文档 A"按钮
2. 验证: 浏览器触发下载，文件扩展名为 .docx
3. 点击"下载文档 B"按钮
4. 验证: 同上
5. 截图: `reports/p26_download.png`

## P27-P29: 审核结果页面

### P27: 选择审核运行

1. 打开 /audit-results
2. 在下拉框中选择已完成的审核运行
3. 验证: 左栏显示该运行的审核点列表
4. 截图: `reports/p27_select_run.png`

### P28: 查看审核点详情

1. 点击某个审核点
2. 验证: 中栏 PointInsight 显示完整信息（标题、类别、严重程度、verdict、evidence、legal_basis）
3. 截图: `reports/p28_point_insight.png`

### P29: 状态徽章展示

1. 观察审核点列表
2. 验证: passed 显示绿色徽章，failed 显示红色，uncertain 显示黄色
3. 截图: `reports/p29_status_badges.png`

## P30-P32: 工作底稿（如可达）

### P30: 加载工作底稿

1. 从审核结果页或直接打开 /workpaper（需 audit_run_id 参数）
2. 验证: HTML 工作底稿正常渲染
3. 截图: `reports/p30_workpaper_loaded.png`

### P31: 编辑工作底稿

1. 在编辑器中修改内容
2. 触发保存（自动保存或手动保存）
3. 验证: 版本号递增
4. 截图: `reports/p31_workpaper_edited.png`

### P32: 定稿下载

1. 点击定稿按钮
2. 等待定稿完成
3. 点击下载 DOCX
4. 验证: 浏览器触发文件下载
5. 截图: `reports/p32_workpaper_download.png`

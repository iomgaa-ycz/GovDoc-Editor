# E2E 测试报告：文件审核

## 测试时间
2026-04-20 04:20-04:45 UTC

## 前端交互流程测试

### 创建项目
- 状态: 成功
- 项目名: "E2E测试-审核流程"（子代理创建）
- API: `POST /api/v1/projects` → 201 Created

### 上传招标文件
- 状态: **失败 (500)**
- API: `POST /api/v1/projects/{id}/tender-doc` → 500 Internal Server Error
- 根因: 文档转换服务 `100.81.95.44:7861` 未运行，`ConnectionRefusedError`
- 影响: PDF→Markdown 转换依赖外部 Tika/markitdown 服务

### 选择审核点
- 状态: 未达到（依赖上传成功）
- 注: 子代理发现数据库中有上一轮遗留的审核运行 `cd226931`

### 审核进度（遗留运行 cd226931）
- 状态: **stale running**（PES 进程已随服务器重启丢失）
- 5 个审核点: 1 running（永远不会完成）, 4 pending
- 审核点内容:
  - "2.限定供应商所在行业或限制其他行业供应商参与竞争。" — running（stale）
  - "3.设置对企业规模的不合理限制以排斥中小企业。" — pending
  - "1.直接或变相对外地企业进入本地市场设置阻碍。" — pending (x2)
  - "2.限定供应商所在行业或限制其他行业供应商参与竞争。" — pending

## 发现的问题

| 优先级 | 问题 | 说明 |
|--------|------|------|
| P0 | 文档转换服务未运行 | `100.81.95.44:7861` ConnectionRefused，阻塞所有 PDF/DOC 上传 |
| P1 | 审核运行无重启恢复 | 服务器重启后 in-flight 审核永远卡在 running，无超时或清理机制 |
| P1 | 上传 500 无前端提示 | 后端返回 500 后前端无 toast/弹窗，用户无法感知 |

## 截图
- `tests/e2e/reports/audit_running.png` — 审核进度页面
- `tests/e2e/reports/audit_stale_running.png` — 遗留审核卡住状态

## 最终结论
- 前端交互流程（创建项目）: 通过
- 文件上传: 失败（外部依赖）
- 审核端到端: 未测到（被上传阻塞）
- 需先启动文档转换服务才能完整测试

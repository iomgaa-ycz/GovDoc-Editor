# Research Wiki 索引

> 自动生成，请勿手动编辑。

## Plans (7)

- [审查点表格导入实施计划](plans/checkpoint-import-plan.md) — 文件导入管道模式（XLS/XLSX/CSV）
- [前端契约测试基础设施计划](plans/frontend-contract-tests.md) — vitest + MSW 前端测试基础
- [CI/CD Docker 部署计划](plans/cicd-deploy.md) — 双轨部署拓扑（testing/stable）
- [CI/CD 密钥管理计划](plans/cicd-secrets.md) — GitHub Actions 密钥注入策略
- [Alembic 统一数据库初始化计划](plans/alembic-unify.md) — DB schema 单一来源方案
- [E2E 测试清单](plans/e2e-test-checklist.md) — API + Playwright 端到端测试用例
- [多文件审核功能实施计划](plans/multi-file-audit.md) — 多附件审核建模与 API 扩展

## Designs (3)

- [审查点表格导入设计](designs/checkpoint-import-design.md) — 列映射与解析器设计
- [技术债务清理设计](designs/tech-debt-cleanup-design.md) — P0-P2 重构不变量与验收标准
- [CI/CD 部署架构设计](designs/cicd-design.md) — Docker + nginx + GitHub Actions 架构

## Findings (2)

- [Graphify 缺失边分析](findings/graphify-missing-edges.md) — 代码图工具盲点（JSX/默认值/字符串导入）
- [多文件审核调查报告](findings/multi-file-audit-investigation.md) — 补充文件利用不足的根因与修复方向

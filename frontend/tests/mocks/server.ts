// 占位文件：Task 3 提交时会替换为正式 MSW server 装配。
// 留一个最小可解析的 stub，避免 Task 2 commit 期间 setup.ts 解析失败。
import { setupServer } from "msw/node";

export const server = setupServer();

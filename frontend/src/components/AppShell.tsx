import {
  Bot,
  Files,
  GitCompareArrows,
  LayoutDashboard,
  LibraryBig,
  ScrollText,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useWorkbench } from "../context/V3WorkbenchContext";

const navItems = [
  { to: "/", label: "首页入口", icon: LayoutDashboard },
  { to: "/audit-library", label: "审核点库", icon: LibraryBig },
  { to: "/ai-review", label: "AI批量审核", icon: Bot },
  { to: "/workpaper", label: "结果与工作底稿", icon: Files },
  { to: "/audit-results", label: "审核点结果", icon: ScrollText },
  { to: "/compare", label: "文档对比", icon: GitCompareArrows },
];

export function AppShell() {
  const { apiConnected, activeAuditRun, auditProgress } = useWorkbench();

  const isRunning = auditProgress?.status === "running" || auditProgress?.status === "pending";
  const topbarStatus = isRunning
    ? "running"
    : activeAuditRun?.status === "failed"
      ? "failed"
      : activeAuditRun
        ? "completed"
        : "idle";

  return (
    <div className="app-frame">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark" />
          <div>
            <p className="brand-kicker">GovDoc Auditor V3</p>
            <h1>政务智能审查工作台</h1>
          </div>
        </div>
        <div className="topbar-side">
          <span className="topbar-chip">
            {apiConnected ? "GovDoc V3 已连通" : "API 未连通"}
          </span>
          {activeAuditRun ? <span className="topbar-chip">审核运行 {activeAuditRun.id.slice(0, 8)}</span> : null}
          <span className={`topbar-chip topbar-chip--${topbarStatus}`}>
            {topbarStatus === "running"
              ? "项目审查运行中"
              : topbarStatus === "failed"
                ? "当前项目审查失败"
                : topbarStatus === "completed"
                  ? "当前审核已就绪"
                  : "待启动项目审查"}
          </span>
        </div>
      </header>

      <nav className="route-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `route-link${isActive ? " is-active" : ""}`
              }
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}

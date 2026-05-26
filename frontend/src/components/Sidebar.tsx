import { Bot, GitCompareArrows, LayoutDashboard, LibraryBig } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "工作台总览", icon: LayoutDashboard },
  { to: "/audit-library", label: "审核点库", icon: LibraryBig },
  { to: "/ai-review", label: "AI 审查", icon: Bot },
  { to: "/compare", label: "文档对比", icon: GitCompareArrows },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-sidebar flex-col bg-sidebar">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
          <span className="text-sm font-bold text-white">G</span>
        </div>
        <div>
          <p className="text-sm font-semibold text-white">GovDoc Auditor</p>
          <p className="text-[11px] text-text-muted">智能审查工作台</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-2">
        <p className="mb-2 px-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">核心功能</p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) => cn(
                    "flex items-center gap-3 rounded-btn px-3 py-2 text-sm transition-colors",
                    isActive ? "bg-accent text-white font-medium" : "text-gray-400 hover:bg-sidebar-hover hover:text-white",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="mx-3 mb-3 rounded-btn bg-sidebar-active p-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-status-ok" />
          <span className="text-xs text-gray-400">系统正常运行</span>
        </div>
      </div>
    </aside>
  );
}

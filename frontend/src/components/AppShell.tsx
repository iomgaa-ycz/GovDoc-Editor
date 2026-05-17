import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function AppShell() {
  return (
    <div className="min-h-screen bg-surface">
      <Sidebar />
      <main className="ml-sidebar min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}

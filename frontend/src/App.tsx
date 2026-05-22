import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./context/AuthContext";
import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AuditLibraryPage } from "./pages/AuditLibraryPage";
import { AIReviewPage } from "./pages/AIReviewPage";
import { WorkpaperPage } from "./pages/WorkpaperPage";
import { AuditResultsPage } from "./pages/AuditResultsPage";
import { DocComparePage } from "./pages/DocComparePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate replace to="/login" />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/audit-library" element={<AuditLibraryPage />} />
        <Route path="/ai-review" element={<AIReviewPage />} />
        <Route path="/workpaper" element={<WorkpaperPage />} />
        <Route path="/audit-results" element={<AuditResultsPage />} />
        <Route path="/compare" element={<DocComparePage />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}

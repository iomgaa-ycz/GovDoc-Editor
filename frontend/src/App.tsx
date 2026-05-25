import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AuditLibraryPage } from "./pages/AuditLibraryPage";
import { DocCompareHubPage } from "./pages/DocCompareHubPage";
import { DocCompareDetailPage } from "./pages/DocCompareDetailPage";
import { AIReviewHubPage } from "./pages/AIReviewHubPage";
import { AIReviewDetailPage } from "./pages/AIReviewDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/audit-library" element={<AuditLibraryPage />} />
        <Route path="/compare" element={<DocCompareHubPage />} />
        <Route path="/compare/:reviewId" element={<DocCompareDetailPage />} />
        <Route path="/ai-review" element={<AIReviewHubPage />} />
        <Route path="/ai-review/:auditRunId" element={<AIReviewDetailPage />} />
        <Route path="/audit-results" element={<Navigate replace to="/ai-review" />} />
        <Route path="/workpaper" element={<Navigate replace to="/ai-review" />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}

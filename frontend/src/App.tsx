import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AuditLibraryPage } from "./pages/AuditLibraryPage";
import { DocCompareHubPage } from "./pages/DocCompareHubPage";
import { DocCompareDetailPage } from "./pages/DocCompareDetailPage";
import { DocCompareResultPage } from "./pages/DocCompareResultPage";
import { AIReviewHubPage } from "./pages/AIReviewHubPage";
import { AIReviewDetailPage } from "./pages/AIReviewDetailPage";
import FileManagementPage from "./pages/FileManagementPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/files" element={<FileManagementPage />} />
        <Route path="/audit-library" element={<AuditLibraryPage />} />
        <Route path="/compare" element={<DocCompareHubPage />} />
        <Route path="/compare/:reviewId" element={<DocCompareResultPage />} />
        <Route path="/ai-review" element={<AIReviewHubPage />} />
        <Route path="/ai-review/:auditRunId" element={<AIReviewDetailPage />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}

import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { HomePage } from "./pages/HomePage";
import { AuditLibraryPage } from "./pages/AuditLibraryPage";
import { AIReviewPage } from "./pages/AIReviewPage";
import { WorkpaperPage } from "./pages/WorkpaperPage";
import { AuditResultsPage } from "./pages/AuditResultsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/audit-library" element={<AuditLibraryPage />} />
        <Route path="/ai-review" element={<AIReviewPage />} />
        <Route path="/workpaper" element={<WorkpaperPage />} />
        <Route path="/audit-results" element={<AuditResultsPage />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}

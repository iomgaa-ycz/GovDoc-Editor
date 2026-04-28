import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { vi } from "vitest";

import {
  WorkbenchContext,
  type WorkbenchContextValue,
} from "@/context/V3WorkbenchContext";

export function makeWorkbenchValue(
  overrides: Partial<WorkbenchContextValue> = {},
): WorkbenchContextValue {
  return {
    apiConnected: true,
    ruleSources: [],
    activeRuleSource: undefined,
    selectedRuleSourceId: null,
    setSelectedRuleSourceId: vi.fn(),
    checkpoints: [],
    finalCheckpoints: [],
    extractingRuleSourceId: null,
    extractStatus: null,
    extractError: null,
    uploadRuleAndExtract: vi.fn(),
    pollExtractRun: vi.fn(),
    projects: [],
    activeProject: undefined,
    selectedProjectId: null,
    setSelectedProjectId: vi.fn(),
    createProject: vi.fn(),
    uploadTenderDoc: vi.fn(),
    uploadAuditInputDocs: vi.fn(),
    auditInputDocs: {},
    tenderDocs: {},
    auditRuns: [],
    activeAuditRun: undefined,
    selectedAuditRunId: null,
    setSelectedAuditRunId: vi.fn(),
    createAuditRun: vi.fn(),
    loadAuditRunProgress: vi.fn(),
    auditProgress: null,
    logs: [],
    pointRuns: [],
    activePointRun: undefined,
    selectedPointRunId: null,
    setSelectedPointRunId: vi.fn(),
    retryPointRun: vi.fn(),
    workpaperHtml: "",
    workpaperJson: null,
    workpaperSaveStatus: "idle",
    finalizeStatus: "idle",
    loadWorkpaper: vi.fn(),
    clearWorkpaper: vi.fn(),
    setWorkpaperHtml: vi.fn(),
    saveWorkpaper: vi.fn(),
    finalizeWorkpaper: vi.fn(),
    importCheckpointFile: vi.fn(),
    updateCheckpoint: vi.fn(),
    deleteCheckpoint: vi.fn(),
    refreshAll: vi.fn(),
    ...overrides,
  };
}

export function renderWithWorkbench(
  ui: ReactNode,
  overrides: Partial<WorkbenchContextValue> = {},
  route = "/",
) {
  const value = makeWorkbenchValue(overrides);
  return render(
    <MemoryRouter initialEntries={[route]}>
      <WorkbenchContext.Provider value={value}>
        {ui}
      </WorkbenchContext.Provider>
    </MemoryRouter>,
  );
}

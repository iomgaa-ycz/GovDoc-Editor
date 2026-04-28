import type { AuditRun, Project } from "../types/ui";
import {
  getAuditRunDisplayInfo,
  type AuditRunDocs,
} from "../utils/auditRunLabel";

export function AuditRunCurrentInfo(props: {
  run: AuditRun | undefined;
  projects: Project[];
  auditInputDocs: Record<string, AuditRunDocs>;
}) {
  if (!props.run) return null;

  const info = getAuditRunDisplayInfo({
    run: props.run,
    projects: props.projects,
    auditInputDocs: props.auditInputDocs,
  });

  return (
    <section className="audit-run-summary" aria-label="当前审核运行">
      <div className="audit-run-summary__head">
        <span>当前审核运行</span>
        <strong>{info.projectName}</strong>
      </div>
      <div className="audit-run-summary__items">
        <div>
          <span>主文书</span>
          <strong title={info.tenderDocName}>{info.tenderDocName}</strong>
        </div>
        <div>
          <span>附件</span>
          <strong>{info.supplementaryCount} 个</strong>
        </div>
        <div>
          <span>状态</span>
          <strong>{info.status}</strong>
        </div>
      </div>
    </section>
  );
}

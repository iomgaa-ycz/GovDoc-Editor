import { X } from "lucide-react";
import { createPortal } from "react-dom";
import { type PropsWithChildren, type ReactNode } from "react";

export function Modal(
  props: PropsWithChildren<{
    open: boolean;
    title: string;
    subtitle?: string;
    onClose: () => void;
    width?: "md" | "lg";
    footer?: ReactNode;
  }>,
) {
  if (!props.open) {
    return null;
  }

  return createPortal(
    <div className="modal-backdrop" role="presentation" onClick={props.onClose}>
      <div
        className={`modal-card modal-card--${props.width || "md"}`}
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">审核详情</p>
            <h3>{props.title}</h3>
            {props.subtitle ? (
              <p className="modal-subtitle">{props.subtitle}</p>
            ) : null}
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭"
            onClick={props.onClose}
          >
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">{props.children}</div>
        {props.footer ? <div className="modal-footer">{props.footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}

import type { ReactNode } from "react";

type Props = {
  /** Module name, e.g. "Module 3 · Pricing". */
  kicker: string;
  title: ReactNode;
  /** One sentence. */
  subtitle?: ReactNode;
  /** Buttons on the right of the header. */
  actions?: ReactNode;
  /** Sticky footer actions (Save policy, Save override). */
  footer?: ReactNode;
  children: ReactNode;
  /** Extra classes on the scrolling body. */
  bodyClassName?: string;
};

/** One header (kicker / title / subtitle / actions) + scrolling body + optional footer. */
export default function AdminPanel({ kicker, title, subtitle, actions, footer, children, bodyClassName = "" }: Props) {
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="studio-panel-header">
        <div className="min-w-0">
          <p className="studio-panel-kicker">{kicker}</p>
          <h2 className="text-lg font-semibold">{title}</h2>
          {subtitle ? <p className="studio-panel-subtitle mt-0.5">{subtitle}</p> : null}
        </div>
        {actions ? <div className="studio-toolbar flex-wrap justify-end">{actions}</div> : null}
      </header>
      <div className={`studio-panel-body studio-scroll min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden !pt-5 !pb-6 ${bodyClassName}`}>
        {children}
      </div>
      {footer ? <div className="studio-panel-footer flex flex-wrap items-center justify-end gap-2">{footer}</div> : null}
    </div>
  );
}

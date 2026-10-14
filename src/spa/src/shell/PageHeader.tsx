import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./PageHeader.css";

export type Crumb = { label: string; to: string };

/** Consistent page title block: breadcrumbs, title, subtitle, meta, actions. */
export function PageHeader(props: {
  title: ReactNode;
  subtitle?: ReactNode;
  crumbs?: Crumb[];
  /** Inline status chips under the title (badges, live indicator, links). */
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      {props.crumbs?.length ? (
        <nav className="crumbs" aria-label="Breadcrumb">
          <ol>
            {props.crumbs.map((crumb) => (
              <li key={crumb.to}>
                <Link to={crumb.to}>{crumb.label}</Link>
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <div className="page-header-row">
        <div className="page-header-text">
          <h1>{props.title}</h1>
          {props.subtitle ? (
            <p className="muted page-header-subtitle">{props.subtitle}</p>
          ) : null}
          {props.meta ? <div className="page-header-meta">{props.meta}</div> : null}
        </div>
        {props.actions ? (
          <div className="page-header-actions">{props.actions}</div>
        ) : null}
      </div>
    </header>
  );
}

import type { ReactNode } from "react";

/** One settings section with title, optional hint, and body fields. */
export function SectionCard(props: {
  id: string;
  title: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="settings-section" id={props.id} aria-labelledby={`${props.id}-title`}>
      <header className="settings-section-head">
        <h2 id={`${props.id}-title`}>{props.title}</h2>
        {props.hint ? <p className="muted settings-section-hint">{props.hint}</p> : null}
      </header>
      <div className="settings-section-body">{props.children}</div>
    </section>
  );
}

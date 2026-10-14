import type { MouseEvent } from "react";
import "./ServiceSectionNav.css";

export type ServiceSection = { id: string; label: string };

/** Sticky in-page jump links for the long service page. */
export function ServiceSectionNav(props: { sections: ServiceSection[] }) {
  return (
    <nav className="section-nav" aria-label="Service sections">
      {props.sections.map((s) => (
        <a key={s.id} href={`#${s.id}`} onClick={(e) => jump(e, s.id)}>
          {s.label}
        </a>
      ))}
    </nav>
  );
}

function jump(event: MouseEvent, id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  event.preventDefault();
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  window.history.replaceState(window.history.state, "", `#${id}`);
}

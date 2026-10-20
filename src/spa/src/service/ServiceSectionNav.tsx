import { jumpToSection } from "../chrome/scrollSpy";
import { useScrollSpy } from "../chrome/useScrollSpy";

export type ServiceSection = { id: string; label: string };

/** Sticky in-page jump links for the long service page. */
export function ServiceSectionNav(props: { sections: ServiceSection[] }) {
  const active = useScrollSpy(props.sections.map((s) => s.id));
  return (
    <nav className="jump-nav" aria-label="Service sections">
      {props.sections.map((s) => (
        <a
          key={s.id}
          href={`#${s.id}`}
          className={active === s.id ? "is-active" : undefined}
          aria-current={active === s.id ? "location" : undefined}
          onClick={(e) => jumpToSection(e, s.id)}
        >
          {s.label}
        </a>
      ))}
    </nav>
  );
}

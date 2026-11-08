import type { ReactNode } from "react";
import { jumpToSection } from "../../shared/chrome/scrollSpy";
import { useScrollSpy } from "../../shared/chrome/useScrollSpy";
import type { EnabledMap } from "./sectionEnablement";
import {
  SETTINGS_NAV_GROUPS,
  sectionOff,
  settingsNavIds,
} from "./settingsLayout";

/** Sticky section index (sidebar on desktop, chip strip on narrow screens). */
export function SettingsSectionNav(props: { enabled: EnabledMap }) {
  const active = useScrollSpy(settingsNavIds());
  return (
    <nav className="side-nav" aria-label="Settings sections" id="settings-toc">
      {SETTINGS_NAV_GROUPS.map((group) => (
        <SectionGroup key={group.label} label={group.label}>
          {group.items.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={active === item.id ? "is-active" : undefined}
              aria-current={active === item.id ? "location" : undefined}
              onClick={(event) => jumpToSection(event, item.id)}
            >
              {item.label}
              {sectionOff(item, props.enabled) ? (
                <span className="side-nav-off">off</span>
              ) : null}
            </a>
          ))}
        </SectionGroup>
      ))}
    </nav>
  );
}

function SectionGroup(props: { label: string; children: ReactNode }) {
  return (
    <>
      <p className="side-nav-label">{props.label}</p>
      {props.children}
    </>
  );
}

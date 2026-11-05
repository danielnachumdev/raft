import type { ReactNode } from "react";
import type { SectionKind } from "./settingsApi";

/** One settings section with optional enable toggle (flag / derived). */
export function SectionCard(props: {
  id: string;
  title: string;
  hint?: ReactNode;
  kind?: SectionKind;
  enabled?: boolean;
  source?: string;
  onEnabledChange?: (enabled: boolean) => void;
  children: ReactNode;
}) {
  const kind = props.kind ?? "always";
  const enabled = props.enabled ?? true;
  const canToggle = kind !== "always" && props.onEnabledChange;
  return (
    <section
      className={`panel settings-section${enabled ? "" : " settings-section-disabled"}`}
      id={props.id}
      aria-labelledby={`${props.id}-title`}
      data-enabled={enabled ? "true" : "false"}
      data-kind={kind}
    >
      <header className="settings-section-head">
        <div className="settings-section-title-row">
          <h2 id={`${props.id}-title`}>{props.title}</h2>
          {canToggle ? (
            <label
              className={
                enabled
                  ? "chip chip-ok settings-section-enable"
                  : "chip settings-section-enable"
              }
            >
              <input
                type="checkbox"
                id={`${props.id}-enabled`}
                checked={enabled}
                onChange={(e) => props.onEnabledChange?.(e.target.checked)}
              />
              {enabled ? "Enabled" : "Disabled"}
            </label>
          ) : null}
        </div>
        {props.hint ? (
          <p className="muted settings-section-hint">{props.hint}</p>
        ) : null}
        {props.source ? (
          <p className="muted settings-section-source">
            Enablement: <code>{props.source}</code>
          </p>
        ) : null}
      </header>
      <fieldset
        className="settings-section-body"
        disabled={!enabled}
        aria-disabled={!enabled}
      >
        {props.children}
      </fieldset>
    </section>
  );
}

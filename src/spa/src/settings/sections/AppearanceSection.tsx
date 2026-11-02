import { ThemeToggle } from "../../chrome/ThemeToggle";
import { SectionCard } from "../SectionCard";

/** Browser-local light/dark preference (not part of settings.yaml). */
export function AppearanceSection() {
  return (
    <SectionCard
      id="settings-appearance"
      title="Appearance"
      hint="Dashboard theme for this browser only. Applies immediately — not part of host settings."
    >
      <div className="form-grid">
        <div className="field">
          <span id="appearance-theme-label">Theme</span>
          <div className="settings-theme-row">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

import { useRef, type UIEvent } from "react";
import { YamlHighlighter } from "./YamlHighlighter";

const highlighter = new YamlHighlighter();

/** YAML editor for the full operator settings document. */
export function SettingsYamlPanel(props: {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}) {
  const highlightRef = useRef<HTMLPreElement>(null);
  const html = highlighter.highlightHtml(props.value);

  return (
    <div className="settings-yaml" id="settings-yaml">
      <p className="muted settings-yaml-hint">
        Edit the full <code>settings.yaml</code> document. Save validates with
        the same parsers as the form. Secrets show as <code>***</code>; leave
        the mask to keep the stored value.
      </p>
      <label className="field" htmlFor="settings-yaml-editor">
        YAML
        <div className="settings-yaml-shell">
          <pre
            ref={highlightRef}
            className="settings-yaml-highlight"
            aria-hidden="true"
            dangerouslySetInnerHTML={{ __html: html + "\n" }}
          />
          <textarea
            id="settings-yaml-editor"
            className="settings-yaml-editor"
            spellCheck={false}
            rows={28}
            disabled={props.disabled}
            value={props.value}
            onChange={(e) => props.onChange(e.target.value)}
            onScroll={(e) => syncScroll(e, highlightRef.current)}
          />
        </div>
      </label>
    </div>
  );
}

function syncScroll(
  event: UIEvent<HTMLTextAreaElement>,
  highlight: HTMLPreElement | null,
): void {
  if (!highlight) return;
  highlight.scrollTop = event.currentTarget.scrollTop;
  highlight.scrollLeft = event.currentTarget.scrollLeft;
}

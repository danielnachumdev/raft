import { useRef, type UIEvent } from "react";
import { YamlHighlighter } from "../settings/YamlHighlighter";

const highlighter = new YamlHighlighter();

/** YAML editor for the RBAC document with syntax highlighting. */
export function RbacYamlPanel(props: {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}) {
  const highlightRef = useRef<HTMLPreElement>(null);
  const html = highlighter.highlightHtml(props.value);

  return (
    <div className="rbac-yaml" id="rbac-yaml">
      <label className="field" htmlFor="rbac-yaml-editor">
        YAML
        <div className="rbac-yaml-shell">
          <pre
            ref={highlightRef}
            className="rbac-yaml-highlight"
            aria-hidden="true"
            dangerouslySetInnerHTML={{ __html: html + "\n" }}
          />
          <textarea
            id="rbac-yaml-editor"
            className="rbac-yaml-editor"
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

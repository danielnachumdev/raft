import { useState } from "react";

/** Inline code value with a one-click copy control. */
export function CopyableValue(props: { value: string; id: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(props.value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <span className="oauth-setup-value">
      <code id={props.id}>{props.value}</code>
      <button
        type="button"
        className="oauth-copy"
        onClick={() => void onCopy()}
        aria-label={`Copy ${props.id}`}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}

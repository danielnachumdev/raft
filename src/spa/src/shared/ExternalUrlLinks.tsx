/** Clickable external URL list for status rows and service detail. */
import "./ExternalUrlLinks.css";
export function ExternalUrlLinks(props: {
  urls: string[];
  compact?: boolean;
}) {
  if (!props.urls.length) {
    return props.compact ? null : <span className="muted">—</span>;
  }
  return (
    <ul
      className={
        props.compact ? "external-urls external-urls-compact" : "external-urls"
      }
    >
      {props.urls.map((url) => (
        <li key={url}>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            {url}
          </a>
        </li>
      ))}
    </ul>
  );
}

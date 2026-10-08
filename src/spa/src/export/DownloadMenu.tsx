import { buildDownloadItems, type ExportKind } from "./items";
import { useExportOptions } from "./catalog";
import "./DownloadMenu.css";
/** Catalog-driven download links; new formats appear without UI wiring. */
export function DownloadMenu(props: {
  kind: ExportKind;
  hrefFor: (formatId: string) => string;
  disabled?: boolean;
}) {
  const options = useExportOptions(props.kind);
  const items = buildDownloadItems(options, props.hrefFor);
  if (items.length === 0) return null;
  return (
    <div className="download-menu">
      <span className="download-menu-label">Download</span>
      {items.map((item) => (
        <a
          key={item.id}
          className="action-btn download-link"
          href={item.href}
          download
          aria-disabled={props.disabled ? true : undefined}
          onClick={(event) => {
            if (props.disabled) event.preventDefault();
          }}
        >
          {item.label}
        </a>
      ))}
    </div>
  );
}

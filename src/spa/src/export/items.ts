export type ExportOption = {
  id: string;
  label: string;
  media_type: string;
  suffix: string;
};

export type ExportKind = "logs" | "metrics";

export type ExportCatalog = {
  logs: ExportOption[];
  metrics: ExportOption[];
};

export type DownloadItem = {
  id: string;
  label: string;
  href: string;
};

/** Menu rows from a catalog list. Adding a server format needs no UI rewrite. */
export function buildDownloadItems(
  options: ExportOption[],
  hrefFor: (formatId: string) => string,
): DownloadItem[] {
  return options.map((option) => ({
    id: option.id,
    label: option.label,
    href: hrefFor(option.id),
  }));
}

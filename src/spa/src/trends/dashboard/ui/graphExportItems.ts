export type GraphExportHandlers = {
  onCsv: () => void;
  /** When set, PNG appears in the submenu (expanded capture only). */
  onPng?: () => void;
  pngBusy?: boolean;
  disabled?: boolean;
};

export type GraphExportMenuItem = {
  id: string;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
};

/** Build Export submenu rows (CSV always; PNG only when capture is available). */
export function graphExportItems(
  handlers: GraphExportHandlers,
): GraphExportMenuItem[] {
  const items: GraphExportMenuItem[] = [
    {
      id: "csv",
      label: "CSV",
      disabled: handlers.disabled,
      onSelect: handlers.onCsv,
    },
  ];
  if (handlers.onPng) {
    items.push({
      id: "png",
      label: handlers.pngBusy ? "Exporting…" : "PNG",
      disabled: handlers.disabled || handlers.pngBusy,
      onSelect: () => {
        if (!handlers.pngBusy) handlers.onPng?.();
      },
    });
  }
  return items;
}

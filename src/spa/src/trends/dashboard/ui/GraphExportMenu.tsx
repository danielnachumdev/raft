import type { ReactNode } from "react";
import {
  graphExportItems,
  type GraphExportHandlers,
} from "./graphExportItems.ts";
import { MenuButton } from "./MenuButton";
import "./GraphExportMenu.css";

export type GraphExportAppearance = "text" | "icon";

export type { GraphExportHandlers };
export { graphExportItems };

/**
 * Single Export control → submenu of available formats.
 * Text chrome: “Export”; icon chrome: down-arrow (distinct from graph ⋯).
 */
export function GraphExportMenu(
  props: GraphExportHandlers & {
    appearance: GraphExportAppearance;
    className?: string;
  },
) {
  const items = graphExportItems(props);
  const classes = [
    "graph-export-menu",
    props.appearance === "text" ? "is-text" : "is-icon",
    props.className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <MenuButton label="Export" className={classes} items={items}>
      {exportTrigger(props.appearance)}
    </MenuButton>
  );
}

function exportTrigger(appearance: GraphExportAppearance): ReactNode {
  if (appearance === "text") {
    return (
      <>
        <span>Export</span>
        <span className="graph-export-chevron" aria-hidden="true">
          ▾
        </span>
      </>
    );
  }
  return (
    <span className="graph-export-arrow" aria-hidden="true">
      ↓
    </span>
  );
}

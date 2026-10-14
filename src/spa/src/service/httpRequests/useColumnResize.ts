import { useCallback, useRef, useState } from "react";
import {
  applyColumnResize,
  defaultColumnWidths,
  type ColumnWidths,
  type HttpRequestColumnKey,
} from "./columnResize";

/** Pointer-drag column resize; widths live in component state only. */
export function useColumnResize() {
  const [widths, setWidths] = useState<ColumnWidths>(defaultColumnWidths);
  const drag = useRef<{
    key: HttpRequestColumnKey;
    startX: number;
    startWidth: number;
  } | null>(null);

  const onResizePointerDown = useCallback(
    (key: HttpRequestColumnKey, clientX: number) => {
      drag.current = { key, startX: clientX, startWidth: widths[key] };
    },
    [widths],
  );

  const onResizePointerMove = useCallback((clientX: number) => {
    const active = drag.current;
    if (!active) return;
    setWidths((prev) =>
      applyColumnResize(
        prev,
        active.key,
        active.startWidth,
        clientX - active.startX,
      ),
    );
  }, []);

  const onResizePointerUp = useCallback(() => {
    drag.current = null;
  }, []);

  return {
    widths,
    onResizePointerDown,
    onResizePointerMove,
    onResizePointerUp,
  };
}

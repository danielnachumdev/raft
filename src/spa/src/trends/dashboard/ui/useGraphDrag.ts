import { useState, type DragEvent } from "react";

const MIME = "application/x-raft-trends-graph";

export type GraphDrag = {
  dragId: string | null;
  overId: string | null;
  handleProps: (id: string) => {
    draggable: true;
    onDragStart: (e: DragEvent<HTMLElement>) => void;
    onDragEnd: () => void;
  };
  cellProps: (id: string) => {
    onDragOver: (e: DragEvent<HTMLElement>) => void;
    onDragLeave: () => void;
    onDrop: (e: DragEvent<HTMLElement>) => void;
  };
};

/** Native HTML5 drag from a header handle; drop on another cell to take its slot. */
export function useGraphDrag(onMove: (fromId: string, toId: string) => void): GraphDrag {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const reset = () => {
    setDragId(null);
    setOverId(null);
  };
  return {
    dragId,
    overId,
    handleProps: (id) => ({
      draggable: true,
      onDragStart: (e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData(MIME, id);
        const card = e.currentTarget.closest(".trends-grid-cell");
        if (card) e.dataTransfer.setDragImage(card, 24, 24);
        setDragId(id);
      },
      onDragEnd: reset,
    }),
    cellProps: (id) => ({
      onDragOver: (e) => {
        if (!dragId || dragId === id) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (overId !== id) setOverId(id);
      },
      onDragLeave: () => {
        if (overId === id) setOverId(null);
      },
      onDrop: (e) => {
        e.preventDefault();
        const from = e.dataTransfer.getData(MIME) || dragId;
        if (from && from !== id) onMove(from, id);
        reset();
      },
    }),
  };
}

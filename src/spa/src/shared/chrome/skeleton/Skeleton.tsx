import type { CSSProperties, ReactNode } from "react";
import "./Skeleton.css";

export type SkeletonBoneSize = "sm" | "md" | "lg" | "block";

/** Single shimmer bone. Prefer premade builders over assembling these at call sites. */
export function SkeletonBone(props: {
  size?: SkeletonBoneSize;
  width?: string | number;
  height?: string | number;
  className?: string;
  style?: CSSProperties;
}) {
  const size = props.size ?? "md";
  const className = props.className
    ? `skeleton-bone skeleton-bone--${size} ${props.className}`
    : `skeleton-bone skeleton-bone--${size}`;
  const style: CSSProperties = { ...props.style };
  if (props.width !== undefined) {
    style.width =
      typeof props.width === "number" ? `${props.width}%` : props.width;
  }
  if (props.height !== undefined) {
    style.height =
      typeof props.height === "number" ? `${props.height}px` : props.height;
  }
  return <span className={className} style={style} aria-hidden="true" />;
}

/**
 * Accessible shell for cold-load skeletons.
 * Spinner rule: use LoadingState only when no skeleton exists for the surface.
 */
export function SkeletonRoot(props: {
  label: string;
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  const className = props.className
    ? `skeleton-root ${props.className}`
    : "skeleton-root";
  return (
    <div
      className={className}
      id={props.id}
      role="status"
      aria-busy="true"
      aria-live="polite"
      aria-label={props.label}
    >
      <span className="skeleton-sr">{props.label}</span>
      {props.children}
    </div>
  );
}

import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useRbac } from "./RbacContext";

export function RequirePermission(props: {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { loading, can } = useRbac();
  if (loading) return null;
  if (!can(props.permission)) {
    if (props.fallback !== undefined) return props.fallback;
    return <Navigate to="/forbidden" replace />;
  }
  return props.children;
}

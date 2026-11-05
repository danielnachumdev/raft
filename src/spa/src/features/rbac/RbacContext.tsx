import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { allows } from "./permissions";

export type RbacSnapshot = {
  identity: string;
  bootstrap: boolean;
  permissions: string[];
};

type RbacContextValue = {
  loading: boolean;
  rbac: RbacSnapshot | null;
  can: (permission: string) => boolean;
};

const RbacContext = createContext<RbacContextValue>({
  loading: true,
  rbac: null,
  can: () => true,
});

export function RbacProvider(props: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [rbac, setRbac] = useState<RbacSnapshot | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/dashboard/session")
      .then(async (res) => {
        if (!res.ok) return null;
        const body = await res.json();
        return (body.rbac as RbacSnapshot | undefined) ?? null;
      })
      .then((snap) => {
        if (!cancelled) {
          setRbac(snap);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRbac(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value: RbacContextValue = {
    loading,
    rbac,
    can: (permission: string) => {
      if (!rbac || rbac.bootstrap) return true;
      return allows(rbac.permissions, permission);
    },
  };

  return (
    <RbacContext.Provider value={value}>{props.children}</RbacContext.Provider>
  );
}

export function useRbac(): RbacContextValue {
  return useContext(RbacContext);
}

/** Shared recommendation row shape for firewall, alerts, and future areas. */

export type RecommendationItem = {
  id: string;
  title: string;
  summary: string;
  kind?: string;
};

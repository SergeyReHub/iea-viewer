const STORAGE_KEY = "iea_viewer_v2_source_id";

let currentSourceId = localStorage.getItem(STORAGE_KEY) || "iea";

const listeners = new Set<(sourceId: string) => void>();

export function getCurrentSourceId(): string {
  return currentSourceId;
}

export function setCurrentSourceId(sourceId: string): void {
  currentSourceId = sourceId;
  localStorage.setItem(STORAGE_KEY, sourceId);
  listeners.forEach((listener) => listener(sourceId));
}

export function onSourceChange(listener: (sourceId: string) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export interface SourceProfile {
  id: string;
  name: string;
  status: "active" | "planned" | "disabled";
  adapter: string;
  homepage_url: string;
  description: string;
  schema_version: string | null;
  domains: string[];
  db_ok: boolean;
  data_as_of_period?: string | null;
}

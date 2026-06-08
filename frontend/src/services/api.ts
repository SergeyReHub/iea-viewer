import { getCurrentSourceId } from "../stores/source";
import type { SourceProfile } from "../stores/source";

export type Domain = "base" | "oil" | "gas" | "coal" | "electricity";
export type TableType = "ref" | "fact" | "map";
export type { SourceProfile };

export interface TableMeta {
  table: string;
  display_name?: string;
  type: TableType;
  description: string;
}

export interface RawDataResponse {
  domain: Domain;
  table: string;
  limit: number;
  count: number;
  columns: string[];
  rows: Record<string, unknown>[];
}

export type RawStatsRowAxisKey = "country" | "flow";

export interface RawStatsRowAxisMeta {
  key: RawStatsRowAxisKey;
  label: string;
  column: string;
}

export interface RawStatsCell {
  row_key: string;
  col_key: string;
  count: number;
}

export interface RawStatsResponse {
  domain: Domain;
  table: string;
  row_axis: RawStatsRowAxisKey;
  row_axis_label: string;
  frequency_code: string | null;
  row_column: string;
  col_column: string;
  available_row_axes: RawStatsRowAxisMeta[];
  available_frequency_codes: string[];
  period_values: string[];
  row_items: Array<{ key: string; label: string }>;
  col_labels: string[];
  min_count: number;
  max_count: number;
  cells: RawStatsCell[];
}

export interface RawStatsDetailResponse {
  domain: Domain;
  table: string;
  row_axis: RawStatsRowAxisKey;
  row_key: string;
  time_period: string;
  frequency_code: string | null;
  detail_axis_label: string;
  items: Array<{ key: string; label: string; count: number }>;
  ambiguity_dimensions: Array<{
    field: string;
    label: string;
    count: number;
    values: string[];
    truncated: boolean;
  }>;
}

export interface TableDocResponse {
  domain: Domain;
  table: string;
  type: TableType;
  markdown: string;
}

export interface HierarchyNode {
  code: string;
  name: string;
  parent_code: string | null;
  depth: number;
  row_count?: number;
}

export interface MasterHierarchiesResponse {
  fact_tables: { table: string; label: string; description: string }[];
}

export interface MasterFilterDefinition {
  key: string;
  label: string;
  nodes: HierarchyNode[];
}

export interface MasterFilterOptionsResponse {
  fact_table: string;
  filters: MasterFilterDefinition[];
}

export interface MasterReportRequest {
  fact_table: string;
  filter_values: Record<string, string[]>;
  limit: number;
  pivot_layout: "time_rows_filters_columns" | "time_columns_filters_rows";
}

export interface MasterReportResponse {
  count: number;
  columns: string[];
  rows: Record<string, unknown>[];
  pivot: {
    columns: string[];
    rows: Record<string, unknown>[];
  };
}

export interface MasterGuideTemplateMeta {
  id: string;
  domain: "oil" | "gas" | "coal" | "electricity";
  title: string;
}

export interface MasterGuideTableResponse {
  table_id: string;
  title: string;
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface PresetRecord {
  id: string;
  name: string;
  description: string;
  factTable: string;
  selectedFilterValues: Record<string, string[]>;
  pivotLayout: "time_rows_filters_columns" | "time_columns_filters_rows";
  periodFrom: string;
  periodTo: string;
  periodSort: "asc" | "desc";
  updatedAt: string;
  version: number;
}

export interface WhoAmIResponse {
  ip: string | null;
  full_name: string | null;
  can_view_audit: boolean;
}

export interface AuditEventRequest {
  event_type: string;
  page_path: string;
  page_name?: string;
  session_id?: string;
  details?: Record<string, unknown>;
}

export interface AuditLogRecord {
  timestamp_utc: string;
  full_name: string;
  ip: string | null;
  event_type: string;
  page_path: string;
  page_name?: string | null;
  session_id?: string | null;
  user_agent?: string | null;
  details?: Record<string, unknown> | null;
}

const envApiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
const autoApiUrl =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8010/api`
    : "http://localhost:8010/api";
const baseUrl = envApiUrl ? envApiUrl : autoApiUrl;

function sourceApi(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}/v2/sources/${getCurrentSourceId()}${normalized}`;
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function getDomains(): Promise<Domain[]> {
  const response = await fetch(sourceApi("/meta/domains"));
  const payload = await parseJson<{ domains: Domain[] }>(response);
  return payload.domains;
}

export async function getTables(domain: Domain, type: TableType): Promise<TableMeta[]> {
  const response = await fetch(sourceApi(`/meta/tables?domain=${domain}&type=${type}`));
  const payload = await parseJson<{ tables: TableMeta[] }>(response);
  return payload.tables;
}

export async function getRawData(
  domain: Domain,
  tableName: string,
  limit: number
): Promise<RawDataResponse> {
  const encodedTable = encodeURIComponent(tableName);
  const response = await fetch(sourceApi(`/raw/${domain}/${encodedTable}?limit=${limit}`));
  return parseJson<RawDataResponse>(response);
}

export async function getRawStats(
  domain: Domain,
  tableName: string,
  rowAxis?: RawStatsRowAxisKey,
  frequencyCode?: string,
  periodFrom?: string,
  periodTo?: string
): Promise<RawStatsResponse> {
  const encodedTable = encodeURIComponent(tableName);
  const params = new URLSearchParams();
  if (rowAxis) params.set("row_axis", rowAxis);
  if (frequencyCode) params.set("frequency_code", frequencyCode);
  if (periodFrom) params.set("period_from", periodFrom);
  if (periodTo) params.set("period_to", periodTo);
  const query = params.toString();
  const response = await fetch(
    sourceApi(`/raw/stats/${domain}/${encodedTable}${query ? `?${query}` : ""}`)
  );
  return parseJson<RawStatsResponse>(response);
}

export async function getRawStatsDetail(
  domain: Domain,
  tableName: string,
  rowAxis: RawStatsRowAxisKey,
  rowKey: string,
  timePeriod: string,
  frequencyCode?: string
): Promise<RawStatsDetailResponse> {
  const encodedTable = encodeURIComponent(tableName);
  const params = new URLSearchParams();
  params.set("row_axis", rowAxis);
  params.set("row_key", rowKey);
  params.set("time_period", timePeriod);
  if (frequencyCode) params.set("frequency_code", frequencyCode);
  const response = await fetch(sourceApi(`/raw/stats-detail/${domain}/${encodedTable}?${params.toString()}`));
  return parseJson<RawStatsDetailResponse>(response);
}

export async function getTableDoc(domain: Domain, table: string): Promise<TableDocResponse> {
  const encodedTable = encodeURIComponent(table);
  const response = await fetch(sourceApi(`/meta/table-doc?domain=${domain}&table=${encodedTable}`));
  return parseJson<TableDocResponse>(response);
}

export async function getReferenceData(
  domain: Domain,
  tableName: string
): Promise<Omit<RawDataResponse, "limit">> {
  const encodedTable = encodeURIComponent(tableName);
  const response = await fetch(sourceApi(`/reference/${domain}/${encodedTable}`));
  return parseJson<Omit<RawDataResponse, "limit">>(response);
}

export async function getMasterHierarchies(): Promise<MasterHierarchiesResponse> {
  const response = await fetch(sourceApi("/master-report/hierarchies"));
  return parseJson<MasterHierarchiesResponse>(response);
}

export async function getMasterFilterOptions(
  factTable: string,
  selectedFilterValues: Record<string, string[]>
): Promise<MasterFilterOptionsResponse> {
  const response = await fetch(sourceApi("/master-report/filter-options"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      fact_table: factTable,
      selected_filter_values: selectedFilterValues
    })
  });
  return parseJson<MasterFilterOptionsResponse>(response);
}

export async function buildMasterReport(
  payload: MasterReportRequest
): Promise<MasterReportResponse> {
  const response = await fetch(sourceApi("/master-report/report"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson<MasterReportResponse>(response);
}

export async function getMasterGuideTemplates(
  domain: "oil" | "gas" | "coal" | "electricity"
): Promise<MasterGuideTemplateMeta[]> {
  const response = await fetch(sourceApi(`/master-report/guide/templates?domain=${domain}`));
  const payload = await parseJson<{ templates: MasterGuideTemplateMeta[] }>(response);
  return payload.templates;
}

export async function buildMasterGuideTable(
  tableId: string,
  countryCode: string
): Promise<MasterGuideTableResponse> {
  const response = await fetch(sourceApi("/master-report/guide/table"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      table_id: tableId,
      country_code: countryCode
    })
  });
  return parseJson<MasterGuideTableResponse>(response);
}

export function getMasterGuideTzTemplateUrl(): string {
  return sourceApi("/documents/master-guide-oil-tz");
}

export async function getWhoAmI(): Promise<WhoAmIResponse> {
  const response = await fetch(sourceApi("/whoami"));
  return parseJson<WhoAmIResponse>(response);
}

export async function sendAuditEvent(payload: AuditEventRequest): Promise<void> {
  await fetch(sourceApi("/audit/event"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function getAuditLogs(): Promise<AuditLogRecord[]> {
  const response = await fetch(sourceApi("/audit/logs"));
  const payload = await parseJson<{ records: AuditLogRecord[] }>(response);
  return payload.records;
}

export async function getPresets(): Promise<PresetRecord[]> {
  const response = await fetch(sourceApi("/presets"));
  const payload = await parseJson<{ presets: PresetRecord[] }>(response);
  return payload.presets;
}

export async function savePresets(presets: PresetRecord[]): Promise<void> {
  const response = await fetch(sourceApi("/presets"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presets })
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Не удалось сохранить пресеты на сервере");
  }
}

export type PresetMutationPayload = Omit<PresetRecord, "updatedAt" | "version">;
export type PresetConflictStrategy = "reject" | "copy";

export interface PresetUpdateResponse {
  mode: "updated" | "copied_on_conflict";
  preset: PresetRecord;
  sourcePresetId?: string | null;
}

export async function createPreset(preset: PresetMutationPayload): Promise<PresetRecord> {
  const response = await fetch(sourceApi("/presets"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(preset)
  });
  return parseJson<PresetRecord>(response);
}

export async function updatePreset(
  presetId: string,
  preset: PresetMutationPayload,
  expectedVersion: number,
  expectedUpdatedAt?: string,
  conflictStrategy: PresetConflictStrategy = "copy"
): Promise<PresetUpdateResponse> {
  const response = await fetch(sourceApi(`/presets/${encodeURIComponent(presetId)}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...preset,
      expectedVersion,
      expectedUpdatedAt,
      conflictStrategy
    })
  });
  return parseJson<PresetUpdateResponse>(response);
}

export async function deletePreset(
  presetId: string,
  expectedVersion: number,
  expectedUpdatedAt?: string
): Promise<void> {
  const params = new URLSearchParams();
  params.set("expectedVersion", String(expectedVersion));
  if (expectedUpdatedAt) {
    params.set("expectedUpdatedAt", expectedUpdatedAt);
  }
  const response = await fetch(sourceApi(`/presets/${encodeURIComponent(presetId)}?${params.toString()}`), {
    method: "DELETE"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Не удалось удалить пресет");
  }
}

export async function importPresetsToServer(
  presets: PresetMutationPayload[],
  merge = true
): Promise<PresetRecord[]> {
  const response = await fetch(sourceApi("/presets/import"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presets, merge })
  });
  const payload = await parseJson<{ presets: PresetRecord[] }>(response);
  return payload.presets;
}

export async function exportPresetsFromServer(): Promise<{ exported_at: string; presets: PresetRecord[] }> {
  const response = await fetch(sourceApi("/presets/export"));
  return parseJson<{ exported_at: string; presets: PresetRecord[] }>(response);
}

export async function getSources(): Promise<SourceProfile[]> {
  const response = await fetch(`${baseUrl}/v2/sources`);
  const payload = await parseJson<{ sources: SourceProfile[] }>(response);
  return payload.sources;
}

export async function getSourceHealth(sourceId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${baseUrl}/v2/sources/${sourceId}/health`);
  return parseJson<Record<string, unknown>>(response);
}

export interface LoadBatchRow {
  batch_id: string;
  source_id: number;
  domain: string | null;
  file_name: string | null;
  status: string;
  records_inserted: number | null;
  records_read: number | null;
  records_skipped: number | null;
  records_error: number | null;
  started_at: string | null;
  completed_at: string | null;
  source_code: string | null;
  source_name: string | null;
}

export async function getLoadBatches(limit = 50): Promise<LoadBatchRow[]> {
  const response = await fetch(sourceApi(`/admin/load-batches?limit=${limit}`));
  const payload = await parseJson<{ rows: LoadBatchRow[] }>(response);
  return payload.rows;
}

export async function getValidationErrors(batchId?: string, limit = 100): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (batchId !== undefined) params.set("batch_id", String(batchId));
  const response = await fetch(sourceApi(`/admin/validation-errors?${params.toString()}`));
  const payload = await parseJson<{ rows: Record<string, unknown>[] }>(response);
  return payload.rows;
}

export async function getDataFreshness(): Promise<Record<string, unknown>[]> {
  const response = await fetch(sourceApi("/admin/freshness"));
  const payload = await parseJson<{ rows: Record<string, unknown>[] }>(response);
  return payload.rows;
}

export async function getPrimarySources(domain?: string): Promise<Record<string, unknown>[]> {
  const query = domain ? `?domain=${encodeURIComponent(domain)}` : "";
  const response = await fetch(sourceApi(`/admin/primary-sources${query}`));
  const payload = await parseJson<{ rows: Record<string, unknown>[] }>(response);
  return payload.rows;
}

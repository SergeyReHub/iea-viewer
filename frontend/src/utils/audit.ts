import { sendAuditEvent } from "../services/api";

export type AuditEventType =
  | "app_open"
  | "page_view"
  | "audit_open"
  | "source_switch"
  | "report_build"
  | "report_export"
  | "preset_apply"
  | "preset_create"
  | "preset_update"
  | "preset_delete"
  | "filter_reset"
  | "guide_build"
  | "guide_export"
  | "guide_template_download"
  | "raw_stats_load"
  | "raw_stats_export"
  | "raw_drilldown"
  | "reference_table_open"
  | "reference_preview"
  | "admin_view"
  | "admin_validation_errors"
  | "etl_open";

export const AUDIT_EVENT_LABELS: Record<AuditEventType, string> = {
  app_open: "Открытие приложения",
  page_view: "Просмотр страницы",
  audit_open: "Просмотр журнала аудита",
  source_switch: "Смена источника",
  report_build: "Построение отчёта",
  report_export: "Экспорт отчёта в Excel",
  preset_apply: "Применение пресета",
  preset_create: "Создание пресета",
  preset_update: "Обновление пресета",
  preset_delete: "Удаление пресета",
  filter_reset: "Сброс фильтров",
  guide_build: "Формирование мастер-справки",
  guide_export: "Экспорт мастер-справки",
  guide_template_download: "Скачивание шаблона ТЗ",
  raw_stats_load: "Загрузка статистики сырых данных",
  raw_stats_export: "Экспорт статистики в Excel",
  raw_drilldown: "Детализация ячейки статистики",
  reference_table_open: "Открытие справочника",
  reference_preview: "Просмотр данных справочника",
  admin_view: "Просмотр ETL",
  admin_validation_errors: "Просмотр ошибок валидации",
  etl_open: "Переход на страницу ETL"
};

const SESSION_KEY = "iea_viewer_session_id";

export function getAuditSessionId(): string {
  if (typeof window === "undefined") {
    return "server";
  }
  const existing = window.localStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }
  const created = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(SESSION_KEY, created);
  return created;
}

export interface AuditEventOptions {
  page_path?: string;
  page_name?: string;
  details?: Record<string, unknown>;
}

export function formatAuditEventType(eventType: string): string {
  return AUDIT_EVENT_LABELS[eventType as AuditEventType] ?? eventType;
}

export function formatAuditDetails(details: Record<string, unknown> | null | undefined): string {
  if (!details || !Object.keys(details).length) {
    return "";
  }
  return Object.entries(details)
    .map(([key, value]) => {
      if (value === null || value === undefined || value === "") {
        return "";
      }
      if (typeof value === "object") {
        return `${key}: ${JSON.stringify(value)}`;
      }
      return `${key}: ${String(value)}`;
    })
    .filter(Boolean)
    .join("; ");
}

export async function logAuditEvent(
  eventType: AuditEventType,
  options: AuditEventOptions = {}
): Promise<void> {
  const pagePath =
    options.page_path ??
    (typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/");
  try {
    await sendAuditEvent({
      event_type: eventType,
      page_path: pagePath,
      page_name: options.page_name,
      session_id: getAuditSessionId(),
      details: options.details
    });
  } catch {
    // audit should not break user actions
  }
}

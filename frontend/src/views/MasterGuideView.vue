<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { utils, writeFileXLSX } from "xlsx";
import {
  buildMasterGuideTable,
  getMasterFilterOptions,
  getMasterGuideTemplates,
  getMasterGuideTzTemplateUrl,
  type MasterGuideTableResponse
} from "../services/api";
import { logAuditEvent } from "../utils/audit";

type GuideDomain = "Нефть" | "Газ" | "Уголь" | "Электроэнергия";

interface GuideTemplate {
  id: string;
  domain: GuideDomain;
  title: string;
}

interface CountryOption {
  code: string;
  name: string;
  depth: number;
}

interface CountryHierarchyNode {
  code: string;
  name: string;
  parent_code: string | null;
}

const selectedDomain = ref<GuideDomain>("Нефть");
const selectedCountryCode = ref("");
const loading = ref(false);
const globalError = ref("");
const reportsByTemplateId = ref<Record<string, MasterGuideTableResponse>>({});
const errorsByTemplateId = ref<Record<string, string>>({});
const countryOptions = ref<CountryOption[]>([]);
const countryOptionsLoading = ref(false);
const countryModalOpen = ref(false);
const countrySearchQuery = ref("");

const templates = ref<GuideTemplate[]>([]);

const domainOptions: GuideDomain[] = ["Нефть", "Газ", "Уголь", "Электроэнергия"];

function mapGuideDomain(apiDomain: string): GuideDomain {
  if (apiDomain === "gas") return "Газ";
  if (apiDomain === "coal") return "Уголь";
  if (apiDomain === "electricity") return "Электроэнергия";
  return "Нефть";
}
const filteredTemplates = computed(() => templates.value.filter((item) => item.domain === selectedDomain.value));
const visibleTemplates = computed(() => {
  if (!Object.keys(reportsByTemplateId.value).length) {
    return filteredTemplates.value;
  }
  return filteredTemplates.value.filter((item) => !isGuideTableEmpty(reportsByTemplateId.value[item.id]));
});
const countryFilterKeys = ["country_code", "reporter_code"] as const;
const selectedCountryName = computed(
  () => countryOptions.value.find((item) => item.code === selectedCountryCode.value)?.name ?? selectedCountryCode.value
);
const filteredCountryOptions = computed(() => {
  const query = countrySearchQuery.value.trim().toLowerCase();
  if (!query) {
    return countryOptions.value;
  }
  return countryOptions.value.filter(
    (item) => item.name.toLowerCase().includes(query) || item.code.toLowerCase().includes(query)
  );
});
const canExport = computed(() => visibleTemplates.value.some((template) => Boolean(reportsByTemplateId.value[template.id])));
const oneDecimalGuideTableIds = new Set<string>([
  "oil-oecd-crude-production-tonnes",
  "oil-nonoecd-crude-production-tonnes",
  "oil-oecd-crude-import",
  "oil-oecd-crude-export",
  "oil-oecd-oil-import-by-partners",
  "oil-oecd-oil-export-by-partners",
  "oil-oecd-crude-field-production",
  "oil-oecd-refinery-throughput",
  "oil-oecd-products-production",
  "oil-oecd-products-production-structure",
  "oil-oecd-products-export",
  "oil-oecd-products-import",
  "oil-oecd-products-consumption",
  "oil-nonoecd-products-consumption",
  "oil-nonoecd-products-production",
  "oil-oecd-products-consumption-by-sector",
  "oil-oecd-products-import-by-partners",
  "oil-oecd-products-export-by-partners",
  "gas-oecd-production",
  "gas-nonoecd-production",
  "gas-oecd-consumption",
  "gas-nonoecd-consumption",
  "gas-oecd-import",
  "gas-oecd-export",
  "gas-nonoecd-import",
  "gas-nonoecd-export",
  "gas-import-by-partners",
  "gas-export-by-partners"
]);

function formatCell(value: unknown, tableId: string): string {
  if (value === null || value === undefined || value === "") return "";
  const numeric = typeof value === "number" ? value : typeof value === "string" ? Number(value) : Number.NaN;
  if (Number.isFinite(numeric)) {
    return oneDecimalGuideTableIds.has(tableId) ? numeric.toFixed(1) : numeric.toFixed(3);
  }
  return String(value);
}

function isEmptyGuideCell(value: unknown): boolean {
  return value === null || value === undefined || value === "";
}

function isGuideTableEmpty(report: MasterGuideTableResponse | undefined): boolean {
  if (!report?.rows?.length) {
    return true;
  }
  const valueColumns = report.columns.filter((column) => column !== "Показатель");
  if (!valueColumns.length) {
    return true;
  }
  return report.rows.every((row) => valueColumns.every((column) => isEmptyGuideCell(row[column])));
}

function sanitizeFilePart(value: string): string {
  return value
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
}

function buildSheetName(base: string, index: number, used: Set<string>): string {
  const numberedBase = `${index + 1}_${base}`.slice(0, 31);
  let candidate = numberedBase;
  let suffix = 1;
  while (used.has(candidate)) {
    const suffixLabel = `_${suffix}`;
    candidate = `${numberedBase.slice(0, Math.max(0, 31 - suffixLabel.length))}${suffixLabel}`;
    suffix += 1;
  }
  used.add(candidate);
  return candidate;
}

function exportDomainReportsToExcel(): void {
  const workbook = utils.book_new();
  const usedSheetNames = new Set<string>();
  const templatesToExport = visibleTemplates.value.filter((template) => reportsByTemplateId.value[template.id]);
  if (!templatesToExport.length) {
    return;
  }

  for (let index = 0; index < templatesToExport.length; index += 1) {
    const template = templatesToExport[index];
    const report = reportsByTemplateId.value[template.id];
    if (!report) continue;
    const sheetData = [
      report.columns,
      ...report.rows.map((row) => report.columns.map((column) => row[column] ?? ""))
    ];
    const worksheet = utils.aoa_to_sheet(sheetData);
    worksheet["!autofilter"] = { ref: utils.encode_range({ s: { c: 0, r: 0 }, e: { c: report.columns.length - 1, r: Math.max(0, report.rows.length) } }) };
    worksheet["!cols"] = report.columns.map((column) => {
      const maxLen = Math.max(
        String(column).length,
        ...report.rows.map((row) => String(row[column] ?? "").length)
      );
      return { wch: Math.min(42, Math.max(12, maxLen + 2)) };
    });
    const safeBase = sanitizeFilePart(template.title) || `table_${index + 1}`;
    const sheetName = buildSheetName(safeBase, index, usedSheetNames);
    utils.book_append_sheet(workbook, worksheet, sheetName);
  }

  const domainPartMap: Record<GuideDomain, string> = {
    "Нефть": "oil",
    "Газ": "gas",
    "Уголь": "coal",
    "Электроэнергия": "electricity"
  };
  const domainPart = domainPartMap[selectedDomain.value] ?? "guide";
  const countryPart = sanitizeFilePart(selectedCountryName.value || selectedCountryCode.value || "country");
  writeFileXLSX(workbook, `master_guide_${domainPart}_${countryPart}.xlsx`);
  void logAuditEvent("guide_export", {
    details: {
      domain: selectedDomain.value,
      country: selectedCountryCode.value,
      sheets: templatesToExport.length
    }
  });
}

function downloadTzTemplate(): void {
  const url = getMasterGuideTzTemplateUrl();
  window.open(url, "_blank", "noopener,noreferrer");
  void logAuditEvent("guide_template_download");
}

function formatCountryOptionLabel(option: CountryOption): string {
  if (option.depth <= 0) {
    return option.name;
  }
  return `${"\u00A0\u00A0".repeat(option.depth)}↳ ${option.name}`;
}

function getCountryDepthStyle(option: CountryOption): Record<string, string> {
  return {
    paddingLeft: `${10 + option.depth * 18}px`
  };
}

function openCountryModal(): void {
  if (countryOptionsLoading.value) return;
  countrySearchQuery.value = "";
  countryModalOpen.value = true;
}

function closeCountryModal(): void {
  countryModalOpen.value = false;
}

function selectCountry(code: string): void {
  selectedCountryCode.value = code;
  countryModalOpen.value = false;
}

function buildHierarchicalCountryOptions(nodes: CountryHierarchyNode[]): CountryOption[] {
  const childrenByParent = new Map<string | null, CountryHierarchyNode[]>();
  for (const node of nodes) {
    const parentKey = node.parent_code ?? null;
    const bucket = childrenByParent.get(parentKey) ?? [];
    bucket.push(node);
    childrenByParent.set(parentKey, bucket);
  }
  for (const bucket of childrenByParent.values()) {
    bucket.sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }

  const result: CountryOption[] = [];
  const visited = new Set<string>();
  const walk = (parentCode: string | null, depth: number): void => {
    const children = childrenByParent.get(parentCode) ?? [];
    for (const child of children) {
      if (visited.has(child.code)) continue;
      visited.add(child.code);
      result.push({ code: child.code, name: child.name, depth });
      walk(child.code, depth + 1);
    }
  };

  walk(null, 0);

  const orphans = nodes
    .filter((node) => !visited.has(node.code))
    .sort((a, b) => a.name.localeCompare(b.name, "ru"));
  for (const orphan of orphans) {
    if (visited.has(orphan.code)) continue;
    visited.add(orphan.code);
    result.push({ code: orphan.code, name: orphan.name, depth: 0 });
    walk(orphan.code, 1);
  }

  return result;
}

async function buildDomainReports(): Promise<void> {
  loading.value = true;
  globalError.value = "";
  reportsByTemplateId.value = {};
  errorsByTemplateId.value = {};
  for (const template of filteredTemplates.value) {
    try {
      const payload = await buildMasterGuideTable(template.id, selectedCountryCode.value);
      if (!isGuideTableEmpty(payload)) {
        reportsByTemplateId.value = {
          ...reportsByTemplateId.value,
          [template.id]: payload
        };
      }
    } catch (err) {
      errorsByTemplateId.value = {
        ...errorsByTemplateId.value,
        [template.id]: err instanceof Error ? err.message : "Не удалось сформировать таблицу"
      };
    }
  }
  if (!Object.keys(reportsByTemplateId.value).length) {
    globalError.value = "Не удалось сформировать таблицы выбранного домена";
  } else {
    void logAuditEvent("guide_build", {
      details: {
        domain: selectedDomain.value,
        country: selectedCountryCode.value,
        templates: Object.keys(reportsByTemplateId.value).length
      }
    });
  }
  loading.value = false;
}

watch(selectedDomain, () => {
  reportsByTemplateId.value = {};
  errorsByTemplateId.value = {};
  globalError.value = "";
});

watch(selectedCountryCode, () => {
  reportsByTemplateId.value = {};
  errorsByTemplateId.value = {};
  globalError.value = "";
});

onMounted(async () => {
  try {
    const normalizedTemplates: GuideTemplate[] = [];
    for (const apiDomain of ["oil", "gas", "coal", "electricity"] as const) {
      const items = await getMasterGuideTemplates(apiDomain);
      for (const item of items) {
        normalizedTemplates.push({
          id: item.id,
          title: item.title,
          domain: mapGuideDomain(item.domain)
        });
      }
    }
    templates.value = normalizedTemplates;
  } catch {
    globalError.value = "Не удалось загрузить шаблоны мастер-справки";
  }

  countryOptionsLoading.value = true;
  try {
    const candidateFactTables = [
      "oil.fact_oil_balance",
      "oil.fact_oil_trade",
      "gas.fact_gas_balance",
      "gas.fact_gas_trade",
      "coal.fact_coal_balance",
      "electricity.fact_electricity_balance"
    ];
    for (const factTable of candidateFactTables) {
      try {
        const payload = await getMasterFilterOptions(factTable, {});
        const countryFilter = payload.filters.find((filter) =>
          countryFilterKeys.includes(filter.key as (typeof countryFilterKeys)[number])
        );
        if (!countryFilter?.nodes?.length) {
          continue;
        }
        const options = countryFilter.nodes
          .map((node) => ({
            code: String(node.code),
            name: String(node.name ?? node.code),
            parent_code: node.parent_code ? String(node.parent_code) : null
          }))
          .filter((item) => item.code);
        if (options.length) {
          countryOptions.value = buildHierarchicalCountryOptions(options);
          break;
        }
      } catch {
        // continue with next candidate table
      }
    }
  } finally {
    countryOptionsLoading.value = false;
  }
});
</script>

<template>
  <section class="page-card">
    <div class="page-head">
      <h2>Мастер-справка (нефть, газ, уголь, электроэнергия)</h2>
      <p>Самостоятельные таблицы по шаблонам мастер-справки без перехода в «Мастер отчетов».</p>
    </div>

    <div class="toolbar">
      <div class="toolbar-main-filters">
        <label class="field">
          Домен:
          <select v-model="selectedDomain">
            <option v-for="domain in domainOptions" :key="domain" :value="domain">{{ domain }}</option>
          </select>
        </label>
        <label class="field">
          Страна:
          <button class="btn btn-secondary" type="button" :disabled="countryOptionsLoading" @click="openCountryModal">
            {{
              countryOptionsLoading
                ? "Загрузка стран..."
                : selectedCountryCode
                  ? selectedCountryName
                  : "Выбрать страну"
            }}
          </button>
        </label>
        <button class="btn" type="button" :disabled="loading || !selectedCountryCode" @click="buildDomainReports">
          Сформировать
        </button>
        <button class="btn" type="button" :disabled="loading || !canExport" @click="exportDomainReportsToExcel">
          Выгрузить в Excel
        </button>
      </div>
      <div class="toolbar-side">
        <button class="btn btn-secondary" type="button" @click="downloadTzTemplate">
          Скачать шаблон ТЗ
        </button>
      </div>
    </div>

    <section class="master-preset-card">
      <h4>Шаблоны таблиц — {{ selectedDomain }}</h4>
      <div class="guide-template-group">
        <div v-for="item in visibleTemplates" :key="item.id" class="guide-template-item guide-template-item-column">
          <strong>{{ item.title }}</strong>
          <p v-if="errorsByTemplateId[item.id]" class="error">{{ errorsByTemplateId[item.id] }}</p>
          <template v-else-if="reportsByTemplateId[item.id]">
            <p class="muted">Найдено строк: {{ reportsByTemplateId[item.id].rows.length }}</p>
            <div class="table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th v-for="column in reportsByTemplateId[item.id].columns" :key="`guide-col-${item.id}-${column}`">
                      {{ column }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rowIndex) in reportsByTemplateId[item.id].rows" :key="`guide-row-${item.id}-${rowIndex}`">
                    <td
                      v-for="column in reportsByTemplateId[item.id].columns"
                      :key="`guide-cell-${item.id}-${rowIndex}-${column}`"
                      :class="{ 'guide-empty-cell': column !== 'Показатель' && isEmptyGuideCell(row[column]) }"
                    >
                      {{ formatCell(row[column], item.id) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>
    </section>

    <div v-if="loading" class="loading-inline">
      <span class="spinner"></span>
      <span>Формирование таблиц...</span>
    </div>
    <p v-else-if="globalError" class="error">{{ globalError }}</p>

    <div v-if="countryModalOpen" class="country-picker-backdrop" @click.self="closeCountryModal">
      <section class="country-picker-modal">
        <div class="modal-header">
          <h3>Выберите страну</h3>
          <button class="btn btn-secondary" type="button" @click="closeCountryModal">Закрыть</button>
        </div>
        <input
          v-model="countrySearchQuery"
          class="hierarchy-search"
          type="text"
          placeholder="Поиск по коду или названию..."
        />
        <div class="country-picker-list">
          <button
            v-for="country in filteredCountryOptions"
            :key="country.code"
            type="button"
            class="country-picker-item"
            :class="{ 'country-picker-item-active': country.code === selectedCountryCode }"
            @click="selectCountry(country.code)"
          >
            <span class="country-picker-item-main" :style="getCountryDepthStyle(country)">
              {{ country.name }}
            </span>
          </button>
          <p v-if="!filteredCountryOptions.length" class="empty-state">Ничего не найдено</p>
        </div>
      </section>
    </div>
  </section>
</template>

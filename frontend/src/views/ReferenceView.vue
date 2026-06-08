<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { marked } from "marked";
import type { Domain, TableMeta } from "../services/api";
import { getDomains, getReferenceData, getTableDoc, getTables } from "../services/api";
import { logAuditEvent } from "../utils/audit";

const domains = ref<Domain[]>([]);
const selectedDomain = ref<Domain>("base");
const tables = ref<TableMeta[]>([]);
const loading = ref(false);
const error = ref("");
const selectedTable = ref<string>("");
const docLoading = ref(false);
const docError = ref("");
const markdown = ref("");
const previewLoading = ref(false);
const previewError = ref("");
const searchQuery = ref("");
const selectedReferenceIndex = ref(0);
const selectedFieldFilters = ref<Array<{ key: string; value: string }>>([]);
const previewColumns = ref<string[]>([]);
const previewRows = ref<Record<string, unknown>[]>([]);

const htmlDoc = computed(() => marked.parse(markdown.value) as string);
const selectedTableMeta = computed(
  () => tables.value.find((item) => item.table === selectedTable.value) ?? null
);
const TECHNICAL_COLUMNS = new Set(["id", "created_at", "updated_at", "load_batch_id"]);
const COLUMN_LABELS: Record<string, string> = {
  country_code: "Код страны",
  country_name_ru: "Страна (рус.)",
  country_name: "Страна",
  new_code: "Актуальный код",
  country_type: "Тип записи",
  parent_code: "Родительская группа",
  iso2_code: "ISO-2",
  iso3_code: "ISO-3",
  un_code: "UN код",
  is_aggregate: "Агрегат",
  is_oecd: "OECD",
  is_iea_member: "Член IEA",
  is_eu_member: "Член ЕС",
  is_g20_member: "Член G20",
  fiscal_year_start: "Начало фискального года",
  unit_code: "Код единицы",
  unit_name_ru: "Единица (рус.)",
  unit_name: "Единица",
  unit_symbol: "Обозначение",
  unit_type: "Тип единицы",
  unit_category: "Категория",
  base_unit: "Базовая единица",
  conversion_factor: "Коэффициент пересчета",
  decimals: "Точность",
  frequency_code: "Код периодичности",
  frequency_name_ru: "Периодичность (рус.)",
  frequency_name: "Периодичность",
  source_id: "ID источника",
  source_code: "Код источника",
  source_name: "Источник",
  source_type: "Тип источника",
  source_url: "Ссылка",
  domain: "Домен",
  version: "Версия",
  is_primary: "Основной источник",
  flow_code: "Код потока",
  flow_name_ru: "Поток (рус.)",
  flow_name: "Поток",
  flow_category: "Категория потока",
  flow_group: "Группа потока",
  is_input: "Входящий поток",
  sign_convention: "Знак",
  applicable_domains: "Применимые домены",
  process_code: "Код процесса",
  process_name: "Процесс",
  process_type: "Тип процесса",
  input_products: "Входные продукты",
  output_products: "Выходные продукты",
  typical_efficiency: "Типичный КПД",
  sector_code: "Код сектора",
  sector_name_ru: "Сектор (рус.)",
  sector_name: "Сектор",
  sector_category: "Категория сектора",
  isic_division: "ISIC",
  reporting_type_code: "Код типа отчетности",
  reporting_type_name_ru: "Тип отчетности (рус.)",
  reporting_type_name: "Тип отчетности",
  product_code: "Код продукта",
  product_name_ru: "Продукт (рус.)",
  product_name: "Продукт",
  product_group: "Группа продукта",
  alias_code: "Альтернативный код",
  canonical_code: "Канонический код",
  field_code: "Код месторождения",
  field_name: "Месторождение",
  country: "Страна",
  group_code: "Код группы",
  group_name: "Группа",
  product: "Продукт",
  environment: "Среда",
  product_category: "Категория продукта",
  ncv_flow_code: "Код NCV-потока",
  ncv_flow_name_ru: "NCV-поток (рус.)",
  ncv_flow_name: "NCV-поток",
  corresponding_flow: "Связанный поток"
};
const TABLE_PREFERRED_COLUMNS: Record<string, string[]> = {
  ref_country: [
    "country_code",
    "country_name_ru",
    "country_name",
    "country_type",
    "parent_code",
    "is_aggregate",
    "is_oecd",
    "is_iea_member",
    "is_eu_member",
    "is_g20_member"
  ],
  ref_unit: [
    "unit_code",
    "unit_name_ru",
    "unit_name",
    "unit_symbol",
    "unit_type",
    "unit_category",
    "base_unit",
    "conversion_factor"
  ],
  ref_frequency: ["frequency_code", "frequency_name_ru", "frequency_name"],
  ref_data_source: ["source_code", "source_name", "domain", "source_type", "version", "is_primary"],
  ref_energy_flow: ["flow_code", "flow_name_ru", "flow_name", "flow_category", "flow_group", "parent_code"],
  ref_transformation_process: ["process_code", "process_name", "process_type", "typical_efficiency"],
  ref_sector: ["sector_code", "sector_name_ru", "sector_name", "sector_category", "parent_code", "isic_division"],
  ref_reporting_type: ["reporting_type_code", "reporting_type_name_ru", "reporting_type_name"],
  "oil.ref_oil_product": ["product_code", "product_name_ru", "product_name", "parent_code"],
  "oil.ref_oil_product_alias": ["alias_code", "canonical_code", "product_name_ru", "product_name"],
  "oil.ref_oil_field": ["field_code", "field_name", "country", "group_name", "environment"],
  "gas.ref_gas_product": ["product_code", "product_name_ru", "product_name", "parent_code"],
  "coal.ref_coal_product": ["product_code", "product_name_ru", "product_name", "product_category", "parent_code"],
  "coal.ref_coal_ncv_flow": [
    "ncv_flow_code",
    "ncv_flow_name_ru",
    "ncv_flow_name",
    "corresponding_flow",
    "parent_code"
  ]
};
const normalizedTableName = computed(() =>
  selectedTable.value.includes(".") ? selectedTable.value.split(".")[1] : selectedTable.value
);
const referenceColumns = computed(() => {
  if (!previewRows.value.length) return [];
  const available = previewColumns.value.length
    ? previewColumns.value
    : Object.keys(previewRows.value[0] ?? {});
  const preferred =
    TABLE_PREFERRED_COLUMNS[selectedTable.value] ??
    TABLE_PREFERRED_COLUMNS[normalizedTableName.value] ??
    [];
  const visibleAvailable = available.filter((column) => !TECHNICAL_COLUMNS.has(column));
  const preferredExisting = preferred.filter((column) => visibleAvailable.includes(column));
  return preferredExisting.length ? preferredExisting : visibleAvailable;
});
const filteredReferenceRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return previewRows.value.filter((row) => {
    const queryMatch =
      !query ||
      referenceColumns.value.some((column) =>
        formatReferenceValue(row[column]).toLowerCase().includes(query)
      );
    if (!queryMatch) return false;
    if (!selectedFieldFilters.value.length) return true;
    return selectedFieldFilters.value.every(
      (filter) => formatReferenceValue(row[filter.key]) === filter.value
    );
  });
});
const selectedReferenceRow = computed(
  () => filteredReferenceRows.value[selectedReferenceIndex.value] ?? null
);
const selectedFieldFilterChips = computed(() =>
  selectedFieldFilters.value.map((filter) => ({
    ...filter,
    id: `${filter.key}:${filter.value}`,
    label: `${getColumnLabel(filter.key)}: ${filter.value}`
  }))
);
const selectedReferenceFields = computed(() => {
  if (!selectedReferenceRow.value) return [];
  return referenceColumns.value.map((column) => ({
    key: column,
    label: getColumnLabel(column),
    value: formatReferenceValue(selectedReferenceRow.value?.[column]),
    active: selectedFieldFilters.value.some(
      (filter) =>
        filter.key === column && filter.value === formatReferenceValue(selectedReferenceRow.value?.[column])
    )
  }));
});

function formatReferenceValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function getColumnLabel(column: string): string {
  if (COLUMN_LABELS[column]) return COLUMN_LABELS[column];
  return column.replace(/_/g, " ");
}

function onCardFieldClick(fieldKey: string, value: string): void {
  if (value === "—") return;
  const exists = selectedFieldFilters.value.some(
    (item) => item.key === fieldKey && item.value === value
  );
  if (exists) {
    selectedFieldFilters.value = selectedFieldFilters.value.filter(
      (item) => !(item.key === fieldKey && item.value === value)
    );
    return;
  }
  selectedFieldFilters.value = [...selectedFieldFilters.value, { key: fieldKey, value }];
}

function removeCardFilter(filterKey: string, filterValue: string): void {
  selectedFieldFilters.value = selectedFieldFilters.value.filter(
    (item) => !(item.key === filterKey && item.value === filterValue)
  );
}

async function loadDomains(): Promise<void> {
  domains.value = await getDomains();
  if (!domains.value.includes(selectedDomain.value)) {
    selectedDomain.value = domains.value[0] ?? "base";
  }
}

async function loadTables(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    tables.value = [
      ...(await getTables(selectedDomain.value, "ref")),
      ...(selectedDomain.value === "base" || ["oil", "gas", "coal", "electricity"].includes(selectedDomain.value)
        ? await getTables(selectedDomain.value, "map")
        : [])
    ];
    selectedTable.value = tables.value[0]?.table ?? "";
    await loadTableDoc();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не удалось загрузить справочники";
  } finally {
    loading.value = false;
  }
}

async function loadTableDoc(): Promise<void> {
  if (!selectedTable.value) {
    markdown.value = "";
    return;
  }

  docLoading.value = true;
  docError.value = "";
  try {
    const payload = await getTableDoc(selectedDomain.value, selectedTable.value);
    markdown.value = payload.markdown;
  } catch (err) {
    docError.value = err instanceof Error ? err.message : "Не удалось загрузить описание";
    markdown.value = "";
  } finally {
    docLoading.value = false;
  }
}

async function loadPreview(): Promise<void> {
  if (!selectedTable.value) {
    previewColumns.value = [];
    previewRows.value = [];
    return;
  }

  previewLoading.value = true;
  previewError.value = "";
  searchQuery.value = "";
  selectedFieldFilters.value = [];
  selectedReferenceIndex.value = 0;
  try {
    const payload = await getReferenceData(selectedDomain.value, selectedTable.value);
    previewColumns.value = payload.columns;
    previewRows.value = payload.rows;
    void logAuditEvent("reference_preview", {
      details: {
        domain: selectedDomain.value,
        table: selectedTable.value,
        rows: payload.rows.length,
        columns: payload.columns.length
      }
    });
  } catch (err) {
    previewError.value = err instanceof Error ? err.message : "Не удалось загрузить preview";
    previewColumns.value = [];
    previewRows.value = [];
  } finally {
    previewLoading.value = false;
  }
}

watch(selectedDomain, async () => {
  await loadTables();
});

watch(selectedTable, async () => {
  await loadTableDoc();
  await loadPreview();
});

watch(filteredReferenceRows, (rows) => {
  if (!rows.length) {
    selectedReferenceIndex.value = 0;
    return;
  }
  if (selectedReferenceIndex.value >= rows.length) {
    selectedReferenceIndex.value = 0;
  }
});

onMounted(async () => {
  await loadDomains();
  await loadTables();
});
</script>

<template>
  <section class="page-card">
    <div class="page-head">
      <h2>Справочники</h2>
      <p>Выберите таблицу из списка слева, чтобы открыть полное описание.</p>
    </div>

    <div class="toolbar">
      <label class="field">
        Домен:
        <select v-model="selectedDomain">
          <option v-for="domain in domains" :key="domain" :value="domain">
            {{ domain }}
          </option>
        </select>
      </label>
    </div>

    <div class="content-grid">
      <div>
        <div v-if="loading" class="loading-inline">
          <span class="spinner"></span>
          <span>Загрузка...</span>
        </div>
        <p v-else-if="error" class="error">{{ error }}</p>
        <ul v-else class="table-list">
          <li v-for="table in tables" :key="table.table">
            <button
              type="button"
              class="table-link"
              :class="{ active: selectedTable === table.table }"
              @click="selectedTable = table.table"
            >
              <span>{{ table.display_name ?? table.table }}</span>
              <span class="muted">{{ table.description }}</span>
            </button>
          </li>
        </ul>
      </div>

      <article class="md-card">
        <div v-if="docLoading" class="loading-inline">
          <span class="spinner"></span>
          <span>Загрузка описания...</span>
        </div>
        <p v-else-if="docError" class="error">{{ docError }}</p>
        <div v-else class="md-content" v-html="htmlDoc"></div>
      </article>
    </div>

    <div class="preview">
      <h3>Справочная информация: {{ selectedTableMeta?.display_name ?? selectedTable }}</h3>
      <div v-if="previewLoading" class="loading-inline">
        <span class="spinner"></span>
        <span>Загрузка preview...</span>
      </div>
      <p v-else-if="previewError" class="error">{{ previewError }}</p>
      <p v-else class="muted">Записей: {{ filteredReferenceRows.length }}</p>
      <div class="toolbar">
        <label class="field">
          Поиск по справочнику:
          <input v-model="searchQuery" type="text" placeholder="Введите текст для фильтрации..." />
        </label>
        <div v-if="selectedFieldFilterChips.length" class="active-card-filter">
          <span v-for="chip in selectedFieldFilterChips" :key="chip.id" class="chip">
            {{ chip.label }}
            <button
              type="button"
              class="chip-close"
              aria-label="Удалить фильтр"
              @click="removeCardFilter(chip.key, chip.value)"
            >
              ×
            </button>
          </span>
        </div>
      </div>

      <div v-if="filteredReferenceRows.length" class="reference-layout">
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th v-for="column in referenceColumns" :key="column">{{ getColumnLabel(column) }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) in filteredReferenceRows"
                :key="index"
                class="reference-row"
                :class="{ 'reference-row-active': selectedReferenceIndex === index }"
                @click="selectedReferenceIndex = index"
              >
                <td v-for="column in referenceColumns" :key="column">
                  {{ formatReferenceValue(row[column]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <aside class="reference-details">
          <h4>Карточка записи</h4>
          <div v-if="selectedReferenceRow" class="reference-details-grid">
            <div v-for="field in selectedReferenceFields" :key="field.key" class="reference-detail-item">
              <div class="reference-detail-label">{{ field.label }}</div>
              <button
                type="button"
                class="reference-detail-value reference-detail-btn"
                :class="{ 'reference-detail-btn-active': field.active }"
                @click="onCardFieldClick(field.key, field.value)"
              >
                {{ field.value }}
              </button>
            </div>
          </div>
          <p v-else class="muted">Выберите строку в таблице слева.</p>
        </aside>
      </div>
      <p v-else-if="!previewLoading && !previewError" class="muted">По текущему фильтру записей нет.</p>
    </div>
  </section>
</template>

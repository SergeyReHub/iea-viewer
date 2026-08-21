<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { utils, writeFileXLSX } from "xlsx";
import HierarchyChecklist from "../components/HierarchyChecklist.vue";
import {
  buildIndicatorLabelGroups,
  mapIndicatorShortLabels
} from "../utils/indicatorLabels";
import { logAuditEvent } from "../utils/audit";
import {
  buildMasterReport,
  createPreset as createPresetOnServer,
  deletePreset as deletePresetOnServer,
  getMasterFilterOptions,
  getMasterHierarchies,
  getPresets,
  importPresetsToServer,
  updatePreset as updatePresetOnServer,
  type PresetMutationPayload,
  type MasterFilterDefinition,
  type MasterReportResponse
} from "../services/api";

const loading = ref(false);
const error = ref("");

const availableFilters = ref<MasterFilterDefinition[]>([]);
const activeFilterKey = ref("");
const selectedFilterValues = ref<Record<string, string[]>>({});
const factTables = ref<{ table: string; label: string; description: string }[]>([]);
const selectedFactTable = ref("oil.fact_oil_balance");
const pivotLayout = ref<"time_rows_filters_columns" | "time_columns_filters_rows">(
  "time_columns_filters_rows"
);

const reportLoading = ref(false);
const reportError = ref("");
const report = ref<MasterReportResponse | null>(null);
const reportPivotLayout = ref<"time_rows_filters_columns" | "time_columns_filters_rows">(
  "time_rows_filters_columns"
);
const reportLimit = ref(2000);
const filtersLoading = ref(false);
const periodFrom = ref("");
const periodTo = ref("");
const periodSort = ref<"asc" | "desc">("asc");
const showRowTotals = ref(false);
const showColumnTotals = ref(false);

interface FilterPreset {
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

interface GuideTableTemplate {
  id: string;
  group: "Нефть" | "Газ";
  title: string;
  description: string;
  factTable: string;
  selectedFilterValues: Record<string, string[]>;
  pivotLayout?: "time_rows_filters_columns" | "time_columns_filters_rows";
  periodFrom?: string;
  periodTo?: string;
  periodSort?: "asc" | "desc";
}

const GUIDE_TABLE_TEMPLATES: GuideTableTemplate[] = [
  {
    id: "oil-oecd-crude-production-tonnes",
    group: "Нефть",
    title: "Добыча нефтяного сырья в стране ОЭСР, (тыс. тонн)",
    description: "Месячная динамика добычи в странах ОЭСР.",
    factTable: "oil.fact_oil_crude_supply",
    selectedFilterValues: { flow_code: ["INDPROD"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-nonoecd-crude-production-tonnes",
    group: "Нефть",
    title: "Добыча нефтяного сырья в стране не-ОЭСР, (тыс. тонн)",
    description: "Годовая добыча в странах не-ОЭСР.",
    factTable: "oil.fact_oil_crude_supply",
    selectedFilterValues: { flow_code: ["INDPROD"], frequency_code: ["A"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-nonoecd-crude-bpd",
    group: "Нефть",
    title: "Добыча нефтяного сырья в стране не-ОЭСР, (тыс. баррелей в день)",
    description: "Добыча/прогноз в баррелях в день.",
    factTable: "oil.fact_oil_world_supply",
    selectedFilterValues: { frequency_code: ["A"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-field-production",
    group: "Нефть",
    title: "Добыча нефти по месторождениям в стране ОЭСР, (тыс. баррелей в день)",
    description: "Добыча по месторождениям.",
    factTable: "oil.fact_oil_field_production",
    selectedFilterValues: { frequency_code: ["A"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-crude-field-production",
    group: "Нефть",
    title: "Добыча нефтяного сырья по месторождениям в стране ОЭСР, (тыс. баррелей в день)",
    description: "Добыча нефтяного сырья по месторождениям.",
    factTable: "oil.fact_oil_field_production",
    selectedFilterValues: { frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-crude-import",
    group: "Нефть",
    title: "Импорт нефтяного сырья в страну ОЭСР, (тыс. тонн)",
    description: "Импорт нефтяного сырья.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-crude-export",
    group: "Нефть",
    title: "Экспорт нефтяного сырья из страны ОЭСР, (тыс. тонн)",
    description: "Экспорт нефтяного сырья.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-oil-import-by-partners",
    group: "Нефть",
    title: "Импорт нефти в страну ОЭСР по направлениям, (тыс. тонн)",
    description: "Структура импорта по странам-партнерам.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-crude-import-by-partners",
    group: "Нефть",
    title: "Импорт нефтяного сырья в страну ОЭСР по направлениям, (тыс. тонн)",
    description: "Структура импорта нефтяного сырья по странам-партнерам.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-oil-export-by-partners",
    group: "Нефть",
    title: "Экспорт нефти из страны ОЭСР по направлениям, (тыс. тонн)",
    description: "Структура экспорта по странам-партнерам.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-crude-export-by-partners",
    group: "Нефть",
    title: "Экспорт нефтяного сырья из страны ОЭСР по направлениям, (тыс. тонн)",
    description: "Структура экспорта нефтяного сырья по странам-партнерам.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-refinery-throughput",
    group: "Нефть",
    title: "Объём первичной переработки нефти в стране ОЭСР, (тыс. тонн)",
    description: "Загрузка/переработка НПЗ.",
    factTable: "oil.fact_oil_refinery_throughput",
    selectedFilterValues: { frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-products-production",
    group: "Нефть",
    title: "Производство нефтепродуктов в стране ОЭСР, (тыс. тонн)",
    description: "Производство нефтепродуктов.",
    factTable: "oil.fact_oil_balance",
    selectedFilterValues: { flow_code: ["REFGROUT"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-products-consumption",
    group: "Нефть",
    title: "Потребление нефтепродуктов в стране ОЭСР, (тыс. тонн)",
    description: "Потребление нефтепродуктов.",
    factTable: "oil.fact_oil_balance",
    selectedFilterValues: { flow_code: ["TOTCONS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-oecd-products-consumption-by-sector",
    group: "Нефть",
    title: "Структура потребления нефтепродуктов в стране ОЭСР, (тыс. тонн)",
    description: "Структура потребления нефтепродуктов по видам.",
    factTable: "oil.fact_oil_balance",
    selectedFilterValues: { frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-products-production-structure",
    group: "Нефть",
    title: "Структура производства нефтепродуктов в стране ОЭСР, (тыс. тонн)",
    description: "Структура производства нефтепродуктов по видам.",
    factTable: "oil.fact_oil_balance",
    selectedFilterValues: { flow_code: ["REFINOUT"], frequency_code: ["M"] }
  },
  {
    id: "oil-oecd-products-export",
    group: "Нефть",
    title: "Экспорт нефтепродуктов из страны ОЭСР, (тыс. тонн)",
    description: "Экспорт нефтепродуктов.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-nonoecd-products-export",
    group: "Нефть",
    title: "Экспорт нефтепродуктов из страны не-ОЭСР, (тыс. тонн)",
    description: "Годовой экспорт нефтепродуктов стран не-ОЭСР.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-products-import",
    group: "Нефть",
    title: "Импорт нефтепродуктов в страну ОЭСР, (тыс. тонн)",
    description: "Импорт нефтепродуктов.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "oil-nonoecd-products-import",
    group: "Нефть",
    title: "Импорт нефтепродуктов в страну не-ОЭСР, (тыс. тонн)",
    description: "Годовой импорт нефтепродуктов стран не-ОЭСР.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-nonoecd-products-consumption",
    group: "Нефть",
    title: "Потребление нефтепродуктов в стране не-ОЭСР, (тыс. тонн)",
    description: "Годовое потребление нефтепродуктов (world supply).",
    factTable: "oil.fact_oil_world_supply",
    selectedFilterValues: { flow_code: ["NETDELIV"], frequency_code: ["A"] }
  },
  {
    id: "oil-nonoecd-products-production",
    group: "Нефть",
    title: "Производство нефтепродуктов в стране не-ОЭСР, (тыс. тонн)",
    description: "Годовое производство нефтепродуктов (world supply).",
    factTable: "oil.fact_oil_world_supply",
    selectedFilterValues: { flow_code: ["REFINOUT"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-products-import-by-partners",
    group: "Нефть",
    title: "Импорт нефтепродуктов в страну ОЭСР по направлениям, (тыс. тонн)",
    description: "Структура импорта нефтепродуктов по партнерам.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["A"] }
  },
  {
    id: "oil-oecd-products-export-by-partners",
    group: "Нефть",
    title: "Экспорт нефтепродуктов из страны ОЭСР по направлениям, (тыс. тонн)",
    description: "Структура экспорта нефтепродуктов по партнерам.",
    factTable: "oil.fact_oil_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "gas-oecd-production",
    group: "Газ",
    title: "Добыча газа в стране ОЭСР, (млрд м³)",
    description: "Месячная добыча газа.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["INDPROD"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "gas-nonoecd-production",
    group: "Газ",
    title: "Добыча газа в стране не-ОЭСР, (млрд м³)",
    description: "Годовая добыча газа в странах не-ОЭСР.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["INDPROD"], frequency_code: ["A"] }
  },
  {
    id: "gas-oecd-import",
    group: "Газ",
    title: "Импорт газа в страну ОЭСР, (млрд м³)",
    description: "Помесячный импорт газа с агрегацией по годам.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["ENTRIES"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "gas-oecd-export",
    group: "Газ",
    title: "Экспорт газа из страны ОЭСР, (млрд м³)",
    description: "Помесячный экспорт газа с агрегацией по годам.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["EXITS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "gas-oecd-export-import",
    group: "Газ",
    title: "Экспорт и импорт газа в стране ОЭСР, (млрд м³)",
    description: "Сводный импорт/экспорт газа.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["IMPORTS", "EXPORTS"], frequency_code: ["M"] },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "gas-oecd-export-import-annual",
    group: "Газ",
    title: "Экспорт и импорт газа в страну ОЭСР, (млрд м³)",
    description: "Годовой импорт/экспорт газа.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["IMPORTS", "EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "gas-nonoecd-import",
    group: "Газ",
    title: "Импорт газа в страну не-ОЭСР, (млрд м³)",
    description: "Годовой импорт газа стран не-ОЭСР.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["A"] }
  },
  {
    id: "gas-nonoecd-export",
    group: "Газ",
    title: "Экспорт газа из страны не-ОЭСР, (млрд м³)",
    description: "Годовой экспорт газа стран не-ОЭСР.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "gas-oecd-consumption",
    group: "Газ",
    title: "Потребление газа в стране ОЭСР, (млрд м³)",
    description: "Потребление газа: годовые данные с 2020 и месячные с 2025-01.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: {
      flow_code: ["GRDEL_INLAND_OBS"],
      unit_code: ["M_M3"],
      frequency_code: ["M"]
    },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "gas-nonoecd-consumption",
    group: "Газ",
    title: "Потребление газа в стране не-ОЭСР, (млрд м³)",
    description: "Годовое потребление газа в странах не-ОЭСР.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: {
      flow_code: ["GRDEL_INLAND_OBS"],
      unit_code: ["M_M3"],
      frequency_code: ["A"]
    }
  },
  {
    id: "gas-import-by-partners",
    group: "Газ",
    title: "Импорт газа в страну ОЭСР по направлениям, (млрд м³)",
    description: "Структура импорта газа по партнерам.",
    factTable: "gas.fact_gas_trade",
    selectedFilterValues: { flow_code: ["IMPORTS"], frequency_code: ["A"] }
  },
  {
    id: "gas-lng-import-by-partners",
    group: "Газ",
    title: "Импорт СПГ в страну ОЭСР по направлениям, (млрд м³)",
    description: "Структура импорта СПГ по партнёрам за последний доступный год.",
    factTable: "gas.fact_gas_trade",
    selectedFilterValues: {
      flow_code: ["IMPORTS"],
      product_code: ["LNG"],
      unit_code: ["M_M3"],
      frequency_code: ["A"]
    }
  },
  {
    id: "gas-export-by-partners",
    group: "Газ",
    title: "Экспорт газа из страны ОЭСР по направлениям, (млрд м³)",
    description: "Структура экспорта газа по партнерам.",
    factTable: "gas.fact_gas_trade",
    selectedFilterValues: { flow_code: ["EXPORTS"], frequency_code: ["A"] }
  },
  {
    id: "gas-lng-export-by-partners",
    group: "Газ",
    title: "Экспорт СПГ из страны ОЭСР по направлениям, (млрд м³)",
    description: "Структура экспорта СПГ по партнёрам за последний доступный год.",
    factTable: "gas.fact_gas_trade",
    selectedFilterValues: {
      flow_code: ["EXPORTS"],
      product_code: ["LNG"],
      unit_code: ["M_M3"],
      frequency_code: ["A"]
    }
  },
  {
    id: "gas-oecd-consumption",
    group: "Газ",
    title: "Потребление газа в стране ОЭСР, (млрд м³)",
    description: "Потребление газа: годовые данные с 2020 и месячные с 2025-01.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: {
      flow_code: ["GRDEL_INLAND_OBS"],
      unit_code: ["M_M3"],
      frequency_code: ["M"]
    },
    pivotLayout: "time_columns_filters_rows"
  },
  {
    id: "gas-oecd-consumption-by-sectors",
    group: "Газ",
    title: "Потребление газа в стране ОЭСР по секторам, (млрд м³)",
    description: "Секторная структура потребления газа.",
    factTable: "gas.fact_gas_balance",
    selectedFilterValues: { frequency_code: ["A"] }
  },
  {
    id: "coal-oecd-production",
    group: "Уголь",
    title: "Добыча угля в стране ОЭСР, (тыс. тонн)",
    description: "Годовая добыча каменного и бурого угля в странах ОЭСР.",
    factTable: "coal.fact_coal_balance",
    selectedFilterValues: {
      flow_code: ["INDPROD"],
      product_code: ["HARDCOAL", "BROWNCOAL"],
      unit_code: ["KT"],
      frequency_code: ["A"]
    }
  },
  {
    id: "coal-nonoecd-production",
    group: "Уголь",
    title: "Добыча угля в стране не-ОЭСР, (тыс. тонн)",
    description: "Годовая добыча каменного и бурого угля в странах не-ОЭСР.",
    factTable: "coal.fact_coal_balance",
    selectedFilterValues: {
      flow_code: ["INDPROD"],
      product_code: ["HARDCOAL", "BROWNCOAL"],
      unit_code: ["KT"],
      frequency_code: ["A"]
    }
  },
  {
    id: "coal-oecd-consumption",
    group: "Уголь",
    title: "Потребление угля в стране ОЭСР, (тыс. тонн)",
    description: "Годовое потребление каменного и бурого угля в странах ОЭСР.",
    factTable: "coal.fact_coal_balance",
    selectedFilterValues: {
      flow_code: ["TES"],
      product_code: ["HARDCOAL", "BROWNCOAL"],
      unit_code: ["KT"],
      frequency_code: ["A"]
    }
  },
  {
    id: "coal-nonoecd-consumption",
    group: "Уголь",
    title: "Потребление угля в стране не-ОЭСР, (тыс. тонн)",
    description: "Годовое потребление каменного и бурого угля в странах не-ОЭСР.",
    factTable: "coal.fact_coal_balance",
    selectedFilterValues: {
      flow_code: ["TES"],
      product_code: ["HARDCOAL", "BROWNCOAL"],
      unit_code: ["KT"],
      frequency_code: ["A"]
    }
  }
];

const ALL_COUNTRIES_TOKEN = "__all_countries__";
const LIST_COUNTRIES_EXCLUDED_CODES = [
  "WORLD",
  "OECDTOT",
  "NONOECDTOT",
  "OECDAM",
  "OECDAO",
  "OECDEUR",
  "EURASIA",
  "ASIA",
  "AFRICA",
  "MIDDLE_EAST",
  "LATIN_AMERICA"
];

const LEGACY_PRESET_MIGRATION_FLAG = "iea.masterReport.presets.migrated.v1";
const LEGACY_PRESET_KEYS = [
  "iea.masterReport.filterPresets",
  "masterReport.filterPresets",
  "filterPresets",
  "presets"
];

const filterPresets = ref<
  FilterPreset[]
>([]);
const selectedPresetId = ref("");
const presetName = ref("");
const presetDescription = ref("");
const pendingGuideTemplateId = ref("");
let skipFilterRefresh = false;
const route = useRoute();

const activeFilter = computed(() =>
  availableFilters.value.find((item) => item.key === activeFilterKey.value) ?? null
);
const selectedFactTableLabel = computed(
  () =>
    factTables.value.find((item) => item.table === selectedFactTable.value)?.label ??
    selectedFactTable.value
);
const factTablesByDomain = computed(() => {
  const grouped = new Map<string, { table: string; label: string; description: string }[]>();
  for (const table of factTables.value) {
    const domain = table.table.includes(".") ? table.table.split(".")[0] : "other";
    const bucket = grouped.get(domain) ?? [];
    bucket.push(table);
    grouped.set(domain, bucket);
  }
  return Array.from(grouped.entries()).map(([domain, tables]) => ({ domain, tables }));
});

const selectedCountsText = computed(() =>
  availableFilters.value
    .map((item) => `${item.label}: ${(selectedFilterValues.value[item.key] ?? []).length}`)
    .join(", ")
);
const appliedFiltersList = computed(() => {
  return availableFilters.value
    .map((filter) => {
      const selectedValues = selectedFilterValues.value[filter.key] ?? [];
      if (!selectedValues.length) {
        return null;
      }
      const labelMap = new Map(filter.nodes.map((node) => [String(node.code), String(node.name ?? node.code)]));
      const displayValues = selectedValues.map((value) => labelMap.get(String(value)) ?? String(value));
      return {
        key: filter.key,
        label: filter.label,
        values: displayValues
      };
    })
    .filter(
      (
        item
      ): item is {
        key: string;
        label: string;
        values: string[];
      } => item !== null
    );
});
const hasSelectedFilters = computed(() =>
  availableFilters.value.some((item) => (selectedFilterValues.value[item.key] ?? []).length > 0)
);
const presetsForCurrentTable = computed(() =>
  filterPresets.value.filter((item) => item.factTable === selectedFactTable.value)
);
const selectedPreset = computed(
  () => presetsForCurrentTable.value.find((item) => item.id === selectedPresetId.value) ?? null
);
interface ChartSeries {
  name: string;
  shortLabel: string;
  values: Array<number | null>;
  color: string;
  points: Array<{ x: number; y: number; value: number } | null>;
}

const chartPalette = [
  "#2563eb",
  "#16a34a",
  "#dc2626",
  "#9333ea",
  "#f59e0b",
  "#0891b2",
  "#db2777",
  "#65a30d"
];
const chartHoverIndex = ref<number | null>(null);

function getPeriodToken(value: string): string {
  return value.split("|")[0]?.trim() ?? value;
}

function periodSortKey(value: string): number {
  const token = getPeriodToken(value);
  const monthMatch = token.match(/^(\d{4})-(\d{2})$/);
  if (monthMatch) {
    return Number(monthMatch[1]) * 100 + Number(monthMatch[2]);
  }
  const quarterMatch = token.match(/^(\d{4})-Q([1-4])$/i);
  if (quarterMatch) {
    return Number(quarterMatch[1]) * 10 + Number(quarterMatch[2]);
  }
  const yearMatch = token.match(/^(\d{4})$/);
  if (yearMatch) {
    return Number(yearMatch[1]) * 100;
  }
  const fallback = Date.parse(token);
  return Number.isFinite(fallback) ? fallback : Number.MAX_SAFE_INTEGER;
}

function comparePeriodsByLabel(a: string, b: string): number {
  const keyDiff = periodSortKey(a) - periodSortKey(b);
  if (keyDiff !== 0) return keyDiff;
  return a.localeCompare(b, "ru");
}

function normalizePeriodSelection(value: string, edge: "from" | "to" = "from"): string {
  if (!value) return "";
  if (pivotPeriodValues.value.includes(value)) {
    return value;
  }
  const token = getPeriodToken(value);
  const matched = pivotPeriodValues.value.find((item) => getPeriodToken(item) === token);
  if (matched) {
    return matched;
  }

  const sorted = [...pivotPeriodValues.value].sort(comparePeriodsByLabel);
  if (!sorted.length) {
    return value;
  }

  const yearMatch = token.match(/^(\d{4})$/);
  if (yearMatch) {
    const year = yearMatch[1];
    const yearCandidates = sorted.filter((item) => {
      const itemToken = getPeriodToken(item);
      return itemToken === year || itemToken.startsWith(`${year}-`) || itemToken.startsWith(`${year}Q`);
    });
    if (yearCandidates.length) {
      return edge === "from" ? yearCandidates[0] : yearCandidates[yearCandidates.length - 1];
    }

    const yearStart = Number(year) * 100;
    const pick = edge === "from"
      ? sorted.find((item) => periodSortKey(item) >= yearStart)
      : [...sorted].reverse().find((item) => periodSortKey(item) <= yearStart + 99);
    if (pick) {
      return pick;
    }
  }

  return edge === "from" ? sorted[0] : sorted[sorted.length - 1];
}

function ensurePeriodRangeOrder(): void {
  if (!periodFrom.value || !periodTo.value) {
    return;
  }
  if (periodSortKey(periodFrom.value) <= periodSortKey(periodTo.value)) {
    return;
  }
  const from = periodFrom.value;
  periodFrom.value = periodTo.value;
  periodTo.value = from;
}

const pivotPeriodValues = computed(() => {
  if (!report.value?.pivot?.columns?.length) return [];
  const pivot = report.value.pivot;
  const firstColumn = pivot.columns[0];
  const labels =
    reportPivotLayout.value === "time_rows_filters_columns"
      ? pivot.rows.map((row) => String(row[firstColumn] ?? ""))
      : pivot.columns.slice(1).map((column) => String(column));
  return Array.from(new Set(labels)).sort(comparePeriodsByLabel);
});
const periodFromOptions = computed(() => {
  const options = [...pivotPeriodValues.value];
  if (periodFrom.value && !options.includes(periodFrom.value)) {
    options.push(periodFrom.value);
  }
  return options.sort(comparePeriodsByLabel);
});
const periodToOptions = computed(() => {
  const options = [...pivotPeriodValues.value];
  if (periodTo.value && !options.includes(periodTo.value)) {
    options.push(periodTo.value);
  }
  return options.sort(comparePeriodsByLabel);
});

const filteredPivot = computed(() => {
  if (!report.value?.pivot?.columns?.length) {
    return null;
  }

  const pivot = report.value.pivot;
  const firstColumn = pivot.columns[0];
  const timeInRows = reportPivotLayout.value === "time_rows_filters_columns";
  const fromKey = periodFrom.value ? periodSortKey(periodFrom.value) : null;
  const toKey = periodTo.value ? periodSortKey(periodTo.value) : null;
  const direction = periodSort.value === "asc" ? 1 : -1;
  const periodInRange = (label: string): boolean => {
    const key = periodSortKey(label);
    if (fromKey !== null && key < fromKey) return false;
    if (toKey !== null && key > toKey) return false;
    return true;
  };

  if (timeInRows) {
    const rows = pivot.rows
      .filter((row) => periodInRange(String(row[firstColumn] ?? "")))
      .slice()
      .sort(
        (a, b) =>
          comparePeriodsByLabel(String(a[firstColumn] ?? ""), String(b[firstColumn] ?? "")) * direction
      );
    return {
      columns: pivot.columns,
      rows
    };
  }

  const periodColumns = pivot.columns
    .slice(1)
    .map((column) => String(column))
    .filter((column) => periodInRange(column))
    .sort((a, b) => comparePeriodsByLabel(a, b) * direction);
  const rows = pivot.rows.map((row) => {
    const next: Record<string, unknown> = { [firstColumn]: row[firstColumn] };
    for (const column of periodColumns) {
      next[column] = row[column];
    }
    return next;
  });
  return {
    columns: [firstColumn, ...periodColumns],
    rows
  };
});

function parseNumericCell(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

const pivotWithTotals = computed(() => {
  if (!filteredPivot.value?.columns?.length) {
    return null;
  }
  if (!showRowTotals.value && !showColumnTotals.value) {
    return filteredPivot.value;
  }

  const firstColumn = filteredPivot.value.columns[0];
  const columns = [...filteredPivot.value.columns];
  const rows = filteredPivot.value.rows.map((row) => ({ ...row }));

  if (showRowTotals.value) {
    const dataColumns = columns.slice(1);
    for (const row of rows) {
      const rowTotal = dataColumns.reduce((sum, column) => {
        const numeric = parseNumericCell(row[column]);
        return sum + (numeric ?? 0);
      }, 0);
      row["Итого"] = rowTotal;
    }
    columns.push("Итого");
  }

  if (showColumnTotals.value) {
    const totalRow: Record<string, unknown> = { [firstColumn]: "Итого" };
    for (const column of columns.slice(1)) {
      totalRow[column] = rows.reduce((sum, row) => {
        const numeric = parseNumericCell(row[column]);
        return sum + (numeric ?? 0);
      }, 0);
    }
    rows.push(totalRow);
  }

  return { columns, rows };
});

interface PivotDisplayRow {
  key: string;
  fullLabel: string;
  shortLabel: string;
  row: Record<string, unknown>;
}

const pivotIndicatorPresentation = computed(() => {
  if (!pivotWithTotals.value?.columns.length) {
    return {
      groups: [] as Array<{ commonLabel: string; commonSuffix: string; rows: PivotDisplayRow[] }>,
      totalRows: [] as PivotDisplayRow[]
    };
  }

  const firstColumn = pivotWithTotals.value.columns[0];
  const dataRows = pivotWithTotals.value.rows.filter((row) => String(row[firstColumn]) !== "Итого");
  const totalRows = pivotWithTotals.value.rows.filter((row) => String(row[firstColumn]) === "Итого");
  const labels = dataRows.map((row) => String(row[firstColumn] ?? ""));
  const shortByFull = mapIndicatorShortLabels(labels);
  const groups = buildIndicatorLabelGroups(labels);

  const displayGroups = groups.map((group, groupIndex) => ({
    commonLabel: group.commonLabel,
    commonSuffix: group.commonSuffix,
    rows: dataRows
      .filter((row) => group.items.some((item) => item.fullLabel === String(row[firstColumn] ?? "")))
      .map((row, rowIndex) => {
        const fullLabel = String(row[firstColumn] ?? "");
        return {
          key: `group-${groupIndex}-row-${rowIndex}`,
          fullLabel,
          shortLabel: shortByFull.get(fullLabel) ?? fullLabel,
          row
        };
      })
  }));

  return {
    groups: displayGroups,
    totalRows: totalRows.map((row, index) => ({
      key: `total-${index}`,
      fullLabel: "Итого",
      shortLabel: "Итого",
      row
    }))
  };
});

const chartData = computed(() => {
  if (!filteredPivot.value?.columns?.length || !filteredPivot.value.rows.length) {
    return null;
  }

  const columns = filteredPivot.value.columns;
  const rows = filteredPivot.value.rows;
  const firstColumn = columns[0];
  const timeInRows = reportPivotLayout.value === "time_rows_filters_columns";

  const xLabels: string[] = timeInRows
    ? rows.map((row) => String(row[firstColumn] ?? ""))
    : columns.slice(1);

  const seriesLabels = timeInRows
    ? columns.slice(1)
    : rows.map((row) => String(row[firstColumn] ?? ""));
  const shortLabelMap = mapIndicatorShortLabels(seriesLabels);

  const series: ChartSeries[] = timeInRows
    ? columns.slice(1).map((column, idx) => ({
        name: column,
        shortLabel: shortLabelMap.get(column) ?? column,
        color: chartPalette[idx % chartPalette.length],
        values: rows.map((row) => {
          const value = row[column];
          if (value === null || value === undefined || value === "") return null;
          const parsed = Number(value);
          return Number.isFinite(parsed) ? parsed : null;
        }),
        points: []
      }))
    : rows.map((row, idx) => {
        const name = String(row[firstColumn] ?? `Серия ${idx + 1}`);
        return {
          name,
          shortLabel: shortLabelMap.get(name) ?? name,
          color: chartPalette[idx % chartPalette.length],
          values: columns.slice(1).map((column) => {
            const value = row[column];
            if (value === null || value === undefined || value === "") return null;
            const parsed = Number(value);
            return Number.isFinite(parsed) ? parsed : null;
          }),
          points: []
        };
      });

  const allValues = series.flatMap((item) => item.values).filter((value): value is number => value !== null);
  if (!allValues.length || !xLabels.length) {
    return null;
  }

  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const range = maxValue - minValue || 1;
  const width = 960;
  const height = 320;
  const paddingX = 52;
  const paddingY = 24;
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingY * 2;

  const points = series.map((item) => {
    const pointList = item.values.map((value, index) => {
        if (value === null) return null;
        const x = paddingX + (xLabels.length === 1 ? 0 : (index / (xLabels.length - 1)) * plotWidth);
        const y = height - paddingY - ((value - minValue) / range) * plotHeight;
        return { x, y, value };
      });
    const path = pointList
      .filter((value): value is { x: number; y: number; value: number } => value !== null)
      .map((point) => `${point.x},${point.y}`)
      .join(" ");
    return { ...item, path, points: pointList };
  });

  const yTicks = Array.from({ length: 5 }, (_, idx) => {
    const ratio = idx / 4;
    const value = minValue + (maxValue - minValue) * (1 - ratio);
    const y = paddingY + plotHeight * ratio;
    return { y, value };
  });

  const xLabelMaxLen = xLabels.reduce(
    (maxLen, label) => Math.max(maxLen, getPeriodToken(label).length),
    1
  );
  const approxLabelWidthPx = Math.max(56, xLabelMaxLen * 7 + 10);
  const maxTicks = Math.max(2, Math.floor(plotWidth / approxLabelWidthPx));
  const xTickStep = Math.max(1, Math.ceil(xLabels.length / maxTicks));
  const xTicks = xLabels
    .map((label, index) => ({ label, index }))
    .filter((item) => item.index % xTickStep === 0 || item.index === xLabels.length - 1)
    .map((item) => ({
      ...item,
      displayLabel: getPeriodToken(item.label),
      x: paddingX + (xLabels.length === 1 ? 0 : (item.index / (xLabels.length - 1)) * plotWidth)
    }));

  return {
    width,
    height,
    paddingX,
    paddingY,
    plotWidth,
    xLabels,
    series: points.filter((item) => item.path),
    xTicks,
    yTicks
  };
});

const chartLegendGroups = computed(() => {
  if (!chartData.value?.series.length) {
    return [];
  }
  const groups = buildIndicatorLabelGroups(chartData.value.series.map((series) => series.name));
  const colorByFullLabel = new Map(chartData.value.series.map((series) => [series.name, series.color]));
  return groups.map((group) => ({
    commonLabel: group.commonLabel,
    commonSuffix: group.commonSuffix,
    items: group.items.map((item) => ({
      fullLabel: item.fullLabel,
      shortLabel: item.shortLabel,
      color: colorByFullLabel.get(item.fullLabel) ?? "#64748b"
    }))
  }));
});

const chartHoverPayload = computed(() => {
  if (!chartData.value || chartHoverIndex.value === null) return null;

  const index = Math.max(0, Math.min(chartHoverIndex.value, chartData.value.xLabels.length - 1));
  const x =
    chartData.value.paddingX +
    (chartData.value.xLabels.length === 1
      ? 0
      : (index / (chartData.value.xLabels.length - 1)) * chartData.value.plotWidth);
  const items = chartData.value.series
    .map((series) => {
      const point = series.points[index];
      if (!point) return null;
      return {
        name: series.shortLabel,
        fullName: series.name,
        color: series.color,
        y: point.y,
        value: point.value
      };
    })
    .filter(
      (item): item is { name: string; fullName: string; color: string; y: number; value: number } =>
        item !== null
    )
    .sort((a, b) => b.value - a.value);

  return {
    x,
    label: chartData.value.xLabels[index],
    items
  };
});

const chartTooltipStyle = computed<Record<string, string> | null>(() => {
  if (!chartData.value || !chartHoverPayload.value) return null;

  const ratio = chartHoverPayload.value.x / chartData.value.width;
  const anchorPercent = Math.max(0, Math.min(100, ratio * 100));
  const nearRightEdge = ratio > 0.62;

  return {
    top: "14px",
    left: nearRightEdge
      ? `calc(${anchorPercent}% - 12px)`
      : `calc(${anchorPercent}% + 12px)`,
    transform: nearRightEdge ? "translateX(-100%)" : "translateX(0)"
  };
});

function onChartMouseMove(event: MouseEvent): void {
  if (!chartData.value) return;
  const svg = event.currentTarget as SVGSVGElement;
  const rect = svg.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const left = chartData.value.paddingX;
  const right = chartData.value.width - chartData.value.paddingX;
  const clamped = Math.max(left, Math.min(right, x * (chartData.value.width / rect.width)));
  const ratio = chartData.value.xLabels.length === 1 ? 0 : (clamped - left) / chartData.value.plotWidth;
  chartHoverIndex.value = Math.round(ratio * (chartData.value.xLabels.length - 1));
}

function onChartMouseLeave(): void {
  chartHoverIndex.value = null;
}

function exportPivotToExcel(): void {
  if (!pivotWithTotals.value?.columns?.length || !pivotWithTotals.value.rows.length) {
    return;
  }

  const columns = pivotWithTotals.value.columns;
  const rows = pivotWithTotals.value.rows;
  const sheetData = [
    columns,
    ...rows.map((row) => columns.map((column) => row[column] ?? ""))
  ];
  const worksheet = utils.aoa_to_sheet(sheetData);
  const workbook = utils.book_new();
  utils.book_append_sheet(workbook, worksheet, "Сводная таблица");
  const tableName = selectedFactTable.value.replace(/\./g, "_");
  writeFileXLSX(workbook, `svodnaya_${tableName}.xlsx`);
  void logAuditEvent("report_export", {
    details: {
      fact_table: selectedFactTable.value,
      rows: rows.length,
      columns: columns.length
    }
  });
}

function formatPivotCellValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const numeric =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number(value)
        : Number.NaN;
  if (Number.isFinite(numeric)) {
    return numeric.toFixed(3);
  }
  return String(value);
}

function toPresetRecord(preset: FilterPreset): PresetMutationPayload {
  return {
    id: preset.id,
    name: preset.name,
    description: preset.description,
    factTable: preset.factTable,
    selectedFilterValues: preset.selectedFilterValues,
    pivotLayout: preset.pivotLayout,
    periodFrom: preset.periodFrom,
    periodTo: preset.periodTo,
    periodSort: preset.periodSort
  };
}

function toFilterPreset(raw: unknown): FilterPreset | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const item = raw as Record<string, unknown>;
  if (
    typeof item.id !== "string" ||
    typeof item.name !== "string" ||
    typeof item.factTable !== "string" ||
    !item.selectedFilterValues ||
    typeof item.selectedFilterValues !== "object"
  ) {
    return null;
  }
  const selectedFilterValues = Object.fromEntries(
    Object.entries(item.selectedFilterValues as Record<string, unknown>).map(([key, values]) => [
      key,
      Array.isArray(values) ? values.map((value) => String(value)) : []
    ])
  );
  return {
    id: item.id,
    name: item.name,
    description: typeof item.description === "string" ? item.description : "",
    factTable: item.factTable,
    selectedFilterValues,
    pivotLayout:
      item.pivotLayout === "time_columns_filters_rows"
        ? "time_columns_filters_rows"
        : "time_rows_filters_columns",
    periodFrom: typeof item.periodFrom === "string" ? item.periodFrom : "",
    periodTo: typeof item.periodTo === "string" ? item.periodTo : "",
    periodSort: item.periodSort === "desc" ? "desc" : "asc",
    updatedAt: typeof item.updatedAt === "string" ? item.updatedAt : new Date(0).toISOString(),
    version: typeof item.version === "number" && Number.isFinite(item.version) && item.version > 0 ? item.version : 1
  };
}

function parseLegacyPresetPayload(rawValue: string): FilterPreset[] {
  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map(toFilterPreset).filter((item): item is FilterPreset => item !== null);
  } catch {
    return [];
  }
}

function readLegacyPresetsFromLocalStorage(): FilterPreset[] {
  if (typeof window === "undefined" || !window.localStorage) {
    return [];
  }
  const collected: FilterPreset[] = [];
  const seenIds = new Set<string>();
  const candidateKeys = new Set<string>(LEGACY_PRESET_KEYS);
  for (let i = 0; i < window.localStorage.length; i += 1) {
    const key = window.localStorage.key(i);
    if (!key) continue;
    const lowered = key.toLowerCase();
    if (lowered.includes("preset")) {
      candidateKeys.add(key);
    }
  }

  for (const key of candidateKeys) {
    const rawValue = window.localStorage.getItem(key);
    if (!rawValue) {
      continue;
    }
    const parsed = parseLegacyPresetPayload(rawValue);
    for (const preset of parsed) {
      if (seenIds.has(preset.id)) {
        continue;
      }
      seenIds.add(preset.id);
      collected.push(preset);
    }
  }
  return collected;
}

async function migrateLegacyPresetsOnce(): Promise<void> {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  if (window.localStorage.getItem(LEGACY_PRESET_MIGRATION_FLAG) === "done") {
    return;
  }
  try {
    const legacyPresets = readLegacyPresetsFromLocalStorage();
    if (legacyPresets.length > 0) {
      await importPresetsToServer(legacyPresets.map(toPresetRecord), true);
    }
    window.localStorage.setItem(LEGACY_PRESET_MIGRATION_FLAG, "done");
  } catch {
    // If migration fails, keep trying on next startup.
  }
}

async function loadFilterPresets(): Promise<void> {
  await migrateLegacyPresetsOnce();
  try {
    const serverPresets = await getPresets();
    filterPresets.value = serverPresets
      .map(toFilterPreset)
      .filter((item): item is FilterPreset => item !== null);
  } catch {
    filterPresets.value = [];
  }
}

function cloneSelectedFilters(): Record<string, string[]> {
  const snapshot: Record<string, string[]> = {};
  for (const filter of availableFilters.value) {
    snapshot[filter.key] = [...(selectedFilterValues.value[filter.key] ?? [])];
  }
  return snapshot;
}

function getCurrentPostFilters(): Pick<
  FilterPreset,
  "pivotLayout" | "periodFrom" | "periodTo" | "periodSort"
> {
  return {
    pivotLayout: pivotLayout.value,
    periodFrom: periodFrom.value,
    periodTo: periodTo.value,
    periodSort: periodSort.value
  };
}

function applyPresetById(presetId: string): void {
  const preset = presetsForCurrentTable.value.find((item) => item.id === presetId);
  if (!preset) return;
  const nextValues: Record<string, string[]> = {};
  for (const filter of availableFilters.value) {
    const presetValues = preset.selectedFilterValues[filter.key] ?? [];
    const isAllCountriesPreset =
      presetValues.length === 1 &&
      presetValues[0] === ALL_COUNTRIES_TOKEN &&
      (filter.key === "country_code" || filter.key === "reporter_code");
    if (isAllCountriesPreset) {
      const allCountries = filter.nodes
        .map((node) => String(node.code))
        .filter((code) => !LIST_COUNTRIES_EXCLUDED_CODES.includes(code));
      nextValues[filter.key] = allCountries;
      continue;
    }
    nextValues[filter.key] = [...presetValues];
  }
  skipFilterRefresh = true;
  selectedFilterValues.value = nextValues;
  pivotLayout.value = preset.pivotLayout;
  periodFrom.value = normalizePeriodSelection(preset.periodFrom, "from");
  periodTo.value = normalizePeriodSelection(preset.periodTo, "to");
  periodSort.value = preset.periodSort;
  void logAuditEvent("preset_apply", {
    details: {
      preset_id: preset.id,
      preset_name: preset.name,
      fact_table: preset.factTable
    }
  });
}

function onPresetChange(): void {
  const preset = selectedPreset.value;
  if (!preset) {
    presetName.value = "";
    presetDescription.value = "";
    return;
  }
  presetName.value = preset.name;
  presetDescription.value = preset.description;
  applyPresetById(preset.id);
}

async function addPreset(): Promise<void> {
  const name = presetName.value.trim();
  if (!name) return;
  const presetToCreate: PresetMutationPayload = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    name,
    description: presetDescription.value.trim(),
    factTable: selectedFactTable.value,
    selectedFilterValues: cloneSelectedFilters(),
    ...getCurrentPostFilters()
  };
  try {
    const createdPreset = await createPresetOnServer(presetToCreate);
    const mapped = toFilterPreset(createdPreset);
    if (!mapped) {
      throw new Error("Некорректный ответ сервера при создании пресета");
    }
    filterPresets.value = [mapped, ...filterPresets.value];
    selectedPresetId.value = mapped.id;
    void logAuditEvent("preset_create", {
      details: {
        preset_id: mapped.id,
        preset_name: mapped.name,
        fact_table: mapped.factTable
      }
    });
  } catch (err) {
    await loadFilterPresets();
    reportError.value = err instanceof Error ? err.message : "Не удалось создать пресет";
  }
}

async function updatePreset(): Promise<void> {
  const current = selectedPreset.value;
  if (!current) return;
  const name = presetName.value.trim();
  if (!name) return;
  const payload: PresetMutationPayload = {
    id: current.id,
    name,
    description: presetDescription.value.trim(),
    factTable: selectedFactTable.value,
    selectedFilterValues: cloneSelectedFilters(),
    ...getCurrentPostFilters()
  };
  try {
    const updated = await updatePresetOnServer(
      current.id,
      payload,
      current.version,
      current.updatedAt,
      "copy"
    );
    const mapped = toFilterPreset(updated.preset);
    if (!mapped) {
      throw new Error("Некорректный ответ сервера при обновлении пресета");
    }
    if (updated.mode === "copied_on_conflict") {
      filterPresets.value = [mapped, ...filterPresets.value];
      selectedPresetId.value = mapped.id;
      presetName.value = mapped.name;
      presetDescription.value = mapped.description;
      reportError.value = "Исходный пресет уже изменен другим пользователем. Ваша версия сохранена как копия.";
    } else {
      filterPresets.value = filterPresets.value.map((item) => (item.id === current.id ? mapped : item));
      reportError.value = "";
    }
    void logAuditEvent("preset_update", {
      details: {
        preset_id: mapped.id,
        preset_name: mapped.name,
        fact_table: mapped.factTable,
        mode: updated.mode
      }
    });
  } catch (err) {
    await loadFilterPresets();
    reportError.value =
      err instanceof Error
        ? err.message
        : "Не удалось обновить пресет: он мог быть изменен в другой сессии";
  }
}

async function deletePreset(): Promise<void> {
  const current = selectedPreset.value;
  if (!current) return;
  try {
    await deletePresetOnServer(current.id, current.version, current.updatedAt);
    filterPresets.value = filterPresets.value.filter((item) => item.id !== current.id);
    selectedPresetId.value = "";
    presetName.value = "";
    presetDescription.value = "";
    void logAuditEvent("preset_delete", {
      details: {
        preset_id: current.id,
        preset_name: current.name,
        fact_table: current.factTable
      }
    });
  } catch (err) {
    await loadFilterPresets();
    reportError.value =
      err instanceof Error
        ? err.message
        : "Не удалось удалить пресет: он мог быть изменен в другой сессии";
  }
}

function applyGuideTemplateState(template: GuideTableTemplate): void {
  const nextValues: Record<string, string[]> = {};
  for (const filter of availableFilters.value) {
    nextValues[filter.key] = [...(template.selectedFilterValues[filter.key] ?? [])];
  }
  skipFilterRefresh = true;
  selectedFilterValues.value = nextValues;
  pivotLayout.value = template.pivotLayout ?? "time_columns_filters_rows";
  periodFrom.value = template.periodFrom ?? "";
  periodTo.value = template.periodTo ?? "";
  periodSort.value = template.periodSort ?? "asc";
  selectedPresetId.value = "";
  presetName.value = template.title;
  presetDescription.value = template.description;
}

async function applyGuideTemplate(templateId: string): Promise<void> {
  const template = GUIDE_TABLE_TEMPLATES.find((item) => item.id === templateId);
  if (!template) {
    return;
  }
  if (!availableFilters.value.length) {
    pendingGuideTemplateId.value = templateId;
    return;
  }
  if (selectedFactTable.value !== template.factTable) {
    pendingGuideTemplateId.value = templateId;
    selectedFactTable.value = template.factTable;
    return;
  }
  applyGuideTemplateState(template);
  await generateReport();
}

const activeFilterValues = computed<string[]>({
  get() {
    return selectedFilterValues.value[activeFilterKey.value] ?? [];
  },
  set(nextValues) {
    selectedFilterValues.value = {
      ...selectedFilterValues.value,
      [activeFilterKey.value]: nextValues
    };
  }
});

async function loadHierarchies(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const payload = await getMasterHierarchies();
    factTables.value = payload.fact_tables;
    if (!factTables.value.some((table) => table.table === selectedFactTable.value)) {
      selectedFactTable.value = factTables.value[0]?.table ?? "oil.fact_oil_balance";
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не удалось загрузить иерархии";
  } finally {
    loading.value = false;
  }
}

async function loadFiltersForTable(): Promise<void> {
  if (!selectedFactTable.value) {
    availableFilters.value = [];
    activeFilterKey.value = "";
    selectedFilterValues.value = {};
    return;
  }

  filtersLoading.value = true;
  report.value = null;
  availableFilters.value = [];
  activeFilterKey.value = "";
  skipFilterRefresh = true;
  selectedFilterValues.value = {};
  try {
    const payload = await getMasterFilterOptions(selectedFactTable.value, {});
    availableFilters.value = payload.filters;
    if (!payload.filters.some((item) => item.key === activeFilterKey.value)) {
      activeFilterKey.value = payload.filters[0]?.key ?? "";
    }
  } finally {
    filtersLoading.value = false;
  }
}

async function refreshFilterCounts(): Promise<void> {
  if (skipFilterRefresh) {
    skipFilterRefresh = false;
    return;
  }
  if (!selectedFactTable.value || !availableFilters.value.length) {
    return;
  }
  const payload = await getMasterFilterOptions(
    selectedFactTable.value,
    selectedFilterValues.value
  );
  availableFilters.value = payload.filters;
}

function resetAllFilters(): void {
  const clearedValues: Record<string, string[]> = {};
  for (const filter of availableFilters.value) {
    clearedValues[filter.key] = [];
  }
  selectedFilterValues.value = clearedValues;
  report.value = null;
  reportError.value = "";
  void logAuditEvent("filter_reset", {
    details: { fact_table: selectedFactTable.value }
  });
}

async function generateReport(): Promise<void> {
  reportLoading.value = true;
  reportError.value = "";
  try {
    report.value = await buildMasterReport({
      fact_table: selectedFactTable.value,
      filter_values: selectedFilterValues.value,
      limit: reportLimit.value,
      pivot_layout: pivotLayout.value
    });
    reportPivotLayout.value = pivotLayout.value;
    void logAuditEvent("report_build", {
      details: {
        fact_table: selectedFactTable.value,
        pivot_layout: pivotLayout.value,
        row_count: report.value?.pivot?.rows.length ?? 0
      }
    });
  } catch (err) {
    reportError.value = err instanceof Error ? err.message : "Не удалось построить отчет";
    report.value = null;
  } finally {
    reportLoading.value = false;
  }
}

onMounted(async () => {
  await loadFilterPresets();
  await loadHierarchies();
  await loadFiltersForTable();
  if (pendingGuideTemplateId.value) {
    const template = GUIDE_TABLE_TEMPLATES.find((item) => item.id === pendingGuideTemplateId.value);
    pendingGuideTemplateId.value = "";
    if (template && template.factTable === selectedFactTable.value) {
      applyGuideTemplateState(template);
      await generateReport();
    }
  }
  if (typeof route.query.guide_template === "string" && route.query.guide_template) {
    await applyGuideTemplate(route.query.guide_template);
  }
});

watch(selectedFactTable, async () => {
  selectedPresetId.value = "";
  presetName.value = "";
  presetDescription.value = "";
  await loadFiltersForTable();
  if (pendingGuideTemplateId.value) {
    const template = GUIDE_TABLE_TEMPLATES.find((item) => item.id === pendingGuideTemplateId.value);
    pendingGuideTemplateId.value = "";
    if (template && template.factTable === selectedFactTable.value) {
      applyGuideTemplateState(template);
      await generateReport();
    }
  }
});

watch(
  () => route.query.guide_template,
  async (templateId) => {
    if (typeof templateId !== "string" || !templateId) {
      return;
    }
    await applyGuideTemplate(templateId);
  }
);

watch(
  selectedFilterValues,
  async () => {
    await refreshFilterCounts();
  },
  { deep: true }
);

watch(pivotLayout, async () => {
  if (!hasSelectedFilters.value || reportLoading.value) {
    return;
  }
  await generateReport();
});

watch(pivotPeriodValues, () => {
  periodFrom.value = normalizePeriodSelection(periodFrom.value, "from");
  periodTo.value = normalizePeriodSelection(periodTo.value, "to");
  ensurePeriodRangeOrder();
});

watch([periodFrom, periodTo], () => {
  ensurePeriodRangeOrder();
});

watch(presetsForCurrentTable, (nextPresets) => {
  if (!nextPresets.some((item) => item.id === selectedPresetId.value)) {
    selectedPresetId.value = "";
    presetName.value = "";
    presetDescription.value = "";
  }
});
</script>

<template>
  <section class="page-card">
    <div class="page-head">
      <h2>Мастер отчетов</h2>
      <p>Сначала выберите таблицу из сырых данных, затем настраивайте фильтры по ее колонкам.</p>
    </div>

    <div v-if="loading" class="loading-inline">
      <span class="spinner"></span>
      <span>Загрузка иерархий...</span>
    </div>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else class="toolbar">
      <div class="toolbar-main-filters">
        <label class="field">
          Таблица из "Сырых данных":
          <select v-model="selectedFactTable">
            <optgroup
              v-for="group in factTablesByDomain"
              :key="`domain-${group.domain}`"
              :label="group.domain.toUpperCase()"
            >
              <option v-for="table in group.tables" :key="table.table" :value="table.table">
                {{ table.label }}
              </option>
            </optgroup>
          </select>
        </label>

        <label class="field">
          Какой фильтр настраиваем:
          <select v-model="activeFilterKey" :disabled="filtersLoading || !availableFilters.length">
            <option v-if="filtersLoading" value="">Загрузка...</option>
            <option v-for="filter in availableFilters" :key="filter.key" :value="filter.key">
              {{ filter.label }}
            </option>
          </select>
        </label>
        <span class="muted">
          Активные фильтры: {{ selectedCountsText || "нет" }}
        </span>
      </div>
    </div>

    <div class="applied-filters">
      <div class="applied-filters-head">
        <h4>Примененные фильтры</h4>
        <button
          class="btn btn-secondary applied-filters-reset-btn"
          type="button"
          :disabled="!hasSelectedFilters"
          @click="resetAllFilters"
        >
          Сбросить все фильтры
        </button>
      </div>
      <div class="chips">
        <span v-for="filter in appliedFiltersList" :key="filter.key" class="chip">
          {{ filter.label }}: {{ filter.values.join(", ") }}
        </span>
        <span v-if="!appliedFiltersList.length" class="muted">Пока нет активных фильтров</span>
      </div>
    </div>

    <div v-if="!loading && !error && !filtersLoading" class="master-grid">
      <HierarchyChecklist
        v-if="activeFilter"
        :key="activeFilterKey"
        :title="activeFilter.label"
        :nodes="activeFilter.nodes"
        v-model="activeFilterValues"
      />
      <section class="master-preset-card">
        <h4>Пресеты фильтров</h4>
        <label class="field">
          Выбранный пресет:
          <select v-model="selectedPresetId" @change="onPresetChange">
            <option value="">Не выбран</option>
            <option v-for="preset in presetsForCurrentTable" :key="preset.id" :value="preset.id">
              {{ preset.name }}
            </option>
          </select>
        </label>
        <label class="field">
          Название пресета:
          <input v-model="presetName" type="text" placeholder="Например: Базовый набор" />
        </label>
        <label class="field">
          Описание:
          <textarea
            v-model="presetDescription"
            rows="3"
            placeholder="Кратко опишите, для чего нужен этот пресет"
          ></textarea>
        </label>
        <div class="preset-actions">
          <button class="btn btn-secondary" type="button" :disabled="!presetName.trim()" @click="addPreset">
            Добавить
          </button>
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="!selectedPresetId || !presetName.trim()"
            @click="updatePreset"
          >
            Обновить
          </button>
          <button class="btn btn-secondary" type="button" :disabled="!selectedPresetId" @click="deletePreset">
            Удалить
          </button>
        </div>
      </section>
    </div>
    <div v-else-if="!loading && !error && filtersLoading" class="loading-inline">
      <span class="spinner"></span>
      <span>Загрузка фильтров для выбранной таблицы...</span>
    </div>

    <div class="toolbar">
      <label class="field">
        Вид сводной таблицы:
        <select v-model="pivotLayout">
          <option value="time_rows_filters_columns">Период в строках</option>
          <option value="time_columns_filters_rows">Период в столбцах</option>
        </select>
      </label>
      <button class="btn" :disabled="reportLoading || !hasSelectedFilters" @click="generateReport">
        Сформировать отчет
      </button>
    </div>

    <div v-if="reportLoading" class="loading-inline">
      <span class="spinner"></span>
      <span>Формирование отчета...</span>
    </div>
    <p v-else-if="reportError" class="error">{{ reportError }}</p>

    <div v-if="report" class="preview">
      <p class="muted">Найдено строк: {{ report.count }}</p>
      <h4>Сводная таблица — {{ selectedFactTableLabel }}</h4>
      <div class="toolbar">
        <label class="field">
          Период с:
          <select v-model="periodFrom">
            <option value="">Любой</option>
            <option v-for="period in periodFromOptions" :key="`from-${period}`" :value="period">
              {{ period }}
            </option>
          </select>
        </label>
        <label class="field">
          Период по:
          <select v-model="periodTo">
            <option value="">Любой</option>
            <option v-for="period in periodToOptions" :key="`to-${period}`" :value="period">
              {{ period }}
            </option>
          </select>
        </label>
        <label class="field">
          Сортировка периода:
          <select v-model="periodSort">
            <option value="asc">По возрастанию</option>
            <option value="desc">По убыванию</option>
          </select>
        </label>
        <label class="field checkbox-field">
          <input v-model="showRowTotals" type="checkbox" />
          Итого по строкам
        </label>
        <label class="field checkbox-field">
          <input v-model="showColumnTotals" type="checkbox" />
          Итого по столбцам
        </label>
      </div>
      <div class="table-wrap">
        <table v-if="pivotWithTotals" class="table pivot-table">
          <thead>
            <tr>
              <th v-for="column in pivotWithTotals.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="(group, groupIndex) in pivotIndicatorPresentation.groups"
              :key="`pivot-group-${groupIndex}`"
            >
              <tr v-if="group.commonLabel || group.commonSuffix" class="pivot-group-row">
                <td :colspan="pivotWithTotals.columns.length" class="pivot-group-cell">
                  <div v-if="group.commonLabel" class="pivot-group-title">{{ group.commonLabel }}</div>
                  <div v-if="group.commonSuffix" class="pivot-group-suffix">{{ group.commonSuffix }}</div>
                </td>
              </tr>
              <tr v-for="displayRow in group.rows" :key="displayRow.key">
                <td v-for="(column, columnIndex) in pivotWithTotals.columns" :key="`${displayRow.key}-${column}`">
                  <span
                    v-if="columnIndex === 0 && displayRow.shortLabel !== displayRow.fullLabel"
                    :title="displayRow.fullLabel"
                  >
                    {{ displayRow.shortLabel }}
                  </span>
                  <template v-else>
                    {{ formatPivotCellValue(columnIndex === 0 ? displayRow.shortLabel : displayRow.row[column]) }}
                  </template>
                </td>
              </tr>
            </template>
            <tr
              v-for="displayRow in pivotIndicatorPresentation.totalRows"
              :key="displayRow.key"
              class="pivot-total-row"
            >
              <td v-for="column in pivotWithTotals.columns" :key="`${displayRow.key}-${column}`">
                {{ formatPivotCellValue(displayRow.row[column]) }}
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">После фильтра по периоду данных не осталось.</p>
      </div>
      <div class="toolbar">
        <button class="btn" :disabled="!pivotWithTotals?.rows.length" @click="exportPivotToExcel">
          Выгрузить сводную в Excel
        </button>
      </div>

      <h4>График по сводной таблице</h4>
      <div v-if="chartData" class="chart-card">
        <svg
          class="pivot-chart"
          :viewBox="`0 0 ${chartData.width} ${chartData.height}`"
          xmlns="http://www.w3.org/2000/svg"
          @mousemove="onChartMouseMove"
          @mouseleave="onChartMouseLeave"
        >
          <line
            :x1="chartData.paddingX"
            :x2="chartData.paddingX"
            :y1="chartData.paddingY"
            :y2="chartData.height - chartData.paddingY"
            stroke="#94a3b8"
            stroke-width="1"
          />
          <line
            :x1="chartData.paddingX"
            :x2="chartData.width - chartData.paddingX"
            :y1="chartData.height - chartData.paddingY"
            :y2="chartData.height - chartData.paddingY"
            stroke="#94a3b8"
            stroke-width="1"
          />
          <g v-for="tick in chartData.yTicks" :key="`y-${tick.y}`">
            <line
              :x1="chartData.paddingX"
              :x2="chartData.width - chartData.paddingX"
              :y1="tick.y"
              :y2="tick.y"
              stroke="#e2e8f0"
              stroke-width="1"
            />
            <text x="8" :y="tick.y + 4" class="chart-label">
              {{ tick.value.toLocaleString("ru-RU", { maximumFractionDigits: 2 }) }}
            </text>
          </g>
          <g v-for="tick in chartData.xTicks" :key="`x-${tick.index}`">
            <line
              :x1="tick.x"
              :x2="tick.x"
              :y1="chartData.height - chartData.paddingY"
              :y2="chartData.height - chartData.paddingY + 4"
              stroke="#94a3b8"
              stroke-width="1"
            />
            <text
              :x="tick.x"
              :y="chartData.height - chartData.paddingY + 18"
              class="chart-label chart-x-label"
            >
              {{ tick.displayLabel }}
            </text>
          </g>
          <polyline
            v-for="item in chartData.series"
            :key="item.name"
            :points="item.path"
            :stroke="item.color"
            fill="none"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <line
            v-if="chartHoverPayload"
            :x1="chartHoverPayload.x"
            :x2="chartHoverPayload.x"
            :y1="chartData.paddingY"
            :y2="chartData.height - chartData.paddingY"
            stroke="#475569"
            stroke-width="1"
            stroke-dasharray="4 4"
          />
          <circle
            v-for="item in chartHoverPayload?.items ?? []"
            :key="`hover-point-${item.name}`"
            :cx="chartHoverPayload?.x"
            :cy="item.y"
            r="4"
            :fill="item.color"
            stroke="#ffffff"
            stroke-width="1.5"
          />
        </svg>
        <div v-if="chartHoverPayload" class="chart-tooltip" :style="chartTooltipStyle ?? undefined">
          <div class="chart-tooltip-title">{{ chartHoverPayload.label }}</div>
          <div v-for="item in chartHoverPayload.items" :key="`hover-tip-${item.fullName ?? item.name}`" class="chart-tooltip-row">
            <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
            <span class="chart-tooltip-name" :title="item.fullName !== item.name ? item.fullName : undefined">
              {{ item.name }}
            </span>
            <strong>{{ item.value.toLocaleString("ru-RU", { maximumFractionDigits: 2 }) }}</strong>
          </div>
        </div>
        <div class="chart-legend">
          <div v-for="(group, groupIndex) in chartLegendGroups" :key="`legend-group-${groupIndex}`" class="legend-group">
            <div v-if="group.commonLabel || group.commonSuffix" class="legend-group-header">
              <div v-if="group.commonLabel" class="legend-group-title">{{ group.commonLabel }}</div>
              <div v-if="group.commonSuffix" class="legend-group-suffix">{{ group.commonSuffix }}</div>
            </div>
            <div class="legend-group-items">
              <span
                v-for="item in group.items"
                :key="`legend-${item.fullLabel}`"
                class="legend-item"
                :title="item.shortLabel !== item.fullLabel ? item.fullLabel : undefined"
              >
                <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
                {{ item.shortLabel }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="muted">Недостаточно числовых данных для построения графика.</p>
    </div>
  </section>
</template>

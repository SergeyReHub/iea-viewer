<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { marked } from "marked";
import { utils, writeFileXLSX } from "xlsx";
import type {
  Domain,
  RawStatsDetailResponse,
  RawStatsResponse,
  RawStatsRowAxisKey,
  TableMeta
} from "../services/api";
import { getDomains, getRawStats, getRawStatsDetail, getTableDoc, getTables } from "../services/api";
import { logAuditEvent } from "../utils/audit";

const domains = ref<Domain[]>([]);
const selectedDomain = ref<Domain>("oil");
const factTables = ref<TableMeta[]>([]);
const selectedTable = ref<string>("");
const loadingTables = ref(false);
const tableError = ref("");
const docError = ref("");
const markdown = ref("");
const docLoading = ref(false);
const statsLoading = ref(false);
const statsError = ref("");
const rawStats = ref<RawStatsResponse | null>(null);
const rowAxis = ref<RawStatsRowAxisKey>("country");
const frequencyCode = ref("");
const periodFrom = ref("");
const periodTo = ref("");
const hideEmptyRows = ref(true);
let syncingAxes = false;
const statsSortColumn = ref<string>("");
const statsSortDirection = ref<"desc" | "asc">("desc");
const rowAlphabeticalSort = ref(false);
const selectedStatsCell = ref<{ rowKey: string; rowLabel: string; colLabel: string } | null>(null);
const statsDetailLoading = ref(false);
const statsDetailError = ref("");
const statsDetail = ref<RawStatsDetailResponse | null>(null);
const FREQUENCY_LABELS: Record<string, string> = {
  A: "Ежегодно",
  Q: "Ежеквартально",
  M: "Ежемесячно",
  W: "Еженедельно",
  D: "Ежедневно"
};

const htmlDoc = computed(() => marked.parse(markdown.value) as string);
const rowAxisOptions = computed(() => rawStats.value?.available_row_axes ?? []);
const frequencyOptions = computed(() => rawStats.value?.available_frequency_codes ?? []);
const frequencyOptionsWithLabel = computed(() =>
  frequencyOptions.value.map((value) => ({
    value,
    label: FREQUENCY_LABELS[value] ? `${value} — ${FREQUENCY_LABELS[value]}` : value
  }))
);
const periodOptions = computed(() => rawStats.value?.period_values ?? []);
const statsCellMap = computed(() => {
  const map = new Map<string, number>();
  for (const cell of rawStats.value?.cells ?? []) {
    map.set(`${cell.row_key}||${cell.col_key}`, cell.count);
  }
  return map;
});
const sortedRowItems = computed(() => {
  const items = [...(rawStats.value?.row_items ?? [])];
  if (!statsSortColumn.value) {
    if (rowAlphabeticalSort.value) {
      items.sort((a, b) => a.label.localeCompare(b.label, "ru"));
    }
    return items;
  }
  const direction = statsSortDirection.value === "desc" ? -1 : 1;
  items.sort((a, b) => {
    const aCount = getStatsCellValue(a.key, statsSortColumn.value);
    const bCount = getStatsCellValue(b.key, statsSortColumn.value);
    if (aCount !== bCount) {
      return (aCount - bCount) * direction;
    }
    return a.label.localeCompare(b.label, "ru");
  });
  return items;
});
const displayedRowItems = computed(() => {
  if (!hideEmptyRows.value || !rawStats.value) {
    return sortedRowItems.value;
  }
  return sortedRowItems.value.filter((rowItem) =>
    rawStats.value!.col_labels.some((colLabel) => getStatsCellValue(rowItem.key, colLabel) > 0)
  );
});

async function loadDomains(): Promise<void> {
  const allDomains = await getDomains();
  domains.value = allDomains.filter((domain) => domain !== "base");
  if (!domains.value.includes(selectedDomain.value)) {
    selectedDomain.value = domains.value[0] ?? "oil";
  }
}

async function loadFactTables(): Promise<void> {
  loadingTables.value = true;
  tableError.value = "";
  rawStats.value = null;
  statsError.value = "";
  try {
    factTables.value = await getTables(selectedDomain.value, "fact");
    selectedTable.value = factTables.value[0]?.table ?? "";
    await loadTableDoc();
  } catch (err) {
    tableError.value =
      err instanceof Error ? err.message : "Не удалось загрузить список сырых таблиц";
  } finally {
    loadingTables.value = false;
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

async function loadRawStats(): Promise<void> {
  if (!selectedTable.value) {
    rawStats.value = null;
    return;
  }

  statsLoading.value = true;
  statsError.value = "";
  try {
    const payload = await getRawStats(
      selectedDomain.value,
      selectedTable.value,
      rowAxis.value,
      frequencyCode.value || undefined,
      periodFrom.value || undefined,
      periodTo.value || undefined
    );
    rawStats.value = payload;
    if (payload.row_axis !== rowAxis.value || (payload.frequency_code ?? "") !== frequencyCode.value) {
      syncingAxes = true;
      rowAxis.value = payload.row_axis;
      frequencyCode.value = payload.frequency_code ?? "";
      syncingAxes = false;
    }
    void logAuditEvent("raw_stats_load", {
      details: {
        domain: selectedDomain.value,
        table: selectedTable.value,
        row_axis: payload.row_axis,
        cells: payload.cells.length
      }
    });
  } catch (err) {
    statsError.value = err instanceof Error ? err.message : "Не удалось загрузить статистику";
    rawStats.value = null;
  } finally {
    statsLoading.value = false;
  }
}

function getStatsCellValue(rowLabel: string, colLabel: string): number {
  return statsCellMap.value.get(`${rowLabel}||${colLabel}`) ?? 0;
}

function getStatsCellStyle(value: number): Record<string, string> {
  const min = rawStats.value?.min_count ?? 0;
  const max = rawStats.value?.max_count ?? 0;
  if (max <= min) {
    return { backgroundColor: "rgba(37, 99, 235, 0.16)", color: "#0f172a" };
  }
  const ratio = (value - min) / (max - min);
  const alpha = 0.08 + ratio * 0.62;
  return {
    backgroundColor: `rgba(37, 99, 235, ${alpha.toFixed(3)})`,
    color: ratio > 0.58 ? "#ffffff" : "#0f172a"
  };
}

function onStatsColumnClick(colLabel: string): void {
  if (statsSortColumn.value !== colLabel) {
    statsSortColumn.value = colLabel;
    statsSortDirection.value = "desc";
    rowAlphabeticalSort.value = false;
    return;
  }
  if (statsSortDirection.value === "desc") {
    statsSortDirection.value = "asc";
    return;
  }
  statsSortColumn.value = "";
  statsSortDirection.value = "desc";
}

function onFirstColumnHeaderClick(): void {
  statsSortColumn.value = "";
  statsSortDirection.value = "desc";
  rowAlphabeticalSort.value = !rowAlphabeticalSort.value;
}

function getStatsSortMarker(colLabel: string): string {
  if (statsSortColumn.value !== colLabel) {
    return "";
  }
  return statsSortDirection.value === "desc" ? " ↓" : " ↑";
}

function exportStatsToExcel(): void {
  if (!rawStats.value) {
    return;
  }
  const worksheetData: Array<Array<string | number>> = [
    [rawStats.value.row_axis_label, ...rawStats.value.col_labels]
  ];
  for (const rowItem of displayedRowItems.value) {
    worksheetData.push([
      rowItem.label,
      ...rawStats.value.col_labels.map((colLabel) => getStatsCellValue(rowItem.key, colLabel))
    ]);
  }

  const workbook = utils.book_new();
  const worksheet = utils.aoa_to_sheet(worksheetData);
  utils.book_append_sheet(workbook, worksheet, "Статистика");
  const safeTableName = (selectedTable.value || rawStats.value.table).replace(/[^\w.-]+/g, "_");
  writeFileXLSX(workbook, `stats_${safeTableName}.xlsx`);
  void logAuditEvent("raw_stats_export", {
    details: {
      domain: selectedDomain.value,
      table: selectedTable.value,
      rows: displayedRowItems.value.length
    }
  });
}

async function onStatsCellClick(rowKey: string, rowLabel: string, colLabel: string): Promise<void> {
  selectedStatsCell.value = { rowKey, rowLabel, colLabel };
  statsDetailLoading.value = true;
  statsDetailError.value = "";
  statsDetail.value = null;
  try {
    statsDetail.value = await getRawStatsDetail(
      selectedDomain.value,
      selectedTable.value,
      rowAxis.value,
      rowKey,
      colLabel,
      frequencyCode.value || undefined
    );
    void logAuditEvent("raw_drilldown", {
      details: {
        domain: selectedDomain.value,
        table: selectedTable.value,
        row: rowLabel,
        period: colLabel,
        count: statsDetail.value.count
      }
    });
  } catch (err) {
    statsDetailError.value = err instanceof Error ? err.message : "Не удалось загрузить детализацию ячейки";
  } finally {
    statsDetailLoading.value = false;
  }
}

watch(selectedDomain, async () => {
  await loadFactTables();
});

watch(selectedTable, async () => {
  await loadTableDoc();
  periodFrom.value = "";
  periodTo.value = "";
  statsSortColumn.value = "";
  statsSortDirection.value = "desc";
  rowAlphabeticalSort.value = false;
  selectedStatsCell.value = null;
  statsDetail.value = null;
  statsDetailError.value = "";
  await loadRawStats();
});

watch([rowAxis, frequencyCode, periodFrom, periodTo], async () => {
  if (syncingAxes) return;
  statsSortColumn.value = "";
  statsSortDirection.value = "desc";
  rowAlphabeticalSort.value = false;
  selectedStatsCell.value = null;
  statsDetail.value = null;
  statsDetailError.value = "";
  await loadRawStats();
});

onMounted(async () => {
  await loadDomains();
  await loadFactTables();
});
</script>

<template>
  <section class="page-card">
    <div class="page-head">
      <h2>Сырые данные</h2>
      <p>Выберите таблицу и изучите статистику по записям.</p>
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

    <div v-if="loadingTables" class="loading-inline">
      <span class="spinner"></span>
      <span>Загрузка списка таблиц...</span>
    </div>
    <p v-else-if="tableError" class="error">{{ tableError }}</p>

    <div class="content-grid">
      <div>
        <ul v-if="factTables.length" class="table-list">
          <li v-for="table in factTables" :key="table.table">
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
      <h2>Статистика по таблице</h2>
      <p class="muted">
        В ячейке — количество записей для комбинации выбранных осей.
      </p>
      <div class="toolbar">
        <label class="field">
          Строки:
          <select v-model="rowAxis" :disabled="statsLoading || !rowAxisOptions.length">
            <option v-for="axis in rowAxisOptions" :key="`row-${axis.key}`" :value="axis.key">
              {{ axis.label }}
            </option>
          </select>
        </label>
        <label class="field">
          Частота:
          <select v-model="frequencyCode" :disabled="statsLoading || !frequencyOptions.length">
            <option v-for="item in frequencyOptionsWithLabel" :key="`freq-${item.value}`" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>
        <label class="field">
          Период с:
          <select v-model="periodFrom" :disabled="statsLoading || !periodOptions.length">
            <option value="">Любой</option>
            <option v-for="item in periodOptions" :key="`from-${item}`" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="field">
          Период по:
          <select v-model="periodTo" :disabled="statsLoading || !periodOptions.length">
            <option value="">Любой</option>
            <option v-for="item in periodOptions" :key="`to-${item}`" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="field checkbox-field">
          <input v-model="hideEmptyRows" type="checkbox" />
          Скрыть пустые строки
        </label>
        <button class="btn" :disabled="statsLoading || !rawStats" @click="exportStatsToExcel">
          Выгрузить в Excel
        </button>
      </div>
      <div v-if="statsLoading" class="loading-inline">
        <span class="spinner"></span>
        <span>Считаем статистику...</span>
      </div>
      <p v-else-if="statsError" class="error">{{ statsError }}</p>
      <div v-else-if="rawStats" class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th class="sticky-first-col">
                <button type="button" class="stats-col-btn" @click="onFirstColumnHeaderClick">
                  {{ rawStats.row_axis_label }}{{ rowAlphabeticalSort ? " А-Я" : "" }}
                </button>
              </th>
              <th v-for="colLabel in rawStats.col_labels" :key="`stat-col-${colLabel}`">
                <button type="button" class="stats-col-btn" @click="onStatsColumnClick(colLabel)">
                  {{ colLabel }}{{ getStatsSortMarker(colLabel) }}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rowItem in displayedRowItems" :key="`stat-row-${rowItem.key}`">
              <td class="sticky-first-col"><strong>{{ rowItem.label }}</strong></td>
              <td
                v-for="colLabel in rawStats.col_labels"
                :key="`stat-cell-${rowItem.key}-${colLabel}`"
                :style="getStatsCellStyle(getStatsCellValue(rowItem.key, colLabel))"
                class="stats-cell"
                @click="onStatsCellClick(rowItem.key, rowItem.label, colLabel)"
              >
                {{ getStatsCellValue(rowItem.key, colLabel) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="stats-detail">
        <h3>Детализация выбранной ячейки</h3>
        <p v-if="selectedStatsCell" class="muted">
          {{ rawStats?.row_axis_label }}: {{ selectedStatsCell.rowLabel }}, период: {{ selectedStatsCell.colLabel }}
        </p>
        <p v-else class="muted">Нажмите на любую ячейку таблицы статистики.</p>
        <div v-if="statsDetailLoading" class="loading-inline">
          <span class="spinner"></span>
          <span>Загрузка детализации...</span>
        </div>
        <p v-else-if="statsDetailError" class="error">{{ statsDetailError }}</p>
        <div v-else-if="statsDetail" class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>{{ statsDetail.detail_axis_label }}</th>
                <th>Количество</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in statsDetail.items" :key="`detail-${item.key}`">
                <td>{{ item.label }}</td>
                <td>{{ item.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="statsDetail && statsDetail.ambiguity_dimensions.length" class="stats-ambiguity">
          <h4>Почему в ячейке несколько записей</h4>
          <div
            v-for="dimension in statsDetail.ambiguity_dimensions"
            :key="`dim-${dimension.field}`"
            class="stats-ambiguity-item"
          >
            <strong>{{ dimension.label }}</strong>
            <span class="muted"> ({{ dimension.count }} вариантов)</span>
            <ul class="stats-ambiguity-values">
              <li v-for="value in dimension.values" :key="`dim-${dimension.field}-${value}`" class="muted">
                {{ value }}
              </li>
              <li v-if="dimension.truncated" class="muted">...</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.sticky-first-col {
  position: sticky;
  left: 0;
  z-index: 1;
  background: #f8fafc;
}

.stats-col-btn {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  cursor: pointer;
  color: inherit;
}
.stats-cell {
  cursor: pointer;
}
.stats-detail {
  margin-top: 1rem;
}
.stats-ambiguity {
  margin-top: 0.9rem;
}
.stats-ambiguity-item {
  margin: 0.4rem 0 0.7rem;
}
.stats-ambiguity-values {
  margin: 0.3rem 0 0;
  padding-left: 1.15rem;
}
.stats-ambiguity-values li {
  margin: 0.1rem 0;
}

.checkbox-field {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}
</style>

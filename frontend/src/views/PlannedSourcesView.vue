<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { getSources, type SourceProfile } from "../services/api";
import { logAuditEvent } from "../utils/audit";

const route = useRoute();
const sources = ref<SourceProfile[]>([]);
const loading = ref(true);
const error = ref("");

const activeSources = computed(() => sources.value.filter((s) => s.status === "active"));
const plannedSources = computed(() => sources.value.filter((s) => s.status !== "active"));
const highlight = computed(() => String(route.query.highlight || ""));

const monthNames = [
  "январь",
  "февраль",
  "март",
  "апрель",
  "май",
  "июнь",
  "июль",
  "август",
  "сентябрь",
  "октябрь",
  "ноябрь",
  "декабрь"
];

function openEtlPage(): void {
  void logAuditEvent("etl_open", { page_path: "/admin", page_name: "admin" });
}

function statusLabel(status: SourceProfile["status"]): string {
  if (status === "disabled") return "отключён";
  return "планируется";
}

function formatDataAsOfPeriod(period: string | null | undefined): string {
  if (!period) return "не определена";
  const yearMatch = /^(\d{4})$/.exec(period);
  if (yearMatch) {
    return `${yearMatch[1]} г.`;
  }
  const monthMatch = /^(\d{4})-(\d{2})$/.exec(period);
  if (monthMatch) {
    const monthIndex = Number(monthMatch[2]) - 1;
    if (monthIndex >= 0 && monthIndex < monthNames.length) {
      return `${monthNames[monthIndex]} ${monthMatch[1]}`;
    }
  }
  const quarterMatch = /^(\d{4})-Q([1-4])$/i.exec(period);
  if (quarterMatch) {
    return `${quarterMatch[2]} кв. ${quarterMatch[1]}`;
  }
  return period;
}

function activeSourceStatus(source: SourceProfile): string {
  return `Актуальность данных: ${formatDataAsOfPeriod(source.data_as_of_period)}`;
}

onMounted(async () => {
  try {
    sources.value = await getSources();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не удалось загрузить каталог источников";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="planned-page">
    <h1>Планируемые источники данных</h1>
    <p class="lead">
      Viewer v2 поддерживает несколько подключений к БД. Сейчас активен только IEA (схема IEA data 2 ETL).
      Остальные источники зарегистрированы и будут подключены после отдельного ETL-проекта.
    </p>

    <p v-if="loading">Загрузка...</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else class="cards">
      <RouterLink
        v-for="source in activeSources"
        :key="source.id"
        :to="{ name: 'admin' }"
        class="card card-active card-link"
        :class="{ highlight: highlight === source.id }"
        @click="openEtlPage"
      >
        <h2>{{ source.name }}</h2>
        <p class="status">{{ activeSourceStatus(source) }}</p>
        <p>{{ source.description }}</p>
        <span class="card-action">Открыть ETL</span>
      </RouterLink>

      <article
        v-for="source in plannedSources"
        :key="source.id"
        class="card"
        :class="{ highlight: highlight === source.id }"
      >
        <h2>{{ source.name }}</h2>
        <p class="status">Статус: {{ statusLabel(source.status) }}</p>
        <p>{{ source.description }}</p>
        <a v-if="source.homepage_url" :href="source.homepage_url" target="_blank" rel="noopener">
          Открыть портал данных
        </a>
      </article>
    </div>
  </section>
</template>

<style scoped>
.planned-page {
  max-width: 960px;
}
.lead {
  margin-bottom: 1.5rem;
  line-height: 1.5;
}
.cards {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
.card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1rem;
  background: #fafafa;
}
.card-active {
  border-color: #2ecc71;
  background: #f6fffa;
}
.card-link {
  display: block;
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}
.card-link:hover {
  box-shadow: 0 2px 8px rgba(46, 204, 113, 0.25);
  transform: translateY(-1px);
}
.card.highlight {
  border-color: #3498db;
  box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
}
.card-action {
  display: inline-block;
  margin-top: 0.5rem;
  color: #2980b9;
  text-decoration: underline;
}
.status {
  font-size: 0.85rem;
  opacity: 0.8;
}
.error {
  color: #c0392b;
}
</style>

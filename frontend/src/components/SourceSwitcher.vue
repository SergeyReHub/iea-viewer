<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getSources, type SourceProfile } from "../services/api";
import { logAuditEvent } from "../utils/audit";
import { getCurrentSourceId, onSourceChange, setCurrentSourceId } from "../stores/source";

const router = useRouter();
const sources = ref<SourceProfile[]>([]);
const currentId = ref(getCurrentSourceId());
const loading = ref(true);
const loadError = ref("");

const fallbackSources: SourceProfile[] = [
  {
    id: "iea",
    name: "IEA",
    status: "active",
    adapter: "iea_etl",
    homepage_url: "https://www.iea.org/data-and-statistics",
    description: "",
    schema_version: "2026-06",
    domains: ["base", "coal", "oil", "gas", "electricity"],
    db_ok: false
  }
];

const currentSource = computed(() => sources.value.find((s) => s.id === currentId.value));

onMounted(async () => {
  try {
    sources.value = await getSources();
    loadError.value = "";
  } catch (err) {
    sources.value = fallbackSources;
    const message = err instanceof Error ? err.message : String(err);
    loadError.value = message.includes("500")
      ? "API error 500 — проверьте VITE_DEV_API_PROXY в .env (порт backend)"
      : "API недоступен — запустите backend (docker compose / scripts\\dev.bat)";
  } finally {
    const urlSource = new URLSearchParams(window.location.search).get("source");
    if (urlSource && sources.value.some((s) => s.id === urlSource)) {
      setCurrentSourceId(urlSource);
      currentId.value = urlSource;
    }
    loading.value = false;
  }
  onSourceChange((id) => {
    currentId.value = id;
  });
});

async function onChange(event: Event): Promise<void> {
  const select = event.target as HTMLSelectElement;
  const nextId = select.value;
  const profile = sources.value.find((s) => s.id === nextId);
  if (!profile) return;

  if (profile.status !== "active") {
    router.push({ name: "planned-sources", query: { highlight: nextId } });
    return;
  }

  const prev = currentId.value;
  setCurrentSourceId(nextId);
  currentId.value = nextId;
  await logAuditEvent("source_switch", {
    page_path: "/source-switch",
    page_name: `Источник: ${profile.name}`,
    details: {
      source_id: profile.id,
      source_name: profile.name
    }
  });

  if (prev !== nextId) {
    router.push({ path: "/", query: { source: nextId } });
    window.location.reload();
  }
}
</script>

<template>
  <label class="source-switcher">
    <span class="source-label">Источник</span>
    <select :value="currentId" :disabled="loading" @change="onChange">
      <option v-for="source in sources" :key="source.id" :value="source.id">
        {{ source.name }}
        {{ source.status === "active" ? (source.db_ok ? "" : " (БД недоступна)") : " (скоро)" }}
      </option>
    </select>
    <span v-if="loadError" class="warn" :title="loadError">API offline</span>
    <span v-else-if="currentSource?.status === 'active' && !currentSource.db_ok" class="warn">нет связи с БД</span>
  </label>
</template>

<style scoped>
.source-switcher {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-right: 1rem;
}
.source-label {
  font-size: 0.85rem;
  opacity: 0.85;
}
select {
  min-width: 10rem;
}
.warn {
  color: #c0392b;
  font-size: 0.8rem;
}
</style>

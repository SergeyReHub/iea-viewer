<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import SourceSwitcher from "./components/SourceSwitcher.vue";
import { getAuditLogs, getWhoAmI, type AuditLogRecord } from "./services/api";
import {
  formatAuditDetails,
  formatAuditEventType,
  logAuditEvent
} from "./utils/audit";

const fullName = ref<string | null>(null);
const userIp = ref<string | null>(null);
const canViewAudit = ref(false);
const route = useRoute();
const auditModalOpen = ref(false);
const auditLoading = ref(false);
const auditError = ref("");
const auditRecords = ref<AuditLogRecord[]>([]);
const selectedAuditUser = ref("__all__");

const userDisplay = computed(() => {
  if (fullName.value) return fullName.value;
  return "Пользователь не определен";
});
const auditUsers = computed(() => {
  const users = new Set(
    auditRecords.value
      .map((record) => record.full_name?.trim())
      .filter((name): name is string => Boolean(name))
  );
  return Array.from(users).sort((a, b) => a.localeCompare(b, "ru"));
});
const filteredAuditRecords = computed(() => {
  if (selectedAuditUser.value === "__all__") {
    return auditRecords.value;
  }
  return auditRecords.value.filter((record) => record.full_name === selectedAuditUser.value);
});

function formatAuditTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU");
}

async function openAuditModal(): Promise<void> {
  if (!canViewAudit.value) {
    return;
  }
  selectedAuditUser.value = "__all__";
  auditModalOpen.value = true;
  auditLoading.value = true;
  auditError.value = "";
  void logAuditEvent("audit_open");
  try {
    auditRecords.value = await getAuditLogs();
  } catch (err) {
    auditError.value = err instanceof Error ? err.message : "Не удалось загрузить аудит";
    auditRecords.value = [];
  } finally {
    auditLoading.value = false;
  }
}

function closeAuditModal(): void {
  auditModalOpen.value = false;
}

onMounted(async () => {
  try {
    const payload = await getWhoAmI();
    fullName.value = payload.full_name;
    userIp.value = payload.ip;
    canViewAudit.value = payload.can_view_audit;
  } catch {
    fullName.value = null;
    userIp.value = null;
    canViewAudit.value = false;
  }
  try {
    await logAuditEvent("app_open", {
      page_path: route.path,
      page_name: typeof route.name === "string" ? route.name : undefined
    });
  } catch {
    // audit should not break app startup
  }
});

watch(
  () => route.fullPath,
  async (nextPath) => {
    try {
      await logAuditEvent("page_view", {
        page_path: nextPath,
        page_name: typeof route.name === "string" ? route.name : undefined
      });
    } catch {
      // audit should not break navigation
    }
  }
);
</script>

<template>
  <div class="layout">
    <header class="app-header">
      <div>
        <p class="eyebrow">Multi-source Data Explorer</p>
        <h1>IEA Viewer v2</h1>
      </div>
      <div class="header-right">
        <SourceSwitcher />
        <button
          v-if="canViewAudit"
          type="button"
          class="user-caption user-caption-btn"
          @click="openAuditModal"
        >
          {{ userDisplay }}
        </button>
        <p v-else class="user-caption">{{ userDisplay }}</p>
        <nav class="nav">
          <RouterLink to="/">Справочники</RouterLink>
          <RouterLink to="/raw">Сырые данные</RouterLink>
          <RouterLink to="/master-report">Мастер отчетов</RouterLink>
          <RouterLink to="/master-guide">Мастер-справка</RouterLink>
          <RouterLink v-if="canViewAudit" to="/planned-sources">Источники</RouterLink>
        </nav>
      </div>
    </header>

    <main class="page-shell">
      <RouterView />
    </main>

    <div v-if="auditModalOpen" class="modal-backdrop" @click.self="closeAuditModal">
      <section class="modal-card">
        <div class="modal-header">
          <h3>Лог аудита</h3>
          <button type="button" class="btn btn-secondary" @click="closeAuditModal">Закрыть</button>
        </div>
        <div class="audit-modal-body">
          <p v-if="auditLoading" class="loading-inline">
            <span class="spinner"></span>
            <span>Загрузка аудита...</span>
          </p>
          <p v-else-if="auditError" class="error">{{ auditError }}</p>
          <div v-else class="audit-log-content">
            <div class="audit-filter-row">
              <label class="field">
                Пользователь
                <select v-model="selectedAuditUser">
                  <option value="__all__">Все пользователи</option>
                  <option v-for="user in auditUsers" :key="`audit-user-${user}`" :value="user">
                    {{ user }}
                  </option>
                </select>
              </label>
            </div>
            <div class="table-wrap modal-table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>Время</th>
                    <th>ФИО</th>
                    <th>Событие</th>
                    <th>Страница</th>
                    <th>Детали</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(record, idx) in filteredAuditRecords" :key="`audit-${idx}`">
                    <td>{{ formatAuditTime(record.timestamp_utc) }}</td>
                    <td>{{ record.full_name }}</td>
                    <td>{{ formatAuditEventType(record.event_type) }}</td>
                    <td>{{ record.page_name || record.page_path }}</td>
                    <td class="audit-details-cell">{{ formatAuditDetails(record.details) }}</td>
                  </tr>
                  <tr v-if="filteredAuditRecords.length === 0">
                    <td colspan="5" class="muted">Нет записей по выбранному пользователю</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

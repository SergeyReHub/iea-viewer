<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  getDataFreshness,
  getLoadBatches,
  getValidationErrors,
  type LoadBatchRow
} from "../services/api";
import { logAuditEvent } from "../utils/audit";

const loading = ref(true);
const error = ref("");
const batches = ref<LoadBatchRow[]>([]);
const freshness = ref<Record<string, unknown>[]>([]);
const errors = ref<Record<string, unknown>[]>([]);
const selectedBatchId = ref<string | null>(null);

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    [batches.value, freshness.value] = await Promise.all([getLoadBatches(30), getDataFreshness()]);
    errors.value = await getValidationErrors(undefined, 50);
    void logAuditEvent("admin_view", {
      details: { batches: batches.value.length }
    });
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Ошибка загрузки админ-данных";
  } finally {
    loading.value = false;
  }
}

async function loadErrorsForBatch(batchId: string): Promise<void> {
  selectedBatchId.value = batchId;
  errors.value = await getValidationErrors(batchId, 100);
  void logAuditEvent("admin_validation_errors", {
    details: { batch_id: batchId, errors: errors.value.length }
  });
}

onMounted(loadAll);
</script>

<template>
  <section class="admin-page">
    <h1>ETL / Администрирование</h1>
    <p class="lead">Read-only просмотр журнала загрузок и ошибок валидации текущего источника.</p>

    <p v-if="loading">Загрузка...</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else>
      <h2>Актуальность данных</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Домен</th>
            <th>Код</th>
            <th>Источник</th>
            <th>Primary</th>
            <th>Последняя загрузка</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in freshness" :key="idx">
            <td>{{ row.domain }}</td>
            <td>{{ row.source_code }}</td>
            <td>{{ row.source_name }}</td>
            <td>{{ row.is_primary ? "да" : "нет" }}</td>
            <td>{{ row.last_completed_at || "—" }}</td>
          </tr>
        </tbody>
      </table>

      <h2>Журнал load_batch</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Batch ID</th>
            <th>Домен</th>
            <th>Файл</th>
            <th>Статус</th>
            <th>Загружено</th>
            <th>Начало</th>
            <th>Завершение</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="batch in batches" :key="batch.batch_id">
            <td>{{ batch.batch_id }}</td>
            <td>{{ batch.domain || "—" }}</td>
            <td>{{ batch.file_name || "—" }}</td>
            <td>{{ batch.status }}</td>
            <td>{{ batch.records_inserted ?? "—" }}</td>
            <td>{{ batch.started_at || "—" }}</td>
            <td>{{ batch.completed_at || "—" }}</td>
            <td>
              <button type="button" @click="loadErrorsForBatch(batch.batch_id)">Ошибки</button>
            </td>
          </tr>
        </tbody>
      </table>

      <h2>
        validation_error
        <span v-if="selectedBatchId"> (batch {{ selectedBatchId }})</span>
      </h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Batch</th>
            <th>Тип</th>
            <th>Сообщение</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in errors" :key="idx">
            <td>{{ row.error_id }}</td>
            <td>{{ row.batch_id }}</td>
            <td>{{ row.error_type }}</td>
            <td>{{ row.error_message }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<style scoped>
.admin-page {
  max-width: 1100px;
}
.lead {
  margin-bottom: 1rem;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}
.data-table th,
.data-table td {
  border: 1px solid #ddd;
  padding: 0.4rem 0.5rem;
  text-align: left;
}
.error {
  color: #c0392b;
}
</style>

# IEA Viewer v2 — спецификация возможностей

> Версия документа: 1.0  
> Дата: 2026-06-05  
> Репозиторий: `iea-viewer-v2`  
> Целевая БД Phase 1: [IEA data 2 ETL](../IEA%20data%202%20ETL)

## 1. Видение и границы

**IEA Viewer v2** — web-интерфейс (Vue 3 + FastAPI) для просмотра и оперативной аналитики энергетической статистики из **нескольких PostgreSQL-источников**. Phase 1 реализует полный viewer для IEA ETL; семь внешних источников зарегистрированы как профили `planned`.

### In scope (Phase 1)

- Multi-source registry и переключатель источника в UI
- Все экраны v1, адаптированные под схему IEA ETL
- ETL-aware отображение (`source_id`, `qualifier`, `old_data`, `map_*_old_code`)
- Админ-просмотр `load_batch` / `validation_error`
- Presets и audit, scoped per source

### Out of scope (Phase 1)

- ETL-загрузка файлов
- Изменение DDL
- RBAC / полноценный BI
- Реальные подключения к Eurostat, JODI, EIA, OPEC, Energy Institute, Trade Map, UN Comtrade
- Cross-source analytics (сравнение IEA vs Eurostat)

---

## 2. Каталог источников данных

| id | Название | Статус | URL |
|----|----------|--------|-----|
| `iea` | IEA | **active** | https://www.iea.org/data-and-statistics |
| `eurostat` | Eurostat | planned | https://ec.europa.eu/eurostat/data/database |
| `jodi` | JODI | planned | http://www.jodidb.org/ReportFolders/reportFolders.aspx |
| `eia` | EIA | planned | https://www.eia.gov/international/data/world |
| `opec` | OPEC | planned | https://publications.opec.org/asb/Download |
| `energy_institute` | Energy Institute | planned | https://www.energyinst.org/statistical-review/resources-and-data-downloads |
| `trademap` | Trade Map | planned | https://www.trademap.org/Index.aspx |
| `un_comtrade` | UN Comtrade | planned | https://comtradeplus.un.org/TradeFlow |

Конфигурация: [`config/sources.yaml`](../config/sources.yaml). Подключение active-источника: env `{SOURCE_ID}_DB_URL` или `IEA_DB_URL`.

---

## 3. Архитектура multi-DB

```
Vue3 UI → FastAPI /api/v2/sources/{source_id}/... → CatalogAdapter → asyncpg Pool → PostgreSQL
```

- **SourceRegistry** — загрузка профилей, health-check
- **ConnectionPoolManager** — пул на каждый active source
- **CatalogAdapter** — каталог доменов/таблиц (Phase 1: `IeaEtlAdapter`)
- **ContextVar** — текущий pool в scope запроса
- Presets: `backend/data/presets/{source_id}/`
- Audit: `backend/logs/audit/{source_id}.jsonl`

Подробнее: [`docs/03_architecture/multi-source.md`](03_architecture/multi-source.md)

---

## 4. Экраны

| Экран | Маршрут | Назначение |
|-------|---------|------------|
| Справочники | `/` | `ref_*` + `map_*_old_code` |
| Сырые данные | `/raw` | `fact_*`, heatmap, drill-down |
| Мастер отчётов | `/master-report` | Pivot, фильтры, график, presets |
| Мастер-справка | `/master-guide` | Шаблоны oil/gas/coal/electricity |
| ETL | `/admin` | load_batch, validation_error, freshness |
| Источники | `/planned-sources` | Карточки planned sources |

---

## 5. Реестр фич

### A. Базовая платформа

| ID | Фича | Статус |
|----|------|--------|
| FR-A01 | Multi-source registry + health | ✅ |
| FR-A02 | Source Switcher + `?source=iea` | ✅ |
| FR-A03 | API `/api/v2/sources/{id}/...` | ✅ |
| FR-A04 | Adapter pattern | ✅ |
| FR-A05 | Planned sources UI | ✅ |
| FR-A06 | Whitelist catalog + information_schema | ✅ |
| FR-A07 | Markdown docs per table | ✅ |
| FR-A08 | Docker Compose multi-DSN | ✅ |
| FR-A09 | GitLab CI/CD | ✅ |

### B. Справочники

| ID | Фича | Статус |
|----|------|--------|
| FR-B01 | Домены base/coal/oil/gas/electricity | ✅ |
| FR-B02 | ref_* + map_*_old_code | ✅ |
| FR-B03–B07 | Docs, search, hide tech cols, RU labels, hierarchy | ✅ (из v1) |

### C. Сырые данные

| ID | Фича | Статус |
|----|------|--------|
| FR-C01–C06 | 19 fact, preview, heatmap, drill-down, Excel | ✅ (из v1) |
| FR-C07 | source_id / primary sources (admin API) | ✅ |
| FR-C08–C09 | qualifier/conf_status, NULL vs 0 | ✅ |
| FR-C10 | old_data debug toggle | ✅ |
| FR-C11–C12 | Trade/special dimensions | ✅ (данные + docs) |

### D. Мастер отчётов

| ID | Фича | Статус |
|----|------|--------|
| FR-D01–D13 | Pivot, filters, chart, presets (v1) | ✅ |
| FR-D14 | Server-side aggregation | ✅ (`services/pivot.py`) |
| FR-D15–D19 | source_id filter, unit/sign/OECD/conversion | ✅ (логика v1 + ETL refs) |

### E. Мастер-справка

| ID | Фича | Статус |
|----|------|--------|
| FR-E01–E02 | Oil/gas templates | ✅ |
| FR-E03–E04 | Coal/electricity templates | ✅ (4 новых) |
| FR-E05–E09 | Batch build, Excel, TZ, single backend source | ✅ |

### F. Admin / ETL

| ID | Фича | Статус |
|----|------|--------|
| FR-F01–F03 | load_batch, validation_error, freshness | ✅ |
| FR-F04 | Read-only | ✅ |

### G. Пользователи и аудит

| ID | Фича | Статус |
|----|------|--------|
| FR-G01–G04 | IP→ФИО, audit, modal, presets per source | ✅ |

---

## 6. Нефункциональные требования

| ID | Требование |
|----|------------|
| NFR-1 | Docker Compose, hot reload |
| NFR-2 | Read-only DB user (рекомендуется) |
| NFR-3 | API v2 source-scoped |
| NFR-4 | Русский UI |
| NFR-5 | Legacy API v1 `/api/*` для IEA (default pool) |

---

## 7. Матрица v1 → v2

| Область | v1 | v2 |
|---------|----|----|
| БД | одна `mea_data` | multi-source pools |
| API | `/api/meta/...` | `/api/v2/sources/iea/meta/...` |
| Коды | `new_code` model | `map_*_old_code`, `old_data` |
| Electricity guide | нет | 2 шаблона |
| Coal guide | нет | 2 шаблона |
| Admin ETL | нет | load_batch UI |
| Planned sources | нет | 7 карточек |

---

## 8. Roadmap

| Phase | Содержание |
|-------|------------|
| 0 | Bootstrap, spec, registry ✅ |
| 1 | IEA core screens ✅ |
| 2 | Analytics, guide extension ✅ |
| 3 | Admin, audit, docs ✅ |
| 4 | External sources ETL + adapters |

---

## 9. Зависимости от ETL

- Схема: `base` → `coal|oil|gas|electricity`
- Конвенции: `recomendation/db_conventions.md` в IEA data 2 ETL
- 19 fact-таблиц, map-таблицы, `ref_data_source.is_primary`
- Gas views: `gas.v_gas_balance` (опционально для запросов)

См. [`docs/07_database/iea-etl-mapping.md`](07_database/iea-etl-mapping.md)

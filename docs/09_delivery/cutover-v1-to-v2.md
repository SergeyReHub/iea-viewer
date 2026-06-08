# Cutover: iea-viewer v1 → v2

Цель: остановить v1 и поднять v2 на **тех же портах** (8010 API, 5180 UI) с мигрированными пресетами и БД `iea_data`.

## Предусловия

- [ ] ETL IEA data 2 заполнил `iea_data` на `192.168.245.32`
- [ ] Репозиторий `iea-viewer-v2` зарегистрирован в GitLab, runner `docker50` доступен
- [ ] На runner создан `deploy/.env` (см. `deploy/.env.example`)
- [ ] В GitLab CI/CD Variables: `ENV_FILE` → путь к `deploy/.env`

## Шаг 1. Отключить автодеплой v1

В репозитории **`iea-viewer`**:

- удалить job `deploy-code-job` из `.gitlab-ci.yml`, **или**
- добавить `when: manual` к deploy job

Иначе следующий push в v1 снова займёт порты 8010/5180.

## Шаг 2. Подготовить deploy/.env для v2

```ini
IEA_DB_URL=postgresql://USER:PASS@192.168.245.32:5432/iea_data
PGHOST=192.168.245.32
PGDATABASE=iea_data
# ... PGUSER, PGPASSWORD ...

FORCE_SEED_PRESETS=true   # только на первом cutover
AUDIT_VIEWER_IPS=...      # при необходимости
IDENTITY_IP_MAP_EXTRA=... # при необходимости
```

## Шаг 3. Деплой v2

**Через CI:** merge/push в `master` → pipeline соберёт образы и выполнит deploy job.

Deploy job автоматически:

1. Останавливает контейнеры v1 (`iea-viewer-backend`, `iea-viewer-frontend`)
2. При наличии `V1_COMPOSE_DIR` — `docker compose down` legacy-стека
3. Поднимает v2 (`iea-viewer-v2-backend`, `iea-viewer-frontend`)
4. Проверяет `/api/health` и ≥30 пресетов

**Вручную на сервере:**

```bash
bash deploy/deploy.sh
```

## Шаг 4. Проверка после cutover

| Проверка | Ожидание |
|----------|----------|
| http://192.168.245.50:5180 | UI v2, мастер-отчёт / мастер-справка |
| http://192.168.245.50:8010/api/health | `{"status":"ok"}` |
| GET /api/v2/sources/iea/presets | ≥ 35 пресетов |
| Мастер-справка, Германия | Таблицы без ошибок |
| Аудит | События пишутся в volume |

## Шаг 5. После успешного cutover

1. В `deploy/.env` установить `FORCE_SEED_PRESETS=false` (чтобы деплои не перезаписывали пользовательские пресеты)
2. Зафиксировать в `project.yaml` endpoints: prod → `:5180` v2

## Откат на v1 (аварийный)

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
cd /path/to/iea-viewer
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

> v1 использует БД `mea_data`; данные v2 в `iea_data` не затрагиваются.

## Отличия v2 от v1 при деплое

| | v1 | v2 |
|---|----|----|
| БД | `mea_data` | `iea_data` |
| API paths | `/api/...` | `/api/v2/sources/iea/...` (+ legacy) |
| Config mount | `report_of_preset` | `config/sources.yaml` |
| Volumes | `iea_viewer_*` | `iea_viewer_v2_*` |
| Пресеты | volume / export API | seed из образа + volume |

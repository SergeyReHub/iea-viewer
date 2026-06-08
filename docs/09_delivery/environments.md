# Окружения и выкладка (iea-viewer-v2)

## Продакшен

| Сервис | Порт | URL (prod) |
|--------|------|------------|
| UI | 5180 | http://192.168.245.50:5180 |
| API | 8010 | http://192.168.245.50:8010/api |
| Health | 8010 | http://192.168.245.50:8010/api/health |

База данных: PostgreSQL `192.168.245.32:5432`, БД **`iea_data`** (IEA data 2 ETL).

## CI/CD (GitLab)

Pipeline в `.gitlab-ci.yml`, runner с тегом **`docker50`** (тот же хост, что и v1).

| Stage | Действие |
|-------|----------|
| build | Сборка и push образов `backend`, `frontend` |
| release | Тег `latest` на ветке `master` |
| deploy | Остановка v1 → `docker compose up` v2 на портах 8010/5180 |
| logs | Хвост логов после деплоя |

### Переменные CI на сервере

| Переменная | Назначение |
|------------|------------|
| `ENV_FILE` | Путь к `deploy/.env` на runner (секреты БД, audit) |
| `V1_COMPOSE_DIR` | (опционально) путь к checkout `iea-viewer` для `docker compose down` v1 |

### Первичная настройка на runner

1. Скопировать `deploy/.env.example` → `deploy/.env`, указать реальные `PG*` / `IEA_DB_URL`.
2. В GitLab CI/CD Variables задать `ENV_FILE=/path/to/iea-viewer-v2/deploy/.env`.
3. На первом cutover в `deploy/.env` установить `FORCE_SEED_PRESETS=true`.
4. **Отключить auto-deploy v1** в репозитории `iea-viewer` (удалить job `deploy-code-job` или перевести в `when: manual`).

### Ручной деплой на сервере

```bash
cp deploy/.env.example deploy/.env   # отредактировать
chmod +x deploy/stop-v1.sh deploy/deploy.sh
bash deploy/deploy.sh
```

## Локальная разработка

См. корневой `README.md` и `docker-compose.yml` (hot reload, bind mounts).

Frontend в prod обращается к API по `http://<host>:8010/api` (как в v1). В dev Vite проксирует `/api` при `npm run dev`.

## Данные на volume

| Volume | Содержимое |
|--------|------------|
| `iea_viewer_v2_data` | Пресеты (`/app/data/presets/iea/`), прочие runtime-данные |
| `iea_viewer_v2_logs` | Аудит (`/app/logs`) |

Пресеты из v1 (`scripts/v1_presets_export.json`, 35 шт.) вшиваются в backend-образ и копируются в volume при первом старте (или при `FORCE_SEED_PRESETS=true`).

## Cutover v1 → v2

Подробный чеклист: [`cutover-v1-to-v2.md`](cutover-v1-to-v2.md).

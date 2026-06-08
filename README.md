# IEA Viewer v2

Web-интерфейс (Vue 3 + FastAPI) для просмотра энергетической статистики из **нескольких PostgreSQL-источников**.

Phase 1: полная поддержка БД [IEA data 2 ETL](https://gitlab.cdu.ru/barrdak/iea-etl).  
Phase 4: Eurostat, JODI, EIA, OPEC, Energy Institute, Trade Map, UN Comtrade (профили зарегистрированы).

## Документация

- [`docs/VIEWER_V2_FEATURES.md`](docs/VIEWER_V2_FEATURES.md) — полная спецификация фич
- [`docs/03_architecture/multi-source.md`](docs/03_architecture/multi-source.md) — multi-DB архитектура
- [`docs/api.md`](docs/api.md) — API v2

## Быстрый старт

**Вариант 1 — Docker (рекомендуется):**

```bash
cp .env.example .env
# укажите IEA_DB_URL
docker compose up --build
```

**Вариант 2 — локально (нужны оба процесса):**

```bash
# Windows: двойной клик или из корня проекта
scripts\dev.bat
```

Или в двух терминалах:

```bash
# Terminal 1 — backend (обязательно!)
cd backend
set SOURCES_CONFIG=..\config\sources.yaml
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

# Terminal 2 — frontend (проксирует /api → :8010)
cd frontend
npm install && npm run dev
```

> Если в консоли браузера `ERR_CONNECTION_REFUSED` или **500** на `/api/...` — backend не доступен с frontend.

**Типичная причина:** frontend (`npm run dev`) проксирует `/api` на `127.0.0.1:8010`, а Docker-backend проброшен на **8011**.  
В `.env` в корне проекта задайте:

```ini
VITE_DEV_API_PROXY=http://127.0.0.1:8011
API_HOST_PORT=8011
```

Перезапустите `npm run dev` в `frontend/`.

- UI: http://localhost:5180
- API: http://localhost:8010/api
- Health: http://localhost:8010/api/health
- Sources: http://localhost:8010/api/v2/sources

## Структура

```
config/sources.yaml    # каталог источников
backend/               # FastAPI
frontend/              # Vue 3
docs/                  # документация
```

## CI/CD и прод

- [Окружения и выкладка](docs/09_delivery/environments.md)
- [Cutover v1 → v2](docs/09_delivery/cutover-v1-to-v2.md)

Prod: **8010** (API), **5180** (UI) на `192.168.245.50`. Pipeline GitLab, runner `docker50`.

## Связь с v1

[iea-viewer](../iea-viewer) + [iea-data-structure](../iea-data-structure) → v1  
**iea-viewer-v2** + **IEA data 2 ETL** → v2

# API v2

Base URL: `http://localhost:8010/api`

## Global

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + version |
| GET | `/v2/sources` | List all source profiles |
| GET | `/v2/sources/{source_id}` | Source profile + health |
| GET | `/v2/sources/{source_id}/health` | DB health + adapter details |

## Source-scoped (example: `source_id=iea`)

Prefix: `/v2/sources/iea`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/meta/domains` | Domain list |
| GET | `/meta/tables?domain=&type=ref\|fact\|map` | Table catalog |
| GET | `/meta/table-doc?domain=&table=` | Markdown doc |
| GET | `/reference/{domain}/{table}` | Full ref/map data |
| GET | `/raw/{domain}/{table}?limit=` | Fact preview |
| GET | `/raw/stats/...` | Coverage heatmap |
| POST | `/master-report/report` | Pivot report |
| POST | `/master-report/filter-options` | Filter trees |
| GET | `/master-report/guide/templates?domain=` | Guide templates |
| GET | `/presets` | List presets |
| GET | `/admin/load-batches` | ETL batch log |
| GET | `/admin/validation-errors` | Validation errors |
| GET | `/admin/freshness` | Data freshness |
| POST | `/audit/event` | Write audit |

## Legacy v1

`/api/meta/...`, `/api/raw/...` etc. still work against default IEA pool (compatibility).

## Planned source

Calls to data endpoints with `source_id=eurostat` → **503** with profile JSON.

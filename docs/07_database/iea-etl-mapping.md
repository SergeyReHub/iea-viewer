# IEA ETL schema mapping (viewer)

## PostgreSQL schemas

| Schema | Content |
|--------|---------|
| `base` | Shared refs, map_country/unit/flow_old_code, load_batch |
| `coal` | 4 fact, ref_coal_product, map_coal_product_old_code |
| `oil` | 8 fact, ref_oil_*, map_oil_product_old_code |
| `gas` | 2 fact, views, map_gas_product_old_code |
| `electricity` | 5 fact, ref_electricity_*, map (empty) |

## Viewer registry

Static whitelist: `backend/app/metadata/tables.py`  
Display names: `backend/app/api/meta.py`  
Descriptions: `backend/app/metadata/descriptions/`

## UI rules (from ETL conventions)

- Filter facts by `source_id`; default = `ref_data_source.is_primary`
- Display `qualifier` / `conf_status` badges
- `value IS NULL` ≠ `0`
- `old_data` JSONB — debug mode only
- Trade tables: check reporter/partner column names per domain

## Authority

Schema changes happen only in [IEA data 2 ETL](../../IEA%20data%202%20ETL) — viewer is read-only.

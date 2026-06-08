import asyncio
import asyncpg

URL_BASE = "postgresql://postgres:postgres@192.168.245.32:5432"
DBS = ["iea_data", "mea_data"]
SCHEMAS = ["base", "oil", "gas", "coal", "electricity"]


async def get_tables(conn):
    rows = await conn.fetch(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = ANY($1::text[])
          AND table_type = 'BASE TABLE'
        ORDER BY 1, 2
        """,
        SCHEMAS,
    )
    return [(r["table_schema"], r["table_name"]) for r in rows]


async def count_table(conn, schema, table):
    try:
        return await conn.fetchval(f'SELECT count(*)::bigint FROM "{schema}"."{table}"')
    except Exception as exc:
        return f"ERR:{type(exc).__name__}"


async def table_periods(conn, schema, table):
    cols = {
        r["column_name"]
        for r in await conn.fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=$1 AND table_name=$2
            """,
            schema,
            table,
        )
    }
    if "time_period" not in cols:
        return None
    row = await conn.fetchrow(
        f'SELECT min(time_period::text) AS min_p, max(time_period::text) AS max_p FROM "{schema}"."{table}"'
    )
    return (row["min_p"], row["max_p"])


async def load_batch_summary(conn):
    row = await conn.fetchrow(
        """
        SELECT count(*)::int AS total,
               count(*) FILTER (WHERE status='COMPLETED')::int AS completed,
               count(*) FILTER (WHERE status='FAILED')::int AS failed,
               max(started_at)::text AS last_started,
               max(batch_id) AS last_batch
        FROM base.load_batch
        """
    )
    return dict(row)


async def main() -> None:
    conns = {db: await asyncpg.connect(f"{URL_BASE}/{db}") for db in DBS}
    tables_by_db = {db: await get_tables(conns[db]) for db in DBS}
    all_tables = sorted(set(tables_by_db["iea_data"]) | set(tables_by_db["mea_data"]))

    only_iea = sorted(set(tables_by_db["iea_data"]) - set(tables_by_db["mea_data"]))
    only_mea = sorted(set(tables_by_db["mea_data"]) - set(tables_by_db["iea_data"]))

    print("=== SUMMARY ===")
    for db in DBS:
        print(f"{db}: tables={len(tables_by_db[db])}")
    print(f"common={len(set(tables_by_db['iea_data']) & set(tables_by_db['mea_data']))}")
    print(f"only_iea={len(only_iea)} only_mea={len(only_mea)}")

    if only_iea:
        print("\n--- only iea_data ---")
        for schema, table in only_iea:
            print(f"  {schema}.{table}")
    if only_mea:
        print("\n--- only mea_data ---")
        for schema, table in only_mea:
            print(f"  {schema}.{table}")

    diffs = []
    same = 0
    print("\n=== ROW COUNT DIFFS ===")
    for schema, table in all_tables:
        if (schema, table) not in tables_by_db["iea_data"] or (schema, table) not in tables_by_db["mea_data"]:
            continue
        iea = await count_table(conns["iea_data"], schema, table)
        mea = await count_table(conns["mea_data"], schema, table)
        if isinstance(iea, str) or isinstance(mea, str):
            print(f"{schema}.{table}: iea={iea} mea={mea}")
            continue
        if iea == mea:
            same += 1
            continue
        iea_p = await table_periods(conns["iea_data"], schema, table)
        mea_p = await table_periods(conns["mea_data"], schema, table)
        diffs.append((abs(iea - mea), schema, table, iea, mea, iea - mea, iea_p, mea_p))

    diffs.sort(reverse=True)
    print(f"same_count={same} different={len(diffs)}")
    for _, schema, table, iea, mea, delta, iea_p, mea_p in diffs:
        pct = f"{(delta / mea * 100):+.1f}%" if mea else "n/a"
        print(f"{schema}.{table}: iea={iea:,} mea={mea:,} delta={delta:+,} ({pct})")
        if iea_p or mea_p:
            print(f"  iea period: {iea_p}")
            print(f"  mea period: {mea_p}")

    print("\n=== load_batch ===")
    for db in DBS:
        print(f"{db}: {await load_batch_summary(conns[db])}")

    print("\n=== FACT TOTALS BY DOMAIN ===")
    for db in DBS:
        print(db)
        for schema in SCHEMAS:
            total = 0
            n = 0
            for s, t in tables_by_db[db]:
                if s != schema or not t.startswith("fact_"):
                    continue
                c = await count_table(conns[db], s, t)
                if isinstance(c, int):
                    total += c
                    n += 1
            print(f"  {schema}: {n} tables, {total:,} rows")

    for conn in conns.values():
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

import os
import requests
from dotenv import load_dotenv
load_dotenv()

CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://localhost:8123")
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "analytics")
CLICKHOUSE_TABLE = os.getenv("CLICKHOUSE_TABLE", "llm_usage_events")

CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD")

def main():
    if not CLICKHOUSE_USER or not CLICKHOUSE_PASSWORD:
        raise RuntimeError("CLICKHOUSE_USER / CLICKHOUSE_PASSWORD not set")

    query = f"""
    INSERT INTO {CLICKHOUSE_DB}.{CLICKHOUSE_TABLE}
    SETTINGS input_format_skip_unknown_fields=1
    FORMAT JSONEachRow
    """

    with open("data/events.jsonl", "r", encoding="utf-8") as f:
        data = f.read()

    r = requests.post(
        CLICKHOUSE_URL,
        params={"query": query},
        data=data.encode("utf-8"),
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASSWORD),
        timeout=30,
    )
    r.raise_for_status()
    print("Inserted events into ClickHouse.")

if __name__ == '__main__':
    main()
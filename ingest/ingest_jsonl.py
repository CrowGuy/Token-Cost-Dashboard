import json
import sys
import requests

CLICKHOUSE_URL = "http://localhost:8123"
DB = "analytics"
TABLE = "llm_usage_events"
JSONL_PATH = "data/events.jsonl"

USER = "admin"
PASSWORD = "admin123"

def main():
    # ClickHouse 可以直接 ingest JSONEachRow
    query = f"""
        INSERT INTO {DB}.{TABLE}
        SETTINGS input_format_skip_unknown_fields=1
        FORMAT JSONEachRow
        """
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        data = f.read()

    r = requests.post(
        CLICKHOUSE_URL,
        params={"query": query},
        data=data.encode("utf-8"),
        auth=(USER, PASSWORD),
        timeout=30,
    )

    if r.status_code != 200:
        print("Status:", r.status_code)
        print("Response:", r.text[:2000])

    r.raise_for_status()
    print("Inserted events into ClickHouse.")

if __name__ == "__main__":
    main()
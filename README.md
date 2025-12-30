# Token-Cost-Dashboard
Token cost dashboard for LLM serverices.

## Repo Layout
```
token-cost-dashboard/
  docker-compose.yml
  pricing/
    price_book.yaml
  schema/
    llm_usage_event.json
  gateway_sdk/
    __init__.py
    instrument.py
    pricing.py
    emitter.py
  ingest/
    clickhouse_ddl.sql
    ingest_jsonl.py
  examples/
    demo_call.py
  data/
    events.jsonl
  .env
```
## Create your .env
```
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_DB=analytics
CLICKHOUSE_USER=<account>
CLICKHOUSE_PASSWORD=<password>
```

## ClickHouse + Metabase
```bash
docker compose up -d
```
| Metabase 連 ClickHouse 需要 ClickHouse JDBC driver

## ClickHouse Event DDL
```bash
source scripts/load_env.sh .env

curl -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" "${CLICKHOUSE_URL}/" --data-binary @ingest/01_create_db.sql
curl -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" "${CLICKHOUSE_URL}/" --data-binary @ingest/02_create_table.sql

source scripts/unload_env.sh
```

## Pricing table versionlize
| 之後價格調整：只新增一筆更晚的 effective_from，不要覆寫舊的。這就是版本化的核心。

## Quick Start
```bash
python -m examples.demo_call
```

## Import data into ClickHouse
```bash
pip install requests pyyaml
python ingest/ingest_jsonl.py
```

## Build the Query in the Metabase
### Overview：今日/本週總成本
```sql
SELECT
  toDate(timestamp) AS day,
  sum(computed_cost) AS cost
FROM analytics.llm_usage_events
WHERE timestamp >= now() - INTERVAL 7 DAY
GROUP BY day
ORDER BY day;
```
Convert to Line chart  
X-axis：day  
Y-axis：cost  
Name：`Daily Cost (Last 7 Days)`  

### Top tenants（誰在花）
```sql
SELECT
  tenant_id,
  sum(computed_cost) AS cost,
  sum(total_tokens) AS tokens
FROM analytics.llm_usage_events
WHERE timestamp >= now() - INTERVAL 7 DAY
GROUP BY tenant_id
ORDER BY cost DESC
LIMIT 10;
```
Convert to Bar chart  
X-axis：tenant_id  
Y-axis：cost  
Name：`Top Tenants by Cost (7d)`  

### Cost by feature（花在哪）
```sql
SELECT
  feature,
  sum(computed_cost) AS cost,
  sum(prompt_tokens) AS prompt_tokens,
  sum(completion_tokens) AS completion_tokens
FROM analytics.llm_usage_events
WHERE timestamp >= now() - INTERVAL 7 DAY
GROUP BY feature
ORDER BY cost DESC;
```
Convert to Bar chart (Stacked bar)  
X-axis：feature  
Y-axis：cost  
Name：Cost by Feature  

### Token trends：prompt vs completion（為什麼變貴）
```sql
SELECT
  toStartOfHour(timestamp) AS h,
  sum(prompt_tokens) AS prompt_tokens,
  sum(completion_tokens) AS completion_tokens,
  sum(computed_cost) AS cost
FROM analytics.llm_usage_events
WHERE timestamp >= now() - INTERVAL 72 HOUR
GROUP BY h
ORDER BY h;
```
Convert to Line chart (Set as Multiple series)
X-axis：hour  
Y-axis：
 - prompt_tokens
 - completion_tokens
  
Name：Token Trend: Prompt vs Completion

Next to do:  
✅ ClickHouse 的「每小時 rollup 表」+ 物化視圖（查詢快很多）  
✅ v1 anomaly（7 天基準 + z-score/倍數規則）+ alert webhook 範例
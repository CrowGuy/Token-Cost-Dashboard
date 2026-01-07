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

## Environments
- Python 3.10  

Plz based on the bellow command to install libs in your python env.
```bash
pip install -r requirements.txt
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
set -a; source .env.clickhouse; set +a;
curl -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" "${CLICKHOUSE_URL}/" --data-binary @ingest/01_create_db.sql
curl -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" "${CLICKHOUSE_URL}/" --data-binary @ingest/02_create_table.sql
```

## Pricing table versionlize
| 之後價格調整：只新增一筆更晚的 effective_from，不要覆寫舊的。這就是版本化的核心。

## Quick Start
Set up the env var.
```bash
set -a
source .env.llm
source .env.app
set +a
```
Just demo with fake call.
```bash
python -m examples.demo_call
```
If you wanna demo with real call.
```bash
python -m examples.demo_real_call
```

## Import data into ClickHouse
```bash
python ingest/ingest_jsonl.py
```


## 🎯 Dashboard 設計目標
Token Cost Dashboard 主要回答四個核心問題：

- 現在花了多少錢？（整體趨勢）
- 是誰在花錢？（Tenant / 使用者）
- 錢花在哪裡？（Feature / 功能）
- 為什麼突然變貴？（Prompt vs Completion、重試、單一 request）

因此整體設計採用「**由上而下（Top-down）**」的分析流程：
`Overall` → `Feature` → `Request` → `Attempt`

## 📊 資料來源
資料表：`analytics.llm_usage_events`
主要欄位：
- timestamp  
- tenant_id  
- feature  
- request_id  
- attempt  
- prompt_tokens  
- completion_tokens  
- total_tokens  
- computed_cost  
- latency_ms  
- retry_count  
- model / provider / region  
- cache_hit  

---
## 1️⃣ Overall Cost Overview（整體成本趨勢）
### 用途
快速確認 **最近 7 天每日成本是否異常上升**，並作為所有分析的入口。

### SQL（每日成本）
```sql
SELECT
  day,
  sum(computed_cost) AS cost
FROM
(
  SELECT
    toDate(timestamp) AS day,
    computed_cost
  FROM analytics.llm_usage_events
  WHERE timestamp >= now() - INTERVAL 7 DAY
)
GROUP BY day
ORDER BY day
WITH FILL
  FROM toDate(now() - INTERVAL 6 DAY)
  TO toDate(now())
  STEP 1;
```
**Metabase Visualization**
- Type：Line chart
- X-axis：day
- Y-axis：cost
- Name：Daily Cost (Last 7 Days)

> `WITH FILL` 確保即使某天沒有流量，也會顯示 0，避免折線圖斷裂。
---
## 2️⃣ Top Tenants（誰在花錢）
### 用途
快速找出 成本貢獻最高的 Tenant，判斷是否是單一客戶導致成本異常。

### SQL
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
**Metabase Visualization**
- Type：Bar chart
- X-axis：tenant_id
- Y-axis：cost
- Name：Top Tenants by Cost (7d)
---
## 3️⃣ Cost by Feature（錢花在哪）
### 用途
確認 哪一個 feature 是主要成本來源，也是後續 drill-down 的第一層。

### SQL
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
**Metabase Visualization**
- Type：Stacked Bar chart
- X-axis：feature
- Y-axis：cost
- Name：Cost by Feature
---
## 4️⃣ Token Trend（為什麼變貴）
### 用途
判斷成本上升是來自：
- Prompt 變長？
- Completion 變多？
- 還是兩者同時增加？

### SQL（最近 72 小時，按小時）
```sql
SELECT
  hour,
  sum(prompt_tokens) AS prompt_tokens,
  sum(completion_tokens) AS completion_tokens
FROM
(
  SELECT
    toStartOfHour(timestamp) AS hour,
    prompt_tokens,
    completion_tokens
  FROM analytics.llm_usage_events
  WHERE timestamp >= now() - INTERVAL 72 HOUR
)
GROUP BY hour
ORDER BY hour
WITH FILL
  FROM toStartOfHour(now() - INTERVAL 72 HOUR)
  TO toStartOfHour(now())
  STEP INTERVAL 1 HOUR;
```
**Metabase Visualization**
- Type：Line chart（Multiple series）
- X-axis：hour
- Series：  
  - prompt_tokens
  - completion_tokens
- Name：`Token Trend: Prompt vs Completion`
---
## 5️⃣ Drill Down：從 Feature → Request → Attempt
### 分析路徑
```
Feature 成本飆升
  → 找出該 Feature 的高成本 Request
    → 查看單一 Request 的重試、tokens 與成本分佈
```
### Q1：Feature Ranking（Feature 概覽）
#### 目的：比較 feature 的成本、流量、延遲與重試情況。
```sql
SELECT
  feature,
  sum(computed_cost) AS cost,
  sum(prompt_tokens) AS prompt_tokens,
  sum(completion_tokens) AS completion_tokens,
  count() AS calls,
  avg(latency_ms) AS avg_latency_ms,
  sum(retry_count) AS retries,
  sum(cache_hit) AS cache_hits
FROM analytics.llm_usage_events
WHERE timestamp >= now() - INTERVAL 7 DAY
GROUP BY feature
ORDER BY cost DESC;
```
Name：`Feature Ranking (7d)`

----
### Q2：Requests by Feature（Request 列表）
#### 目的：查看某一 feature 底下，最近的 request 與其成本。
```sql
SELECT
  timestamp,
  request_id,
  concat(
    'http://localhost:3000/question/44-request-detail-by-request-id?request_id=',
    request_id
  ) AS request_link,
  tenant_id,
  model,
  total_tokens,
  computed_cost,
  latency_ms,
  status
FROM analytics.llm_usage_events
WHERE {{feature}}
ORDER BY timestamp DESC
LIMIT 200;
```
**Metabase 參數設定（非常重要）**
- {{feature}}
  - Type：Field Filter
  - Field：analytics.llm_usage_events.feature
  - Widget：Dropdown / Search
- Visualization：Table
- Name：Requests (by Feature)
---
### Q3：Request Detail（最終 Drill-down）
#### 目的：分析單一 request 的完整生命週期：
- 總共幾次 attempt
- 每次 attempt 的 tokens / cost / latency
- 哪一次最貴

#### 此 Query 會產生：
- 一列 Summary（Header）
- 多列 Attempt 明細
```sql
WITH
  req AS (
    SELECT *
    FROM analytics.llm_usage_events
    WHERE request_id = {{request_id}}
  ),

  summary_raw AS (
    SELECT
      toString({{request_id}}) AS req_id,
      min(timestamp) AS first_seen,
      max(timestamp) AS last_seen,
      any(feature) AS feature,
      any(tenant_id) AS tenant_id,
      any(user_id) AS user_id,
      count() AS attempts,
      sum(prompt_tokens) AS total_prompt_tokens,
      sum(completion_tokens) AS total_completion_tokens,
      sum(total_tokens) AS total_tokens,
      sum(computed_cost) AS summary_total_cost,
      sum(retry_count) AS total_retry_count
    FROM req
  ),

  summary AS (
    SELECT
      0 AS sort_key,
      concat('— REQUEST ', req_id, ' SUMMARY —') AS row_type,

      first_seen,
      last_seen,
      feature,
      tenant_id,
      user_id,
      attempts,
      total_prompt_tokens,
      total_completion_tokens,
      total_tokens,
      summary_total_cost AS total_cost,
      total_retry_count,

      if(total_tokens = 0, 0.0, toFloat64(total_prompt_tokens) / toFloat64(total_tokens)) AS prompt_share,
      CAST(NULL AS Nullable(Float64)) AS attempt_cost_share,  -- summary 不用

      CAST(NULL AS Nullable(UInt8)) AS attempt,
      CAST(NULL AS Nullable(String)) AS provider,
      CAST(NULL AS Nullable(String)) AS model,
      CAST(NULL AS Nullable(String)) AS region,
      CAST(NULL AS Nullable(Int32)) AS latency_ms,
      CAST(NULL AS Nullable(String)) AS status,
      CAST(NULL AS Nullable(UInt8)) AS cache_hit,
      CAST(NULL AS Nullable(String)) AS prompt_template_id
    FROM summary_raw
  ),

  details AS (
    SELECT
      1 AS sort_key,
      '' AS row_type,

      timestamp AS first_seen,
      CAST(NULL AS Nullable(DateTime64(3, 'UTC'))) AS last_seen,

      CAST(NULL AS Nullable(String)) AS feature,
      CAST(NULL AS Nullable(String)) AS tenant_id,
      CAST(NULL AS Nullable(String)) AS user_id,

      CAST(NULL AS Nullable(UInt64)) AS attempts,
      prompt_tokens AS total_prompt_tokens,
      completion_tokens AS total_completion_tokens,
      total_tokens,
      computed_cost AS total_cost,
      retry_count AS total_retry_count,

      CAST(NULL AS Nullable(Float64)) AS prompt_share,

      -- attempt_cost_share: 單次 attempt cost / request 總 cost
      if(
        (SELECT summary_total_cost FROM summary_raw) = 0,
        0.0,
        toFloat64(computed_cost) / toFloat64((SELECT summary_total_cost FROM summary_raw))
      ) AS attempt_cost_share,

      attempt,
      provider,
      model,
      region,
      latency_ms,
      status,
      cache_hit,
      prompt_template_id
    FROM req
  )

SELECT
  sort_key,
  row_type,
  first_seen,
  last_seen,
  feature,
  tenant_id,
  user_id,
  attempts,
  total_prompt_tokens,
  total_completion_tokens,
  total_tokens,
  total_cost,
  total_retry_count,
  prompt_share,
  attempt_cost_share,

  attempt,
  provider,
  model,
  region,
  latency_ms,
  status,
  cache_hit,
  prompt_template_id,

  if(
    sort_key = 0,
    concat('http://localhost:3000/dashboard/3-cost-drill-down-feature-first?feature=', feature),
    CAST(NULL AS Nullable(String))
  ) AS back_to_feature_dashboard
FROM (
  SELECT * FROM summary
  UNION ALL
  SELECT * FROM details
)
ORDER BY
  sort_key ASC,
  attempt ASC,
  first_seen ASC;
```
**Metabase 參數設定**
- Name：Request Detail (by request_id)
- {{request_id}}
  - Type：Text
  - Widget：Input
- Visualization：Table

**Summary Row 會額外計算：**
- prompt_share（Prompt tokens / Total tokens）
- Request 總成本
- Attempt 數量與重試次數
**Attempt Row 會顯示：**
- attempt_cost_share（單次 attempt 成本佔比）
- latency / model / provider / status
---
### 🧠 設計重點總結
- Top-down 分析路徑：避免一開始就看 raw logs
- Feature-first drill-down：最符合產品與成本歸因
- Summary + Detail 合併顯示：一眼看懂 request 的全貌
- Prompt vs Completion 拆分：直接對應成本上升原因
- ClickHouse 聚合 + Metabase 參數化：效能與可維護性兼顧

Next to do:  
### Milestone A：Dashboard 變產品（1～2 天）
Overview + Token trend（你已有）
✅ Drill-down：feature → request list → request detail
✅ 可用的時間軸補齊（你已在做）

驗收
能從「成本上升」一路 drill 到「是哪幾筆 request」

### Milestone B：會自動抓爆點（1～2 天）
✅ Anomaly v1：今日 vs 過去 7 天平均（feature/tenant/model）
✅ Webhook 通知（超過門檻）
驗收
demo：刻意讓某 feature prompt 變長 → 觸發告警

### Milestone C：性能與可擴充（0.5～1 天）
✅ hourly rollup + MV
dashboard query 改讀 rollup
raw 表保留作鑽到底
驗收
同一張 dashboard 在資料量變大後仍然秒開
CREATE TABLE IF NOT EXISTS analytics.llm_usage_events
(
  event_date Date DEFAULT toDate(timestamp),
  timestamp DateTime64(3, 'UTC'),

  request_id String,
  attempt UInt16 DEFAULT 1,

  tenant_id String,
  user_id String,
  feature LowCardinality(String),
  endpoint LowCardinality(String),
  prompt_template_id LowCardinality(String),

  provider LowCardinality(String),
  model LowCardinality(String),
  region LowCardinality(String),

  prompt_tokens UInt32,
  completion_tokens UInt32,
  total_tokens UInt32,

  latency_ms UInt32,
  status LowCardinality(String),
  retry_count UInt16,
  cache_hit UInt8,

  price_version LowCardinality(String),
  unit_price_prompt Float64,
  unit_price_completion Float64,
  computed_cost Float64,

  -- 方便分析但不觸碰 PII
  prompt_chars UInt32 DEFAULT 0,
  completion_chars UInt32 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, tenant_id, feature, model, endpoint, request_id, attempt)
SETTINGS index_granularity = 8192;
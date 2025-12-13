#!/bin/bash
# Run after Elasticsearch starts: ./infra/es-index-template.sh

set -e

ES_HOST="${ES_HOST:-localhost:9200}"

echo "Creating Elasticsearch index template for crawler logs..."

curl -X PUT "http://${ES_HOST}/_index_template/crawler-traces-template" \
  -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["crawler-traces*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "index.refresh_interval": "5s"
    },
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "level_detail": { "type": "keyword" },
        "logger": { "type": "keyword" },
        "trace_context": {
          "properties": {
            "session_id": { "type": "keyword" },
            "request_id": { "type": "keyword" },
            "trace_id": { "type": "keyword" },
            "span_id": { "type": "keyword" },
            "parent_span_id": { "type": "keyword" }
          }
        },
        "event": {
          "properties": {
            "category": { "type": "keyword" },
            "type": { "type": "keyword" },
            "name": { "type": "text" }
          }
        },
        "context": {
          "properties": {
            "agent_id": { "type": "keyword" },
            "agent_type": { "type": "keyword" },
            "tool_name": { "type": "keyword" },
            "model_name": { "type": "keyword" },
            "model_provider": { "type": "keyword" },
            "iteration": { "type": "integer" },
            "url": { "type": "keyword" }
          }
        },
        "metrics": {
          "properties": {
            "duration_ms": { "type": "float" },
            "time_to_first_token_ms": { "type": "float" },
            "tokens_input": { "type": "integer" },
            "tokens_output": { "type": "integer" },
            "tokens_total": { "type": "integer" },
            "estimated_cost_usd": { "type": "float" },
            "retry_count": { "type": "integer" },
            "content_size_bytes": { "type": "integer" }
          }
        },
        "tags": { "type": "keyword" },
        "message": { "type": "text" }
      }
    }
  }
}'

echo ""
echo "Index template created successfully!"
echo ""
echo "Next steps:"
echo "  1. Access Kibana at http://localhost:5601"
echo "  2. Create a data view with pattern: crawler-traces-*"
echo "  3. Use Discover to explore your logs"

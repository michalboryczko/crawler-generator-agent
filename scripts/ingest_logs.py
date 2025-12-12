#!/usr/bin/env python3
"""Ingest JSONL log files into Elasticsearch.

Usage:
    python scripts/ingest_logs.py [log_dir] [es_host]

Examples:
    # Ingest from default directory
    python scripts/ingest_logs.py

    # Ingest from specific directory
    python scripts/ingest_logs.py /path/to/logs

    # Ingest to remote Elasticsearch
    python scripts/ingest_logs.py logs http://elasticsearch.example.com:9200
"""

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from elasticsearch import Elasticsearch, helpers
except ImportError:
    print("Error: elasticsearch package not found")
    print("Install it with: pip install elasticsearch>=8.0.0")
    sys.exit(1)


def ingest_logs(log_dir: str = "logs", es_host: str = "http://localhost:9200"):
    """Ingest all JSONL files from log_dir into Elasticsearch.

    Args:
        log_dir: Directory containing .jsonl log files
        es_host: Elasticsearch host URL
    """
    es = Elasticsearch([es_host])

    # Check connection
    if not es.ping():
        print(f"Error: Cannot connect to Elasticsearch at {es_host}")
        print("Make sure Elasticsearch is running:")
        print("  docker compose -f docker-compose.logging.yml up -d")
        sys.exit(1)

    print(f"Connected to Elasticsearch at {es_host}")

    # Generate index name with date
    index_name = f"crawler-logs-{datetime.now().strftime('%Y.%m.%d')}"
    log_path = Path(log_dir)

    if not log_path.exists():
        print(f"Error: Log directory not found: {log_dir}")
        sys.exit(1)

    jsonl_files = list(log_path.glob("*.jsonl"))
    if not jsonl_files:
        print(f"No .jsonl files found in {log_dir}")
        sys.exit(0)

    print(f"Found {len(jsonl_files)} log file(s) to ingest")

    def generate_actions():
        """Generate bulk actions from log files."""
        total_docs = 0
        for log_file in jsonl_files:
            print(f"Processing: {log_file}")
            file_docs = 0
            with open(log_file) as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            doc = json.loads(line)
                            yield {
                                "_index": index_name,
                                "_source": doc
                            }
                            file_docs += 1
                            total_docs += 1
                        except json.JSONDecodeError as e:
                            print(f"  Warning: Skipping line {line_num}: {e}")
            print(f"  Processed {file_docs} documents")

    # Bulk ingest
    print("\nIngesting to Elasticsearch...")
    success, errors = helpers.bulk(es, generate_actions(), stats_only=True)

    print(f"\nIngestion complete!")
    print(f"  Index: {index_name}")
    print(f"  Documents ingested: {success}")
    if errors:
        print(f"  Errors: {errors}")

    # Print helpful next steps
    print("\nNext steps:")
    print("  1. Open Kibana: http://localhost:5601")
    print("  2. Go to Stack Management > Data Views")
    print(f"  3. Create data view with pattern: crawler-logs-*")
    print("  4. Use Discover to explore your logs")
    print("\nUseful KQL queries:")
    print("  level: \"ERROR\"                    # Find errors")
    print("  event.type: \"llm.call.complete\"   # Find LLM calls")
    print("  metrics.duration_ms > 5000         # Find slow operations")


def main():
    """Main entry point."""
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "logs"
    es_host = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:9200"

    print(f"Ingesting logs from: {log_dir}")
    print(f"Elasticsearch host: {es_host}")
    print()

    ingest_logs(log_dir, es_host)


if __name__ == "__main__":
    main()

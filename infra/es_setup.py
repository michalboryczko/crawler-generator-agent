#!/usr/bin/env python3
"""Elasticsearch index setup script.

Creates index templates from schema definitions in src/observability/schema.py.
This ensures ES mappings stay in sync with Python code.

Usage:
    python infra/es_setup.py                    # Setup all templates
    python infra/es_setup.py --print            # Print templates as JSON
    python infra/es_setup.py --host es:9200     # Custom ES host
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.observability.schema import (
    generate_log_index_template,
    generate_trace_index_template,
)


def create_index_template(es_host: str, template_name: str, template_body: dict) -> bool:
    """Create an index template in Elasticsearch.

    Args:
        es_host: Elasticsearch host:port
        template_name: Name for the template
        template_body: Template definition

    Returns:
        True if successful
    """
    import urllib.request
    import urllib.error

    url = f"http://{es_host}/_index_template/{template_name}"
    data = json.dumps(template_body).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        method='PUT',
        headers={'Content-Type': 'application/json'}
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('acknowledged', False)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Error creating {template_name}: {e.code} - {error_body}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup Elasticsearch index templates from schema definitions"
    )
    parser.add_argument(
        "--host",
        default="localhost:9200",
        help="Elasticsearch host:port (default: localhost:9200)"
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="Print templates as JSON instead of creating them"
    )
    parser.add_argument(
        "--logs-pattern",
        default="crawler-logs*",
        help="Index pattern for logs (default: crawler-logs*)"
    )
    parser.add_argument(
        "--traces-pattern",
        default="crawler-traces*",
        help="Index pattern for traces (default: crawler-traces*)"
    )
    args = parser.parse_args()

    # Generate templates from schema
    templates = {
        "crawler-logs-template": generate_log_index_template(args.logs_pattern),
        "crawler-traces-template": generate_trace_index_template(args.traces_pattern),
    }

    if args.print_only:
        for name, body in templates.items():
            print(f"# {name}")
            print(json.dumps(body, indent=2))
            print()
        return 0

    # Create templates in ES
    print(f"Creating Elasticsearch index templates on {args.host}...")
    print()

    success = True
    for name, body in templates.items():
        print(f"Creating {name}...", end=" ")
        if create_index_template(args.host, name, body):
            print("OK")
        else:
            print("FAILED")
            success = False

    print()
    if success:
        print("All templates created successfully!")
        print()
        print("Next steps:")
        print("  1. Access Kibana at http://localhost:5601")
        print("  2. Create data views:")
        print(f"     - {args.logs_pattern} for log events")
        print(f"     - {args.traces_pattern} for trace spans")
        print("  3. Use Discover to explore your data")
        return 0
    else:
        print("Some templates failed to create.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

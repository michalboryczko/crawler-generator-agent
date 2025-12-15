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


def delete_index_template(es_host: str, template_name: str) -> bool:
    """Delete an index template from Elasticsearch.

    Args:
        es_host: Elasticsearch host:port
        template_name: Name of the template to delete

    Returns:
        True if successful or template didn't exist
    """
    import urllib.error
    import urllib.request

    url = f"http://{es_host}/_index_template/{template_name}"

    req = urllib.request.Request(url, method='DELETE')

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('acknowledged', False)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Template doesn't exist, that's fine
            return True
        error_body = e.read().decode('utf-8')
        print(f"Error deleting {template_name}: {e.code} - {error_body}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        return False


def list_indices(es_host: str, pattern: str) -> list:
    """List indices matching a pattern.

    Args:
        es_host: Elasticsearch host:port
        pattern: Index pattern prefix (e.g., "crawler-logs")

    Returns:
        List of index names
    """
    import fnmatch
    import urllib.error
    import urllib.request

    url = f"http://{es_host}/_cat/indices?format=json"

    try:
        with urllib.request.urlopen(url) as response:
            indices = json.loads(response.read().decode('utf-8'))
            # Filter by pattern using fnmatch
            return [idx['index'] for idx in indices if fnmatch.fnmatch(idx['index'], pattern)]
    except Exception:
        return []


def delete_index(es_host: str, index_pattern: str) -> bool:
    """Delete indices matching a pattern.

    ES 8.x blocks wildcard deletes, so we list indices first then delete by name.

    Args:
        es_host: Elasticsearch host:port
        index_pattern: Index pattern to delete (e.g., "crawler-logs*")

    Returns:
        True if successful or indices didn't exist
    """
    import urllib.error
    import urllib.request

    # List matching indices first
    indices = list_indices(es_host, index_pattern)

    if not indices:
        return True  # Nothing to delete

    # Delete each index by exact name
    all_ok = True
    for index_name in indices:
        url = f"http://{es_host}/{index_name}"
        req = urllib.request.Request(url, method='DELETE')

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                if not result.get('acknowledged', False):
                    all_ok = False
        except urllib.error.HTTPError as e:
            if e.code != 404:
                error_body = e.read().decode('utf-8')
                print(f"Error deleting {index_name}: {e.code} - {error_body}", file=sys.stderr)
                all_ok = False
        except urllib.error.URLError as e:
            print(f"Connection error: {e.reason}", file=sys.stderr)
            all_ok = False

    return all_ok


def create_index_template(es_host: str, template_name: str, template_body: dict) -> bool:
    """Create an index template in Elasticsearch.

    Args:
        es_host: Elasticsearch host:port
        template_name: Name for the template
        template_body: Template definition

    Returns:
        True if successful
    """
    import urllib.error
    import urllib.request

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
        "--clean",
        action="store_true",
        help="Delete existing indices before setup (fresh start)"
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
        "crawler-logs-template": (args.logs_pattern, generate_log_index_template(args.logs_pattern)),
        "crawler-traces-template": (args.traces_pattern, generate_trace_index_template(args.traces_pattern)),
    }

    if args.print_only:
        for name, (_pattern, body) in templates.items():
            print(f"# {name}")
            print(json.dumps(body, indent=2))
            print()
        return 0

    success = True

    # Clean existing indices if requested
    if args.clean:
        print(f"Cleaning existing indices on {args.host}...")
        print()
        for _name, (pattern, _body) in templates.items():
            print(f"Deleting indices {pattern}...", end=" ")
            if delete_index(args.host, pattern):
                print("OK")
            else:
                print("FAILED")
                success = False
        print()

    # Delete existing templates before creating new ones
    print(f"Deleting existing templates on {args.host}...")
    print()
    for name in templates:
        print(f"Deleting {name}...", end=" ")
        if delete_index_template(args.host, name):
            print("OK")
        else:
            print("FAILED")
            success = False
    print()

    # Create templates in ES
    print("Creating index templates...")
    print()

    for name, (_pattern, body) in templates.items():
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

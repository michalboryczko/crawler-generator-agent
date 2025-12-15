#!/bin/bash
# Setup Kibana dashboards and data views for crawler logs
# Run this AFTER Kibana is fully started

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up Kibana for Crawler Agent logs..."
echo "Kibana URL: $KIBANA_URL"

# Wait for Kibana to be ready
echo "Waiting for Kibana to be ready..."
for i in {1..30}; do
    if curl -s "$KIBANA_URL/api/status" | grep -q '"level":"available"'; then
        echo "Kibana is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Kibana not ready after 30 attempts"
        exit 1
    fi
    echo "  Attempt $i/30 - waiting..."
    sleep 2
done

# Import saved objects (data view, searches, visualizations, dashboard)
echo ""
echo "Importing dashboard and visualizations..."
IMPORT_RESULT=$(curl -s -X POST "$KIBANA_URL/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@$SCRIPT_DIR/kibana-dashboard.ndjson")

if echo "$IMPORT_RESULT" | grep -q '"success":true'; then
    echo "Dashboard imported successfully!"
else
    echo "Import result: $IMPORT_RESULT"
fi

echo ""
echo "============================================"
echo "Setup complete!"
echo ""
echo "What was created:"
echo "  - Data view: crawler-traces-*"
echo "  - Saved searches:"
echo "      * All Logs"
echo "      * Errors Only"
echo "      * LLM Calls"
echo "      * Agent Events"
echo "      * Slow Operations"
echo "  - Visualizations:"
echo "      * Errors Over Time (line chart)"
echo "      * Total LLM Cost (metric)"
echo "      * Total Tokens (metric)"
echo "      * Events by Category (pie)"
echo "      * Agent Duration (bar)"
echo "      * Log Levels (pie)"
echo "      * Tool Usage (bar)"
echo "      * Cost by Model (pie)"
echo "  - Dashboard: Crawler Agent Dashboard"
echo ""
echo "Access Kibana at: $KIBANA_URL"
echo ""
echo "Quick links:"
echo "  Dashboard:  $KIBANA_URL/app/dashboards#/view/crawler-dashboard"
echo "  Discover:   $KIBANA_URL/app/discover"
echo "============================================"

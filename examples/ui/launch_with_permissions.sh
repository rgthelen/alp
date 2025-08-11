#!/bin/bash

# ALP UI Programs Launch Script with Proper Permissions
# This script demonstrates how to run ALP programs with the required security permissions

echo "ALP UI Examples - Launch with Permissions"
echo "=========================================="
echo ""
echo "Choose which program to run:"
echo "1) Calculator (no special permissions needed)"
echo "2) Weather (needs HTTP permission)"
echo "3) Multi-Tool (mixed permissions)"
echo "4) Full Orchestrator (all permissions)"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo "Running Calculator UI..."
        uv run python main.py examples/ui/calculator.alp
        ;;
    2)
        echo "Running Weather UI with HTTP permission..."
        echo "This requires access to api.open-meteo.com"
        ALP_HTTP_ALLOWLIST=api.open-meteo.com uv run python main.py examples/ui/weather_ui.alp
        ;;
    3)
        echo "Running Multi-Tool UI..."
        uv run python main.py examples/ui/multi_tool.alp
        ;;
    4)
        echo "Running Full Orchestrator with all permissions..."
        echo "This enables:"
        echo "  - HTTP access to weather APIs"
        echo "  - File I/O for data processing"
        echo "  - LLM access (if configured)"
        
        # Set all necessary permissions
        ALP_HTTP_ALLOWLIST=api.open-meteo.com,api.weatherapi.com \
        ALP_IO_ROOT=/tmp/alp_workspace \
        ALP_ALLOW_WRITE=true \
        uv run python main.py examples/ui/orchestrator.alp
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
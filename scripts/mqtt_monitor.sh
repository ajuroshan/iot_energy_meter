#!/bin/bash
# MQTT Monitor Script for IoT Energy Meter
# Subscribes to all station topics to monitor traffic

# Configuration
PROD_BROKER="15.207.150.87"
LOCAL_BROKER="localhost"
TOPIC_PREFIX="charging/stations"

# Station UUIDs
STATION_1_UUID="a079734a-0e2d-4589-9da8-82ce079c6519"
STATION_2_UUID="bce9c8e1-bce0-406c-a182-6285c7f1a5a1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}     IoT Energy Meter - MQTT Monitor${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_usage() {
    echo "Usage: $0 [environment] [options]"
    echo ""
    echo "Environments:"
    echo "  production, prod    Connect to AWS production (15.207.150.87)"
    echo "  local, dev          Connect to local Docker (localhost)"
    echo ""
    echo "Options:"
    echo "  --station1          Monitor only Station 1"
    echo "  --station2          Monitor only Station 2"
    echo "  --all               Monitor all topics (default)"
    echo ""
    echo "Examples:"
    echo "  $0 production                  # Monitor all topics on production"
    echo "  $0 local --station1            # Monitor Station 1 on local"
    echo "  $0 prod --all                  # Monitor all topics on production"
}

# Parse arguments
ENV="production"
STATION_FILTER="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        production|prod)
            ENV="production"
            shift
            ;;
        local|dev)
            ENV="local"
            shift
            ;;
        --station1)
            STATION_FILTER="station1"
            shift
            ;;
        --station2)
            STATION_FILTER="station2"
            shift
            ;;
        --all)
            STATION_FILTER="all"
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# Set broker based on environment
if [ "$ENV" = "production" ]; then
    BROKER="$PROD_BROKER"
    ENV_LABEL="PRODUCTION (AWS)"
else
    BROKER="$LOCAL_BROKER"
    ENV_LABEL="LOCAL (Docker)"
fi

# Determine topic pattern
if [ "$STATION_FILTER" = "station1" ]; then
    TOPIC_PATTERN="${TOPIC_PREFIX}/${STATION_1_UUID}/#"
elif [ "$STATION_FILTER" = "station2" ]; then
    TOPIC_PATTERN="${TOPIC_PREFIX}/${STATION_2_UUID}/#"
else
    TOPIC_PATTERN="${TOPIC_PREFIX}/#"
fi

print_header
echo ""
echo -e "${GREEN}Environment:${NC} $ENV_LABEL"
echo -e "${GREEN}Broker:${NC}      $BROKER:1883"
echo -e "${GREEN}Topic:${NC}       $TOPIC_PATTERN"
echo ""
echo -e "${YELLOW}Subscribing to MQTT topics...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""
echo -e "${BLUE}------------------------------------------------${NC}"

# Run mosquitto_sub via Docker
docker compose exec -T mqtt mosquitto_sub \
    -h "$BROKER" \
    -p 1883 \
    -t "$TOPIC_PATTERN" \
    -v \
    --pretty 2>/dev/null || {
    echo -e "${RED}Failed to connect. Make sure:${NC}"
    echo "  1. Docker containers are running (docker compose ps)"
    echo "  2. The broker is accessible (nc -zv $BROKER 1883)"
    exit 1
}

#!/bin/bash

# AI-powered RFP Response Agent - Configuration Management Script
# This script manages environment-specific configurations

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_DIR="$PROJECT_ROOT/config"

# Default values
ENVIRONMENT="dev"
ACTION=""
CONFIG_KEY=""
CONFIG_VALUE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] ACTION

Manage environment-specific configurations

ACTIONS:
    list                            List all configurations for environment
    get KEY                         Get specific configuration value
    set KEY VALUE                   Set configuration value
    delete KEY                      Delete configuration key
    validate                        Validate configuration format

OPTIONS:
    -e, --environment ENVIRONMENT   Environment name (dev, staging, prod) [default: dev]
    -h, --help                     Show this help message

EXAMPLES:
    $0 -e dev list                              # List dev configurations
    $0 -e prod get SAM_API_KEY                  # Get production API key
    $0 -e staging set COMPANY_NAME "My Company" # Set staging company name
    $0 validate                                 # Validate all configurations

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        list|get|set|delete|validate)
            ACTION="$1"
            shift
            break
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Parse action-specific arguments
case "$ACTION" in
    get|delete)
        if [[ $# -lt 1 ]]; then
            print_error "Key is required for $ACTION action"
            exit 1
        fi
        CONFIG_KEY="$1"
        ;;
    set)
        if [[ $# -lt 2 ]]; then
            print_error "Key and value are required for set action"
            exit 1
        fi
        CONFIG_KEY="$1"
        CONFIG_VALUE="$2"
        ;;
esac

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Environment must be one of: dev, staging, prod"
    exit 1
fi

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

CONFIG_FILE="$CONFIG_DIR/$ENVIRONMENT.env"

print_success "Configuration management completed!"
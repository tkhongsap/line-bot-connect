#!/bin/bash

# Load Testing Script for LINE Bot Async Processing
# This script provides easy execution of various load testing scenarios

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOAD_TEST_DIR="$PROJECT_ROOT/tests/load"
RESULTS_DIR="$PROJECT_ROOT/load_test_results"

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

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

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install uv first."
        exit 1
    fi
    
    # Check if pytest is available
    if ! uv run python -c "import pytest" &> /dev/null; then
        print_error "pytest is not available. Installing test dependencies..."
        uv sync --group test
    fi
    
    # Check if load test files exist
    if [ ! -f "$LOAD_TEST_DIR/test_async_load_scenarios.py" ]; then
        print_error "Load test files not found at $LOAD_TEST_DIR"
        exit 1
    fi
    
    print_success "Dependencies check passed"
}

# Function to run a specific load test scenario
run_scenario() {
    local scenario=$1
    local output_file="$RESULTS_DIR/load_test_${scenario}_$(date +%Y%m%d_%H%M%S).log"
    
    print_status "Running $scenario load test scenario..."
    print_status "Results will be saved to: $output_file"
    
    # Create a temporary pytest configuration
    local pytest_args="-v -s --tb=short"
    
    # Add markers for different scenarios
    case $scenario in
        "light"|"moderate")
            pytest_args="$pytest_args -m 'load and not slow'"
            ;;
        "heavy"|"burst"|"endurance")
            pytest_args="$pytest_args -m 'load and slow'"
            ;;
        "streaming")
            pytest_args="$pytest_args -k 'streaming_focused'"
            ;;
        "batch")
            pytest_args="$pytest_args -k 'batch_processing_focused'"
            ;;
    esac
    
    # Run the specific test
    local test_method=""
    case $scenario in
        "light")
            test_method="test_light_load_scenario"
            ;;
        "moderate")
            test_method="test_moderate_load_scenario"
            ;;
        "heavy")
            test_method="test_heavy_load_scenario"
            ;;
        "burst")
            test_method="test_burst_load_scenario"
            ;;
        "endurance")
            test_method="test_endurance_scenario"
            ;;
        "streaming")
            test_method="test_streaming_focused_load"
            ;;
        "batch")
            test_method="test_batch_processing_focused_load"
            ;;
    esac
    
    # Execute the test with output capture
    if uv run pytest "$LOAD_TEST_DIR/test_async_load_scenarios.py::TestAsyncLoadScenarios::$test_method" \
        $pytest_args --capture=no 2>&1 | tee "$output_file"; then
        print_success "Load test $scenario completed. Results saved to $output_file"
        return 0
    else
        print_error "Load test $scenario failed. Check $output_file for details"
        return 1
    fi
}

# Function to run all load test scenarios
run_all_scenarios() {
    print_status "Running all load test scenarios..."
    
    local scenarios=("light" "moderate" "streaming" "batch")
    local failed_scenarios=()
    local passed_scenarios=()
    
    for scenario in "${scenarios[@]}"; do
        if run_scenario "$scenario"; then
            passed_scenarios+=("$scenario")
        else
            failed_scenarios+=("$scenario")
        fi
        echo "" # Add spacing between tests
    done
    
    # Summary
    print_status "Load test summary:"
    if [ ${#passed_scenarios[@]} -gt 0 ]; then
        print_success "Passed scenarios: ${passed_scenarios[*]}"
    fi
    if [ ${#failed_scenarios[@]} -gt 0 ]; then
        print_error "Failed scenarios: ${failed_scenarios[*]}"
        return 1
    fi
    
    print_success "All load tests completed successfully!"
    return 0
}

# Function to run stress tests (heavy scenarios)
run_stress_tests() {
    print_status "Running stress test scenarios..."
    print_warning "These tests may take several minutes and consume significant resources"
    
    local scenarios=("heavy" "burst" "endurance")
    local failed_scenarios=()
    local passed_scenarios=()
    
    for scenario in "${scenarios[@]}"; do
        if run_scenario "$scenario"; then
            passed_scenarios+=("$scenario")
        else
            failed_scenarios+=("$scenario")
        fi
        echo "" # Add spacing between tests
    done
    
    # Summary
    print_status "Stress test summary:"
    if [ ${#passed_scenarios[@]} -gt 0 ]; then
        print_success "Passed scenarios: ${passed_scenarios[*]}"
    fi
    if [ ${#failed_scenarios[@]} -gt 0 ]; then
        print_warning "Failed scenarios: ${failed_scenarios[*]}"
        print_warning "Some failures in stress tests may be expected under extreme load"
    fi
    
    return 0
}

# Function to run manual load test using Python script
run_manual_test() {
    local scenario=${1:-"moderate"}
    local output_file="$RESULTS_DIR/manual_load_test_${scenario}_$(date +%Y%m%d_%H%M%S).log"
    
    print_status "Running manual $scenario load test..."
    print_status "Results will be saved to: $output_file"
    
    if uv run python "$LOAD_TEST_DIR/test_async_load_scenarios.py" "$scenario" 2>&1 | tee "$output_file"; then
        print_success "Manual load test completed. Results saved to $output_file"
        return 0
    else
        print_error "Manual load test failed. Check $output_file for details"
        return 1
    fi
}

# Function to generate load test report
generate_report() {
    print_status "Generating load test report..."
    
    local report_file="$RESULTS_DIR/load_test_report_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$report_file" << EOF
# Load Test Report

Generated on: $(date)

## Test Environment
- Python Version: $(uv run python --version)
- Test Framework: pytest
- Load Test Location: $LOAD_TEST_DIR

## Recent Test Results

EOF
    
    # Add recent test results
    local recent_logs=$(find "$RESULTS_DIR" -name "*.log" -type f -mtime -1 | sort -r | head -10)
    
    if [ -n "$recent_logs" ]; then
        echo "### Recent Test Logs (Last 24 hours)" >> "$report_file"
        echo "" >> "$report_file"
        
        for log_file in $recent_logs; do
            local basename=$(basename "$log_file")
            echo "- [$basename]($log_file)" >> "$report_file"
        done
        echo "" >> "$report_file"
    fi
    
    # Add recommendations
    cat >> "$report_file" << EOF
## Load Test Scenarios

### Available Scenarios:
1. **light** - Basic functionality test with minimal load
2. **moderate** - Normal operating conditions simulation
3. **heavy** - High load stress testing
4. **burst** - Sudden traffic spike simulation
5. **endurance** - Long-running stability test
6. **streaming** - Streaming operation focused test
7. **batch** - Batch processing focused test

### Usage Examples:
\`\`\`bash
# Run specific scenario
./scripts/run_load_tests.sh run light

# Run all basic scenarios
./scripts/run_load_tests.sh all

# Run stress tests
./scripts/run_load_tests.sh stress

# Run manual test
./scripts/run_load_tests.sh manual moderate
\`\`\`

## Performance Benchmarks

Load tests should meet the following criteria:
- Error rate < 5%
- P95 response time < 5000ms for most scenarios
- Throughput > minimum threshold for each scenario
- Memory usage within acceptable limits
- No memory leaks or resource exhaustion

## Monitoring

During load tests, monitor:
- CPU usage
- Memory consumption
- Network I/O
- Database connections (if applicable)
- Queue sizes
- Error rates and types

EOF
    
    print_success "Load test report generated: $report_file"
}

# Function to clean up old results
cleanup_results() {
    local days=${1:-7}
    print_status "Cleaning up load test results older than $days days..."
    
    if find "$RESULTS_DIR" -name "*.log" -type f -mtime +$days -delete 2>/dev/null; then
        print_success "Cleanup completed"
    else
        print_warning "No old results found or cleanup failed"
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Load Testing Script for LINE Bot Async Processing

Usage: $0 <command> [options]

Commands:
    run <scenario>  - Run a specific load test scenario
    all            - Run all basic load test scenarios
    stress         - Run stress test scenarios (heavy, burst, endurance)
    manual <scenario> - Run manual load test using Python script
    report         - Generate load test report
    cleanup [days] - Clean up old results (default: 7 days)
    help           - Show this help message

Scenarios:
    light          - Light load test (5 users, 30 seconds)
    moderate       - Moderate load test (20 users, 60 seconds)
    heavy          - Heavy load test (50 users, 120 seconds)
    burst          - Burst load test (100 users, fast ramp-up)
    endurance      - Long-running test (15 users, 300 seconds)
    streaming      - Streaming-focused test
    batch          - Batch processing-focused test

Examples:
    $0 run light                    # Run light load test
    $0 all                         # Run all basic scenarios
    $0 stress                      # Run stress tests
    $0 manual moderate             # Run manual moderate test
    $0 report                      # Generate report
    $0 cleanup 14                  # Clean up results older than 14 days

Results are saved to: $RESULTS_DIR
EOF
}

# Main script logic
main() {
    case "${1:-help}" in
        "run")
            if [ -z "$2" ]; then
                print_error "Please specify a scenario to run"
                show_usage
                exit 1
            fi
            check_dependencies
            run_scenario "$2"
            ;;
        "all")
            check_dependencies
            run_all_scenarios
            ;;
        "stress")
            check_dependencies
            run_stress_tests
            ;;
        "manual")
            check_dependencies
            run_manual_test "$2"
            ;;
        "report")
            generate_report
            ;;
        "cleanup")
            cleanup_results "$2"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
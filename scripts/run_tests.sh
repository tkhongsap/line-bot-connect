#!/bin/bash

# Test runner script for LINE Bot application
# This script provides various test execution options

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if pytest is available
check_pytest() {
    if ! command -v pytest &> /dev/null; then
        print_error "pytest not found. Install test dependencies with: uv sync --group test"
        exit 1
    fi
}

# Install test dependencies
install_deps() {
    print_header "Installing Test Dependencies"
    if command -v uv &> /dev/null; then
        uv sync --group test
        print_success "Dependencies installed with uv"
    elif command -v pip &> /dev/null; then
        pip install -e ".[test]"
        print_success "Dependencies installed with pip"
    else
        print_error "Neither uv nor pip found"
        exit 1
    fi
}

# Run all tests
run_all_tests() {
    print_header "Running All Tests"
    pytest tests/ -v --tb=short
}

# Run unit tests only
run_unit_tests() {
    print_header "Running Unit Tests"
    pytest tests/unit/ -v -m unit
}

# Run integration tests only
run_integration_tests() {
    print_header "Running Integration Tests"
    pytest tests/integration/ -v -m integration
}

# Run tests with coverage
run_with_coverage() {
    print_header "Running Tests with Coverage"
    pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=80
    print_success "Coverage report generated in htmlcov/"
}

# Run specific test file
run_specific_test() {
    local test_file="$1"
    if [[ -z "$test_file" ]]; then
        print_error "Please specify a test file"
        exit 1
    fi
    
    print_header "Running Test File: $test_file"
    pytest "$test_file" -v
}

# Run tests with specific marker
run_marked_tests() {
    local marker="$1"
    if [[ -z "$marker" ]]; then
        print_error "Please specify a test marker"
        exit 1
    fi
    
    print_header "Running Tests with Marker: $marker"
    pytest tests/ -v -m "$marker"
}

# Run slow tests
run_slow_tests() {
    print_header "Running Slow Tests"
    pytest tests/ -v -m slow
}

# Run quick tests (exclude slow)
run_quick_tests() {
    print_header "Running Quick Tests"
    pytest tests/ -v -m "not slow"
}

# Lint and format checks
run_lint_checks() {
    print_header "Running Lint Checks"
    
    # Check if linting tools are available
    if command -v flake8 &> /dev/null; then
        print_warning "Running flake8..."
        flake8 src/ tests/ || print_warning "flake8 found issues"
    else
        print_warning "flake8 not installed, skipping..."
    fi
    
    if command -v black &> /dev/null; then
        print_warning "Checking black formatting..."
        black --check src/ tests/ || print_warning "black formatting issues found"
    else
        print_warning "black not installed, skipping..."
    fi
    
    if command -v isort &> /dev/null; then
        print_warning "Checking import sorting..."
        isort --check-only src/ tests/ || print_warning "import sorting issues found"
    else
        print_warning "isort not installed, skipping..."
    fi
}

# Run tests in parallel
run_parallel_tests() {
    print_header "Running Tests in Parallel"
    if command -v pytest-xdist &> /dev/null; then
        pytest tests/ -v -n auto
    else
        print_warning "pytest-xdist not installed, running sequentially"
        run_all_tests
    fi
}

# Clean test artifacts
clean_artifacts() {
    print_header "Cleaning Test Artifacts"
    
    # Remove coverage files
    rm -rf htmlcov/ .coverage
    
    # Remove pytest cache
    rm -rf .pytest_cache/
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    print_success "Test artifacts cleaned"
}

# Show test statistics
show_test_stats() {
    print_header "Test Statistics"
    
    echo "Test files:"
    find tests/ -name "test_*.py" | wc -l
    
    echo "Total tests:"
    pytest --collect-only -q tests/ 2>/dev/null | grep "test session starts" -A 1 | tail -1 || echo "Unknown"
    
    echo "Test markers available:"
    pytest --markers | grep "^@pytest.mark" | sort
}

# Help function
show_help() {
    echo "LINE Bot Test Runner"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install           Install test dependencies"
    echo "  all              Run all tests"
    echo "  unit             Run unit tests only"
    echo "  integration      Run integration tests only"
    echo "  coverage         Run tests with coverage report"
    echo "  file <path>      Run specific test file"
    echo "  marker <name>    Run tests with specific marker"
    echo "  slow             Run slow tests only"
    echo "  quick            Run quick tests (exclude slow)"
    echo "  parallel         Run tests in parallel"
    echo "  lint             Run linting checks"
    echo "  clean            Clean test artifacts"
    echo "  stats            Show test statistics"
    echo "  help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 all                              # Run all tests"
    echo "  $0 unit                             # Run unit tests"
    echo "  $0 coverage                         # Run with coverage"
    echo "  $0 file tests/unit/test_openai_service.py  # Run specific file"
    echo "  $0 marker openai_api               # Run OpenAI API tests"
}

# Main script logic
main() {
    local command="${1:-help}"
    
    case "$command" in
        "install")
            install_deps
            ;;
        "all")
            check_pytest
            run_all_tests
            ;;
        "unit")
            check_pytest
            run_unit_tests
            ;;
        "integration")
            check_pytest
            run_integration_tests
            ;;
        "coverage")
            check_pytest
            run_with_coverage
            ;;
        "file")
            check_pytest
            run_specific_test "$2"
            ;;
        "marker")
            check_pytest
            run_marked_tests "$2"
            ;;
        "slow")
            check_pytest
            run_slow_tests
            ;;
        "quick")
            check_pytest
            run_quick_tests
            ;;
        "parallel")
            check_pytest
            run_parallel_tests
            ;;
        "lint")
            run_lint_checks
            ;;
        "clean")
            clean_artifacts
            ;;
        "stats")
            show_test_stats
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
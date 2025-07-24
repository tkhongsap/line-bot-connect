# Testing Guide for LINE Bot Application

This document provides comprehensive guidance for testing the LINE Bot application.

## Quick Start

```bash
# Install test dependencies
./scripts/run_tests.sh install

# Run all tests
./scripts/run_tests.sh all

# Run tests with coverage
./scripts/run_tests.sh coverage
```

## Test Structure

The testing suite is organized into different levels and categories:

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests for individual components
│   ├── test_openai_service.py
│   ├── test_line_service.py
│   └── test_conversation_service.py
├── integration/             # Integration tests for endpoints
│   └── test_webhook_endpoints.py
└── fixtures/                # Test data and fixtures
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
Test individual components in isolation with mocked dependencies.

```bash
# Run all unit tests
./scripts/run_tests.sh unit

# Run specific service tests
./scripts/run_tests.sh marker openai_api
./scripts/run_tests.sh marker line_api
```

### Integration Tests (`@pytest.mark.integration`)
Test component interactions and HTTP endpoints.

```bash
# Run all integration tests
./scripts/run_tests.sh integration
```

## Test Configuration

### pytest.ini
Main pytest configuration with:
- Test discovery patterns
- Coverage settings (80% minimum)
- Custom markers
- Output formatting

### conftest.py
Shared fixtures including:
- Mock settings and services
- Sample test data
- HTTP request blocking (prevents accidental API calls)

## Available Test Commands

### Basic Commands
```bash
./scripts/run_tests.sh all          # Run all tests
./scripts/run_tests.sh unit         # Unit tests only
./scripts/run_tests.sh integration  # Integration tests only
./scripts/run_tests.sh coverage     # With coverage report
```

### Advanced Commands
```bash
./scripts/run_tests.sh quick        # Skip slow tests
./scripts/run_tests.sh slow         # Run slow tests only
./scripts/run_tests.sh parallel     # Run in parallel (if pytest-xdist available)
./scripts/run_tests.sh file tests/unit/test_openai_service.py  # Specific file
```

### Maintenance Commands
```bash
./scripts/run_tests.sh lint         # Run linting checks
./scripts/run_tests.sh clean        # Clean test artifacts
./scripts/run_tests.sh stats        # Show test statistics
```

## Test Markers

Custom pytest markers for test categorization:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests  
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.mock` - Tests requiring extensive mocking
- `@pytest.mark.line_api` - Tests involving LINE Bot API
- `@pytest.mark.openai_api` - Tests involving OpenAI API

## Coverage Requirements

- **Minimum coverage**: 80%
- **Coverage reports**: Terminal + HTML (htmlcov/)
- **Exclude patterns**: Test files, migrations, config files

View detailed coverage:
```bash
./scripts/run_tests.sh coverage
open htmlcov/index.html  # View HTML report
```

## Writing Tests

### Unit Test Example
```python
@pytest.mark.unit
@pytest.mark.openai_api
def test_get_response_success(self, openai_service, sample_openai_response):
    """Test successful OpenAI response"""
    openai_service.client.chat.completions.create.return_value = sample_openai_response
    
    result = openai_service.get_response("user123", "Hello", use_streaming=False)
    
    assert result['success'] is True
    assert result['message'] == "Expected response"
```

### Integration Test Example
```python
@pytest.mark.integration
def test_webhook_endpoint(self, client):
    """Test webhook POST endpoint"""
    response = client.post('/webhook', 
                          data='{"events": []}',
                          headers={'X-Line-Signature': 'signature'})
    
    assert response.status_code == 200
```

## Test Fixtures

### Available Fixtures
- `mock_settings` - Mock application settings
- `conversation_service` - Fresh ConversationService instance
- `openai_service` - OpenAIService with mocked dependencies
- `line_service` - LineService with mocked dependencies
- `sample_line_message_event` - Sample LINE webhook event
- `sample_conversation_history` - Sample conversation data

### Using Fixtures
```python
def test_conversation_flow(self, conversation_service, sample_conversation_history):
    # conversation_service is automatically injected
    # sample_conversation_history provides test data
    pass
```

## Continuous Integration

### GitHub Actions (Recommended)
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install uv
      - run: uv sync --group test
      - run: ./scripts/run_tests.sh coverage
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure you're in the project root
   export PYTHONPATH=$PWD:$PYTHONPATH
   ```

2. **Coverage Too Low**
   ```bash
   # View detailed coverage report
   ./scripts/run_tests.sh coverage
   # Add tests for uncovered code
   ```

3. **Slow Tests**
   ```bash
   # Skip slow tests during development
   ./scripts/run_tests.sh quick
   ```

4. **HTTP Request Errors**
   - Tests should not make real HTTP requests
   - Use mocking instead of actual API calls
   - The `no_requests` fixture prevents accidental requests

### Debug Mode
```bash
# Run with verbose output and no capture
pytest tests/ -v -s --tb=long

# Run specific test with debugging
pytest tests/unit/test_openai_service.py::TestOpenAIService::test_specific_method -v -s
```

## Test Data Management

### Environment Variables
Tests run with clean environment - no real API keys needed.

### Mock Data
- Sample responses are provided in fixtures
- Add new sample data to `conftest.py`
- Keep test data minimal but realistic

### Temporary Files
- Tests automatically clean up temporary files
- Use `tmpdir` fixture for file operations
- Never write to project directories during tests

## Performance Testing

### Load Testing (Optional)
```bash
# Install additional tools
pip install locust

# Run load tests (if implemented)
locust -f tests/performance/locustfile.py
```

### Memory Usage
```bash
# Monitor memory usage during tests
pip install memory-profiler
python -m memory_profiler tests/unit/test_conversation_service.py
```

## Best Practices

1. **Test Independence**: Each test should be isolated and able to run independently
2. **Mock External Services**: Never make real API calls in tests
3. **Clear Test Names**: Use descriptive test method names
4. **Test Edge Cases**: Include error conditions and boundary values
5. **Fast Execution**: Keep tests fast, mark slow tests appropriately
6. **Maintainable**: Tests should be easy to understand and maintain

## Dependencies

### Required
- `pytest>=7.4.0` - Test framework
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.11.0` - Mocking utilities

### Optional
- `pytest-xdist` - Parallel test execution
- `pytest-benchmark` - Performance benchmarking
- `pytest-html` - HTML test reports
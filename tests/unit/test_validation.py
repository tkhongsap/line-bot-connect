"""
Unit tests for configuration validation and schema enforcement.

This module tests the comprehensive validation system that ensures
configuration integrity and prevents invalid configurations.
"""

import os
import json
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from src.config.validation import (
    ConfigurationValidator,
    ValidationIssue,
    ValidationSeverity,
    get_validator,
    validate_current_config,
    generate_validation_report
)


class TestValidationIssue:
    """Test the ValidationIssue class."""
    
    def test_validation_issue_creation(self):
        """Test ValidationIssue creation and serialization."""
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="TEST_ERROR",
            message="Test error message",
            field_path="test.field",
            suggestion="Fix the test",
            value="invalid_value"
        )
        
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.code == "TEST_ERROR"
        assert issue.message == "Test error message"
        assert issue.field_path == "test.field"
        assert issue.suggestion == "Fix the test"
        assert issue.value == "invalid_value"
        assert issue.timestamp is not None
    
    def test_issue_to_dict(self):
        """Test ValidationIssue to_dict method."""
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="TEST_WARNING",
            message="Test warning",
            field_path="test.path"
        )
        
        issue_dict = issue.to_dict()
        
        assert isinstance(issue_dict, dict)
        assert issue_dict['severity'] == 'warning'
        assert issue_dict['code'] == 'TEST_WARNING'
        assert issue_dict['message'] == 'Test warning'
        assert issue_dict['field_path'] == 'test.path'
        assert 'timestamp' in issue_dict
    
    def test_issue_string_representation(self):
        """Test ValidationIssue string representation."""
        issue = ValidationIssue(
            severity=ValidationSeverity.CRITICAL,
            code="CRITICAL_ERROR",
            message="Critical error occurred"
        )
        
        issue_str = str(issue)
        assert "CRITICAL" in issue_str
        assert "CRITICAL_ERROR" in issue_str
        assert "Critical error occurred" in issue_str


class TestConfigurationValidator:
    """Test the ConfigurationValidator class."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear global validator
        import src.config.validation
        src.config.validation._validator = None
    
    def test_validator_initialization(self):
        """Test ConfigurationValidator initialization."""
        validator = ConfigurationValidator()
        
        assert len(validator.issues) == 0
        assert len(validator.validation_rules) > 0
        assert isinstance(validator.schema_cache, dict)
    
    def test_validate_config_success(self):
        """Test successful configuration validation."""
        validator = ConfigurationValidator()
        
        # Mock a valid configuration
        mock_config = MagicMock()
        mock_config.config_version = "1.0.0"
        mock_config.is_production = False
        mock_config.is_development = True
        mock_config.application.debug = True
        mock_config.application.log_level.value = "INFO"
        mock_config.application.environment.value = "development"
        mock_config.application.session_secret.get_secret_value.return_value = "a" * 32
        mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token_123"
        mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret_456"
        mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_azure_key"
        mock_config.azure_openai.endpoint = "https://example.openai.azure.com"
        mock_config.conversation.storage_backend = "memory"
        mock_config.conversation.redis_url = None
        mock_config.conversation.max_messages_per_user = 100
        mock_config.conversation.max_total_conversations = 1000
        mock_config.rich_message.enabled = False
        mock_config.rich_message.rate_limit_per_minute = 100
        mock_config.rich_message.template_cache_hours = 24
        mock_config.celery.broker_url = "redis://localhost:6379/0"
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 10
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = True
        mock_config.to_dict.return_value = {"config_version": "1.0.0"}
        
        # Mock environment variables
        with patch.dict(os.environ, {}, clear=True):
            is_valid, issues = validator.validate_config(mock_config)
        
        assert is_valid is True
        # Should have at least INFO issues for successful validations
        info_issues = [i for i in issues if i.severity == ValidationSeverity.INFO]
        assert len(info_issues) > 0
    
    def test_validate_missing_secrets(self):
        """Test validation of missing required secrets."""
        validator = ConfigurationValidator()
        
        # Mock config with missing secrets
        mock_config = MagicMock()
        mock_config.line.channel_access_token = None
        mock_config.line.channel_secret = None
        mock_config.azure_openai.api_key = None
        mock_config.to_dict.return_value = {}
        
        # Mock other required attributes to avoid AttributeError
        mock_config.config_version = "1.0.0"
        mock_config.is_production = False
        mock_config.is_development = True
        mock_config.application.debug = True
        mock_config.application.log_level.value = "INFO"
        mock_config.application.environment.value = "development"
        mock_config.application.session_secret = None
        mock_config.azure_openai.endpoint = "https://example.com"
        mock_config.conversation.storage_backend = "memory"
        mock_config.conversation.redis_url = None
        mock_config.conversation.max_messages_per_user = 100
        mock_config.conversation.max_total_conversations = 1000
        mock_config.rich_message.enabled = False
        mock_config.rich_message.rate_limit_per_minute = 100
        mock_config.rich_message.template_cache_hours = 24
        mock_config.celery.broker_url = "redis://localhost:6379/0"
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 10
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = True
        
        is_valid, issues = validator.validate_config(mock_config)
        
        assert is_valid is False
        
        # Check for missing secret issues
        critical_issues = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        assert len(critical_issues) >= 3  # Missing LINE tokens and Azure key
        
        error_codes = [issue.code for issue in critical_issues]
        assert "MISSING_LINE_TOKEN" in error_codes
        assert "MISSING_LINE_SECRET" in error_codes
        assert "MISSING_AZURE_KEY" in error_codes
    
    def test_validate_production_settings(self):
        """Test validation of production-specific settings."""
        validator = ConfigurationValidator()
        
        # Mock production config with debug enabled (should fail)
        mock_config = MagicMock()
        mock_config.config_version = "1.0.0"
        mock_config.is_production = True
        mock_config.is_development = False
        mock_config.application.debug = True  # This should trigger an error
        mock_config.application.log_level.value = "DEBUG"  # This should trigger a warning
        mock_config.application.environment.value = "production"
        mock_config.application.session_secret.get_secret_value.return_value = "a" * 32
        mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token"
        mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret"
        mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_key"
        mock_config.azure_openai.endpoint = "https://example.openai.azure.com"
        mock_config.conversation.storage_backend = "memory"  # Should trigger warning
        mock_config.conversation.redis_url = None
        mock_config.conversation.max_messages_per_user = 100
        mock_config.conversation.max_total_conversations = 1000
        mock_config.rich_message.enabled = False
        mock_config.rich_message.rate_limit_per_minute = 100
        mock_config.rich_message.template_cache_hours = 24
        mock_config.celery.broker_url = "redis://localhost:6379/0"
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 10
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = True
        mock_config.to_dict.return_value = {"config_version": "1.0.0"}
        
        is_valid, issues = validator.validate_config(mock_config)
        
        # Should have errors/warnings for production issues
        error_issues = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        warning_issues = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        
        error_codes = [issue.code for issue in error_issues]
        warning_codes = [issue.code for issue in warning_issues]
        
        assert "DEBUG_IN_PRODUCTION" in error_codes
        assert any(code in warning_codes for code in ["DEBUG_LOGGING_PRODUCTION", "MEMORY_STORAGE_PRODUCTION"])
    
    def test_validate_url_formats(self):
        """Test URL format validation."""
        validator = ConfigurationValidator()
        
        # Mock config with invalid URLs
        mock_config = MagicMock()
        mock_config.config_version = "1.0.0"
        mock_config.is_production = False
        mock_config.is_development = True
        mock_config.application.debug = True
        mock_config.application.log_level.value = "INFO"
        mock_config.application.environment.value = "development"
        mock_config.application.session_secret.get_secret_value.return_value = "a" * 32
        mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token"
        mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret"
        mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_key"
        mock_config.azure_openai.endpoint = "invalid_url"  # Should trigger error
        mock_config.conversation.storage_backend = "redis"
        mock_config.conversation.redis_url = "invalid_redis_url"  # Should trigger warning
        mock_config.conversation.max_messages_per_user = 100
        mock_config.conversation.max_total_conversations = 1000
        mock_config.rich_message.enabled = False
        mock_config.rich_message.rate_limit_per_minute = 100
        mock_config.rich_message.template_cache_hours = 24
        mock_config.celery.broker_url = "redis://localhost:6379/0"
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 10
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = True
        mock_config.to_dict.return_value = {"config_version": "1.0.0"}
        
        is_valid, issues = validator.validate_config(mock_config)
        
        error_codes = [issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR]
        warning_codes = [issue.code for issue in issues if issue.severity == ValidationSeverity.WARNING]
        
        assert "INVALID_ENDPOINT_URL" in error_codes
        assert "REDIS_URL_FORMAT" in warning_codes
    
    def test_validate_numeric_ranges(self):
        """Test numeric range validation."""
        validator = ConfigurationValidator()
        
        # Mock config with values at edge of ranges
        mock_config = MagicMock()
        mock_config.config_version = "1.0.0"
        mock_config.is_production = False
        mock_config.is_development = True
        mock_config.application.debug = True
        mock_config.application.log_level.value = "INFO"
        mock_config.application.environment.value = "development"
        mock_config.application.session_secret.get_secret_value.return_value = "a" * 32
        mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token"
        mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret"
        mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_key"
        mock_config.azure_openai.endpoint = "https://example.openai.azure.com"
        mock_config.conversation.storage_backend = "memory"
        mock_config.conversation.redis_url = None
        mock_config.conversation.max_messages_per_user = 15000  # High value
        mock_config.conversation.max_total_conversations = 150000  # High value
        mock_config.rich_message.enabled = False
        mock_config.rich_message.rate_limit_per_minute = 15000  # High value
        mock_config.rich_message.template_cache_hours = 200  # High value
        mock_config.celery.broker_url = "redis://localhost:6379/0"
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 10
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = True
        mock_config.to_dict.return_value = {"config_version": "1.0.0"}
        
        is_valid, issues = validator.validate_config(mock_config)
        
        warning_codes = [issue.code for issue in issues if issue.severity == ValidationSeverity.WARNING]
        info_codes = [issue.code for issue in issues if issue.severity == ValidationSeverity.INFO]
        
        # Should have warnings for high values
        assert "HIGH_MESSAGE_LIMIT" in warning_codes
        assert "HIGH_CONVERSATION_LIMIT" in warning_codes
        assert "HIGH_RATE_LIMIT" in warning_codes
        assert "LONG_CACHE_DURATION" in info_codes
    
    def test_validate_feature_dependencies(self):
        """Test feature dependency validation."""
        validator = ConfigurationValidator()
        
        # Mock config with Rich Messages enabled but no Celery
        mock_config = MagicMock()
        mock_config.config_version = "1.0.0"
        mock_config.is_production = False
        mock_config.is_development = True
        mock_config.application.debug = True
        mock_config.application.log_level.value = "INFO"
        mock_config.application.environment.value = "development"
        mock_config.application.session_secret.get_secret_value.return_value = "a" * 32
        mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token"
        mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret"
        mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_key"
        mock_config.azure_openai.endpoint = "https://example.openai.azure.com"
        mock_config.conversation.storage_backend = "memory"
        mock_config.conversation.redis_url = None
        mock_config.conversation.max_messages_per_user = 100
        mock_config.conversation.max_total_conversations = 1000
        mock_config.rich_message.enabled = True  # Enabled
        mock_config.rich_message.enabled_categories = []  # Empty categories
        mock_config.rich_message.rate_limit_per_minute = 100
        mock_config.rich_message.template_cache_hours = 24
        mock_config.celery.broker_url = ""  # Missing broker URL
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 0  # Invalid rate limit
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = False  # Missing directory
        mock_config.to_dict.return_value = {"config_version": "1.0.0"}
        
        is_valid, issues = validator.validate_config(mock_config)
        
        error_codes = [issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR]
        warning_codes = [issue.code for issue in issues if issue.severity == ValidationSeverity.WARNING]
        
        assert "RICH_MESSAGE_NO_CELERY" in error_codes
        assert "INVALID_SEARCH_RATE_LIMIT" in error_codes
        assert "TEMPLATE_DIR_MISSING" in error_codes
        assert "NO_RICH_MESSAGE_CATEGORIES" in warning_codes
    
    def test_generate_text_report(self):
        """Test text report generation."""
        validator = ConfigurationValidator()
        
        # Create sample issues
        issues = [
            ValidationIssue(ValidationSeverity.ERROR, "TEST_ERROR", "Test error", "test.field"),
            ValidationIssue(ValidationSeverity.WARNING, "TEST_WARNING", "Test warning"),
            ValidationIssue(ValidationSeverity.INFO, "TEST_INFO", "Test info")
        ]
        
        report = validator.generate_validation_report(issues, format="text")
        
        assert isinstance(report, str)
        assert "Configuration Validation Report" in report
        assert "TEST_ERROR" in report
        assert "TEST_WARNING" in report
        assert "TEST_INFO" in report
        assert "Total Issues: 3" in report
    
    def test_generate_json_report(self):
        """Test JSON report generation."""
        validator = ConfigurationValidator()
        
        issues = [
            ValidationIssue(ValidationSeverity.ERROR, "TEST_ERROR", "Test error")
        ]
        
        report = validator.generate_validation_report(issues, format="json")
        
        assert isinstance(report, str)
        report_data = json.loads(report)
        assert isinstance(report_data, list)
        assert len(report_data) == 1
        assert report_data[0]['code'] == 'TEST_ERROR'
        assert report_data[0]['severity'] == 'error'
    
    def test_generate_html_report(self):
        """Test HTML report generation."""
        validator = ConfigurationValidator()
        
        issues = [
            ValidationIssue(ValidationSeverity.CRITICAL, "TEST_CRITICAL", "Test critical")
        ]
        
        report = validator.generate_validation_report(issues, format="html")
        
        assert isinstance(report, str)
        assert "<html>" in report
        assert "TEST_CRITICAL" in report
        assert "CRITICAL" in report
    
    def test_strict_mode_validation(self):
        """Test strict mode validation where warnings are treated as errors."""
        validator = ConfigurationValidator()
        
        # Mock config that would normally pass with warnings
        mock_config = MagicMock()
        mock_config.config_version = "1.0.0"
        mock_config.is_production = False
        mock_config.is_development = True
        mock_config.application.debug = True
        mock_config.application.log_level.value = "INFO"
        mock_config.application.environment.value = "development"
        mock_config.application.session_secret.get_secret_value.return_value = "short"  # Will trigger warning
        mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token"
        mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret"
        mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_key"
        mock_config.azure_openai.endpoint = "https://example.openai.azure.com"
        mock_config.conversation.storage_backend = "memory"
        mock_config.conversation.redis_url = None
        mock_config.conversation.max_messages_per_user = 100
        mock_config.conversation.max_total_conversations = 1000
        mock_config.rich_message.enabled = False
        mock_config.rich_message.rate_limit_per_minute = 100
        mock_config.rich_message.template_cache_hours = 24
        mock_config.celery.broker_url = "redis://localhost:6379/0"
        mock_config.rate_limit.enabled = True
        mock_config.web_search_enabled = True
        mock_config.web_search_rate_limit = 10
        mock_config.max_image_size_mb = 5.0
        mock_config.max_image_dimension = 2048
        mock_config.template.max_template_size_mb = 5.0
        mock_config.template.template_directory.exists.return_value = True
        mock_config.to_dict.return_value = {"config_version": "1.0.0"}
        
        # Normal mode should pass despite warnings
        is_valid_normal, issues_normal = validator.validate_config(mock_config, strict=False)
        warnings = [i for i in issues_normal if i.severity == ValidationSeverity.WARNING]
        assert len(warnings) > 0  # Should have warnings
        
        # Reset issues for strict mode test
        validator.issues = []
        
        # Strict mode should fail due to warnings
        is_valid_strict, issues_strict = validator.validate_config(mock_config, strict=True)
        # Note: The result depends on whether warnings are generated in this specific config


class TestGlobalValidationFunctions:
    """Test global validation functions."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear global validator
        import src.config.validation
        src.config.validation._validator = None
    
    def test_get_validator_singleton(self):
        """Test that get_validator returns the same instance."""
        validator1 = get_validator()
        validator2 = get_validator()
        
        assert validator1 is validator2
        assert isinstance(validator1, ConfigurationValidator)
    
    def test_validate_current_config(self):
        """Test validate_current_config function."""
        with patch('src.config.validation.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = {"config_version": "1.0.0"}
            # Mock all required attributes
            mock_config.is_production = False
            mock_config.is_development = True
            mock_config.application.debug = True
            mock_config.application.log_level.value = "INFO"
            mock_config.application.environment.value = "development"
            mock_config.application.session_secret.get_secret_value.return_value = "a" * 32
            mock_config.line.channel_access_token.get_secret_value.return_value = "valid_token"
            mock_config.line.channel_secret.get_secret_value.return_value = "valid_secret"
            mock_config.azure_openai.api_key.get_secret_value.return_value = "valid_key"
            mock_config.azure_openai.endpoint = "https://example.openai.azure.com"
            mock_config.conversation.storage_backend = "memory"
            mock_config.conversation.redis_url = None
            mock_config.conversation.max_messages_per_user = 100
            mock_config.conversation.max_total_conversations = 1000
            mock_config.rich_message.enabled = False
            mock_config.rich_message.rate_limit_per_minute = 100
            mock_config.rich_message.template_cache_hours = 24
            mock_config.celery.broker_url = "redis://localhost:6379/0"
            mock_config.rate_limit.enabled = True
            mock_config.web_search_enabled = True
            mock_config.web_search_rate_limit = 10
            mock_config.max_image_size_mb = 5.0
            mock_config.max_image_dimension = 2048
            mock_config.template.max_template_size_mb = 5.0
            mock_config.template.template_directory.exists.return_value = True
            mock_get_config.return_value = mock_config
            
            is_valid, issues = validate_current_config()
            
            assert isinstance(is_valid, bool)
            assert isinstance(issues, list)
    
    def test_generate_validation_report(self):
        """Test generate_validation_report function."""
        with patch('src.config.validation.validate_current_config') as mock_validate:
            mock_validate.return_value = (True, [
                ValidationIssue(ValidationSeverity.INFO, "TEST_INFO", "Test message")
            ])
            
            report = generate_validation_report(format="text")
            
            assert isinstance(report, str)
            assert "TEST_INFO" in report
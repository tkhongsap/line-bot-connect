"""
Configuration Validation and Schema Enforcement

This module provides comprehensive validation and schema enforcement
for the centralized configuration system, ensuring configuration
integrity and preventing invalid configurations from being applied.
"""

import os
import json
import jsonschema
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
from enum import Enum
from datetime import datetime

from pydantic import ValidationError as PydanticValidationError
from src.config.centralized_config import CentralizedConfig, get_config

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Validation issue severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationIssue:
    """Represents a configuration validation issue"""
    
    def __init__(
        self,
        severity: ValidationSeverity,
        code: str,
        message: str,
        field_path: str = "",
        suggestion: str = "",
        value: Any = None
    ):
        self.severity = severity
        self.code = code
        self.message = message
        self.field_path = field_path
        self.suggestion = suggestion
        self.value = value
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'severity': self.severity.value,
            'code': self.code,
            'message': self.message,
            'field_path': self.field_path,
            'suggestion': self.suggestion,
            'value': str(self.value) if self.value is not None else None,
            'timestamp': self.timestamp.isoformat()
        }
    
    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.code}: {self.message}"


class ConfigurationValidator:
    """
    Comprehensive configuration validator with schema enforcement.
    
    This class provides validation capabilities for configuration data,
    including schema validation, business rule validation, and security checks.
    """
    
    def __init__(self):
        """Initialize the configuration validator"""
        self.issues: List[ValidationIssue] = []
        self.schema_cache: Dict[str, Dict[str, Any]] = {}
        self.validation_rules: List[callable] = []
        
        # Load built-in validation rules
        self._load_builtin_rules()
    
    def _load_builtin_rules(self) -> None:
        """Load built-in validation rules"""
        self.validation_rules = [
            self._validate_required_secrets,
            self._validate_url_formats,
            self._validate_numeric_ranges,
            self._validate_environment_consistency,
            self._validate_security_settings,
            self._validate_dependency_compatibility,
            self._validate_resource_limits,
            self._validate_feature_dependencies
        ]
    
    def validate_config(
        self,
        config: Optional[CentralizedConfig] = None,
        strict: bool = False
    ) -> Tuple[bool, List[ValidationIssue]]:
        """
        Validate a configuration instance.
        
        Args:
            config: Configuration to validate (uses current if None)
            strict: If True, warnings are treated as errors
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        if config is None:
            config = get_config()
        
        self.issues = []
        
        try:
            # 1. Pydantic schema validation (already done during instantiation)
            self._add_issue(
                ValidationSeverity.INFO,
                "PYDANTIC_VALID",
                "Configuration passed Pydantic schema validation"
            )
            
            # 2. Run custom validation rules
            for rule in self.validation_rules:
                try:
                    rule(config)
                except Exception as e:
                    self._add_issue(
                        ValidationSeverity.ERROR,
                        "RULE_EXCEPTION",
                        f"Validation rule failed: {e}",
                        suggestion="Check validation rule implementation"
                    )
            
            # 3. JSON Schema validation (if schema exists)
            self._validate_json_schema(config)
            
            # 4. Check for deprecated configurations
            self._validate_deprecated_settings(config)
            
            # 5. Environment-specific validation
            self._validate_environment_specific(config)
            
        except Exception as e:
            self._add_issue(
                ValidationSeverity.CRITICAL,
                "VALIDATION_EXCEPTION",
                f"Critical validation error: {e}"
            )
        
        # Determine if configuration is valid
        error_severities = [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        if strict:
            error_severities.append(ValidationSeverity.WARNING)
        
        has_errors = any(issue.severity in error_severities for issue in self.issues)
        is_valid = not has_errors
        
        return is_valid, self.issues.copy()
    
    def _add_issue(
        self,
        severity: ValidationSeverity,
        code: str,
        message: str,
        field_path: str = "",
        suggestion: str = "",
        value: Any = None
    ) -> None:
        """Add a validation issue"""
        issue = ValidationIssue(severity, code, message, field_path, suggestion, value)
        self.issues.append(issue)
        
        # Log the issue
        log_level = {
            ValidationSeverity.INFO: logging.INFO,
            ValidationSeverity.WARNING: logging.WARNING,
            ValidationSeverity.ERROR: logging.ERROR,
            ValidationSeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.INFO)
        
        logger.log(log_level, str(issue))
    
    def _validate_required_secrets(self, config: CentralizedConfig) -> None:
        """Validate that required secrets are present and properly formatted"""
        
        # Check LINE Bot secrets
        if not config.line.channel_access_token:
            self._add_issue(
                ValidationSeverity.CRITICAL,
                "MISSING_LINE_TOKEN",
                "LINE channel access token is required",
                field_path="line.channel_access_token",
                suggestion="Set LINE_CHANNEL_ACCESS_TOKEN environment variable"
            )
        
        if not config.line.channel_secret:
            self._add_issue(
                ValidationSeverity.CRITICAL,
                "MISSING_LINE_SECRET",
                "LINE channel secret is required",
                field_path="line.channel_secret",
                suggestion="Set LINE_CHANNEL_SECRET environment variable"
            )
        
        # Check Azure OpenAI secrets
        if not config.azure_openai.api_key:
            self._add_issue(
                ValidationSeverity.CRITICAL,
                "MISSING_AZURE_KEY",
                "Azure OpenAI API key is required",
                field_path="azure_openai.api_key",
                suggestion="Set AZURE_OPENAI_API_KEY environment variable"
            )
        
        # Validate secret formats (basic checks)
        if config.line.channel_access_token:
            token = config.line.channel_access_token.get_secret_value()
            if len(token) < 10:
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "SHORT_LINE_TOKEN",
                    "LINE access token appears too short",
                    field_path="line.channel_access_token",
                    suggestion="Verify token is complete and correct"
                )
    
    def _validate_url_formats(self, config: CentralizedConfig) -> None:
        """Validate URL formats"""
        
        # Azure OpenAI endpoint
        endpoint = config.azure_openai.endpoint
        if not endpoint.startswith(('http://', 'https://')):
            self._add_issue(
                ValidationSeverity.ERROR,
                "INVALID_ENDPOINT_URL",
                f"Azure OpenAI endpoint must be a valid HTTP(S) URL: {endpoint}",
                field_path="azure_openai.endpoint",
                suggestion="Ensure endpoint starts with https://"
            )
        
        # Redis URLs
        if config.conversation.storage_backend == "redis":
            redis_url = config.conversation.redis_url
            if redis_url and not redis_url.startswith('redis://'):
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "REDIS_URL_FORMAT",
                    f"Redis URL should start with redis://: {redis_url}",
                    field_path="conversation.redis_url",
                    suggestion="Use format: redis://host:port/db"
                )
    
    def _validate_numeric_ranges(self, config: CentralizedConfig) -> None:
        """Validate numeric values are within reasonable ranges"""
        
        # Conversation limits
        if config.conversation.max_messages_per_user > 10000:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_MESSAGE_LIMIT",
                f"Very high messages per user limit: {config.conversation.max_messages_per_user}",
                field_path="conversation.max_messages_per_user",
                suggestion="Consider memory usage implications"
            )
        
        if config.conversation.max_total_conversations > 100000:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_CONVERSATION_LIMIT",
                f"Very high total conversations limit: {config.conversation.max_total_conversations}",
                field_path="conversation.max_total_conversations",
                suggestion="Consider memory and storage implications"
            )
        
        # Rate limits
        if config.rich_message.rate_limit_per_minute > 10000:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_RATE_LIMIT",
                f"Very high rate limit: {config.rich_message.rate_limit_per_minute}/min",
                field_path="rich_message.rate_limit_per_minute",
                suggestion="Ensure your infrastructure can handle this rate"
            )
        
        # Template cache duration
        if config.rich_message.template_cache_hours > 168:  # 1 week
            self._add_issue(
                ValidationSeverity.INFO,
                "LONG_CACHE_DURATION",
                f"Long template cache duration: {config.rich_message.template_cache_hours} hours",
                field_path="rich_message.template_cache_hours",
                suggestion="Consider if updates will be delayed too long"
            )
    
    def _validate_environment_consistency(self, config: CentralizedConfig) -> None:
        """Validate configuration consistency for the current environment"""
        
        # Production environment checks
        if config.is_production:
            if config.application.debug:
                self._add_issue(
                    ValidationSeverity.ERROR,
                    "DEBUG_IN_PRODUCTION",
                    "Debug mode should not be enabled in production",
                    field_path="application.debug",
                    suggestion="Set DEBUG=false for production"
                )
            
            if config.application.log_level.value == "DEBUG":
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "DEBUG_LOGGING_PRODUCTION",
                    "Debug logging in production may impact performance",
                    field_path="application.log_level",
                    suggestion="Use INFO or WARNING level for production"
                )
        
        # Development environment checks
        if config.is_development:
            if not config.application.debug:
                self._add_issue(
                    ValidationSeverity.INFO,
                    "NO_DEBUG_DEVELOPMENT",
                    "Debug mode is disabled in development",
                    field_path="application.debug",
                    suggestion="Consider enabling debug for development"
                )
    
    def _validate_security_settings(self, config: CentralizedConfig) -> None:
        """Validate security-related settings"""
        
        # Session secret
        if config.application.session_secret:
            secret = config.application.session_secret.get_secret_value()
            if len(secret) < 32:
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "WEAK_SESSION_SECRET",
                    "Session secret is shorter than recommended 32 characters",
                    field_path="application.session_secret",
                    suggestion="Use a longer, randomly generated secret"
                )
        
        # Rate limiting
        if not config.rate_limit.enabled:
            self._add_issue(
                ValidationSeverity.WARNING,
                "RATE_LIMITING_DISABLED",
                "Rate limiting is disabled",
                field_path="rate_limit.enabled",
                suggestion="Enable rate limiting for production use"
            )
    
    def _validate_dependency_compatibility(self, config: CentralizedConfig) -> None:
        """Validate dependency compatibility"""
        
        # Rich Messages require Celery
        if config.rich_message.enabled:
            if not config.celery.broker_url:
                self._add_issue(
                    ValidationSeverity.ERROR,
                    "RICH_MESSAGE_NO_CELERY",
                    "Rich Messages enabled but Celery broker not configured",
                    field_path="celery.broker_url",
                    suggestion="Configure CELERY_BROKER_URL for Rich Message automation"
                )
        
        # Redis storage requires Redis URL
        if config.conversation.storage_backend == "redis":
            if not config.conversation.redis_url:
                self._add_issue(
                    ValidationSeverity.ERROR,
                    "REDIS_STORAGE_NO_URL",
                    "Redis storage backend selected but no Redis URL configured",
                    field_path="conversation.redis_url",
                    suggestion="Set Redis URL or use memory storage"
                )
    
    def _validate_resource_limits(self, config: CentralizedConfig) -> None:
        """Validate resource usage limits"""
        
        # Image processing limits
        if config.max_image_size_mb > 20:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_IMAGE_SIZE_LIMIT",
                f"High image size limit: {config.max_image_size_mb}MB",
                field_path="max_image_size_mb",
                suggestion="Consider memory usage and processing time"
            )
        
        if config.max_image_dimension > 4096:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_IMAGE_DIMENSION",
                f"High image dimension limit: {config.max_image_dimension}px",
                field_path="max_image_dimension",
                suggestion="Consider processing time and memory usage"
            )
        
        # Template size limit
        if config.template.max_template_size_mb > 10:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_TEMPLATE_SIZE",
                f"High template size limit: {config.template.max_template_size_mb}MB",
                field_path="template.max_template_size_mb",
                suggestion="Large templates may impact performance"
            )
    
    def _validate_feature_dependencies(self, config: CentralizedConfig) -> None:
        """Validate feature dependencies and interactions"""
        
        # Web search and multimodal features
        if config.web_search_enabled and config.web_search_rate_limit <= 0:
            self._add_issue(
                ValidationSeverity.ERROR,
                "INVALID_SEARCH_RATE_LIMIT",
                "Web search enabled but rate limit is invalid",
                field_path="web_search_rate_limit",
                suggestion="Set a positive rate limit value"
            )
        
        # Rich Message categories
        if config.rich_message.enabled and not config.rich_message.enabled_categories:
            self._add_issue(
                ValidationSeverity.WARNING,
                "NO_RICH_MESSAGE_CATEGORIES",
                "Rich Messages enabled but no categories configured",
                field_path="rich_message.enabled_categories",
                suggestion="Enable at least one content category"
            )
        
        # Template configuration
        if config.rich_message.enabled:
            if not config.template.template_directory.exists():
                self._add_issue(
                    ValidationSeverity.ERROR,
                    "TEMPLATE_DIR_MISSING",
                    f"Template directory not found: {config.template.template_directory}",
                    field_path="template.template_directory",
                    suggestion="Create template directory or update path"
                )
    
    def _validate_json_schema(self, config: CentralizedConfig) -> None:
        """Validate against JSON schema if available"""
        schema_file = Path(__file__).parent / "config_schema.json"
        
        if not schema_file.exists():
            return
        
        try:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
            
            config_dict = config.to_dict(include_secrets=False)
            jsonschema.validate(config_dict, schema)
            
            self._add_issue(
                ValidationSeverity.INFO,
                "JSON_SCHEMA_VALID",
                "Configuration passed JSON schema validation"
            )
            
        except jsonschema.ValidationError as e:
            self._add_issue(
                ValidationSeverity.ERROR,
                "JSON_SCHEMA_INVALID",
                f"JSON schema validation failed: {e.message}",
                field_path=".".join(str(p) for p in e.absolute_path),
                suggestion="Fix configuration to match schema"
            )
        except Exception as e:
            self._add_issue(
                ValidationSeverity.WARNING,
                "JSON_SCHEMA_ERROR",
                f"Could not validate JSON schema: {e}",
                suggestion="Check schema file format"
            )
    
    def _validate_deprecated_settings(self, config: CentralizedConfig) -> None:
        """Check for deprecated configuration settings"""
        
        # Example: Check for old environment variable formats
        deprecated_envs = [
            "OLD_LINE_TOKEN",
            "LEGACY_OPENAI_KEY",
            "DEPRECATED_SETTING"
        ]
        
        for env_var in deprecated_envs:
            if os.environ.get(env_var):
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "DEPRECATED_ENV_VAR",
                    f"Deprecated environment variable in use: {env_var}",
                    suggestion="Migrate to new configuration format"
                )
    
    def _validate_environment_specific(self, config: CentralizedConfig) -> None:
        """Validate environment-specific requirements"""
        
        env = config.application.environment
        
        if env.value == "production":
            # Production-specific validations
            if config.conversation.storage_backend == "memory":
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "MEMORY_STORAGE_PRODUCTION",
                    "Using memory storage in production",
                    field_path="conversation.storage_backend",
                    suggestion="Consider Redis storage for production"
                )
        
        elif env.value == "testing":
            # Testing-specific validations
            if config.rich_message.enabled:
                self._add_issue(
                    ValidationSeverity.INFO,
                    "RICH_MESSAGE_IN_TESTING",
                    "Rich Messages enabled in testing environment",
                    suggestion="May want to disable for cleaner tests"
                )
    
    def generate_validation_report(
        self,
        issues: List[ValidationIssue],
        format: str = "text"
    ) -> str:
        """
        Generate a validation report.
        
        Args:
            issues: List of validation issues
            format: Report format ("text", "json", "html")
            
        Returns:
            Formatted validation report
        """
        if format == "json":
            return json.dumps([issue.to_dict() for issue in issues], indent=2)
        
        elif format == "html":
            return self._generate_html_report(issues)
        
        else:  # text format
            return self._generate_text_report(issues)
    
    def _generate_text_report(self, issues: List[ValidationIssue]) -> str:
        """Generate text validation report"""
        if not issues:
            return "✅ Configuration validation passed with no issues.\n"
        
        # Group issues by severity
        by_severity = {}
        for issue in issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)
        
        lines = ["📋 Configuration Validation Report", "=" * 40, ""]
        
        # Summary
        total_issues = len(issues)
        critical = len(by_severity.get(ValidationSeverity.CRITICAL, []))
        errors = len(by_severity.get(ValidationSeverity.ERROR, []))
        warnings = len(by_severity.get(ValidationSeverity.WARNING, []))
        info = len(by_severity.get(ValidationSeverity.INFO, []))
        
        lines.append(f"Total Issues: {total_issues}")
        lines.append(f"🔴 Critical: {critical}")
        lines.append(f"❌ Errors: {errors}")
        lines.append(f"⚠️  Warnings: {warnings}")
        lines.append(f"ℹ️  Info: {info}")
        lines.extend(["", ""])
        
        # Detailed issues
        severity_order = [
            ValidationSeverity.CRITICAL,
            ValidationSeverity.ERROR,
            ValidationSeverity.WARNING,
            ValidationSeverity.INFO
        ]
        
        for severity in severity_order:
            if severity not in by_severity:
                continue
            
            severity_issues = by_severity[severity]
            severity_emoji = {
                ValidationSeverity.CRITICAL: "🔴",
                ValidationSeverity.ERROR: "❌",
                ValidationSeverity.WARNING: "⚠️",
                ValidationSeverity.INFO: "ℹ️"
            }[severity]
            
            lines.append(f"{severity_emoji} {severity.value.upper()} ({len(severity_issues)})")
            lines.append("-" * 30)
            
            for issue in severity_issues:
                lines.append(f"• {issue.code}: {issue.message}")
                if issue.field_path:
                    lines.append(f"  Path: {issue.field_path}")
                if issue.suggestion:
                    lines.append(f"  💡 {issue.suggestion}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _generate_html_report(self, issues: List[ValidationIssue]) -> str:
        """Generate HTML validation report"""
        # Simple HTML report - could be enhanced with CSS styling
        html = """
        <html>
        <head><title>Configuration Validation Report</title></head>
        <body>
        <h1>Configuration Validation Report</h1>
        """
        
        if not issues:
            html += "<p style='color: green;'>✅ Configuration validation passed with no issues.</p>"
        else:
            for issue in issues:
                color = {
                    ValidationSeverity.CRITICAL: "red",
                    ValidationSeverity.ERROR: "red",
                    ValidationSeverity.WARNING: "orange",
                    ValidationSeverity.INFO: "blue"
                }.get(issue.severity, "black")
                
                html += f"""
                <div style="border-left: 4px solid {color}; padding: 10px; margin: 10px 0;">
                    <strong>[{issue.severity.value.upper()}] {issue.code}</strong><br>
                    {issue.message}<br>
                    {f"<em>Path: {issue.field_path}</em><br>" if issue.field_path else ""}
                    {f"<small>💡 {issue.suggestion}</small>" if issue.suggestion else ""}
                </div>
                """
        
        html += "</body></html>"
        return html


# Global validator instance
_validator: Optional[ConfigurationValidator] = None


def get_validator() -> ConfigurationValidator:
    """Get the global configuration validator"""
    global _validator
    if _validator is None:
        _validator = ConfigurationValidator()
    return _validator


def validate_current_config(strict: bool = False) -> Tuple[bool, List[ValidationIssue]]:
    """Validate the current configuration"""
    validator = get_validator()
    return validator.validate_config(strict=strict)


def generate_validation_report(format: str = "text") -> str:
    """Generate a validation report for the current configuration"""
    is_valid, issues = validate_current_config()
    validator = get_validator()
    return validator.generate_validation_report(issues, format=format)
"""
Integration testing utilities for Clockman.

This module provides comprehensive testing tools for validating
webhook, plugin, and integration functionality.
"""

import json
import logging
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from contextlib import contextmanager
from unittest.mock import Mock, patch

from .events.events import ClockmanEvent, EventType
from .webhooks.models import WebhookConfig, WebhookDelivery, DeliveryStatus
from .plugins.base import BasePlugin, PluginInfo

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a test execution."""
    name: str
    success: bool
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[Exception] = None


@dataclass
class TestSuite:
    """A collection of related tests."""
    name: str
    tests: List[Callable] = field(default_factory=list)
    setup: Optional[Callable] = None
    teardown: Optional[Callable] = None


class MockWebhookServer:
    """Mock webhook server for testing webhook deliveries."""
    
    def __init__(self, port: int = 8000):
        """Initialize the mock server."""
        self.port = port
        self.requests: List[Dict[str, Any]] = []
        self.response_status = 200
        self.response_body = '{"status": "ok"}'
        self.response_delay = 0.0
        self.fail_count = 0  # Number of requests to fail before succeeding
        self._current_fails = 0
        
    def add_request(self, method: str, path: str, headers: Dict[str, str], body: str) -> None:
        """Record a request to the mock server."""
        self.requests.append({
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "path": path,
            "headers": headers,
            "body": body
        })
    
    def clear_requests(self) -> None:
        """Clear recorded requests."""
        self.requests.clear()
        self._current_fails = 0
    
    def set_failure_mode(self, fail_count: int, status_code: int = 500) -> None:
        """Set the server to fail a certain number of requests."""
        self.fail_count = fail_count
        self._current_fails = 0
        self.response_status = status_code
    
    def set_delay(self, delay_seconds: float) -> None:
        """Set response delay."""
        self.response_delay = delay_seconds
    
    @contextmanager
    def running(self):
        """Context manager to run the mock server."""
        # In a real implementation, this would start an actual HTTP server
        # For testing, we'll use mock patches
        original_requests = []
        
        def mock_post(*args, **kwargs):
            """Mock HTTP POST request."""
            time.sleep(self.response_delay)
            
            # Record request
            self.add_request(
                method="POST",
                path=kwargs.get('url', ''),
                headers=kwargs.get('headers', {}),
                body=json.dumps(kwargs.get('json', {}))
            )
            
            # Check if should fail
            if self._current_fails < self.fail_count:
                self._current_fails += 1
                mock_response = Mock()
                mock_response.status_code = self.response_status
                mock_response.text = f"Error {self.response_status}"
                mock_response.headers = {}
                mock_response.raise_for_status.side_effect = Exception(f"HTTP {self.response_status}")
                return mock_response
            
            # Success response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = self.response_body
            mock_response.headers = {"Content-Type": "application/json"}
            return mock_response
        
        with patch('httpx.Client.post', side_effect=mock_post):
            yield self


class TestPlugin(BasePlugin):
    """A test plugin for integration testing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize test plugin."""
        super().__init__(config)
        self.events_received: List[ClockmanEvent] = []
        self.initialization_called = False
        self.shutdown_called = False
        self.should_fail_on_event = False
        self.custom_info: Optional[PluginInfo] = None
    
    @property
    def info(self) -> PluginInfo:
        """Get plugin info."""
        if self.custom_info:
            return self.custom_info
        
        return PluginInfo(
            name="Test Plugin",
            version="1.0.0",
            description="A plugin for testing integration functionality",
            author="Clockman Team",
            supported_events=[EventType.SESSION_STARTED, EventType.SESSION_STOPPED],
        )
    
    def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialization_called = True
    
    def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.shutdown_called = True
    
    def handle_event(self, event: ClockmanEvent) -> None:
        """Handle an event."""
        if self.should_fail_on_event:
            raise Exception("Test plugin intentionally failed")
        
        self.events_received.append(event)
    
    def clear_events(self) -> None:
        """Clear received events."""
        self.events_received.clear()


class IntegrationTester:
    """Comprehensive integration testing framework."""
    
    def __init__(self, integration_manager):
        """Initialize the tester."""
        self.integration_manager = integration_manager
        self.test_results: List[TestResult] = []
        self.test_suites: List[TestSuite] = []
        self.mock_server = MockWebhookServer()
        self.test_plugins: Dict[str, TestPlugin] = {}
        
    def add_test_suite(self, suite: TestSuite) -> None:
        """Add a test suite."""
        self.test_suites.append(suite)
    
    def create_test_webhook(self, name: str = "test-webhook") -> WebhookConfig:
        """Create a test webhook configuration."""
        return WebhookConfig(
            id=uuid4(),
            name=name,
            url=f"http://localhost:{self.mock_server.port}/webhook",
            event_types=[EventType.SESSION_STARTED, EventType.SESSION_STOPPED],
            description="Test webhook for integration testing"
        )
    
    def create_test_plugin(self, name: str = "test-plugin") -> TestPlugin:
        """Create and register a test plugin."""
        plugin = TestPlugin()
        plugin.custom_info = PluginInfo(
            name=name,
            version="1.0.0",
            description=f"Test plugin: {name}",
            author="Test Framework",
            supported_events=[EventType.SESSION_STARTED, EventType.SESSION_STOPPED],
        )
        
        self.test_plugins[name] = plugin
        return plugin
    
    def create_test_event(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> ClockmanEvent:
        """Create a test event."""
        from .events.event_manager import EventManager
        
        event_manager = EventManager()
        return event_manager.create_event(
            event_type=event_type,
            data=data or {"test": True, "timestamp": datetime.utcnow().isoformat()},
            metadata={"source": "integration_tester"}
        )
    
    def run_test(self, test_func: Callable, name: str) -> TestResult:
        """Run a single test."""
        start_time = datetime.utcnow()
        
        try:
            result = test_func()
            success = result if isinstance(result, bool) else True
            message = "Test passed" if success else "Test failed"
            
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return TestResult(
                name=name,
                success=success,
                duration_ms=duration_ms,
                message=message
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return TestResult(
                name=name,
                success=False,
                duration_ms=duration_ms,
                message=f"Test failed with exception: {e}",
                exception=e
            )
    
    def run_test_suite(self, suite: TestSuite) -> List[TestResult]:
        """Run all tests in a suite."""
        results = []
        
        # Run setup
        if suite.setup:
            try:
                suite.setup()
            except Exception as e:
                logger.error(f"Test suite '{suite.name}' setup failed: {e}")
                return [TestResult(
                    name=f"{suite.name}_setup",
                    success=False,
                    duration_ms=0,
                    message=f"Setup failed: {e}",
                    exception=e
                )]
        
        # Run tests
        for i, test in enumerate(suite.tests):
            test_name = f"{suite.name}_{i}"
            if hasattr(test, '__name__'):
                test_name = f"{suite.name}_{test.__name__}"
            
            result = self.run_test(test, test_name)
            results.append(result)
        
        # Run teardown
        if suite.teardown:
            try:
                suite.teardown()
            except Exception as e:
                logger.error(f"Test suite '{suite.name}' teardown failed: {e}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all registered test suites."""
        all_results = []
        suite_results = {}
        
        for suite in self.test_suites:
            results = self.run_test_suite(suite)
            all_results.extend(results)
            suite_results[suite.name] = results
        
        self.test_results = all_results
        
        # Calculate summary statistics
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results if r.success)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration_ms for r in all_results)
        
        return {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
            "total_duration_ms": total_duration,
            "suite_results": suite_results,
            "results": all_results
        }
    
    # Built-in test suites
    
    def webhook_delivery_tests(self) -> TestSuite:
        """Test suite for webhook delivery functionality."""
        def setup():
            # Create test webhook
            self.test_webhook = self.create_test_webhook()
            self.integration_manager.add_webhook(self.test_webhook)
            self.mock_server.clear_requests()
        
        def teardown():
            # Clean up webhook
            self.integration_manager.remove_webhook(self.test_webhook.id)
        
        def test_successful_delivery():
            """Test successful webhook delivery."""
            with self.mock_server.running():
                # Create and emit test event
                event = self.create_test_event(EventType.SESSION_STARTED)
                self.integration_manager.emit_event(event.event_type, event.data)
                
                # Wait a moment for async processing
                time.sleep(0.1)
                
                # Verify request was received
                return len(self.mock_server.requests) > 0
        
        def test_retry_on_failure():
            """Test webhook retry on failure."""
            with self.mock_server.running():
                # Configure server to fail once then succeed
                self.mock_server.set_failure_mode(1, 500)
                
                # Create and emit test event
                event = self.create_test_event(EventType.SESSION_STARTED)
                self.integration_manager.emit_event(event.event_type, event.data)
                
                # Wait for retry
                time.sleep(0.5)
                
                # Process retries
                self.integration_manager.process_webhook_retries()
                
                # Should have 2 requests (original + retry)
                return len(self.mock_server.requests) >= 1
        
        def test_event_filtering():
            """Test webhook event filtering."""
            with self.mock_server.running():
                # Create event that shouldn't match webhook filter
                event = self.create_test_event(EventType.PROJECT_CREATED)
                self.integration_manager.emit_event(event.event_type, event.data)
                
                time.sleep(0.1)
                
                # Should have no requests (event type not in webhook filter)
                return len(self.mock_server.requests) == 0
        
        return TestSuite(
            name="webhook_delivery",
            setup=setup,
            teardown=teardown,
            tests=[test_successful_delivery, test_retry_on_failure, test_event_filtering]
        )
    
    def plugin_lifecycle_tests(self) -> TestSuite:
        """Test suite for plugin lifecycle management."""
        def setup():
            self.test_plugin = self.create_test_plugin("lifecycle-test-plugin")
        
        def test_plugin_initialization():
            """Test plugin initialization."""
            self.test_plugin.initialize()
            return self.test_plugin.initialization_called
        
        def test_plugin_event_handling():
            """Test plugin event handling."""
            event = self.create_test_event(EventType.SESSION_STARTED)
            self.test_plugin.handle_event(event)
            
            return len(self.test_plugin.events_received) == 1
        
        def test_plugin_shutdown():
            """Test plugin shutdown."""
            self.test_plugin.shutdown()
            return self.test_plugin.shutdown_called
        
        def test_plugin_error_handling():
            """Test plugin error handling."""
            self.test_plugin.should_fail_on_event = True
            
            try:
                event = self.create_test_event(EventType.SESSION_STARTED)
                self.test_plugin.handle_event(event)
                return False  # Should have raised exception
            except Exception:
                return True  # Expected behavior
        
        return TestSuite(
            name="plugin_lifecycle",
            setup=setup,
            tests=[
                test_plugin_initialization,
                test_plugin_event_handling,
                test_plugin_shutdown,
                test_plugin_error_handling
            ]
        )
    
    def integration_system_tests(self) -> TestSuite:
        """Test suite for overall integration system."""
        def test_system_enable_disable():
            """Test enabling/disabling integration system."""
            original_state = self.integration_manager.is_enabled()
            
            # Disable
            self.integration_manager.disable()
            disabled_state = self.integration_manager.is_enabled()
            
            # Re-enable
            self.integration_manager.enable()
            enabled_state = self.integration_manager.is_enabled()
            
            # Restore original state
            if original_state:
                self.integration_manager.enable()
            else:
                self.integration_manager.disable()
            
            return not disabled_state and enabled_state
        
        def test_statistics_collection():
            """Test statistics collection."""
            stats = self.integration_manager.get_statistics()
            
            required_keys = [
                "enabled", "initialized", "event_manager", 
                "webhook_manager", "plugin_manager", "hook_manager"
            ]
            
            return all(key in stats for key in required_keys)
        
        def test_event_emission():
            """Test event emission through integration system."""
            # Create a simple event
            event = self.integration_manager.emit_event(
                EventType.SYSTEM_STARTED,
                {"test": True}
            )
            
            return event is not None and event.event_type == EventType.SYSTEM_STARTED
        
        return TestSuite(
            name="integration_system",
            tests=[
                test_system_enable_disable,
                test_statistics_collection,
                test_event_emission
            ]
        )
    
    def generate_test_report(self, results: Dict[str, Any], output_file: Optional[Path] = None) -> str:
        """Generate a comprehensive test report."""
        report_lines = [
            "# Clockman Integration Test Report",
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
            "## Summary",
            f"- Total Tests: {results['total_tests']}",
            f"- Passed: {results['passed']}",
            f"- Failed: {results['failed']}",
            f"- Success Rate: {results['success_rate']:.1%}",
            f"- Total Duration: {results['total_duration_ms']:.1f}ms",
            "",
        ]
        
        # Suite details
        for suite_name, suite_results in results["suite_results"].items():
            suite_passed = sum(1 for r in suite_results if r.success)
            suite_total = len(suite_results)
            
            report_lines.extend([
                f"## Test Suite: {suite_name}",
                f"Passed: {suite_passed}/{suite_total}",
                "",
            ])
            
            for result in suite_results:
                status = "✓ PASS" if result.success else "✗ FAIL"
                report_lines.append(f"- {status} {result.name} ({result.duration_ms:.1f}ms)")
                
                if not result.success:
                    report_lines.append(f"  Error: {result.message}")
                
                if result.details:
                    for key, value in result.details.items():
                        report_lines.append(f"  {key}: {value}")
            
            report_lines.append("")
        
        # Failed test details
        failed_tests = [r for r in results["results"] if not r.success]
        if failed_tests:
            report_lines.extend([
                "## Failed Test Details",
                ""
            ])
            
            for result in failed_tests:
                report_lines.extend([
                    f"### {result.name}",
                    f"- Duration: {result.duration_ms:.1f}ms",
                    f"- Error: {result.message}",
                ])
                
                if result.exception:
                    report_lines.append(f"- Exception: {type(result.exception).__name__}: {result.exception}")
                
                report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        if output_file:
            output_file.write_text(report_text)
            logger.info(f"Test report written to {output_file}")
        
        return report_text


def run_integration_tests(integration_manager) -> Dict[str, Any]:
    """
    Run a comprehensive integration test suite.
    
    Args:
        integration_manager: The integration manager to test
        
    Returns:
        Dictionary with test results
    """
    tester = IntegrationTester(integration_manager)
    
    # Add built-in test suites
    tester.add_test_suite(tester.webhook_delivery_tests())
    tester.add_test_suite(tester.plugin_lifecycle_tests())
    tester.add_test_suite(tester.integration_system_tests())
    
    # Run all tests
    results = tester.run_all_tests()
    
    logger.info(f"Integration tests completed: {results['passed']}/{results['total_tests']} passed")
    
    return results
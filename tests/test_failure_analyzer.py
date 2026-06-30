"""Tests for lib/failure_analyzer.py."""
from failure_analyzer import (
    BADGE_DEFINITIONS,
    FailureAnalyzer,
    FailureCategory,
    FailureReport,
)


def test_failure_category_enum_values():
    assert FailureCategory.PII_LEAK.value == "pii_leak"
    assert FailureCategory.CAPTURE_SUCCESS.value == "capture_success"


def test_all_categories_have_badges():
    for cat in FailureCategory:
        assert cat in BADGE_DEFINITIONS, f"Missing badge for {cat}"
        emoji, css, label = BADGE_DEFINITIONS[cat]
        assert emoji and css and label


def test_failure_report_dataclass_defaults():
    r = FailureReport(
        category=FailureCategory.CAPTURE_SUCCESS,
        screenshot_id="test-id",
        doc_path="articles/foo.md",
        repo_name="MicrosoftDocs/test",
        attempted_action="capture",
        expected_outcome="ok",
        actual_outcome="ok",
        reason="success",
        recommendation="none",
    )
    assert r.severity == "info"
    assert r.details == {}


def test_analyzer_get_report_badge():
    analyzer = FailureAnalyzer()
    report = FailureReport(
        category=FailureCategory.PII_LEAK,
        screenshot_id="x",
        doc_path="x.md",
        repo_name="x",
        attempted_action="x",
        expected_outcome="x",
        actual_outcome="x",
        reason="x",
        recommendation="x",
    )
    emoji, css, label = analyzer.get_report_badge(report)
    assert emoji == "🚨"
    assert css == "pii"
    assert "PII" in label


def test_analyzer_reports_list_starts_empty():
    analyzer = FailureAnalyzer()
    assert analyzer.reports == []


def test_analyze_capture_detects_pii_leak():
    """Real GUID in captured DOM should produce a PII_LEAK report."""
    analyzer = FailureAnalyzer()
    report = analyzer.analyze_capture(
        screenshot_id="test-1",
        doc_path="articles/test.md",
        repo_name="MicrosoftDocs/test",
        captured_page_title="Storage account",
        expected_page_title="Storage account",
        dom_text_content="Subscription ID: 72f988bf-86f1-41af-91ab-2d7cd011db47",
        doc_context="Create a storage account",
        original_image_exists=True,
        captured_image_path="/tmp/x.png",
        callout_targets_found=["Create"],
        callout_targets_expected=["Create"],
    )
    assert report.category == FailureCategory.PII_LEAK


def test_analyze_capture_navigation_failure_on_title_mismatch():
    analyzer = FailureAnalyzer()
    report = analyzer.analyze_capture(
        screenshot_id="test-2",
        doc_path="articles/test.md",
        repo_name="MicrosoftDocs/test",
        captured_page_title="Sign in to Azure",
        expected_page_title="Storage accounts",
        dom_text_content="Sign in with your work account",
        doc_context="Open the Storage accounts blade",
        original_image_exists=True,
        captured_image_path="/tmp/x.png",
        callout_targets_found=[],
        callout_targets_expected=["Create"],
    )
    # Either privilege or navigation failure - both are valid for this scenario
    assert report.category in (
        FailureCategory.NAVIGATION_FAILURE,
        FailureCategory.PRIVILEGE_FAILURE,
    )


def test_analyze_capture_success_path():
    analyzer = FailureAnalyzer()
    report = analyzer.analyze_capture(
        screenshot_id="test-3",
        doc_path="articles/test.md",
        repo_name="MicrosoftDocs/test",
        captured_page_title="Storage accounts",
        expected_page_title="Storage accounts",
        dom_text_content="Create storage account. Use contoso.onmicrosoft.com.",
        doc_context="Open Storage accounts and click Create",
        original_image_exists=True,
        captured_image_path="/tmp/x.png",
        callout_targets_found=["Create"],
        callout_targets_expected=["Create"],
    )
    assert report.category == FailureCategory.CAPTURE_SUCCESS

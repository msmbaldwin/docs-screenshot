"""
Failure detection and reporting for the docs-screenshot skill.

Analyzes capture attempts and classifies failures into actionable categories.
Each failure gets a structured report with severity, recommendation, and
metadata suitable for embedding in the HTML comparison report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Failure categories
# ---------------------------------------------------------------------------

class FailureCategory(Enum):
    """Categories of capture failure, ordered roughly by severity."""

    PRIVILEGE_FAILURE = "privilege_failure"
    NAVIGATION_FAILURE = "navigation_failure"
    DATA_SETUP_FAILURE = "data_setup_failure"
    UI_MISMATCH = "ui_mismatch"
    PII_LEAK = "pii_leak"
    DOC_INSUFFICIENT = "doc_insufficient"
    ELEMENT_NOT_FOUND = "element_not_found"
    SERVICE_RESTRUCTURED = "service_restructured"
    CAPTURE_SUCCESS = "capture_success"


# ---------------------------------------------------------------------------
# Badge definitions (emoji, css_class, label) for the HTML comparison report
# ---------------------------------------------------------------------------

BADGE_DEFINITIONS: dict[FailureCategory, tuple[str, str, str]] = {
    FailureCategory.CAPTURE_SUCCESS:       ("✅", "ok",     "Captured"),
    FailureCategory.PRIVILEGE_FAILURE:     ("🔒", "priv",   "Privilege Issue"),
    FailureCategory.NAVIGATION_FAILURE:    ("❌", "fail",   "Navigation Failed"),
    FailureCategory.DATA_SETUP_FAILURE:    ("❌", "fail",   "Data Setup Failed"),
    FailureCategory.UI_MISMATCH:           ("⚠️", "warn",   "UI Mismatch"),
    FailureCategory.PII_LEAK:              ("🚨", "pii",    "PII Leak"),
    FailureCategory.DOC_INSUFFICIENT:      ("📄", "doc",    "Doc Insufficient"),
    FailureCategory.ELEMENT_NOT_FOUND:     ("🔍", "review", "Element Missing"),
    FailureCategory.SERVICE_RESTRUCTURED:  ("⚠️", "warn",   "Service Restructured"),
}

# Severity ordering so analyze_capture can pick the worst failure.
# Lower number = more severe.
_SEVERITY_ORDER: dict[FailureCategory, int] = {
    FailureCategory.PII_LEAK:              0,
    FailureCategory.PRIVILEGE_FAILURE:     1,
    FailureCategory.NAVIGATION_FAILURE:    2,
    FailureCategory.SERVICE_RESTRUCTURED:  3,
    FailureCategory.DATA_SETUP_FAILURE:    4,
    FailureCategory.ELEMENT_NOT_FOUND:     5,
    FailureCategory.UI_MISMATCH:           6,
    FailureCategory.DOC_INSUFFICIENT:      7,
    FailureCategory.CAPTURE_SUCCESS:       99,
}


# ---------------------------------------------------------------------------
# PII regex patterns (lightweight, post-capture validation only)
# ---------------------------------------------------------------------------

# Standard GUID: 8-4-4-4-12 hex digits
_GUID_RE = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)

# Email addresses (broad match)
_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
)

# IPv4 addresses
_IPV4_RE = re.compile(
    r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
)

# Null GUID is always safe
_NULL_GUID = "00000000-0000-0000-0000-000000000000"

# Fictitious company domains that are safe by convention
_SAFE_DOMAINS = frozenset({
    "contoso.com", "fabrikam.com", "adventure-works.com",
    "wingtiptoys.com", "adatum.com", "northwindtraders.com",
    "example.com", "example.org", "example.net",
})

# Private / documentation / loopback IP ranges that are safe
_SAFE_IP_PREFIXES = (
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.",
    "192.168.", "127.", "169.254.",
    "192.0.2.", "198.51.100.", "203.0.113.",  # documentation ranges
)


# ---------------------------------------------------------------------------
# Privilege / access-denied indicators
# ---------------------------------------------------------------------------

_PRIVILEGE_PHRASES = [
    "access denied",
    "you don't have permission",
    "you do not have permission",
    "forbidden",
    "unauthorized",
    "403",
    "you need permission",
    "insufficient privileges",
    "not authorized",
    "request access",
    "contact your administrator",
    "you don't have access",
    "you do not have access",
]


# ---------------------------------------------------------------------------
# Service restructuring indicators
# ---------------------------------------------------------------------------

_RESTRUCTURED_PHRASES = [
    "this service has been retired",
    "has been renamed to",
    "has been moved to",
    "is no longer available",
    "this feature has been deprecated",
    "has been replaced by",
    "preview has ended",
    "this page has moved",
    "this resource has been deprecated",
]


# ---------------------------------------------------------------------------
# FailureReport dataclass
# ---------------------------------------------------------------------------

@dataclass
class FailureReport:
    """Structured report for a single capture attempt.

    Attributes:
        category: The failure classification.
        screenshot_id: Identifier for the screenshot (typically the filename stem).
        doc_path: Full repo-root-relative path to the source markdown file.
        repo_name: Repository that owns the doc (e.g. "MicrosoftDocs/azure-docs").
        attempted_action: Human-readable description of what the skill tried to do.
        expected_outcome: What should have happened, derived from doc text and alt-text.
        actual_outcome: What actually happened during the capture attempt.
        reason: Why the skill believes the capture failed (or succeeded).
        recommendation: Suggested next step for a human reviewer.
        severity: One of "critical", "warning", or "info".
        details: Arbitrary metadata dict for additional context.
    """

    category: FailureCategory
    screenshot_id: str
    doc_path: str
    repo_name: str
    attempted_action: str
    expected_outcome: str
    actual_outcome: str
    reason: str
    recommendation: str
    severity: str = "info"
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FailureAnalyzer
# ---------------------------------------------------------------------------

class FailureAnalyzer:
    """Runs post-capture checks and produces FailureReport instances.

    Usage:
        analyzer = FailureAnalyzer()
        report = analyzer.analyze_capture(
            screenshot_id="create-resource-group",
            doc_path="articles/azure/create-rg.md",
            ...
        )
        emoji, css, label = analyzer.get_report_badge(report)
        explanation = analyzer.generate_failure_explanation(report)
    """

    def __init__(self) -> None:
        """Initialize with an empty list of collected reports."""
        self.reports: list[FailureReport] = []

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def analyze_capture(
        self,
        screenshot_id: str,
        doc_path: str,
        repo_name: str,
        captured_page_title: str,
        expected_page_title: str,
        dom_text_content: str,
        doc_context: str,
        original_image_exists: bool,
        captured_image_path: str,
        callout_targets_found: list[str],
        callout_targets_expected: list[str],
    ) -> FailureReport:
        """Run all failure checks and return the most severe failure found.

        Checks are evaluated in severity order. If multiple failures are
        detected, the single most severe one is returned. A successful
        capture returns a report with category CAPTURE_SUCCESS.

        Args:
            screenshot_id: Identifier for the screenshot.
            doc_path: Repo-root-relative path to the markdown file.
            repo_name: Repository name (e.g. "MicrosoftDocs/azure-docs").
            captured_page_title: The <title> of the page we actually captured.
            expected_page_title: The page title we expected based on the doc.
            dom_text_content: Full visible text extracted from the captured DOM.
            doc_context: Relevant surrounding text from the markdown source.
            original_image_exists: Whether the original reference image exists.
            captured_image_path: Path to the captured screenshot on disk.
            callout_targets_found: CSS selectors / labels actually located.
            callout_targets_expected: CSS selectors / labels we needed to find.

        Returns:
            A FailureReport for the most severe issue, or CAPTURE_SUCCESS.
        """
        candidates: list[FailureReport] = []

        # 1. Privilege check
        if self.check_privilege_failure(dom_text_content):
            candidates.append(FailureReport(
                category=FailureCategory.PRIVILEGE_FAILURE,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action="Navigate to target page and capture screenshot",
                expected_outcome=f"Page titled '{expected_page_title}' loads normally",
                actual_outcome="Page shows an access-denied or permission error",
                reason="The captured DOM contains privilege/access-denied language",
                recommendation=(
                    "Verify the automation account has the required RBAC roles "
                    "or license entitlements for this portal area."
                ),
                severity="critical",
                details={"captured_title": captured_page_title},
            ))

        # 2. PII leak check
        pii_hits = self.check_pii_leak(dom_text_content)
        if pii_hits:
            candidates.append(FailureReport(
                category=FailureCategory.PII_LEAK,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action="Capture and scrub screenshot of PII",
                expected_outcome="All PII redacted or replaced with fictitious values",
                actual_outcome=f"Found {len(pii_hits)} potential PII pattern(s) in DOM text",
                reason="Post-capture validation detected patterns that look like real PII",
                recommendation=(
                    "Review flagged values manually. If they are fictitious, "
                    "add them to the approved lists in pii_detector.py."
                ),
                severity="critical",
                details={"pii_matches": pii_hits},
            ))

        # 3. Navigation check
        if self.check_navigation_failure(
            expected_page_title, captured_page_title, "", ""
        ):
            candidates.append(FailureReport(
                category=FailureCategory.NAVIGATION_FAILURE,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action=f"Navigate to page titled '{expected_page_title}'",
                expected_outcome=f"Page title contains '{expected_page_title}'",
                actual_outcome=f"Landed on page titled '{captured_page_title}'",
                reason="The captured page title does not match the expected title",
                recommendation=(
                    "Check whether the URL or portal path has changed. "
                    "The doc may need updated navigation instructions."
                ),
                severity="critical",
                details={
                    "expected_title": expected_page_title,
                    "captured_title": captured_page_title,
                },
            ))

        # 4. Service restructured check
        if self._check_service_restructured(dom_text_content):
            candidates.append(FailureReport(
                category=FailureCategory.SERVICE_RESTRUCTURED,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action="Navigate to the documented service page",
                expected_outcome="Service page loads with current UI",
                actual_outcome="Page indicates the service has been retired or renamed",
                reason=(
                    "The DOM text contains language suggesting the service "
                    "has been restructured, retired, or renamed"
                ),
                recommendation=(
                    "This doc likely needs a major rewrite. Escalate to the "
                    "content team for the affected service."
                ),
                severity="warning",
                details={"dom_snippet": dom_text_content[:500]},
            ))

        # 5. Element missing check
        missing = self.check_element_missing(
            callout_targets_expected, callout_targets_found,
        )
        if missing:
            candidates.append(FailureReport(
                category=FailureCategory.ELEMENT_NOT_FOUND,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action="Locate callout target elements in the DOM",
                expected_outcome=f"Found all {len(callout_targets_expected)} callout targets",
                actual_outcome=f"Missing {len(missing)} target(s): {', '.join(missing)}",
                reason="One or more expected UI elements were not found in the DOM",
                recommendation=(
                    "The UI may have changed element names, classes, or structure. "
                    "Update the callout selectors or verify the page state."
                ),
                severity="warning",
                details={
                    "missing_elements": missing,
                    "found_elements": callout_targets_found,
                },
            ))

        # 6. Doc insufficient check
        if not doc_context or len(doc_context.strip()) < 30:
            candidates.append(FailureReport(
                category=FailureCategory.DOC_INSUFFICIENT,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action="Extract navigation instructions from doc context",
                expected_outcome="Doc provides enough detail to locate and reproduce the screenshot",
                actual_outcome="Doc context is empty or too brief to act on",
                reason=(
                    "The surrounding markdown text does not contain enough "
                    "detail to determine how to reproduce this screenshot"
                ),
                recommendation=(
                    "A human should review the doc and add step-by-step "
                    "instructions, or manually capture this screenshot."
                ),
                severity="info",
                details={"doc_context_length": len(doc_context.strip()) if doc_context else 0},
            ))

        # If no failures were found, it is a success
        if not candidates:
            report = FailureReport(
                category=FailureCategory.CAPTURE_SUCCESS,
                screenshot_id=screenshot_id,
                doc_path=doc_path,
                repo_name=repo_name,
                attempted_action="Capture screenshot per doc instructions",
                expected_outcome=f"Screenshot of '{expected_page_title}' captured successfully",
                actual_outcome="Screenshot captured and validated",
                reason="All post-capture checks passed",
                recommendation="No action required",
                severity="info",
                details={
                    "captured_image_path": captured_image_path,
                    "callout_targets_found": len(callout_targets_found),
                },
            )
            self.reports.append(report)
            return report

        # Return the most severe candidate
        candidates.sort(key=lambda r: _SEVERITY_ORDER.get(r.category, 50))
        worst = candidates[0]
        self.reports.append(worst)
        return worst

    # ------------------------------------------------------------------
    # Individual check methods
    # ------------------------------------------------------------------

    def check_privilege_failure(self, dom_text: str) -> bool:
        """Check whether the DOM text contains access-denied indicators.

        Args:
            dom_text: Visible text content extracted from the page DOM.

        Returns:
            True if any privilege/access-denied phrase is found.
        """
        lower = dom_text.lower()
        return any(phrase in lower for phrase in _PRIVILEGE_PHRASES)

    def check_pii_leak(self, dom_text: str) -> list[str]:
        """Scan DOM text for potential PII that was not scrubbed.

        This is a lightweight post-capture check. It flags patterns that
        look like real (non-fictitious) data. The primary scrubbing is
        handled by pii_detector.py before capture; this method catches
        anything that slipped through.

        Args:
            dom_text: Visible text content extracted from the page DOM.

        Returns:
            List of strings describing each potential PII match found.
            Empty list means no PII detected.
        """
        hits: list[str] = []

        # Check for non-approved GUIDs
        for match in _GUID_RE.finditer(dom_text):
            guid = match.group(0).lower()
            if guid == _NULL_GUID:
                continue
            # Flag GUIDs that look like real (non-placeholder) values.
            # Placeholder GUIDs from Microsoft docs typically use
            # repeating patterns like aaaa0a0a-bb1b-... so we flag
            # anything that does not follow that convention.
            if not self._is_placeholder_guid(guid):
                hits.append(f"GUID: {guid}")

        # Check for emails on non-safe domains
        for match in _EMAIL_RE.finditer(dom_text):
            email = match.group(0).lower()
            domain = email.split("@", 1)[1] if "@" in email else ""
            if domain and domain not in _SAFE_DOMAINS:
                hits.append(f"Email: {email}")

        # Check for non-private IP addresses
        for match in _IPV4_RE.finditer(dom_text):
            ip = match.group(1)
            if not self._is_safe_ip(ip):
                hits.append(f"IPv4: {ip}")

        return hits

    def check_navigation_failure(
        self,
        expected_title: str,
        actual_title: str,
        expected_url_fragment: str,
        actual_url: str,
    ) -> bool:
        """Check whether the browser ended up on the wrong page.

        Performs case-insensitive substring matching on the page title.
        If a URL fragment is provided, also checks the actual URL.

        Args:
            expected_title: Page title expected from the doc context.
            actual_title: Page title captured from the browser.
            expected_url_fragment: A substring expected in the URL (can be empty).
            actual_url: The actual URL the browser navigated to (can be empty).

        Returns:
            True if the page appears to be wrong.
        """
        if not expected_title or not actual_title:
            return False

        title_match = expected_title.lower().strip() in actual_title.lower().strip()
        if title_match:
            return False

        # Also accept the reverse containment (actual title is a substring
        # of the expected title) to handle truncated titles.
        reverse_match = actual_title.lower().strip() in expected_title.lower().strip()
        if reverse_match:
            return False

        # URL fragment check (if provided)
        if expected_url_fragment and actual_url:
            if expected_url_fragment.lower() not in actual_url.lower():
                return True

        # Title mismatch is sufficient to flag navigation failure
        return True

    def check_element_missing(
        self,
        expected_elements: list[str],
        found_elements: list[str],
    ) -> list[str]:
        """Return expected elements that were not found in the DOM.

        Comparison is case-insensitive.

        Args:
            expected_elements: List of element selectors or labels expected.
            found_elements: List of element selectors or labels actually located.

        Returns:
            List of expected elements that are missing.
        """
        found_lower = {e.lower().strip() for e in found_elements}
        return [
            e for e in expected_elements
            if e.lower().strip() not in found_lower
        ]

    def check_ui_mismatch(
        self,
        original_dimensions: tuple[int, int],
        captured_dimensions: tuple[int, int],
        similarity_score: float,
    ) -> bool:
        """Detect significant visual differences between original and captured images.

        Uses a combination of dimension ratio and similarity score. A low
        similarity score alone may be acceptable if dimensions are close
        (minor UI refresh), but large dimensional shifts combined with
        low similarity strongly indicate a mismatch.

        Args:
            original_dimensions: (width, height) of the reference image.
            captured_dimensions: (width, height) of the newly captured image.
            similarity_score: 0.0 to 1.0 where 1.0 is identical.

        Returns:
            True if the images appear fundamentally different.
        """
        orig_w, orig_h = original_dimensions
        cap_w, cap_h = captured_dimensions

        if orig_w == 0 or orig_h == 0:
            return False

        width_ratio = cap_w / orig_w
        height_ratio = cap_h / orig_h

        # Flag if dimensions changed drastically (more than 50% in either axis)
        dimension_mismatch = (
            width_ratio < 0.5 or width_ratio > 2.0
            or height_ratio < 0.5 or height_ratio > 2.0
        )

        # Similarity below 0.3 is almost certainly a different page
        if similarity_score < 0.3:
            return True

        # Moderate similarity loss combined with big dimension change
        if similarity_score < 0.6 and dimension_mismatch:
            return True

        return False

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def generate_failure_explanation(self, report: FailureReport) -> str:
        """Generate a human-readable multi-line explanation for the comparison report.

        The output is suitable for embedding in the HTML comparison report
        as a <pre> or <div> block.

        Args:
            report: The FailureReport to explain.

        Returns:
            A multi-line string with the explanation.
        """
        emoji, _, label = self.get_report_badge(report)
        lines = [
            f"{emoji} {label}",
            f"Screenshot: {report.screenshot_id}",
            f"Doc: {report.doc_path} ({report.repo_name})",
            "",
            f"Attempted: {report.attempted_action}",
            f"Expected:  {report.expected_outcome}",
            f"Actual:    {report.actual_outcome}",
            "",
            f"Reason: {report.reason}",
            "",
            f"Recommendation: {report.recommendation}",
            f"Severity: {report.severity}",
        ]

        if report.details:
            lines.append("")
            lines.append("Details:")
            for key, value in report.details.items():
                if isinstance(value, list) and len(value) > 5:
                    lines.append(f"  {key}: [{len(value)} items]")
                else:
                    lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def get_report_badge(self, report: FailureReport) -> tuple[str, str, str]:
        """Return the badge tuple for a failure report.

        Args:
            report: The FailureReport to get a badge for.

        Returns:
            A tuple of (emoji, css_class, label) for the HTML badge.
        """
        return BADGE_DEFINITIONS.get(
            report.category,
            ("❓", "unknown", "Unknown"),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_service_restructured(self, dom_text: str) -> bool:
        """Check whether the DOM indicates a service has been retired or renamed.

        Args:
            dom_text: Visible text from the captured page.

        Returns:
            True if restructuring language is detected.
        """
        lower = dom_text.lower()
        return any(phrase in lower for phrase in _RESTRUCTURED_PHRASES)

    @staticmethod
    def _is_placeholder_guid(guid: str) -> bool:
        """Heuristic check for Microsoft-style placeholder GUIDs.

        Microsoft docs use a specific fictitious GUID pattern with
        repeating letter groups like "aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e".
        Real GUIDs are essentially random and unlikely to match this shape.

        We check whether the GUID uses a limited character set in each
        segment (suggesting it was hand-crafted as a placeholder).

        Args:
            guid: Lowercase GUID string.

        Returns:
            True if the GUID looks like a placeholder.
        """
        # Remove hyphens and check character diversity.
        # Real GUIDs typically use 10+ distinct hex characters across
        # 32 positions. Placeholders tend to use fewer (repetitive patterns).
        hex_chars = guid.replace("-", "")
        distinct = len(set(hex_chars))

        # Placeholders usually have low character diversity (<=8 distinct chars).
        # Real GUIDs almost always use 10+ distinct hex characters.
        return distinct <= 8

    @staticmethod
    def _is_safe_ip(ip: str) -> bool:
        """Check whether an IPv4 address is in a safe (non-routable) range.

        Args:
            ip: Dotted-quad IPv4 address string.

        Returns:
            True if the IP is private, documentation, or loopback.
        """
        if any(ip.startswith(prefix) for prefix in _SAFE_IP_PREFIXES):
            return True

        # Azure wireserver and carrier-grade NAT
        if ip == "168.63.129.16":
            return True
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                first, second = int(parts[0]), int(parts[1])
                if first == 100 and 64 <= second <= 127:
                    return True
            except ValueError:
                pass

        return False


# ---------------------------------------------------------------------------
# Module self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    analyzer = FailureAnalyzer()

    # Test privilege detection
    assert analyzer.check_privilege_failure("You don't have permission to view this resource")
    assert not analyzer.check_privilege_failure("Welcome to Azure Portal")

    # Test PII detection
    hits = analyzer.check_pii_leak("Contact admin@microsoft.com for help")
    assert any("Email" in h for h in hits), f"Expected email PII hit, got {hits}"

    safe = analyzer.check_pii_leak("Contact john@contoso.com for help")
    assert not any("Email" in h for h in safe), f"contoso.com should be safe, got {safe}"

    # Test navigation check
    assert analyzer.check_navigation_failure("Create resource", "Azure Home", "", "")
    assert not analyzer.check_navigation_failure("Create resource", "Create Resource Group", "", "")

    # Test element missing
    missing = analyzer.check_element_missing(
        ["Save button", "Cancel button", "Name field"],
        ["save button", "name field"],
    )
    assert missing == ["Cancel button"], f"Expected ['Cancel button'], got {missing}"

    # Test UI mismatch
    assert analyzer.check_ui_mismatch((800, 600), (800, 600), 0.2)
    assert not analyzer.check_ui_mismatch((800, 600), (810, 605), 0.9)

    # Test full analysis (success case)
    report = analyzer.analyze_capture(
        screenshot_id="test-screenshot",
        doc_path="articles/test.md",
        repo_name="MicrosoftDocs/test",
        captured_page_title="Create Resource Group",
        expected_page_title="Create Resource",
        dom_text_content="Welcome to the Create Resource Group page",
        doc_context="Navigate to the portal and select Create Resource Group from the menu.",
        original_image_exists=True,
        captured_image_path="/tmp/test.png",
        callout_targets_found=["save-btn", "name-input"],
        callout_targets_expected=["save-btn", "name-input"],
    )
    assert report.category == FailureCategory.CAPTURE_SUCCESS

    # Test badge retrieval
    emoji, css_class, label = analyzer.get_report_badge(report)
    assert emoji == "✅"
    assert css_class == "ok"

    # Test failure explanation
    explanation = analyzer.generate_failure_explanation(report)
    assert "Captured" in explanation
    assert "test-screenshot" in explanation

    print("All self-tests passed.")

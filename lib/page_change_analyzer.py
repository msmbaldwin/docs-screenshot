"""
page_change_analyzer.py - Detect significant page changes vs. documentation

When refreshing screenshots for existing docs, the underlying Azure or Fabric
service may have been restructured or renamed (e.g., "Form Recognizer" became
"Document Intelligence"). In these cases the captured screenshot will look
fundamentally different from the original, and the documentation itself may
need rewriting, not just a screenshot update.

This module compares what the documentation describes against what the browser
actually captured, flagging cases where a simple screenshot swap is insufficient.
"""

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Default known service renames across Azure / Microsoft AI
# ---------------------------------------------------------------------------

DEFAULT_SERVICE_RENAMES: dict[str, str] = {
    "Form Recognizer": "Document Intelligence",
    "Azure Form Recognizer": "Azure AI Document Intelligence",
    "Cognitive Services": "Azure AI Services",
    "Azure Cognitive Services": "Azure AI Services",
    "Azure AI Studio": "Azure AI Foundry",
    "AI Studio": "AI Foundry",
    "Azure Machine Learning studio": "Azure AI Foundry",
    "LUIS": "Conversational Language Understanding",
    "QnA Maker": "Custom Question Answering",
    "Text Analytics": "Azure AI Language",
    "Computer Vision": "Azure AI Vision",
    "Face API": "Azure AI Face",
    "Speech Services": "Azure AI Speech",
    "Translator": "Azure AI Translator",
    "Content Moderator": "Azure AI Content Safety",
    "Personalizer": "Azure AI Personalizer",
    "Anomaly Detector": "Azure AI Anomaly Detector",
    "Metrics Advisor": "Azure AI Metrics Advisor",
}

# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------

TITLE_SIMILARITY_THRESHOLD = 0.6   # Below this, the page is considered significantly changed
DIMENSION_CHANGE_THRESHOLD = 0.5   # Large dimension differences suggest a different layout

# Common title prefixes that portals inject and that should be stripped
# before comparison.
_TITLE_STRIP_PREFIXES = [
    "microsoft azure -",
    "azure portal -",
    "microsoft -",
    "azure -",
    "preview -",
    "home -",
]

# Phrases that strongly indicate a 404 / missing-resource page
_NOT_FOUND_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b404\b", re.IGNORECASE),
    re.compile(r"page\s+not\s+found", re.IGNORECASE),
    re.compile(r"resource\s+not\s+found", re.IGNORECASE),
    re.compile(r"not\s+found", re.IGNORECASE),
    re.compile(r"this\s+page\s+(isn.t|is\s+not)\s+available", re.IGNORECASE),
    re.compile(r"we\s+couldn.t\s+find\s+that\s+page", re.IGNORECASE),
    re.compile(r"the\s+resource\s+.+\s+was\s+not\s+found", re.IGNORECASE),
    re.compile(r"does\s+not\s+exist", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PageChangeResult:
    """Result of comparing a captured page against its documentation."""

    has_significant_change: bool           # True if the page differs enough to warrant attention
    change_type: str                       # "none", "service_renamed", "ui_restructured",
                                           # "page_not_found", "layout_changed"
    old_title: str | None = None           # Title from the documentation / original
    new_title: str | None = None           # Title from the captured page
    title_similarity: float = 1.0          # 0.0 = completely different, 1.0 = identical
    old_service_name: str | None = None    # Service name referenced in the doc
    new_service_name: str | None = None    # Replacement service name found on the page
    details: str = ""                      # Human-readable explanation of what changed
    doc_update_needed: bool = False        # True if the doc likely needs more than a screenshot swap
    recommendation: str = ""               # Suggested next step for the author


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class PageChangeAnalyzer:
    """Compares captured page state against documentation expectations.

    Detects service renames, page-not-found errors, layout changes, and
    general title drift so the caller can decide whether a simple screenshot
    refresh is sufficient or the documentation itself needs rewriting.
    """

    def __init__(self, service_renames: dict[str, str] | None = None):
        """Initialize the analyzer.

        Args:
            service_renames: Optional mapping of old service names to new names.
                Merged on top of DEFAULT_SERVICE_RENAMES.  Pass an empty dict
                to use only the built-in mappings.
        """
        self._renames: dict[str, str] = dict(DEFAULT_SERVICE_RENAMES)
        if service_renames:
            self._renames.update(service_renames)

        # Build a case-insensitive lookup for fast matching
        self._renames_lower: dict[str, str] = {
            k.lower(): v for k, v in self._renames.items()
        }
        # Reverse lookup: new name -> old name (lowercase keys)
        self._reverse_renames_lower: dict[str, str] = {
            v.lower(): k for k, v in self._renames.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        doc_title: str | None,
        captured_title: str | None,
        doc_service_name: str | None = None,
        captured_page_text: str | None = None,
        original_image_dimensions: tuple[int, int] | None = None,
        captured_image_dimensions: tuple[int, int] | None = None,
    ) -> PageChangeResult:
        """Run the full analysis pipeline and return a structured result.

        Args:
            doc_title: The page/section title recorded in the documentation.
            captured_title: The <title> or heading extracted from the live page.
            doc_service_name: Service name mentioned in the doc (optional).
            captured_page_text: Visible text from the captured page (optional).
            original_image_dimensions: (width, height) of the original screenshot.
            captured_image_dimensions: (width, height) of the newly captured screenshot.

        Returns:
            A PageChangeResult describing what changed and what to do about it.
        """
        # 1. Check for 404 / page-not-found first
        if captured_page_text and self.is_page_not_found(captured_page_text):
            return PageChangeResult(
                has_significant_change=True,
                change_type="page_not_found",
                old_title=doc_title,
                new_title=captured_title,
                title_similarity=0.0,
                details="The captured page appears to be a 404 or 'not found' error.",
                doc_update_needed=True,
                recommendation=(
                    "The target page no longer exists. Verify the URL is correct "
                    "and check whether the service has moved or been retired."
                ),
            )

        # Also check the title itself for 404 indicators
        if captured_title and self.is_page_not_found(captured_title):
            return PageChangeResult(
                has_significant_change=True,
                change_type="page_not_found",
                old_title=doc_title,
                new_title=captured_title,
                title_similarity=0.0,
                details=f"The page title indicates a missing page: '{captured_title}'.",
                doc_update_needed=True,
                recommendation=(
                    "The target page no longer exists. Verify the URL and "
                    "check whether the service has moved or been retired."
                ),
            )

        # 2. Check for service renames
        rename_result = None
        if doc_service_name and captured_page_text:
            rename_result = self.detect_service_rename(doc_service_name, captured_page_text)
        # Also try using doc_title as a source of service name context
        if not rename_result and doc_title and captured_page_text:
            rename_result = self.detect_service_rename(doc_title, captured_page_text)

        # 3. Title similarity
        title_sim = 1.0
        if doc_title and captured_title:
            title_sim = self.compare_titles(doc_title, captured_title)

        # 4. Dimension change
        dim_change = 0.0
        if original_image_dimensions and captured_image_dimensions:
            dim_change = self.check_dimension_change(
                original_image_dimensions, captured_image_dimensions
            )

        # 5. Determine overall change type and severity
        return self._build_result(
            doc_title=doc_title,
            captured_title=captured_title,
            title_sim=title_sim,
            rename_result=rename_result,
            dim_change=dim_change,
        )

    def compare_titles(self, title_a: str, title_b: str) -> float:
        """Compute fuzzy similarity between two page titles.

        Normalizes both titles (lowercase, strip portal prefixes), then
        computes a weighted combination of Jaccard token similarity and
        substring overlap.

        Args:
            title_a: First title string.
            title_b: Second title string.

        Returns:
            A float from 0.0 (completely different) to 1.0 (identical).
        """
        norm_a = self._normalize_title(title_a)
        norm_b = self._normalize_title(title_b)

        if norm_a == norm_b:
            return 1.0
        if not norm_a or not norm_b:
            return 0.0

        # Jaccard similarity on word tokens
        tokens_a = set(norm_a.split())
        tokens_b = set(norm_b.split())
        if not tokens_a and not tokens_b:
            return 1.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union) if union else 0.0

        # Substring bonus: if one title fully contains the other, boost score
        substring_bonus = 0.0
        if norm_a in norm_b or norm_b in norm_a:
            substring_bonus = 0.3

        # Check for known service rename: if the only difference is a rename,
        # the titles are effectively equivalent.
        rename_bonus = 0.0
        transformed_a = self._apply_renames(norm_a)
        transformed_b = self._apply_renames(norm_b)
        if transformed_a == transformed_b:
            rename_bonus = 0.5
        elif transformed_a and transformed_b:
            # Recompute Jaccard after applying renames
            rtokens_a = set(transformed_a.split())
            rtokens_b = set(transformed_b.split())
            runion = rtokens_a | rtokens_b
            rjaccard = len(rtokens_a & rtokens_b) / len(runion) if runion else 0.0
            if rjaccard > jaccard:
                rename_bonus = (rjaccard - jaccard) * 0.5

        score = jaccard + substring_bonus + rename_bonus
        return min(score, 1.0)

    def detect_service_rename(
        self, doc_text: str, page_text: str
    ) -> tuple[str, str] | None:
        """Check whether the doc references an old service name that the page has replaced.

        Searches for any known old service name in doc_text, then checks
        whether the corresponding new name appears in page_text.

        Args:
            doc_text: Text from the documentation (title, body, alt text, etc.).
            page_text: Visible text extracted from the captured page.

        Returns:
            A (old_name, new_name) tuple if a rename is detected, or None.
        """
        doc_lower = doc_text.lower()
        page_lower = page_text.lower()

        for old_name, new_name in self._renames.items():
            old_lower = old_name.lower()
            new_lower = new_name.lower()

            # Doc mentions the old name, and the page shows the new name
            if old_lower in doc_lower and new_lower in page_lower:
                # Confirm the old name is NOT on the page (i.e., it was truly replaced)
                if old_lower not in page_lower:
                    return (old_name, new_name)

        return None

    def check_dimension_change(
        self, original: tuple[int, int], captured: tuple[int, int]
    ) -> float:
        """Compute how different two image dimensions are.

        Uses the average relative change in width and height.

        Args:
            original: (width, height) of the original image.
            captured: (width, height) of the captured image.

        Returns:
            A float from 0.0 (identical dimensions) to 1.0 (very different).
            Values above 1.0 are clamped.
        """
        if original == captured:
            return 0.0

        orig_w, orig_h = original
        cap_w, cap_h = captured

        if orig_w == 0 or orig_h == 0:
            return 1.0

        width_ratio = abs(cap_w - orig_w) / max(orig_w, cap_w)
        height_ratio = abs(cap_h - orig_h) / max(orig_h, cap_h)

        change = (width_ratio + height_ratio) / 2.0
        return min(change, 1.0)

    def is_page_not_found(self, page_text: str) -> bool:
        """Detect whether the page text indicates a 404 or missing resource.

        Args:
            page_text: Visible text from the captured page (or page title).

        Returns:
            True if the text strongly suggests the page was not found.
        """
        for pattern in _NOT_FOUND_PATTERNS:
            if pattern.search(page_text):
                return True
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalize_title(self, title: str) -> str:
        """Lowercase, strip whitespace, and remove common portal prefixes."""
        result = title.strip().lower()
        for prefix in _TITLE_STRIP_PREFIXES:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        # Collapse multiple spaces
        result = re.sub(r"\s+", " ", result).strip()
        return result

    def _apply_renames(self, text: str) -> str:
        """Replace all known old service names with their new equivalents."""
        result = text
        for old_lower, new_name in self._renames_lower.items():
            if old_lower in result:
                result = result.replace(old_lower, new_name.lower())
        return result

    def _build_result(
        self,
        doc_title: str | None,
        captured_title: str | None,
        title_sim: float,
        rename_result: tuple[str, str] | None,
        dim_change: float,
    ) -> PageChangeResult:
        """Combine all signals into a single PageChangeResult."""
        # Service rename is the strongest signal
        if rename_result:
            old_svc, new_svc = rename_result
            return PageChangeResult(
                has_significant_change=True,
                change_type="service_renamed",
                old_title=doc_title,
                new_title=captured_title,
                title_similarity=title_sim,
                old_service_name=old_svc,
                new_service_name=new_svc,
                details=(
                    f"The service has been renamed from '{old_svc}' to '{new_svc}'. "
                    f"Title similarity: {title_sim:.2f}."
                ),
                doc_update_needed=True,
                recommendation=(
                    f"Update all references from '{old_svc}' to '{new_svc}' in the "
                    f"documentation, then recapture the screenshot."
                ),
            )

        # Low title similarity without a known rename
        if title_sim < TITLE_SIMILARITY_THRESHOLD:
            return PageChangeResult(
                has_significant_change=True,
                change_type="ui_restructured",
                old_title=doc_title,
                new_title=captured_title,
                title_similarity=title_sim,
                details=(
                    f"The page title has changed significantly "
                    f"(similarity {title_sim:.2f} < {TITLE_SIMILARITY_THRESHOLD}). "
                    f"Doc title: '{doc_title}', captured: '{captured_title}'."
                ),
                doc_update_needed=True,
                recommendation=(
                    "The page appears to have been restructured. Review the captured "
                    "page and update the documentation text before replacing the screenshot."
                ),
            )

        # Large dimension change
        if dim_change >= DIMENSION_CHANGE_THRESHOLD:
            return PageChangeResult(
                has_significant_change=True,
                change_type="layout_changed",
                old_title=doc_title,
                new_title=captured_title,
                title_similarity=title_sim,
                details=(
                    f"Image dimensions changed significantly "
                    f"(change ratio {dim_change:.2f} >= {DIMENSION_CHANGE_THRESHOLD}). "
                    f"The page layout may have been redesigned."
                ),
                doc_update_needed=False,
                recommendation=(
                    "The layout appears different. Verify the screenshot still captures "
                    "the correct region and adjust cropping if needed."
                ),
            )

        # Everything looks fine
        return PageChangeResult(
            has_significant_change=False,
            change_type="none",
            old_title=doc_title,
            new_title=captured_title,
            title_similarity=title_sim,
            details="No significant changes detected.",
            doc_update_needed=False,
            recommendation="Screenshot can be refreshed as-is.",
        )


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    analyzer = PageChangeAnalyzer()

    # Test 1: identical titles
    sim = analyzer.compare_titles("Create a virtual machine", "Create a virtual machine")
    assert sim == 1.0, f"Expected 1.0, got {sim}"
    print(f"[PASS] Identical titles: {sim}")

    # Test 2: portal prefix stripping
    sim = analyzer.compare_titles(
        "Microsoft Azure - Create a VM",
        "Azure portal - Create a VM",
    )
    assert sim >= 0.8, f"Expected >= 0.8, got {sim}"
    print(f"[PASS] Prefix-stripped titles: {sim:.2f}")

    # Test 3: completely different titles
    sim = analyzer.compare_titles("Create a virtual machine", "Billing overview")
    assert sim < 0.3, f"Expected < 0.3, got {sim}"
    print(f"[PASS] Different titles: {sim:.2f}")

    # Test 4: service rename detection
    rename = analyzer.detect_service_rename(
        "Use Form Recognizer to extract data",
        "Azure AI Document Intelligence extracts structured data from documents",
    )
    assert rename is not None, "Expected rename detection"
    assert rename[0] == "Form Recognizer"
    assert rename[1] == "Document Intelligence"
    print(f"[PASS] Service rename: {rename[0]} -> {rename[1]}")

    # Test 5: page not found
    assert analyzer.is_page_not_found("404 - Page not found")
    assert analyzer.is_page_not_found("The resource you requested was not found")
    assert not analyzer.is_page_not_found("Welcome to Azure portal")
    print("[PASS] Page-not-found detection")

    # Test 6: dimension change
    ratio = analyzer.check_dimension_change((1200, 800), (1200, 800))
    assert ratio == 0.0, f"Expected 0.0, got {ratio}"
    ratio = analyzer.check_dimension_change((1200, 800), (600, 400))
    assert ratio > 0.3, f"Expected > 0.3, got {ratio}"
    print(f"[PASS] Dimension change: {ratio:.2f}")

    # Test 7: full analysis with rename
    result = analyzer.analyze(
        doc_title="Use Form Recognizer in the Azure portal",
        captured_title="Azure AI Document Intelligence - Overview",
        doc_service_name="Form Recognizer",
        captured_page_text="Azure AI Document Intelligence lets you extract text and structure.",
    )
    assert result.has_significant_change is True
    assert result.change_type == "service_renamed"
    assert result.doc_update_needed is True
    print(f"[PASS] Full analysis (rename): {result.change_type}, doc_update={result.doc_update_needed}")

    # Test 8: full analysis, no change
    result = analyzer.analyze(
        doc_title="Create a virtual machine",
        captured_title="Create a virtual machine",
    )
    assert result.has_significant_change is False
    assert result.change_type == "none"
    print(f"[PASS] Full analysis (no change): {result.change_type}")

    # Test 9: full analysis with 404
    result = analyzer.analyze(
        doc_title="Configure LUIS app",
        captured_title="Page not found",
        captured_page_text="404 - The page you are looking for does not exist.",
    )
    assert result.has_significant_change is True
    assert result.change_type == "page_not_found"
    assert result.doc_update_needed is True
    print(f"[PASS] Full analysis (404): {result.change_type}")

    # Test 10: layout change
    result = analyzer.analyze(
        doc_title="Overview dashboard",
        captured_title="Overview dashboard",
        original_image_dimensions=(1200, 800),
        captured_image_dimensions=(400, 300),
    )
    assert result.has_significant_change is True
    assert result.change_type == "layout_changed"
    print(f"[PASS] Full analysis (layout): {result.change_type}")

    print("\nAll tests passed.")

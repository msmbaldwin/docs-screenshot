"""
Doc-Driven Interaction Analyzer for the docs-screenshot skill.

Parses markdown documentation files to extract image references, determine
what interaction steps (clicks, selections, navigation) are described in the
surrounding text, and analyze whether flyouts or specific data must be present
before capturing a screenshot.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTEXT_WINDOW_CHARS = 500

# Action verbs recognized in doc text, mapped to canonical action names.
# Each key is a regex fragment (case-insensitive) and each value is the
# normalized action string stored in InteractionStep.action.
ACTION_VERB_MAP: dict[str, str] = {
    r"click(?:\s+on)?": "click",
    r"select": "select",
    r"choose": "select",
    r"press": "click",
    r"tap": "click",
    r"expand": "expand",
    r"collapse": "expand",
    r"navigate\s+to": "navigate",
    r"go\s+to": "navigate",
    r"browse\s+to": "navigate",
    r"open": "open",
    r"type": "type",
    r"enter": "type",
    r"input": "type",
    r"scroll(?:\s+(?:down|up|to))?": "scroll",
    r"toggle": "toggle",
    r"turn\s+on": "toggle",
    r"turn\s+off": "toggle",
    r"switch": "toggle",
    r"enable": "toggle",
    r"disable": "toggle",
}

# Words that typically follow a target noun to identify UI element types.
UI_ELEMENT_SUFFIXES = (
    "button", "link", "tab", "menu", "menu item", "option", "checkbox",
    "radio button", "switch", "toggle", "dropdown", "drop-down", "list",
    "field", "text box", "textbox", "input", "pane", "panel", "blade",
    "section", "flyout", "dialog", "modal", "icon", "card", "tile",
    "banner", "breadcrumb", "header", "row", "column", "cell",
)

# Patterns that hint a flyout, panel, or overlay should appear.
FLYOUT_KEYWORDS = re.compile(
    r"\b(?:flyout|panel|pane|blade|dialog|modal|overlay|drawer|sidebar|side\s*bar"
    r"|pop[\s-]?up|popup|slide[\s-]?out|context\s*menu)\b",
    re.IGNORECASE,
)

# Azure resource type patterns found in docs.
AZURE_RESOURCE_TYPES = [
    "Azure OpenAI",
    "Cognitive Services",
    "Document Intelligence",
    "Azure AI Search",
    "Azure AI Services",
    "Azure Machine Learning",
    "Azure SQL",
    "Azure Cosmos DB",
    "Azure Storage",
    "Azure Key Vault",
    "Azure App Service",
    "Azure Functions",
    "Azure Kubernetes Service",
    "Azure Container Apps",
    "Azure Virtual Machine",
    "Azure Logic Apps",
    "Azure API Management",
    "Azure Monitor",
    "Azure Data Factory",
    "Azure Synapse Analytics",
    "Azure Event Hubs",
    "Azure Service Bus",
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class InteractionStep:
    """A single user interaction extracted from documentation text.

    Attributes:
        action: Canonical verb (click, select, expand, navigate, type,
                scroll, toggle, open).
        target: UI element to interact with.
        value: Payload for 'type' and 'select' actions; None otherwise.
        confidence: 0.0 to 1.0 indicating how certain we are this step
                    precedes the image capture.
        source_text: The doc sentence or phrase this was extracted from.
    """

    action: str
    target: str
    value: str | None = None
    confidence: float = 0.5
    source_text: str = ""


@dataclass
class DataRequirement:
    """Describes data that must exist in the environment for a screenshot.

    Attributes:
        description: Human-readable summary (e.g., "a deleted Cognitive
                     Services resource").
        is_required: True when the doc explicitly mentions or highlights
                     this data; False when it is merely visible.
        source_text: The doc text implying this requirement.
        creation_hint: Optional guidance for creating the data (e.g.,
                       "create a resource, then delete it").
    """

    description: str
    is_required: bool = True
    source_text: str = ""
    creation_hint: str | None = None


@dataclass
class ImageReference:
    """An image reference parsed from a markdown documentation file.

    Attributes:
        source_path: Relative media path from the markdown
                     (e.g., "media/article/image.png").
        alt_text: The image alt text.
        image_type: The image type attribute ("content", "icon",
                    "complex", or "screenshot" as a default).
        surrounding_context: Roughly 500 chars before and after the
                             image reference in the markdown.
        step_number: Numbered-step index if the image sits inside a
                     numbered list item; None otherwise.
        preceding_actions: Interaction steps described before this image.
        expected_elements: UI element names mentioned in the alt text or
                          surrounding context that should be visible.
        has_callout_in_original: Whether the original image contains red
                                callout boxes (set externally).
        doc_file_path: Full filesystem path to the markdown file.
        repo_relative_path: Path from the repository root (forward
                            slashes, no drive letter).
    """

    source_path: str
    alt_text: str
    image_type: str = "content"
    surrounding_context: str = ""
    step_number: int | None = None
    preceding_actions: list[InteractionStep] = field(default_factory=list)
    expected_elements: list[str] = field(default_factory=list)
    has_callout_in_original: bool = False
    doc_file_path: str = ""
    repo_relative_path: str = ""

    def is_screenshot(self) -> bool:
        """Classify whether this image is a portal screenshot vs a diagram/icon/art.

        Uses a heuristic chain:
        1. image_type == "icon" → not a screenshot
        2. Alt text or filename contains diagram/conceptual keywords → not a screenshot
        3. Otherwise → assumed to be a screenshot

        Returns:
            True if this image should be treated as a capturable screenshot.
        """
        # Icon type is never a screenshot
        if self.image_type == "icon":
            return False

        _NON_SCREENSHOT_KEYWORDS = [
            "diagram", "architecture", "flowchart", "workflow diagram",
            "illustration", "conceptual", "logo", "banner", "overview diagram",
            "infographic", "topology", "schematic", "data flow", "sequence diagram",
            "decision tree", "state machine", "class diagram", "er diagram",
            "network diagram", "block diagram", "system design",
        ]

        # Check alt text
        alt_lower = self.alt_text.lower()
        for kw in _NON_SCREENSHOT_KEYWORDS:
            if kw in alt_lower:
                return False

        # Check filename
        filename_lower = os.path.basename(self.source_path).lower()
        filename_stem = os.path.splitext(filename_lower)[0].replace("-", " ").replace("_", " ")
        for kw in _NON_SCREENSHOT_KEYWORDS:
            if kw in filename_stem:
                return False

        # Check surrounding context for explicit "the following diagram" or similar
        ctx_lower = self.surrounding_context.lower()
        _CONTEXT_SIGNALS = [
            "the following diagram", "this diagram", "as shown in the diagram",
            "the following illustration", "this illustration",
            "the following flowchart", "this flowchart",
            "the architecture diagram", "conceptual overview",
        ]
        for signal in _CONTEXT_SIGNALS:
            if signal in ctx_lower:
                return False

        return True


# ---------------------------------------------------------------------------
# Regex helpers (compiled once at module load)
# ---------------------------------------------------------------------------

# Matches Microsoft Learn :::image::: blocks.  Captures the entire attribute
# string between the opening and closing markers.
_TRICOLON_IMAGE_RE = re.compile(
    r":::image\s+(.*?):::",
    re.DOTALL,
)

# Matches standard Markdown image syntax: ![alt](path "optional title")
_MARKDOWN_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)",
)

# Extracts key=value or key="value" pairs inside a :::image::: block.
_ATTR_RE = re.compile(
    r'(\w[\w-]*)="([^"]*)"',
)

# Detects numbered list items: "1. ", "2. ", etc.
_NUMBERED_STEP_RE = re.compile(
    r"^(\d+)\.\s",
    re.MULTILINE,
)

# Matches a breadcrumb-style navigation path: X > Y > Z
_NAV_PATH_RE = re.compile(
    r"(?:navigate\s+to|go\s+to|browse\s+to)\s+\**([^.\n]+?(?:\s*>\s*[^.>\n]+)+)\**",
    re.IGNORECASE,
)

# Matches "In the X pane/blade, select/click Y".
# Two variants: one for bold targets, one for non-bold targets.
_IN_PANE_BOLD_RE = re.compile(
    r"[Ii]n\s+the\s+\*\*(.+?)\*\*\s+(?:pane|blade|panel|section|dialog|flyout|menu)"
    r"[,;]?\s+(?:select|click|choose|press|tap)\s+\*\*(.+?)\*\*",
    re.IGNORECASE,
)
_IN_PANE_PLAIN_RE = re.compile(
    r"[Ii]n\s+the\s+(\w[\w\s]*?)\s+(?:pane|blade|panel|section|dialog|flyout|menu)"
    r"[,;]?\s+(?:select|click|choose|press|tap)\s+(?:the\s+)?([^.,;:!?\n]+?)"
    r"(?=[.,;:!?\n]|$)",
    re.IGNORECASE,
)

# Matches "Toggle X to On/Off" or "Turn on/off the X switch"
_TOGGLE_RE = re.compile(
    r"(?:toggle|switch|turn)\s+(?:the\s+)?(?:on|off\s+)?(?:the\s+)?\**(.+?)\**"
    r"\s+(?:switch|toggle)?\s*(?:to\s+)?(on|off)?",
    re.IGNORECASE,
)

# Matches "Enter/Type X in the Y field"
_TYPE_IN_FIELD_RE = re.compile(
    r"(?:enter|type|input)\s+\**(.+?)\**\s+(?:in|into)\s+(?:the\s+)?\**(.+?)\**"
    r"\s*(?:field|text\s*box|textbox|input|box)",
    re.IGNORECASE,
)

# Generic: "Click/Select [the] <target> [button/link/tab/...]"
# Bold variant: verb [the] **target** [suffix]
_GENERIC_ACTION_BOLD_RE = re.compile(
    r"(?:"
    + "|".join(ACTION_VERB_MAP.keys())
    + r")\s+(?:the\s+)?\*\*(.+?)\*\*"
    r"(?:\s+(?:" + "|".join(UI_ELEMENT_SUFFIXES) + r"))?"
    r"(?=[.,;:!\s\n]|$)",
    re.IGNORECASE,
)

# Non-bold variant: verb [the] <target> <suffix>  (suffix required to
# delimit the target reliably when bold markers are absent).
_GENERIC_ACTION_PLAIN_RE = re.compile(
    r"(?:"
    + "|".join(ACTION_VERB_MAP.keys())
    + r")\s+(?:the\s+)?'([^']+)'"
    r"(?:\s+(?:" + "|".join(UI_ELEMENT_SUFFIXES) + r"))?"
    r"(?=[.,;:!\s\n]|$)",
    re.IGNORECASE,
)

# Fallback for unquoted, non-bold targets: requires a suffix word to
# avoid capturing runaway text.
_GENERIC_ACTION_SUFFIX_RE = re.compile(
    r"(?:"
    + "|".join(ACTION_VERB_MAP.keys())
    + r")\s+(?:the\s+)?(\w[\w\s]{1,50}?)"
    r"\s+(" + "|".join(re.escape(s) for s in UI_ELEMENT_SUFFIXES) + r")"
    r"(?=[.,;:!\s\n]|$)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# DocAnalyzer
# ---------------------------------------------------------------------------

class DocAnalyzer:
    """Analyzes markdown documentation to extract image references and
    the interaction steps required before each screenshot capture.
    """

    # ----- public API -------------------------------------------------------

    def parse_markdown_images(
        self,
        markdown_content: str,
        doc_file_path: str,
        repo_root: str,
    ) -> list[ImageReference]:
        """Parse all image references from a markdown file.

        Supports both ``:::image … :::`` (Microsoft Learn) and
        ``![alt](path)`` syntaxes.

        Args:
            markdown_content: Full text of the markdown file.
            doc_file_path: Absolute path to the markdown file on disk.
            repo_root: Absolute path to the repository root.

        Returns:
            A list of ImageReference objects in document order.
        """
        images: list[ImageReference] = []
        repo_rel = self.compute_repo_relative_path(doc_file_path, repo_root)

        # --- :::image::: blocks ---
        for match in _TRICOLON_IMAGE_RE.finditer(markdown_content):
            attrs = dict(_ATTR_RE.findall(match.group(1)))
            source = attrs.get("source", "")
            alt = attrs.get("alt-text", "")
            img_type = attrs.get("type", "content")

            if not source:
                continue

            ctx = self._extract_surrounding_context(
                markdown_content, match.start(), match.end(),
            )
            step = self._detect_step_number(markdown_content, match.start())
            actions = self.extract_interaction_steps(ctx)
            actions = self._assign_confidence(
                actions, markdown_content, match.start(),
            )
            expected = self._extract_expected_elements(alt, ctx)

            images.append(ImageReference(
                source_path=source,
                alt_text=alt,
                image_type=img_type,
                surrounding_context=ctx,
                step_number=step,
                preceding_actions=actions,
                expected_elements=expected,
                has_callout_in_original=False,
                doc_file_path=doc_file_path,
                repo_relative_path=repo_rel,
            ))

        # --- standard markdown images ---
        for match in _MARKDOWN_IMAGE_RE.finditer(markdown_content):
            alt = match.group(1)
            source = match.group(2)

            ctx = self._extract_surrounding_context(
                markdown_content, match.start(), match.end(),
            )
            step = self._detect_step_number(markdown_content, match.start())
            actions = self.extract_interaction_steps(ctx)
            actions = self._assign_confidence(
                actions, markdown_content, match.start(),
            )
            expected = self._extract_expected_elements(alt, ctx)

            images.append(ImageReference(
                source_path=source,
                alt_text=alt,
                image_type="content",
                surrounding_context=ctx,
                step_number=step,
                preceding_actions=actions,
                expected_elements=expected,
                has_callout_in_original=False,
                doc_file_path=doc_file_path,
                repo_relative_path=repo_rel,
            ))

        # Deduplicate by source_path (a single image may match both patterns).
        seen: set[str] = set()
        deduped: list[ImageReference] = []
        for img in images:
            if img.source_path not in seen:
                seen.add(img.source_path)
                deduped.append(img)

        return deduped

    def filter_screenshots(
        self,
        images: list[ImageReference],
        repo_root: str | None = None,
    ) -> tuple[list[ImageReference], list[ImageReference]]:
        """Separate screenshots from non-screenshot images (diagrams, icons, etc.).

        Uses the ``ImageReference.is_screenshot()`` heuristic first. For
        ambiguous cases where the image file exists on disk, opens the image
        and checks for visual characteristics of diagrams (very few colors,
        mostly white background, no photographic content).

        Args:
            images: All parsed image references.
            repo_root: Repo root for resolving image file paths. If provided,
                enables visual inspection fallback for ambiguous images.

        Returns:
            A tuple of (screenshots, skipped) lists.
        """
        screenshots: list[ImageReference] = []
        skipped: list[ImageReference] = []

        for img in images:
            if not img.is_screenshot():
                skipped.append(img)
                continue

            # If we have the repo root, do a quick visual check on
            # ambiguous images (e.g., alt text doesn't clearly indicate type)
            if repo_root and img.source_path:
                doc_dir = os.path.dirname(img.doc_file_path)
                img_path = os.path.join(doc_dir, img.source_path)
                if os.path.isfile(img_path) and self._looks_like_diagram(img_path):
                    skipped.append(img)
                    continue

            screenshots.append(img)

        return screenshots, skipped

    @staticmethod
    def _looks_like_diagram(image_path: str) -> bool:
        """Quick visual heuristic to detect diagrams/flowcharts.

        Diagrams typically have very few unique colors (under 64),
        large white/light background areas, and no photographic gradients.
        Screenshots of portal UIs have many more colors and gradients.

        Returns True if the image looks like a diagram (should be skipped).
        """
        try:
            from PIL import Image
            img = Image.open(image_path).convert("RGB")
            # Downsample to speed up analysis
            thumb = img.resize((100, 100), Image.NEAREST)
            colors = thumb.getcolors(maxcolors=256)
            if colors is None:
                # More than 256 colors; definitely not a simple diagram
                return False

            unique_colors = len(colors)

            # Very few unique colors strongly suggests a diagram/vector art
            if unique_colors < 32:
                return True

            # Check if the background is overwhelmingly white/light
            total_pixels = 100 * 100
            white_ish = sum(
                count for count, (r, g, b) in colors
                if r > 240 and g > 240 and b > 240
            )
            if white_ish > total_pixels * 0.75 and unique_colors < 64:
                return True

            return False
        except Exception:
            return False

    def extract_interaction_steps(self, context: str) -> list[InteractionStep]:
        """Extract interaction steps from the text surrounding an image.

        Recognizes patterns such as:
          - "Click [the] X [button/link/tab]"
          - "Navigate to X > Y > Z"
          - "In the X pane, select Y"
          - "Toggle the X switch to On"
          - "Enter X in the Y field"

        Args:
            context: Markdown text around the image (typically the
                     surrounding_context field of an ImageReference).

        Returns:
            Interaction steps in the order they appear in the text.
        """
        steps: list[InteractionStep] = []
        seen_spans: list[tuple[int, int]] = []

        def _overlaps(start: int, end: int) -> bool:
            return any(s <= start < e or s < end <= e for s, e in seen_spans)

        def _record(step: InteractionStep, start: int, end: int) -> None:
            if not _overlaps(start, end):
                seen_spans.append((start, end))
                steps.append(step)

        # --- navigation paths (X > Y > Z) ---
        for m in _NAV_PATH_RE.finditer(context):
            _record(
                InteractionStep(
                    action="navigate",
                    target=m.group(1).strip().strip("*"),
                    source_text=m.group(0).strip(),
                ),
                m.start(), m.end(),
            )

        # --- "In the X pane, select Y" ---
        for regex in (_IN_PANE_BOLD_RE, _IN_PANE_PLAIN_RE):
            for m in regex.finditer(context):
                pane = m.group(1).strip().strip("*")
                target = m.group(2).strip().strip("*")
                if len(target) < 2 or target.lower() in ("the", "a", "an"):
                    continue
                _record(
                    InteractionStep(
                        action="select",
                        target=f"{target} (in {pane})",
                        source_text=m.group(0).strip(),
                    ),
                    m.start(), m.end(),
                )

        # --- toggle patterns ---
        for m in _TOGGLE_RE.finditer(context):
            target = m.group(1).strip().strip("*")
            value = m.group(2).strip() if m.group(2) else None
            _record(
                InteractionStep(
                    action="toggle",
                    target=target,
                    value=value,
                    source_text=m.group(0).strip(),
                ),
                m.start(), m.end(),
            )

        # --- type / enter in field ---
        for m in _TYPE_IN_FIELD_RE.finditer(context):
            value = m.group(1).strip().strip("*")
            field_name = m.group(2).strip().strip("*")
            _record(
                InteractionStep(
                    action="type",
                    target=field_name,
                    value=value,
                    source_text=m.group(0).strip(),
                ),
                m.start(), m.end(),
            )

        # --- generic action verb + target ---
        # Try bold targets first, then single-quoted, then suffix-delimited.
        for regex in (
            _GENERIC_ACTION_BOLD_RE,
            _GENERIC_ACTION_PLAIN_RE,
            _GENERIC_ACTION_SUFFIX_RE,
        ):
            for m in regex.finditer(context):
                verb_text = m.group(0).split()[0].lower()
                canonical = self._canonicalize_verb(verb_text)
                target = m.group(1).strip().strip("*'\"")

                # Skip very short or obviously wrong targets.
                if len(target) < 2 or target.lower() in (
                    "the", "a", "an", "this", "it",
                ):
                    continue

                _record(
                    InteractionStep(
                        action=canonical,
                        target=target,
                        source_text=m.group(0).strip(),
                    ),
                    m.start(), m.end(),
                )

        return steps

    def analyze_flyout_need(
        self,
        image_ref: ImageReference,
        original_image_path: str | None = None,
    ) -> dict:
        """Determine whether a flyout or panel must be opened before capture.

        Args:
            image_ref: The parsed image reference with surrounding context.
            original_image_path: Optional path to the original screenshot
                                 (reserved for future image analysis).

        Returns:
            A dict with keys: needs_flyout (bool), flyout_trigger (str or
            None), flyout_data_required (list[DataRequirement]),
            and reasoning (str).
        """
        reasons: list[str] = []
        trigger: str | None = None
        needs = False

        combined_text = f"{image_ref.alt_text} {image_ref.surrounding_context}"

        # Check if alt text or context mentions flyout-type UI.
        if FLYOUT_KEYWORDS.search(combined_text):
            needs = True
            reasons.append(
                "The alt text or surrounding context mentions a flyout, "
                "panel, blade, or dialog."
            )

        # Check if preceding actions include a click that would open something.
        for step in image_ref.preceding_actions:
            if step.action in ("click", "open", "expand", "select"):
                target_lower = step.target.lower()
                if any(kw in target_lower for kw in (
                    "manage", "add", "create", "new", "delete", "remove",
                    "edit", "configure", "settings", "properties", "details",
                    "advanced", "more", "options", "show", "view",
                )):
                    needs = True
                    trigger = step.target
                    reasons.append(
                        f"The preceding action '{step.action} {step.target}' "
                        f"likely opens a flyout or panel."
                    )
                    break

        # Rule: if a button is highlighted with a callout in the original
        # AND the screenshot shows a flyout/panel whose title matches that
        # button label, then the button was clicked before the screenshot.
        # Detect this by checking if the alt text or context mentions both
        # a button name and "deleted", "manage", or similar action words
        # that imply a flyout was triggered.
        if not needs:
            ctx_lower = combined_text.lower()
            # Look for patterns like "manage deleted X" which strongly imply
            # a button was clicked to open a management flyout.
            manage_pattern = re.search(
                r"\b(manage\s+deleted|manage\s+\w+\s+resources?|deleted\s+resources?)\b",
                ctx_lower,
            )
            if manage_pattern:
                needs = True
                trigger = manage_pattern.group(0).strip()
                reasons.append(
                    f"Context references '{trigger}', which implies a "
                    f"management flyout was opened via a button click."
                )

        # If no specific trigger found but flyout keywords exist, try to
        # identify the most likely trigger from preceding actions.
        if needs and trigger is None and image_ref.preceding_actions:
            last_click = next(
                (s for s in reversed(image_ref.preceding_actions)
                 if s.action in ("click", "open", "expand")),
                None,
            )
            if last_click:
                trigger = last_click.target

        data_reqs = self.analyze_data_requirements(image_ref) if needs else []

        if not reasons:
            reasons.append(
                "No flyout-related keywords or trigger actions detected."
            )

        return {
            "needs_flyout": needs,
            "flyout_trigger": trigger,
            "flyout_data_required": data_reqs,
            "reasoning": " ".join(reasons),
        }

    def analyze_data_requirements(
        self,
        image_ref: ImageReference,
    ) -> list[DataRequirement]:
        """Determine what data must exist for a screenshot to be accurate.

        Examines the alt text and surrounding context for references to
        resources, records, or states that should be visible in the UI.

        Args:
            image_ref: The parsed image reference.

        Returns:
            A list of DataRequirement objects sorted by importance
            (required first).
        """
        requirements: list[DataRequirement] = []
        combined = f"{image_ref.alt_text} {image_ref.surrounding_context}"

        # Look for "deleted", "existing", "created", and similar state words.
        # The capture group uses a greedy quantifier bounded by clause-ending
        # punctuation or newline (not bare whitespace) so it grabs the full
        # noun phrase.
        _clause_end = r"(?=[.,;:!?\n)}\]]|\s*$)"
        state_patterns: list[tuple[str, re.Pattern[str], str | None]] = [
            (
                "deleted",
                re.compile(
                    r"(?:deleted?|removed?|purged?)\s+"
                    r"(\w+(?:\s+\w+){0,5}?)(?:\s+resources?)?"
                    + _clause_end,
                    re.IGNORECASE,
                ),
                "Create the resource, then delete it before capturing.",
            ),
            (
                "existing",
                re.compile(
                    r"(?:existing|already\s+created|previously\s+created)\s+"
                    r"(\w+(?:\s+\w+){0,5}?)(?:\s+resources?)?"
                    + _clause_end,
                    re.IGNORECASE,
                ),
                "Ensure the resource exists before capturing.",
            ),
            (
                "deployed",
                re.compile(
                    r"(?:deployed|running|active)\s+"
                    r"(\w+(?:\s+\w+){0,5}?)"
                    r"(?:\s+(?:resources?|instances?|services?))?"
                    + _clause_end,
                    re.IGNORECASE,
                ),
                "Deploy the resource before capturing.",
            ),
            (
                "at least one",
                re.compile(
                    r"(?:at\s+least\s+one|one\s+or\s+more|multiple)\s+"
                    r"(\w+(?:\s+\w+){0,5}?)"
                    + _clause_end,
                    re.IGNORECASE,
                ),
                "Create sample items before capturing.",
            ),
        ]

        seen_descriptions: set[str] = set()
        for label, pattern, hint in state_patterns:
            for m in pattern.finditer(combined):
                desc = m.group(1).strip()
                desc_lower = desc.lower()
                # Skip noise words captured alone.
                if desc_lower in (
                    "the", "a", "an", "this", "that", "it", "its",
                    "resources", "resource", "you",
                ):
                    continue
                # Skip captures that are really UI element names (e.g.,
                # "resources button" from "deleted resources button").
                if any(desc_lower.endswith(s) for s in UI_ELEMENT_SUFFIXES):
                    continue
                full_desc = f"a {label} {desc}"
                if full_desc.lower() in seen_descriptions:
                    continue
                seen_descriptions.add(full_desc.lower())
                requirements.append(DataRequirement(
                    description=full_desc,
                    is_required=True,
                    source_text=m.group(0).strip(),
                    creation_hint=hint,
                ))

        # Check for Azure resource type mentions as incidental data.
        for rtype in AZURE_RESOURCE_TYPES:
            if rtype.lower() in combined.lower():
                already = any(rtype.lower() in r.description.lower()
                              for r in requirements)
                if not already:
                    requirements.append(DataRequirement(
                        description=f"an {rtype} resource",
                        is_required=image_ref.has_callout_in_original,
                        source_text=rtype,
                        creation_hint=f"Provision an {rtype} resource.",
                    ))

        # Sort: required first, then alphabetical.
        requirements.sort(key=lambda r: (not r.is_required, r.description))
        return requirements

    def get_expected_page_title(
        self,
        image_ref: ImageReference,
    ) -> str | None:
        """Extract the expected page or blade title from doc context.

        Looks for patterns like "the X page", "the X blade", or
        page/blade names in the alt text.

        Args:
            image_ref: The parsed image reference.

        Returns:
            The expected title string, or None if not found.
        """
        combined = f"{image_ref.alt_text} {image_ref.surrounding_context}"

        # "the <Title> page/blade/pane/screen/view"
        title_re = re.compile(
            r"(?:the\s+)\**(.+?)\**\s+"
            r"(?:page|blade|pane|screen|view|window|dialog|panel)",
            re.IGNORECASE,
        )
        m = title_re.search(combined)
        if m:
            title = m.group(1).strip().strip("*")
            if len(title) > 2 and title.lower() not in ("a", "an", "this"):
                return title

        return None

    def get_expected_resource_type(
        self,
        image_ref: ImageReference,
    ) -> str | None:
        """Extract the Azure resource type mentioned in the doc context.

        Args:
            image_ref: The parsed image reference.

        Returns:
            The resource type string (e.g., "Azure OpenAI"), or None.
        """
        combined = f"{image_ref.alt_text} {image_ref.surrounding_context}"
        combined_lower = combined.lower()

        for rtype in AZURE_RESOURCE_TYPES:
            if rtype.lower() in combined_lower:
                return rtype

        return None

    def compute_repo_relative_path(
        self,
        doc_file_path: str,
        repo_root: str,
    ) -> str:
        """Convert an absolute filesystem path to a repo-root-relative path.

        The result uses forward slashes and contains no drive letter,
        suitable for use in Git operations and URL construction.

        Args:
            doc_file_path: Absolute path to the file.
            repo_root: Absolute path to the repository root.

        Returns:
            Forward-slash separated path relative to repo_root.
        """
        # Normalize both paths so os.path.relpath works reliably.
        abs_file = os.path.normpath(doc_file_path)
        abs_root = os.path.normpath(repo_root)

        rel = os.path.relpath(abs_file, abs_root)
        # Always use forward slashes regardless of OS.
        return rel.replace("\\", "/")

    # ----- private helpers --------------------------------------------------

    def _extract_surrounding_context(
        self,
        content: str,
        match_start: int,
        match_end: int,
    ) -> str:
        """Return ~CONTEXT_WINDOW_CHARS before and after a match position."""
        before_start = max(0, match_start - CONTEXT_WINDOW_CHARS)
        after_end = min(len(content), match_end + CONTEXT_WINDOW_CHARS)
        return content[before_start:after_end]

    def _detect_step_number(
        self,
        content: str,
        image_pos: int,
    ) -> int | None:
        """Find the numbered step the image sits inside, if any.

        Scans backwards from the image position for the nearest numbered
        list marker (e.g., '3. ').
        """
        # Look at the text before the image, up to ~1000 chars.
        search_start = max(0, image_pos - 1000)
        preceding = content[search_start:image_pos]

        # Find all numbered-step markers and return the last one.
        matches = list(_NUMBERED_STEP_RE.finditer(preceding))
        if matches:
            return int(matches[-1].group(1))

        return None

    def _canonicalize_verb(self, verb: str) -> str:
        """Map a raw verb string to its canonical action name."""
        verb_lower = verb.lower().strip()
        for pattern, canonical in ACTION_VERB_MAP.items():
            if re.fullmatch(pattern, verb_lower, re.IGNORECASE):
                return canonical
        return verb_lower

    def _assign_confidence(
        self,
        steps: list[InteractionStep],
        content: str,
        image_pos: int,
    ) -> list[InteractionStep]:
        """Assign confidence scores based on proximity to the image.

        Scoring:
          1.0  if the step text appears in the same numbered step,
               immediately before the image.
          0.8  if the step is in a preceding numbered step.
          0.5  if the step is mentioned in the surrounding context but
               not clearly tied to this specific image.
        """
        if not steps:
            return steps

        current_step = self._detect_step_number(content, image_pos)

        # Find the start of the current numbered step (the line with "N. ").
        current_step_start = 0
        if current_step is not None:
            marker = f"{current_step}."
            search_start = max(0, image_pos - 2000)
            preceding = content[search_start:image_pos]
            idx = preceding.rfind(marker)
            if idx != -1:
                current_step_start = search_start + idx

        for step in steps:
            # Find where the source text appears relative to the image.
            src_pos = content.find(step.source_text)
            if src_pos == -1:
                step.confidence = 0.5
                continue

            if current_step is not None and src_pos >= current_step_start:
                # Same numbered step, immediately before the image.
                step.confidence = 1.0
            elif src_pos < image_pos:
                # Before the image but in a different/preceding step.
                step.confidence = 0.8
            else:
                # After the image or not clearly preceding.
                step.confidence = 0.5

        return steps

    def _extract_expected_elements(
        self,
        alt_text: str,
        context: str,
    ) -> list[str]:
        """Pull UI element names from alt text and surrounding context.

        Identifies quoted strings, bold-formatted names, and known UI
        element suffixes to build a list of elements expected on screen.
        """
        elements: list[str] = []
        seen_lower: set[str] = set()

        def _add(name: str) -> None:
            cleaned = name.strip().strip("*'\"")
            if len(cleaned) > 1 and cleaned.lower() not in seen_lower:
                seen_lower.add(cleaned.lower())
                elements.append(cleaned)

        combined = f"{alt_text} {context}"

        # Bold text in markdown: **text** or __text__
        for m in re.finditer(r"\*\*(.+?)\*\*|__(.+?)__", combined):
            _add(m.group(1) or m.group(2))

        # Single-quoted UI element names: 'Element Name'
        for m in re.finditer(r"'([^']{2,40})'", combined):
            _add(m.group(1))

        # Phrases ending in a UI element suffix.
        suffix_pattern = (
            r"(?:the\s+)(\w[\w\s]{1,40}?)\s+(?:"
            + "|".join(re.escape(s) for s in UI_ELEMENT_SUFFIXES)
            + r")\b"
        )
        for m in re.finditer(suffix_pattern, combined, re.IGNORECASE):
            _add(m.group(1))

        return elements


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_md = """\
# Recover deleted Azure AI Services resources

## Steps

1. Navigate to **portal.azure.com** and sign in.

2. In the Azure portal, search for **Cognitive Services** in the search bar.

3. Click the **Manage deleted resources** button in the toolbar.

   :::image type="content" source="media/recover-resources/manage-deleted-resources.png" alt-text="The Cognitive Services page showing the Manage deleted resources button.":::

4. In the **Manage deleted resources** flyout, select the deleted resource
   you want to recover.

   ![The Manage deleted resources flyout showing a list of deleted resources.](media/recover-resources/deleted-resources-flyout.png)

5. Click **Recover** to restore the resource.
"""

    analyzer = DocAnalyzer()
    images = analyzer.parse_markdown_images(
        sample_md,
        doc_file_path="docs/articles/ai-services/recover-resources.md",
        repo_root="docs",
    )

    print(f"Found {len(images)} image(s):\n")
    for i, img in enumerate(images, 1):
        print(f"  [{i}] {img.source_path}")
        print(f"      alt: {img.alt_text[:80]}...")
        print(f"      type: {img.image_type}")
        print(f"      step: {img.step_number}")
        print(f"      repo path: {img.repo_relative_path}")
        print(f"      actions: {len(img.preceding_actions)}")
        for a in img.preceding_actions:
            print(f"        - {a.action} '{a.target}' (confidence={a.confidence})")
        print(f"      expected elements: {img.expected_elements}")

        flyout = analyzer.analyze_flyout_need(img)
        print(f"      needs flyout: {flyout['needs_flyout']}")
        print(f"      flyout trigger: {flyout['flyout_trigger']}")
        print(f"      reasoning: {flyout['reasoning'][:120]}")

        data_reqs = analyzer.analyze_data_requirements(img)
        for dr in data_reqs:
            print(f"      data req: {dr.description} (required={dr.is_required})")

        title = analyzer.get_expected_page_title(img)
        rtype = analyzer.get_expected_resource_type(img)
        print(f"      page title: {title}")
        print(f"      resource type: {rtype}")
        print()

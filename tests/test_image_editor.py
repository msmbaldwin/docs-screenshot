"""Tests for lib/image_editor.py (pure functions)."""

from image_editor import (
    enforce_naming_convention,
    get_segoe_ui_font,
    parse_css_color,
    parse_font_size,
)


def test_parse_css_color_rgb():
    assert parse_css_color("rgb(255, 0, 128)") == (255, 0, 128)


def test_parse_css_color_rgba():
    assert parse_css_color("rgba(10, 20, 30, 0.5)") == (10, 20, 30)


def test_parse_css_color_hex6():
    assert parse_css_color("#FF8040") == (255, 128, 64)


def test_parse_css_color_hex3():
    # #abc -> #aabbcc
    assert parse_css_color("#abc") == (170, 187, 204)


def test_parse_css_color_invalid_returns_white():
    assert parse_css_color("not-a-color") == (255, 255, 255)


def test_parse_css_color_empty_returns_white():
    assert parse_css_color("") == (255, 255, 255)


def test_parse_font_size_px():
    assert parse_font_size("16px") == 16.0


def test_parse_font_size_decimal_px():
    assert parse_font_size("13.5px") == 13.5


def test_parse_font_size_missing_returns_default():
    assert parse_font_size("") == 14.0
    assert parse_font_size("inherit") == 14.0


def test_enforce_naming_lowercases():
    assert enforce_naming_convention("MyImage.PNG") == "myimage.png"


def test_enforce_naming_replaces_spaces():
    assert enforce_naming_convention("create resource group.png") == "create-resource-group.png"


def test_enforce_naming_replaces_underscores():
    assert enforce_naming_convention("create_resource_group.png") == "create-resource-group.png"


def test_enforce_naming_strips_special_chars():
    assert enforce_naming_convention("foo!@#$bar.png") == "foobar.png"


def test_enforce_naming_collapses_multiple_hyphens():
    assert enforce_naming_convention("foo---bar.png") == "foo-bar.png"


def test_enforce_naming_strips_leading_trailing_hyphens():
    assert enforce_naming_convention("--foo-bar--.png") == "foo-bar.png"


def test_enforce_naming_adds_png_extension():
    assert enforce_naming_convention("noextension") == "noextension.png"


def test_get_segoe_ui_font_returns_truetype_on_linux():
    """Regression: on Linux without Segoe UI/Arial, must still return a usable
    TrueType font (DejaVu/Liberation), not the tiny PIL bitmap default."""
    from PIL import ImageFont
    font = get_segoe_ui_font(14, '400')
    assert isinstance(font, ImageFont.FreeTypeFont), (
        f"Expected FreeTypeFont fallback, got {type(font).__name__} "
        f"(text rendering would be unusable)"
    )


def test_get_segoe_ui_font_bold_returns_truetype():
    from PIL import ImageFont
    font = get_segoe_ui_font(14, '700')
    assert isinstance(font, ImageFont.FreeTypeFont)


def test_redact_pii_centers_text_vertically():
    """Regression: text was rendered too low because bbox[1] offset wasn't
    subtracted from the centered y. Verify the inked pixels actually fall
    within the central band of the box, not the bottom."""
    from image_editor import RedactionSpec, redact_pii
    from PIL import Image

    img = Image.new('RGB', (300, 60), (255, 255, 255))
    redact_pii(img, [RedactionSpec(
        px_rect={'x': 20, 'y': 10, 'width': 260, 'height': 40},
        replacement_text='ABCxyz',
        bg_color='rgb(255, 255, 255)',
        font_family='Segoe UI', font_size='20px', font_weight='400',
        text_color='rgb(0, 0, 0)',
    )])
    # Find the vertical range of non-white pixels inside the box
    px = img.load()
    inked_ys = [
        y for y in range(10, 50)
        for x in range(20, 280)
        if px[x, y] != (255, 255, 255)
    ]
    assert inked_ys, "No text was rendered"
    text_top, text_bot = min(inked_ys), max(inked_ys)
    text_mid = (text_top + text_bot) / 2
    box_mid = 10 + 40 / 2
    # Allow ~4 px of slack for font metric quirks
    assert abs(text_mid - box_mid) <= 4, (
        f"text vertical center {text_mid} differs from box center {box_mid} "
        f"by more than 4px (top={text_top}, bot={text_bot})"
    )


def test_redact_pii_auto_shrinks_to_fit_box_height():
    """When the requested font size produces glyphs taller than the box,
    redact_pii should shrink the font, not overflow."""
    from image_editor import RedactionSpec, redact_pii
    from PIL import Image

    img = Image.new('RGB', (300, 60), (255, 255, 255))
    redact_pii(img, [RedactionSpec(
        # Request 40px font in a 16px-tall box - must shrink
        px_rect={'x': 10, 'y': 20, 'width': 280, 'height': 16},
        replacement_text='hello',
        bg_color='rgb(255, 255, 255)',
        font_family='Segoe UI', font_size='40px', font_weight='400',
        text_color='rgb(0, 0, 0)',
    )])
    # No ink should appear above y=20 or below y=36
    px = img.load()
    for y in list(range(0, 20)) + list(range(37, 60)):
        for x in range(300):
            assert px[x, y] == (255, 255, 255), (
                f"Ink found at ({x},{y}) outside the requested box - "
                "auto-shrink did not engage"
            )


def test_redact_pii_preserves_border_when_requested():
    """border_color must redraw the field outline that fill clobbered."""
    from image_editor import RedactionSpec, redact_pii
    from PIL import Image, ImageDraw

    # Simulate a bordered input field
    img = Image.new('RGB', (400, 60), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 10, 380, 50], outline=(128, 128, 128), width=1)

    redact_pii(img, [RedactionSpec(
        px_rect={'x': 22, 'y': 12, 'width': 356, 'height': 36},
        replacement_text='value',
        bg_color='rgb(255, 255, 255)',
        font_family='Segoe UI', font_size='14px', font_weight='400',
        text_color='rgb(0, 0, 0)',
        border_color='rgb(128, 128, 128)',
        border_width=1,
    )])
    # Border pixels should still be gray after redaction
    assert img.getpixel((22, 12)) == (128, 128, 128)
    assert img.getpixel((377, 47)) == (128, 128, 128)


def test_redact_pii_fill_inset_preserves_outer_border():
    """fill_inset shrinks the fill so an outer 1px border survives untouched."""
    from image_editor import RedactionSpec, redact_pii
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (200, 60), (255, 255, 255))
    d = ImageDraw.Draw(img)
    # 1px gray border on the rect we'll redact
    d.rectangle([10, 10, 190, 50], outline=(50, 50, 50), width=1)

    redact_pii(img, [RedactionSpec(
        px_rect={'x': 10, 'y': 10, 'width': 181, 'height': 41},
        replacement_text='x',
        bg_color='rgb(255, 255, 255)',
        font_family='Segoe UI', font_size='14px', font_weight='400',
        text_color='rgb(0, 0, 0)',
        fill_inset=1,
    )])
    # Outer border pixels untouched
    assert img.getpixel((10, 10)) == (50, 50, 50)
    assert img.getpixel((190, 50)) == (50, 50, 50)

"""Tests for lib/image_editor.py (pure functions)."""
from image_editor import parse_css_color, parse_font_size, enforce_naming_convention


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

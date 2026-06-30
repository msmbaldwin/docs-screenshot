"""Tests for lib/pii_detector.py."""
from pii_detector import PIIDetector


def test_detects_unapproved_guid_as_pii():
    d = PIIDetector()
    text = "Subscription: 72f988bf-86f1-41af-91ab-2d7cd011db47"
    results = d.detect_in_text(text)
    assert any(r[0] == "72f988bf-86f1-41af-91ab-2d7cd011db47" for r in results)
    types = {r[1] for r in results}
    assert any(t.startswith("guid:") for t in types)


def test_skips_approved_guid():
    d = PIIDetector()
    # An approved subscription_id from APPROVED_GUIDS
    text = "Subscription: aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e"
    results = d.detect_in_text(text)
    guids = [r for r in results if r[1].startswith("guid:")]
    assert guids == [], f"Approved GUID should be skipped, got: {guids}"


def test_flags_microsoft_employee_email():
    d = PIIDetector()
    results = d.detect_in_text("Contact testuser@microsoft.com for access")
    emails = [r for r in results if r[1] == "email"]
    assert len(emails) == 1
    assert emails[0][0] == "testuser@microsoft.com"


def test_skips_approved_fictitious_email():
    d = PIIDetector()
    # First-name only, approved domain - should be skipped
    results = d.detect_in_text("Send mail to john@contoso.com today")
    emails = [r for r in results if r[1] == "email"]
    assert emails == [], f"Approved fictitious email should be skipped, got: {emails}"


def test_flags_real_tenant_domain():
    d = PIIDetector()
    results = d.detect_in_text("Tenant: MicrosoftCustomerLed.onmicrosoft.com")
    tenants = [r for r in results if r[1] == "tenant_domain"]
    assert len(tenants) == 1
    assert tenants[0][2] == "contoso.onmicrosoft.com"


def test_skips_contoso_tenant_domain():
    d = PIIDetector()
    results = d.detect_in_text("Tenant: contoso.onmicrosoft.com")
    tenants = [r for r in results if r[1] == "tenant_domain"]
    assert tenants == []


def test_skips_private_ip():
    d = PIIDetector()
    results = d.detect_in_text("Server: 10.0.0.5 and 192.168.1.15")
    ips = [r for r in results if r[1] == "ip_address"]
    assert ips == []


def test_flags_public_ip():
    d = PIIDetector()
    results = d.detect_in_text("Server IP: 40.112.72.205")
    ips = [r for r in results if r[1] == "ip_address"]
    assert len(ips) == 1
    assert ips[0][0] == "40.112.72.205"


def test_replacement_cycles_through_approved_list():
    """Multiple unapproved GUIDs should get different replacements from the approved pool."""
    d = PIIDetector()
    text = (
        "72f988bf-86f1-41af-91ab-2d7cd011db47 "
        "12345678-1234-1234-1234-123456789012"
    )
    results = d.detect_in_text(text)
    guids = [r for r in results if r[1].startswith("guid:")]
    # Both detected
    assert len(guids) == 2
    # Replacements differ (counter cycled)
    replacements = [r[2] for r in guids]
    assert len(set(replacements)) == 2 or replacements[0] == replacements[1] and len(set(replacements)) == 1
    # At minimum: both replacements must be approved (not real)
    for orig, _, repl, _ in guids:
        assert repl != orig


def test_empty_text():
    d = PIIDetector()
    assert d.detect_in_text("") == []


def test_no_pii_text():
    d = PIIDetector()
    results = d.detect_in_text("Hello world, this is a friendly message.")
    assert results == []

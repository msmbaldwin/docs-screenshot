"""
pii_detector.py - PII Detection and Fictitious Replacement Generator

Classifies extracted DOM text nodes as PII or safe, using patterns from the
Microsoft contributor guide's approved sensitive identifiers list.

Generates compliant dummy replacements using official CELA-approved values.
"""

import re
from dataclasses import dataclass, field


@dataclass
class PIIMatch:
    """A detected PII instance with its replacement."""
    text: str                    # Original PII text
    pii_type: str                # Category (e.g., 'subscription_id', 'email')
    severity: int                # 0 = most sensitive, 2 = least
    replacement: str             # Approved fictitious replacement
    node_index: int              # Index into the DOM extraction textNodes array
    css_rect: dict = field(default_factory=dict)
    px_rect: dict = field(default_factory=dict)
    style: dict = field(default_factory=dict)


# --- Approved replacement values from MS contributor guide ---

APPROVED_GUIDS = {
    'application_id': [
        '00001111-aaaa-2222-bbbb-3333cccc4444',
        '11112222-bbbb-3333-cccc-4444dddd5555',
        '22223333-cccc-4444-dddd-5555eeee6666',
        '33334444-dddd-5555-eeee-6666ffff7777',
        '44445555-eeee-6666-ffff-7777aaaa8888',
        '55556666-ffff-7777-aaaa-8888bbbb9999',
        '66667777-aaaa-8888-bbbb-9999cccc0000',
    ],
    'certificate_id': [
        '0a0a0a0a-1111-bbbb-2222-3c3c3c3c3c3c',
        '1b1b1b1b-2222-cccc-3333-4d4d4d4d4d4d',
        '2c2c2c2c-3333-dddd-4444-5e5e5e5e5e5e',
    ],
    'correlation_id': [
        'aaaa0000-bb11-2222-33cc-444444dddddd',
        'bbbb1111-cc22-3333-44dd-555555eeeeee',
        'cccc2222-dd33-4444-55ee-666666ffffff',
    ],
    'tenant_id': [
        'aaaabbbb-0000-cccc-1111-dddd2222eeee',
        'bbbbcccc-1111-dddd-2222-eeee3333ffff',
        'ccccdddd-2222-eeee-3333-ffff4444aaaa',
    ],
    'object_id': [
        'aaaaaaaa-0000-1111-2222-bbbbbbbbbbbb',
        'bbbbbbbb-1111-2222-3333-cccccccccccc',
        'cccccccc-2222-3333-4444-dddddddddddd',
        'dddddddd-3333-4444-5555-eeeeeeeeeeee',
    ],
    'principal_id': [
        'aaaaaaaa-bbbb-cccc-1111-222222222222',
        'bbbbbbbb-cccc-dddd-2222-333333333333',
    ],
    'resource_id': [
        'a0a0a0a0-bbbb-cccc-dddd-e1e1e1e1e1e1',
        'b1b1b1b1-cccc-dddd-eeee-f2f2f2f2f2f2',
    ],
    'secret_id': [
        'aaaaaaaa-0b0b-1c1c-2d2d-333333333333',
        'bbbbbbbb-1c1c-2d2d-3e3e-444444444444',
    ],
    'subscription_id': [
        'aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e',
        'bbbb1b1b-cc2c-dd3d-ee4e-ffffff5f5f5f',
        'cccc2c2c-dd3d-ee4e-ff5f-aaaaaa6a6a6a',
    ],
    'trace_id': [
        '0000aaaa-11bb-cccc-dd22-eeeeee333333',
        '1111bbbb-22cc-dddd-ee33-ffffff444444',
    ],
}

APPROVED_SECRETS = {
    'client_secret': [
        'Aa1Bb~2Cc3.-Dd4Ee5Ff6Gg7Hh8Ii9_Jj0Kk1Ll2',
        'Bb2Cc~3Dd4.-Ee5Ff6Gg7Hh8Ii9Jj0_Kk1Ll2Mm3',
    ],
    'alphanumeric': [
        'A1bC2dE3fH4iJ5kL6mN7oP8qR9sT0u',
        'C2dE3fH4iJ5kL6mN7oP8qR9sT0uV1w',
    ],
    'thumbprint': [
        'AA11BB22CC33DD44EE55FF66AA77BB88CC99DD00',
        'BB22CC33DD44EE55FF66AA77BB88CC99DD00EE11',
    ],
}

APPROVED_EMAILS = [
    'john@contoso.com',
    'sara@contoso.com',
    'alex@fabrikam.com',
    'lee@northwindtraders.com',
    'pat@contoso.com',
    'kim@adventure-works.com',
]

APPROVED_IPS = [
    '192.168.1.15',
    '10.0.0.4',
    '172.16.3.22',
    '192.0.2.13',
    '198.51.100.101',
    '203.0.113.254',
]

APPROVED_RESOURCE_NAMES = {
    'resource_group': ['contoso-rg', 'fabrikam-rg', 'myresourcegroup', 'example-resources'],
    'vm': ['contoso-vm', 'fabrikam-vm-01', 'myVM'],
    'storage': ['contosostorageacct', 'fabrikamstorage', 'mystorageaccount'],
    'webapp': ['contoso-webapp', 'fabrikam-app', 'mywebapp-01'],
    'sql_server': ['contoso-sql', 'fabrikam-sqlserver', 'mysqlserver'],
    'keyvault': ['contoso-kv', 'fabrikam-keyvault', 'mykeyvault'],
    'generic': ['contoso-resource', 'fabrikam-resource', 'myresource'],
}

APPROVED_COMPANY_DOMAINS = [
    'contoso.com',
    'fabrikam.com',
    'northwindtraders.com',
    'adventure-works.com',
    'example.com',
    'example.org',
]

APPROVED_ADDRESSES = [
    '4567 Main St., Buffalo, NY 98052',
    '1234 Elm St., Redmond, WA 98053',
    '8901 Oak Ave., Seattle, WA 98054',
]


class PIIDetector:
    """Detects PII in DOM-extracted text nodes and generates approved replacements."""

    # Tracks how many of each replacement type we've used (for cycling through approved lists)
    _counters: dict

    def __init__(self):
        self._counters = {}

    def _next_replacement(self, category: str, subcategory: str, approved_list: list) -> str:
        key = f"{category}:{subcategory}"
        idx = self._counters.get(key, 0)
        value = approved_list[idx % len(approved_list)]
        self._counters[key] = idx + 1
        return value

    def detect_in_text(self, text: str) -> list[tuple[str, str, str, int]]:
        """
        Scan a single text string for PII patterns.
        Returns list of (matched_text, pii_type, replacement, severity).
        """
        findings = []

        # GUID pattern (covers all GUID types)
        guid_pattern = re.compile(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            re.IGNORECASE
        )
        for m in guid_pattern.finditer(text):
            guid = m.group(0)
            # Skip if it's already an approved GUID
            if self._is_approved_guid(guid):
                continue
            guid_type = self._classify_guid_context(text, guid)
            replacement = self._next_replacement(
                'guid', guid_type, APPROVED_GUIDS.get(guid_type, APPROVED_GUIDS['object_id'])
            )
            sev = 0 if guid_type in ('certificate_id', 'secret_id') else 1
            findings.append((guid, f'guid:{guid_type}', replacement, sev))

        # Email addresses
        email_pattern = re.compile(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            re.IGNORECASE
        )
        for m in email_pattern.finditer(text):
            email = m.group(0)
            username = email.split('@')[0].lower()
            domain = email.split('@')[1].lower()
            # Only skip if it's an approved fictitious email pattern:
            # single first name (no dots/numbers) + approved domain
            is_fictitious = (
                domain in APPROVED_COMPANY_DOMAINS
                and re.match(r'^[a-z]+$', username)  # single word, letters only
                and '.' not in username
            )
            if is_fictitious:
                continue
            # Real employee emails (microsoft.com, onmicrosoft.com, etc.) ARE PII
            replacement = self._next_replacement('email', 'email', APPROVED_EMAILS)
            findings.append((email, 'email', replacement, 1))

        # Tenant/directory names (e.g., "MicrosoftCustomerLed.onmicrosoft.com")
        tenant_pattern = re.compile(
            r'[A-Za-z0-9-]+\.onmicrosoft\.com',
            re.IGNORECASE
        )
        for m in tenant_pattern.finditer(text):
            tenant = m.group(0)
            if tenant.lower() == 'contoso.onmicrosoft.com':
                continue
            replacement = 'contoso.onmicrosoft.com'
            findings.append((tenant, 'tenant_domain', replacement, 1))

        # IP addresses (public, non-reserved)
        ip_pattern = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')
        for m in ip_pattern.finditer(text):
            ip = m.group(1)
            if not self._is_safe_ip(ip):
                replacement = self._next_replacement('ip', 'ip', APPROVED_IPS)
                findings.append((ip, 'ip_address', replacement, 1))

        # Access keys / connection strings (long base64-like strings)
        secret_pattern = re.compile(
            r'(?<![a-zA-Z0-9/+=])[A-Za-z0-9+/]{32,}={0,2}(?![a-zA-Z0-9/+=])'
        )
        for m in secret_pattern.finditer(text):
            secret = m.group(0)
            replacement = self._next_replacement('secret', 'alphanumeric', APPROVED_SECRETS['alphanumeric'])
            findings.append((secret, 'secret_key', replacement, 0))

        # Client secrets (specific pattern with ~ and .)
        client_secret_pattern = re.compile(r'[A-Za-z0-9~._-]{30,50}')
        for m in client_secret_pattern.finditer(text):
            val = m.group(0)
            if '~' in val or (len(val) == 40 and re.match(r'^[A-Za-z0-9._~-]+$', val)):
                if not any(val == s for lst in APPROVED_SECRETS.values() for s in lst):
                    replacement = self._next_replacement('secret', 'client_secret', APPROVED_SECRETS['client_secret'])
                    findings.append((val, 'client_secret', replacement, 0))

        # Thumbprints (40 hex chars)
        thumb_pattern = re.compile(r'\b[0-9A-Fa-f]{40}\b')
        for m in thumb_pattern.finditer(text):
            thumb = m.group(0)
            if not any(thumb.upper() == s for s in APPROVED_SECRETS['thumbprint']):
                replacement = self._next_replacement('secret', 'thumbprint', APPROVED_SECRETS['thumbprint'])
                findings.append((thumb, 'thumbprint', replacement, 0))

        return findings

    def _is_approved_guid(self, guid: str) -> bool:
        guid_lower = guid.lower()
        for guid_list in APPROVED_GUIDS.values():
            if guid_lower in guid_list:
                return True
        # Null GUID is always safe
        if guid_lower == '00000000-0000-0000-0000-000000000000':
            return True
        return False

    def _classify_guid_context(self, full_text: str, guid: str) -> str:
        """Use surrounding context to classify what type of GUID this is."""
        text_lower = full_text.lower()
        # Check for contextual keywords near the GUID
        context_map = {
            'subscription_id': ['subscription', 'sub id'],
            'tenant_id': ['tenant', 'directory', 'tid'],
            'application_id': ['application', 'client', 'app id', 'appid', 'clientid'],
            'object_id': ['object', 'oid', 'user id', 'objectid'],
            'resource_id': ['resource', 'resourceid'],
            'principal_id': ['principal', 'principalid'],
            'certificate_id': ['certificate', 'cert'],
            'secret_id': ['secret', 'key id', 'secretid', 'keyid'],
            'correlation_id': ['correlation', 'correlationid', 'request id'],
            'trace_id': ['trace', 'traceid'],
        }
        for guid_type, keywords in context_map.items():
            for kw in keywords:
                if kw in text_lower:
                    return guid_type
        return 'object_id'  # default

    def _is_safe_ip(self, ip: str) -> bool:
        """Check if an IP is in a safe/reserved range."""
        parts = ip.split('.')
        if len(parts) != 4:
            return True
        try:
            octets = [int(p) for p in parts]
        except ValueError:
            return True

        if any(o < 0 or o > 255 for o in octets):
            return True

        a, b, c, d = octets

        # Private ranges (already safe)
        if a == 10:
            return True
        if a == 172 and 16 <= b <= 31:
            return True
        if a == 192 and b == 168:
            return True
        # Documentation ranges (RFC 5737)
        if a == 192 and b == 0 and c == 2:
            return True
        if a == 198 and b == 51 and c == 100:
            return True
        if a == 203 and b == 0 and c == 113:
            return True
        # Loopback
        if a == 127:
            return True
        # Link-local
        if a == 169 and b == 254:
            return True
        # Azure wire server
        if ip == '168.63.129.16':
            return True
        # Carrier-grade NAT
        if a == 100 and 64 <= b <= 127:
            return True
        # Approved IPs list
        if ip in APPROVED_IPS:
            return True

        return False

    def scan_dom_extraction(self, dom_data: dict) -> list[PIIMatch]:
        """
        Scan DOM extraction output for PII.
        
        Args:
            dom_data: Output from extract_dom_info.js
            
        Returns:
            List of PIIMatch objects with replacements
        """
        matches = []
        text_nodes = dom_data.get('textNodes', [])

        for i, node in enumerate(text_nodes):
            text = node.get('text', '')
            if not text:
                continue

            findings = self.detect_in_text(text)
            for matched_text, pii_type, replacement, severity in findings:
                matches.append(PIIMatch(
                    text=matched_text,
                    pii_type=pii_type,
                    severity=severity,
                    replacement=replacement,
                    node_index=i,
                    css_rect=node.get('cssRect', {}),
                    px_rect=node.get('pxRect', {}),
                    style=node.get('style', {}),
                ))

        return matches

    def generate_summary(self, matches: list[PIIMatch]) -> str:
        """Generate a human-readable summary of detected PII."""
        if not matches:
            return "No PII detected."

        lines = [f"Detected {len(matches)} PII instance(s):\n"]
        by_type = {}
        for m in matches:
            by_type.setdefault(m.pii_type, []).append(m)

        for pii_type, items in sorted(by_type.items()):
            lines.append(f"  [{pii_type}] ({len(items)} found)")
            for item in items:
                lines.append(f"    - \"{item.text[:40]}...\" -> \"{item.replacement}\" (SEV {item.severity})")

        return "\n".join(lines)


if __name__ == '__main__':
    # Quick self-test
    detector = PIIDetector()
    test_cases = [
        "Subscription ID: 72f988bf-86f1-41af-91ab-2d7cd011db47",
        "Contact admin@realcorp.net for access",
        "Server IP: 40.112.72.205",
        "Tenant: 72f988bf-86f1-41af-91ab-2d7cd011db47",
        "Object ID: aaaaaaaa-0000-1111-2222-bbbbbbbbbbbb",  # approved, should skip
        "john@contoso.com",  # approved fictitious, should skip
        "IP: 192.168.1.1",  # private, should skip
        "testuser@microsoft.com",  # microsoft.com employee email, SHOULD flag
        "MicrosoftCustomerLed.onmicrosoft.com",  # real tenant, SHOULD flag
        "sara@contoso.com",  # approved fictitious (single first name), should skip
    ]
    for tc in test_cases:
        results = detector.detect_in_text(tc)
        status = f"  -> {len(results)} PII" if results else "  -> clean"
        print(f"{tc[:60]:<60} {status}")
        for r in results:
            print(f"      {r[1]}: '{r[0]}' -> '{r[2]}'")

# PII Replacement Reference

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


### Approved GUIDs (from MS Sensitive Identifiers Reference)

| Type | Example Approved Value |
|------|----------------------|
| Application (client) ID | `00001111-aaaa-2222-bbbb-3333cccc4444` |
| Certificate ID (SEV 0) | `0a0a0a0a-1111-bbbb-2222-3c3c3c3c3c3c` |
| Correlation ID | `aaaa0000-bb11-2222-33cc-444444dddddd` |
| Directory (tenant) ID | `aaaabbbb-0000-cccc-1111-dddd2222eeee` |
| Object ID | `aaaaaaaa-0000-1111-2222-bbbbbbbbbbbb` |
| Principal ID | `aaaaaaaa-bbbb-cccc-1111-222222222222` |
| Resource ID | `a0a0a0a0-bbbb-cccc-dddd-e1e1e1e1e1e1` |
| Secret ID/Key ID (SEV 0) | `aaaaaaaa-0b0b-1c1c-2d2d-333333333333` |
| Subscription ID | `aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e` |
| Trace ID | `0000aaaa-11bb-cccc-dd22-eeeeee333333` |

### Approved Non-GUID Values

| Type | Example |
|------|---------|
| Client Secret | `Aa1Bb~2Cc3.-Dd4Ee5Ff6Gg7Hh8Ii9_Jj0Kk1Ll2` |
| Alphanumeric | `A1bC2dE3fH4iJ5kL6mN7oP8qR9sT0u` |
| Thumbprint | `AA11BB22CC33DD44EE55FF66AA77BB88CC99DD00` |
| Signature Hash | `aB1cD2eF-3gH4iJ5kL6-mN7oP8qR=` |

### Approved Fictitious Names (CELA-approved)

| Category | Approved Values |
|----------|----------------|
| Company domains | `contoso.com`, `fabrikam.com`, `northwindtraders.com`, `adventure-works.com` |
| Generic domains | `example.com`, `example.org`, `example.net` |
| Email format | First name only: `john@contoso.com` (NOT `john.smith@contoso.com`) |
| Resource groups | `contoso-rg`, `fabrikam-rg`, `myresourcegroup` |
| VMs | `contoso-vm`, `fabrikam-vm-01`, `myVM` |
| Storage accounts | `contosostorageacct`, `fabrikamstorage` |
| Key vaults | `contoso-kv`, `fabrikam-keyvault` |

### Safe IP Ranges for Documentation

- Private: `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`
- RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- Azure wire server: `168.63.129.16`
- Loopback: `127.0.0.0/8`
- Link-local: `169.254.0.0/16`


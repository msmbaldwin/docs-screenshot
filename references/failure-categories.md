# Failure Categories Reference

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


Each capture attempt is classified into one of the following categories. The badge is shown in the HTML comparison report.

| Category | Badge | Description | Example |
|----------|-------|-------------|---------|
| `CAPTURE_SUCCESS` | ✅ Success | Screenshot matches expectations | Normal successful capture |
| `PRIVILEGE_FAILURE` | 🔒 Privilege | Insufficient permissions to access the page or resource | Cannot access Fabric Admin portal without admin role |
| `NAVIGATION_FAILURE` | ❌ Navigation | Landed on the wrong page after navigation | Went to Cognitive Services overview instead of Azure OpenAI |
| `DATA_SETUP_FAILURE` | ❌ Data Setup | Cannot create the required data for the screenshot | Doc describes a fine-tuned model deployment we cannot provision |
| `UI_MISMATCH` | ⚠️ UI Mismatch | Page looks fundamentally different from the original screenshot | Service restructured with a completely new layout |
| `PII_LEAK` | 🚨 PII Leak | PII detected in the final screenshot after scrubbing | Real email address still visible in a cross-origin iframe |
| `DOC_INSUFFICIENT` | 📄 Doc Gap | Doc text lacks sufficient detail to reproduce the screenshot | Steps do not describe how to reach the target page |
| `ELEMENT_NOT_FOUND` | 🔍 Not Found | Expected UI element is missing from the page | "Playgrounds" not in nav, "More" button also not found |
| `SERVICE_RESTRUCTURED` | ⚠️ Restructured | Service has been renamed or reorganized since the doc was written | Form Recognizer is now Document Intelligence |

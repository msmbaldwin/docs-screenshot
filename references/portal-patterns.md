# Common Azure Portal Popup Patterns

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


These are elements you'll frequently need to dismiss:

| Popup Type | Selector Pattern |
|-----------|-----------------|
| Welcome dialog | `button:has-text("Got it")`, `button:has-text("Maybe later")` |
| Preview banner | `[class*="preview-banner"] button`, `[class*="fxs-banner"] button` |
| Notification toast | `.fxs-toast-container button` |
| What's new | `button:has-text("What's new")` parent close button |
| Feature announcement | `[data-telemetryname="DismissButton"]` |
| Generic close | `[aria-label="Close"]`, `[aria-label="Dismiss"]` |
| Consent/cookie | `button:has-text("Accept")`, `button:has-text("OK")` |


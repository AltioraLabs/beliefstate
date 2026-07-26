"""Manual verification script for PII redaction (issue #15).

Run with: python test_package/test_pii_redaction_verification.py
"""

from beliefstate.extractor import redact_pii

samples = [
    "Contact me at user123@example.com for details.",
    "My phone number is +91 98765-43210",
    "My card number is 4111 1111 1111 1111",
    "SSN: 123-45-6789",
    "No sensitive info here, just a plain sentence.",
]

print("=== BEFORE / AFTER PII Redaction ===\n")
for s in samples:
    print(f"BEFORE: {s}")
    print(f"AFTER:  {redact_pii(s)}\n")

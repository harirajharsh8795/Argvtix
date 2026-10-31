# ADR-006: Reversible Tokenized PII Masking and DLP Filtering

## Status
Accepted

## Context
Enterprise customer support logs frequently contain sensitive Personally Identifiable Information (PII) including 12-digit Indian Aadhaar numbers, Permanent Account Numbers (PAN), credit card details, phone numbers, and email addresses. Leaking these violates DPDP Act (India) and GDPR.

## Decision
We implemented a two-tier data privacy boundary:
1. **PIIMasker:** Pre-ingestion tokenization of sensitive identifiers using regex and checksum validation (e.g. Verhoeff/Luhn algorithms). Sensitive values are converted to structured tokens (`[AADHAAR_MASKED]`, `[PAN_MASKED]`, `[CARD_MASKED]`).
2. **DLPFilter:** Outbound sanitization inspecting LLM responses before sending them back to the user or saving to trace storage.
3. **Reversible Vault (Optional):** In authenticated enterprise setups, a secure encrypted token vault allows authorized compliance officers to detokenize for dispute resolution while keeping developer logs completely clean.

## Consequences
- **Positive:** Zero plaintext PII persisted to trace tables; full compliance with DPDP and PCI-DSS.
- **Trade-off:** Minimal latency overhead (<2ms) during trace recording and egress filtering.

# ADR-009: Proofline Scout — Permission-First Legal Model and Safety Architecture

## Status
Accepted (Blueprint Correction Applied)

## Context
Probing external chatbots without explicit authorization violates Terms of Service, risks IP blacklisting, and carries severe legal and regulatory liability. Automated cold outreach or scraping competitor bots is strictly forbidden in enterprise enterprise environments.

## Decision
Proofline Scout strictly operates under a **Permission-First Legal Model**:
1. **Written Permission Gate (`scope.yaml`):** Scout may ONLY execute against targets defined in a valid, cryptographically signed `scope.yaml` containing host allowlists, path restrictions, validity timestamps, and verified written authorization IDs.
2. **Egress Firewall & Container Isolation:** Scout runs in a dedicated Docker network sandbox (`scout-isolated-net`) with default deny egress. Outbound network traffic is limited strictly to whitelisted hosts in `scope.yaml`.
3. **Emergency Kill Switch:** Dual kill switch (API endpoint `/api/v1/scout/abort`, file flag `.scout_kill`, and dead-man timer) that halts all outbound requests in < 5 seconds.
4. **Target Protection Circuit Breaker:** Auto-aborts immediately upon encountering 3 consecutive 5xx server responses from the target to avoid causing denial-of-service.
5. **Human Review Gate:** Reports are generated with status `DRAFT_PENDING_REVIEW`. Scout has zero cold email or autonomous outreach capability.

## Consequences
- **Positive:** Full legal and regulatory compliance; safe, non-destructive enterprise auditing.
- **Trade-off:** Pre-audit onboarding requires cryptographic scope configuration and sign-off.

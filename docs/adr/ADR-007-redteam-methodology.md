# ADR-007: Automated Red Teaming Methodology — 40-Attack Matrix

## Status
Accepted

## Context
AI agents deployed in production face continuous adversarial threats: prompt injections, delimiter escaping, social engineering, jailbreaks, PII harvesting, and tool fuzzing. Manual penetration testing is slow and cannot be run on every CI build.

## Decision
We built an automated 40-attack red teaming suite spanning 6 primary threat axes:
1. **Direct Injection & System Extraction:** Delimiter escape, role-reversal, system prompt leak probes.
2. **PII Harvesting:** Social engineering prompts soliciting other users' identification numbers.
3. **Guard Boundary Bypass:** High-value refunds, delivered order cancellations, unauthorized discounts.
4. **Toxicity & Tone:** Customer harassment, profanity, and emotional manipulation.
5. **SQL & Tool Injection:** Parameter fuzzing, quote escaping, and stack trace harvesting.
6. **Multilingual & Hinglish Jailbreaks:** Vernacular pretexting and translated jailbreaks (Hindi Devanagari and Roman Hinglish).

The test suite runs automatically via `RedTeamRunner` and computes an aggregate Defense Score (%) across all axes.

## Consequences
- **Positive:** Continuous security regression testing; 100% reproducible defense scores.
- **Trade-off:** Synthetic attacks must be continuously augmented as new jailbreak patterns emerge.

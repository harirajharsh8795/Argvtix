# ADR-011: Hybrid Z-Score and Interquartile Range (IQR) Sliding-Window Anomaly Detection

## Status
Accepted (Missing Item Added)

## Context
Production agent fleets can experience sudden anomalies: refund spikes due to hallucinated loops, latency degradation caused by degraded external vector DBs, or sudden error bursts. Fixed static thresholds trigger false positives during legitimate traffic surges or miss subtle proportional anomalies.

## Decision
We implemented a hybrid statistical anomaly detector using sliding time windows:
1. **Z-Score Detection:** Measures standard deviations from the moving mean ($Z \ge 3.0$) for normally distributed metrics like request latencies.
2. **IQR (Interquartile Range) Detection:** Uses non-parametric quartile spreads ($Q3 + 1.5 \times IQR$) to catch outliers in skewed financial and refund count metrics without being distorted by extreme spikes.
3. **Multi-Channel Alert Dispatcher:** When statistical anomalies or ERP/CRM reconciliation mismatches are detected, findings are routed to Slack webhooks, email stubs, and an in-memory audit ring buffer.

## Consequences
- **Positive:** Adapts dynamically to traffic seasonality; resilient to extreme outlier distortion.
- **Trade-off:** Requires a minimum baseline window (default 10 samples) before calculating metrics.

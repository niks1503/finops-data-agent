# Evaluation report (gemini-3.5-flash-lite)

| Metric | Value |
|---|---|
| Cases | 33 |
| Execution accuracy | 97.0% |
| Answer accuracy | 100.0% |
| Answers rescued by SQL self-correction | 0 |
| Avg / p95 latency | 22.09s / 79.77s |
| Avg tokens per question | 3481 |
| Avg cost per question | $0.0 |

## By category

| Category | Execution accuracy |
|---|---|
| aggregation | 75% |
| anomaly | 100% |
| charge_type | 100% |
| filter | 100% |
| lookup | 100% |
| ranking | 100% |
| safety | 100% |
| totals | 100% |

## Failures

### compute_share_oct
- Q: What percentage of October 2026 usage spend was Compute?
- Gold: `[[48.7317]]`
- Agent rows: `[[47060.3119, 96570.2914]]`
- Answer: In October 2026, Compute spend was $47,060.31 out of a total usage spend of $96,570.29, which accounts for 48.73% of the total usage spend.


# Evaluation report (gemini-3.5-flash-lite)

| Metric | Value |
|---|---|
| Cases | 33 |
| Execution accuracy | 97.0% |
| Answer accuracy | 97.0% |
| Answers rescued by SQL self-correction | 0 |
| Avg / p95 latency | 15.29s / 44.08s |
| Avg tokens per question | 3410 |
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

### payments_prod_avg_daily_oct
- Q: What was payments-prod's average daily usage cost in October 2026?
- Gold: `[[876.9039]]`
- Agent rows: `[[920.749]]`
- Answer: In October 2026, payments-prod had an average daily usage cost of $920.75.


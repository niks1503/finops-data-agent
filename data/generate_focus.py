"""Generate synthetic multi-cloud billing data in the FOCUS format.

FOCUS (FinOps Open Cost and Usage Specification) is the industry-standard
schema for cloud billing exports. This script produces 12 months of daily
charges for several teams across AWS, Google Cloud and Microsoft Azure, with
realistic trend, weekly seasonality and noise, plus a few planted anomalies so
the evaluation benchmark has known, checkable answers.

Usage:
    python data/generate_focus.py --out data/raw/focus_billing.csv
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

START = date(2025, 11, 1)
END = date(2026, 10, 31)

# sub_account_id, name, team, environment, provider, region
ACCOUNTS = [
    ("acc-001", "payments-prod", "Payments", "prod", "AWS", "us-east-1"),
    ("acc-002", "payments-dev", "Payments", "dev", "AWS", "us-east-1"),
    ("acc-003", "data-platform", "Data", "prod", "AWS", "us-west-2"),
    ("acc-004", "ml-research", "ML", "dev", "Google Cloud", "us-central1"),
    ("acc-005", "web-frontend", "Web", "prod", "Microsoft", "eastus"),
    ("acc-006", "analytics", "Data", "prod", "Google Cloud", "asia-south1"),
    ("acc-007", "mobile-backend", "Mobile", "prod", "Microsoft", "centralindia"),
    ("acc-008", "security-tools", "Security", "prod", "AWS", "ap-south-1"),
]

# provider -> list of (service_name, service_category, sku, consumed_unit, unit_price)
SERVICES = {
    "AWS": [
        ("Amazon Elastic Compute Cloud", "Compute", "EC2-OnDemand", "Hours", 0.096),
        ("Amazon Simple Storage Service", "Storage", "S3-Standard", "GB-Mo", 0.023),
        ("Amazon EBS Snapshots", "Storage", "EBS-Snapshot", "GB-Mo", 0.05),
        ("Amazon Relational Database Service", "Databases", "RDS-Postgres", "Hours", 0.17),
        ("AWS Data Transfer", "Networking", "DataTransfer-Out", "GB", 0.09),
    ],
    "Google Cloud": [
        ("Compute Engine", "Compute", "N2-Standard", "Hours", 0.097),
        ("Cloud Storage", "Storage", "GCS-Standard", "GB-Mo", 0.020),
        ("BigQuery", "Analytics", "BQ-Analysis", "TiB", 6.25),
        ("Vertex AI", "AI and Machine Learning", "Vertex-GPU-Training", "Hours", 2.48),
    ],
    "Microsoft": [
        ("Virtual Machines", "Compute", "D4s-v5", "Hours", 0.192),
        ("Storage Accounts", "Storage", "Blob-Hot", "GB-Mo", 0.018),
        ("Azure SQL Database", "Databases", "SQL-GP-vCore", "Hours", 0.505),
        ("Bandwidth", "Networking", "Egress", "GB", 0.087),
    ],
}

# Typical daily spend (USD) by (account, service) before trend and noise.
BASE_DAILY = {
    "acc-001": {"Amazon Elastic Compute Cloud": 420, "Amazon Relational Database Service": 210,
                "Amazon Simple Storage Service": 60, "AWS Data Transfer": 75, "Amazon EBS Snapshots": 25},
    "acc-002": {"Amazon Elastic Compute Cloud": 80, "Amazon Relational Database Service": 35,
                "Amazon Simple Storage Service": 12},
    "acc-003": {"Amazon Elastic Compute Cloud": 260, "Amazon Simple Storage Service": 140,
                "Amazon EBS Snapshots": 90, "AWS Data Transfer": 40},
    "acc-004": {"Compute Engine": 110, "Vertex AI": 180, "Cloud Storage": 30},
    "acc-005": {"Virtual Machines": 150, "Storage Accounts": 20, "Bandwidth": 45},
    "acc-006": {"BigQuery": 230, "Cloud Storage": 55, "Compute Engine": 40},
    "acc-007": {"Virtual Machines": 190, "Azure SQL Database": 120, "Bandwidth": 35},
    "acc-008": {"Amazon Elastic Compute Cloud": 70, "Amazon Simple Storage Service": 15},
}

# Planted anomalies. Each one is a ground-truth fact the agent should be able to find.
ANOMALIES = [
    {
        "id": "storage_snapshot_spike",
        "description": "data-platform EBS Snapshots cost rises ~35% from 2026-09-01 (retention policy changed)",
        "account": "acc-003", "service": "Amazon EBS Snapshots",
        "start": "2026-09-01", "end": "2026-10-31", "multiplier": 1.35,
    },
    {
        "id": "gpu_training_burst",
        "description": "ml-research Vertex AI spend ~2.5x for 10 days (large training run)",
        "account": "acc-004", "service": "Vertex AI",
        "start": "2026-08-10", "end": "2026-08-19", "multiplier": 2.5,
    },
    {
        "id": "dev_new_region",
        "description": "payments-dev starts running EC2 in eu-west-1 from 2026-10-01",
        "account": "acc-002", "service": "Amazon Elastic Compute Cloud",
        "start": "2026-10-01", "end": "2026-10-31", "new_region": "eu-west-1", "daily_cost": 55,
    },
]

REGION_NAMES = {
    "us-east-1": "US East (N. Virginia)", "us-west-2": "US West (Oregon)", "ap-south-1": "Asia Pacific (Mumbai)",
    "eu-west-1": "Europe (Ireland)", "us-central1": "Iowa", "asia-south1": "Mumbai",
    "eastus": "East US", "centralindia": "Central India",
}


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def in_window(d: date, a: dict) -> bool:
    return date.fromisoformat(a["start"]) <= d <= date.fromisoformat(a["end"])


def generate(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    svc_lookup = {p: {s[0]: s for s in lst} for p, lst in SERVICES.items()}
    rows = []
    n_days = (END - START).days + 1
    for i in range(n_days):
        d = START + timedelta(days=i)
        trend = 1 + 0.015 * (i / 30)          # ~1.5% growth per month
        weekly = 0.85 if d.weekday() >= 5 else 1.0  # quieter weekends
        for acc_id, acc_name, team, env, provider, region in ACCOUNTS:
            env_weekly = weekly if env == "prod" else (0.6 if d.weekday() >= 5 else 1.0)
            for svc_name, base in BASE_DAILY[acc_id].items():
                svc = svc_lookup[provider][svc_name]
                cost = base * trend * env_weekly * rng.normal(1.0, 0.06)
                for a in ANOMALIES:
                    if a["account"] == acc_id and a["service"] == svc_name and "multiplier" in a and in_window(d, a):
                        cost *= a["multiplier"]
                rows.append(_row(d, provider, acc_id, acc_name, team, env, region, svc, max(cost, 0.0)))
        for a in ANOMALIES:
            if "new_region" in a and in_window(d, a):
                acc = next(x for x in ACCOUNTS if x[0] == a["account"])
                svc = svc_lookup[acc[4]][a["service"]]
                cost = a["daily_cost"] * rng.normal(1.0, 0.06)
                rows.append(_row(d, acc[4], acc[0], acc[1], acc[2], acc[3], a["new_region"], svc, cost))

    df = pd.DataFrame(rows)
    df = pd.concat([df, _monthly_tax_and_credits(df)], ignore_index=True)
    return df.sort_values(["ChargePeriodStart", "SubAccountId", "ServiceName"]).reset_index(drop=True)


def _row(d, provider, acc_id, acc_name, team, env, region, svc, cost):
    svc_name, category, sku, unit, unit_price = svc
    list_cost = cost * 1.08  # list price before discounts
    return {
        "BillingPeriodStart": month_start(d).isoformat(),
        "BillingPeriodEnd": next_month(d).isoformat(),
        "ChargePeriodStart": d.isoformat(),
        "ChargePeriodEnd": (d + timedelta(days=1)).isoformat(),
        "ChargeCategory": "Usage",
        "ProviderName": provider,
        "BillingCurrency": "USD",
        "SubAccountId": acc_id,
        "SubAccountName": acc_name,
        "ServiceName": svc_name,
        "ServiceCategory": category,
        "SkuId": sku,
        "RegionId": region,
        "RegionName": REGION_NAMES[region],
        "ResourceId": f"{acc_id}/{sku}/{region}",
        "ConsumedQuantity": round(cost / unit_price, 3),
        "ConsumedUnit": unit,
        "ListCost": round(list_cost, 4),
        "BilledCost": round(cost, 4),
        "EffectiveCost": round(cost, 4),
        "Tags": json.dumps({"team": team, "environment": env}),
    }


def _monthly_tax_and_credits(usage: pd.DataFrame) -> pd.DataFrame:
    """One Tax row per account per month (5% of usage) and a monthly credit for analytics."""
    extra = []
    usage = usage.copy()
    usage["month"] = usage["BillingPeriodStart"]
    monthly = usage.groupby(["month", "SubAccountId"]).agg(
        cost=("BilledCost", "sum"), provider=("ProviderName", "first"), name=("SubAccountName", "first"),
        region=("RegionId", "first"), tags=("Tags", "first"), end=("BillingPeriodEnd", "first"),
    ).reset_index()
    for r in monthly.itertuples():
        base = {
            "BillingPeriodStart": r.month, "BillingPeriodEnd": r.end, "ChargePeriodStart": r.month,
            "ChargePeriodEnd": r.end, "ProviderName": r.provider, "BillingCurrency": "USD",
            "SubAccountId": r.SubAccountId, "SubAccountName": r.name, "RegionId": r.region,
            "RegionName": REGION_NAMES[r.region], "ConsumedQuantity": None, "ConsumedUnit": None,
            "SkuId": None, "Tags": r.tags,
        }
        tax = round(r.cost * 0.05, 4)
        extra.append({**base, "ChargeCategory": "Tax", "ServiceName": "Tax", "ServiceCategory": "Other",
                      "ResourceId": None, "ListCost": tax, "BilledCost": tax, "EffectiveCost": tax})
        if r.SubAccountId == "acc-006":  # committed-use credit for analytics
            credit = -round(r.cost * 0.10, 4)
            extra.append({**base, "ChargeCategory": "Credit", "ServiceName": "BigQuery",
                          "ServiceCategory": "Analytics", "ResourceId": None, "ListCost": 0.0,
                          "BilledCost": credit, "EffectiveCost": credit})
    return pd.DataFrame(extra)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/focus_billing.csv")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = generate(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    (out.parent / "planted_anomalies.json").write_text(json.dumps(ANOMALIES, indent=2))
    print(f"Wrote {len(df):,} rows to {out} ({df['ChargePeriodStart'].min()} to {df['ChargePeriodStart'].max()})")


if __name__ == "__main__":
    main()

"""
Mock Benchmark Data Generator for Google Search Console.
Generates realistic multi-page daily time-series with authentic search dynamics,
ranking fluctuations, momentum shifts, and seasonal variance.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import numpy as np
import pandas as pd


CATEGORIES = ["guides", "tutorials", "pricing", "comparisons", "blog", "docs", "product"]


def generate_mock_gsc_dataset(
    num_pages: int = 400,
    num_days: int = 60,
    end_date_str: str = "2026-06-30",
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate realistic multi-page daily Google Search Console performance data.

    Content Archetypes:
    - 25% 'declining': Rank drops from Page 1 to Page 2, impressions collapse >20%
    - 15% 'ctr_decay': Ranking stays stable, but CTR drops sharply (SERP feature crowding)
    - 25% 'steady_pillar': Consistently high ranking and stable healthy traffic
    - 15% 'rising_star': Fresh or updated content climbing up in SERPs
    - 20% 'volatile_longtail': Fluctuating rankings and lower traffic
    """
    np.random.seed(random_seed)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    dates = [(end_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(num_days))]

    records = []

    # Assign archetypes
    archetypes = np.random.choice(
        ["declining", "ctr_decay", "steady_pillar", "rising_star", "volatile_longtail"],
        size=num_pages,
        p=[0.25, 0.15, 0.25, 0.15, 0.20],
    )

    domain = "https://example-saas.com"

    for i in range(num_pages):
        archetype = archetypes[i]
        category = np.random.choice(CATEGORIES)
        page_slug = f"post-{i:03d}-{category}-optimization"
        page_url = f"{domain}/{category}/{page_slug}"

        # Base parameters per archetype
        if archetype == "steady_pillar":
            base_imp = np.random.uniform(800, 2500)
            base_pos = np.random.uniform(1.5, 4.0)
            base_ctr = np.random.uniform(0.06, 0.12)
        elif archetype == "declining":
            base_imp = np.random.uniform(600, 2000)
            base_pos = np.random.uniform(3.0, 6.0)
            base_ctr = np.random.uniform(0.04, 0.08)
        elif archetype == "ctr_decay":
            base_imp = np.random.uniform(500, 1800)
            base_pos = np.random.uniform(2.5, 5.5)
            base_ctr = np.random.uniform(0.05, 0.09)
        elif archetype == "rising_star":
            base_imp = np.random.uniform(150, 600)
            base_pos = np.random.uniform(12.0, 22.0)
            base_ctr = np.random.uniform(0.02, 0.04)
        else:  # volatile_longtail
            base_imp = np.random.uniform(80, 400)
            base_pos = np.random.uniform(8.0, 25.0)
            base_ctr = np.random.uniform(0.01, 0.03)

        half_point = num_days // 2

        for day_idx, d in enumerate(dates):
            day_of_week = datetime.strptime(d, "%Y-%m-%d").weekday()
            weekend_penalty = 0.75 if day_of_week >= 5 else 1.0

            # Trend progression
            if archetype == "declining":
                if day_idx >= half_point:
                    # Deteriorate after mid-point
                    progress = (day_idx - half_point) / (num_days - half_point)
                    pos = base_pos + progress * np.random.uniform(8.0, 14.0)
                    imp = base_imp * (1.0 - progress * np.random.uniform(0.35, 0.65))
                    ctr = max(0.005, base_ctr * (1.0 - progress * 0.4))
                else:
                    pos = base_pos + np.random.normal(0, 0.5)
                    imp = base_imp * np.random.uniform(0.9, 1.1)
                    ctr = base_ctr * np.random.uniform(0.95, 1.05)

            elif archetype == "ctr_decay":
                pos = base_pos + np.random.normal(0, 0.4)
                if day_idx >= half_point:
                    progress = (day_idx - half_point) / (num_days - half_point)
                    ctr = max(0.008, base_ctr * (1.0 - progress * 0.55))
                    # Impressions might stay or drop slightly
                    imp = base_imp * (1.0 - progress * 0.15)
                else:
                    ctr = base_ctr * np.random.uniform(0.95, 1.05)
                    imp = base_imp * np.random.uniform(0.9, 1.1)

            elif archetype == "rising_star":
                progress = day_idx / num_days
                pos = max(1.2, base_pos - progress * np.random.uniform(6.0, 12.0))
                imp = base_imp * (1.0 + progress * np.random.uniform(1.5, 3.0))
                ctr = min(0.15, base_ctr * (1.0 + progress * 0.8))

            elif archetype == "steady_pillar":
                pos = max(1.0, base_pos + np.random.normal(0, 0.3))
                imp = base_imp * np.random.uniform(0.92, 1.08)
                ctr = base_ctr * np.random.uniform(0.95, 1.05)

            else:  # volatile_longtail
                pos = max(1.0, base_pos + np.random.normal(0, 3.5))
                imp = max(10, base_imp * np.random.uniform(0.6, 1.4))
                ctr = max(0.005, base_ctr * np.random.uniform(0.7, 1.3))

            # Apply weekend penalty and random noise
            imp_val = int(max(0, round(imp * weekend_penalty + np.random.normal(0, imp * 0.05))))
            ctr_val = float(np.clip(ctr + np.random.normal(0, 0.003), 0.001, 0.40))
            clk_val = int(round(imp_val * ctr_val))
            pos_val = float(np.clip(pos, 1.0, 100.0))

            records.append({
                "report_date": d,
                "page_url": page_url,
                "impressions": imp_val,
                "clicks": clk_val,
                "ctr": ctr_val,
                "avg_position": pos_val,
            })

    df = pd.DataFrame(records)
    return df

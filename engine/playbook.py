"""
Editorial Remediation Playbook for Search Discoverability.
Provides concrete, prioritized action items and validation checklists
for editors to prevent traffic decay.
"""

from __future__ import annotations
from typing import TypedDict


class ActionPlaybook(TypedDict):
    primary_action: str
    checklist: list[str]
    time_estimate: str
    what_would_make_it_wrong: str


PLAYBOOK_CATALOG: dict[str, ActionPlaybook] = {
    "POSITION_EROSION_DANGER": {
        "primary_action": "Comprehensive Content & Search Intent Refresh",
        "checklist": [
            "Audit current Page 1 SERP competitors to identify recent content gaps or new subtopics.",
            "Update outdated dates, statistics, product screenshots, or obsolete guidance.",
            "Add a structured FAQ section answering fresh user queries from People Also Ask.",
            "Add 3-5 internal links from topically related, high-authority internal pages.",
        ],
        "time_estimate": "45–60 mins",
        "what_would_make_it_wrong": "Temporary ranking drop due to an ongoing Google core algorithm rollout or site-wide URL migration.",
    },
    "CTR_DECAY_SERP_CROWDING": {
        "primary_action": "Title Tag & Meta Snippet Optimization",
        "checklist": [
            "Rewrite title tag to front-load high-intent keywords and include current year / benefit hooks.",
            "Test question-based or number-driven title formats to win clicks over AI Overviews.",
            "Implement Article/FAQ Schema markup to enhance SERP rich snippets.",
            "Review Google Search Console query report to spot queries where impressions exploded but CTR collapsed.",
        ],
        "time_estimate": "20–30 mins",
        "what_would_make_it_wrong": "Google introduced a prominent AI Overview or commercial widget displacing all organic blue links equally.",
    },
    "MOMENTUM_DECELERATION": {
        "primary_action": "Search Volume & Distribution Audit",
        "checklist": [
            "Check Google Trends for core target keywords to confirm whether demand is seasonally falling.",
            "Check if an internal newer article has inadvertently cannibalized this URL's target keywords.",
            "Repromote content across social channels, newsletters, or partner hubs to rebuild external signals.",
            "Strengthen anchor text of inbound internal links pointing to this page.",
        ],
        "time_estimate": "30 mins",
        "what_would_make_it_wrong": "Expected seasonal dip (e.g. holiday or industry-wide seasonal fluctuation).",
    },
    "HIGH_VOLATILITY_TURBULENCE": {
        "primary_action": "Technical SEO & Canonical Audit",
        "checklist": [
            "Inspect URL in GSC URL Inspection Tool for canonicalization errors or indexing discrepancies.",
            "Verify that mobile usability, Core Web Vitals (INP, LCP), and server response times (TTFB) are green.",
            "Ensure content doesn't contain mixed signals or conflicting H1/title tags.",
            "Allow 7 days before major content overhaul to confirm ranking stability.",
        ],
        "time_estimate": "25 mins",
        "what_would_make_it_wrong": "Google actively testing multiple URLs from your domain for the same query.",
    },
    "STALE_HIGH_IMPACT_PILLAR": {
        "primary_action": "Priority Flagship Deep Refresh",
        "checklist": [
            "Conduct full editorial audit: rewrite introduction to improve immediate reader hook and dwell time.",
            "Add proprietary data, custom charts, infographics, or expert commentary to defeat AI summaries.",
            "Ensure top-of-page table of contents and jump links are functional.",
            "Set editorial update date in meta headers and submit URL for immediate re-indexing in GSC.",
        ],
        "time_estimate": "90 mins",
        "what_would_make_it_wrong": "Short-term tracking gap or temporary bot traffic filtering in Google Search Console.",
    },
    "HEALTHY_MOMENTUM": {
        "primary_action": "Maintain & Monitor",
        "checklist": [
            "Page is performing strongly; preserve existing title and URL structure.",
            "Consider using this page as an internal link source to boost slipping pages.",
        ],
        "time_estimate": "5 mins",
        "what_would_make_it_wrong": "Sudden emerging competitor surge in the current week.",
    },
}


def get_playbook_for_reason(reason_code: str) -> ActionPlaybook:
    """Retrieve editorial action playbook for a specific reason code."""
    return PLAYBOOK_CATALOG.get(reason_code, PLAYBOOK_CATALOG["POSITION_EROSION_DANGER"])

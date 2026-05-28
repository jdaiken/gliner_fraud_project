"""
Regulatory references with official source hyperlinks.
"""

REGULATORY_REFERENCES = [
    {
        "id": "bsa",
        "title": "Bank Secrecy Act (BSA)",
        "product_line": "Enterprise-wide AML program for banks that place or receive network deposits",
        "summary": (
            "Requires financial institutions to maintain AML programs, monitor transactions, "
            "and file reports that document suspicious activity connected to deposit flows."
        ),
        "links": [
            {"label": "FinCEN BSA overview", "url": "https://www.fincen.gov/resources/statutes-and-regulations/bank-secrecy-act"},
            {"label": "31 U.S.C. § 5311", "url": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title31-chapter53-subchapterII&num=0&edition=prelim"},
            {"label": "31 CFR Chapter X (eCFR)", "url": "https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X"},
        ],
    },
    {
        "id": "sar",
        "title": "Suspicious Activity Reports (SAR)",
        "product_line": "SAR-ready narratives and entity extraction for HIGH-tier cases",
        "summary": (
            "Mandates filing when transactions aggregate to suspicious patterns, including "
            "unusual outflows, rapid balance movement, or high-risk geography."
        ),
        "links": [
            {"label": "31 CFR § 1020.320 (eCFR)", "url": "https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1020/subpart-B/section-1020.320"},
            {"label": "FinCEN SAR statutes", "url": "https://www.fincen.gov/resources/statutes-regulations/suspicious-activity-reports"},
        ],
    },
    {
        "id": "fdic-pass",
        "title": "FDIC pass-through deposit insurance",
        "product_line": "Reciprocal and ICS-style placement: insured capacity across network banks",
        "summary": (
            "Pass-through insurance applies when placement records, titling, and bank eligibility "
            "meet regulatory conditions. Monitoring supports evidence that funds remain traceable."
        ),
        "links": [
            {"label": "12 CFR § 330.15 (eCFR)", "url": "https://www.ecfr.gov/current/title-12/chapter-III/subchapter-B/part-330/subpart-A/section-330.15"},
            {"label": "FDIC deposit insurance", "url": "https://www.fdic.gov/resources/deposit-insurance/"},
        ],
    },
    {
        "id": "ffiec",
        "title": "FFIEC BSA/AML examination expectations",
        "product_line": "Model validation, tiered review queues, and audit-ready workpapers",
        "summary": (
            "Examiners expect risk-based monitoring, documented thresholds, and clear escalation "
            "from alerts to investigation to SAR decisioning."
        ),
        "links": [
            {"label": "FFIEC BSA/AML Examination Manual", "url": "https://bsaaml.ffiec.gov/manual"},
            {"label": "Transaction monitoring (manual index)", "url": "https://bsaaml.ffiec.gov/manual/Appendices/01"},
        ],
    },
    {
        "id": "reg-e",
        "title": "Regulation E (EFT protections)",
        "product_line": "Instant payment and transfer typologies in monitored populations",
        "summary": (
            "Where institutions offer electronic transfers, error resolution and unauthorized "
            "transfer rules apply. Unusual velocity or off-hours activity may overlap AML review."
        ),
        "links": [
            {"label": "12 CFR Part 1005 (eCFR)", "url": "https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-1005"},
            {"label": "CFPB Regulation E", "url": "https://www.consumerfinance.gov/rules-policy/regulations/1005/"},
        ],
    },
    {
        "id": "patriot",
        "title": "USA PATRIOT Act enhancements",
        "product_line": "Large-dollar relationships and high-risk jurisdiction exposure",
        "summary": (
            "Customer due diligence and enhanced monitoring for higher-risk relationships "
            "align with geographic and balance-drain signals in transaction data."
        ),
        "links": [
            {"label": "31 U.S.C. § 5318 (eCFR index)", "url": "https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010"},
            {"label": "FinCEN CDD rule resources", "url": "https://www.fincen.gov/resources/statutes-regulations/cdd-final-rule"},
        ],
    },
]

RISK_AREA_THEMES = [
    {
        "title": "Large-balance and placement concentration",
        "body": (
            "Reciprocal deposit and deposit-placement networks exist to keep large balances insured "
            "and distributed across member institutions. Unusual single-transaction size or rapid "
            "origin balance drains can signal mule activity, account takeover, or structuring ahead "
            "of movement off the network."
        ),
    },
    {
        "title": "Geographic and corridor risk",
        "body": (
            "Nationwide placement implies exposure to many jurisdictions. Concentration of HIGH-tier "
            "volume in specific countries should be reconciled to sanctions screening, high-risk country "
            "policies, and member bank policy lists."
        ),
    },
    {
        "title": "Liquidity sweeps and velocity",
        "body": (
            "Sweep and reciprocal structures move funds on short horizons. Late-night activity, "
            "repeat outflows from the same origin, and unusual velocity warrant "
            "timeline review alongside static risk scores."
        ),
    },
]

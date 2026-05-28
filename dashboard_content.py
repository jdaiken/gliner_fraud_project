"""
Analyst-facing explanations for dashboard metrics and pipeline outputs.
"""

from brand import RISK_ASSESSMENT_PAGE

TAB_INTROS = {
    "Brief": (
        "The executive brief is your starting point for management and interview walkthroughs. "
        "Scan tier mix, labeled fraud capture in the HIGH queue, and geographic pressure before drilling into detail. "
        "Use it to frame how much volume sits in priority tiers, not as a filing decision."
    ),
    "Overview": (
        "Overview shows how the full scored population splits across risk tiers and scores. "
        "Compare the pie chart to the histogram to see whether alerts cluster at tier cutoffs or spread across the scale. "
        "If labeled fraud exists, use the validation bar chart to judge whether HIGH tier concentrates known fraud."
    ),
    "Geography": (
        "Geography maps origin-country patterns for volume, counts, fraud rate, or HIGH-tier exposure. "
        "Look for jurisdictions that drive outsized dollars or fraud rate versus transaction count. "
        "Pair the map with the country table to name specific locations for enhanced due diligence."
    ),
    "Financial": (
        "Financial impact translates scores into dollars: total volume, fraud loss where labeled, HIGH-tier exposure, and origin outflow. "
        "Focus on HIGH exposure and tier or type bars to prioritize reviews that move the most money. "
        "Top account outflows highlight originators that may need limits, holds, or KYC refresh."
    ),
    "Transactions": (
        "Transactions is the operational review queue. "
        "Filter by tier, type, and minimum score to build a working set, then sort mentally by score and amount. "
        "Watch balance drained, late night, and high-risk country flags alongside score when deciding escalation."
    ),
    "SAR narratives": (
        "SAR narratives are synthetic investigation memos for HIGH-tier flags, shaped like FinCEN-style prose for demo and NLP extraction. "
        "Search filters the queue in real time. Use the z-score slider to tune the word tree and topic model, double-click words to add stop words, "
        "and set topic count manually or from the suggestion. Sample narratives below are fully expanded with highlighted risk language."
    ),
    "Risk register": (
        "The risk register shows GLiNER-extracted entities from narrative text: accounts, amounts, countries, and risk factors. "
        "Rows are colored by risk tier and risk score is heat-ranked so the highest-priority SARs surface first. "
        "Check reconciliation metrics to see how often extracted values match transaction fields."
    ),
    RISK_ASSESSMENT_PAGE: (
        "The risk assessment is the long-form narrative analysis with regulatory references and chart callouts. "
        "Scroll the full document for methodology, findings, and compliance mapping. "
        "Use the PDF control on this page when you need a portable copy for reviewers."
    ),
    "Exports": (
        "Exports packages deliverables for offline review: the Excel workpaper and risk assessment files. "
        "Regenerate the workpaper when pipeline outputs change so topic modeling and alerts stay current. "
        "Download HTML for interactive briefs or PDF for static distribution."
    ),
    "Data guide": (
        "The data guide documents how synthetic data flows through scoring, financial rollups, SAR generation, and NLP extraction. "
        "Use it when onboarding analysts or explaining demo limitations. "
        "Field definitions and tier rules here match columns in exports and the workpaper dictionary."
    ),
}

PIPELINE_STEPS = [
    (
        "1. Transaction data",
        "Raw mobile-money style transactions (synthetic PaySim or your own CSV). "
        "Each row is one transfer, payment, or cash movement with amount, accounts, country, and hour.",
    ),
    (
        "2. Anomaly scoring",
        "Isolation Forest finds statistically unusual patterns without using fraud labels. "
        "Every row gets a **risk score (0–100)** and tier: HIGH, MEDIUM, or LOW.",
    ),
    (
        "3. Financial impact",
        "Dollar volume, outflows, and labeled fraud loss are rolled up for portfolio and country views.",
    ),
    (
        "4. Exploratory analysis",
        "Diagnostic charts and summaries under `outputs/eda/` for portfolio shape and fraud patterns.",
    ),
    (
        "5. SAR narratives",
        "HIGH-tier cases receive FinCEN-style investigation memos for demo review and NLP.",
    ),
    (
        "6. SAR topic modeling",
        "TF-IDF + NMF themes across the narrative corpus; outputs feed the dashboard and Excel workpaper.",
    ),
    (
        "7. GLiNER extraction",
        "Entity extraction (or regex fallback offline) populates the structured risk register.",
    ),
    (
        "8. Analyst workpaper",
        "Excel workbook with methodology, scored data, SARs, topics, register, and financial rollups.",
    ),
]

FIELD_GLOSSARY = {
    "transaction_id": ("Transaction ID", "Unique identifier for each simulated payment."),
    "type": ("Transaction type", "PAYMENT, TRANSFER, CASH_OUT, DEBIT, or CASH_IN. Fraud in PaySim appears only in TRANSFER and CASH_OUT."),
    "amount": ("Amount ($)", "Value of the transaction in U.S. dollars."),
    "country": ("Country", "Origin jurisdiction (ISO-style code). Used for geographic risk and maps."),
    "hour": ("Hour of day", "0–23. Late night (0–4) is a common AML red flag."),
    "risk_score": ("Risk score", "0 = typical for this dataset; 100 = most unusual. Based on amount, balance change, type, time, and country flags."),
    "risk_tier": ("Risk tier", "Analyst triage bucket: HIGH (≥75), MEDIUM (≥45), LOW (<45)."),
    "anomaly_flag": ("Anomaly flag", "1 = top ~2% outliers flagged by Isolation Forest. Not the same as HIGH tier."),
    "balance_drained": ("Balance drained", "1 if the origin account went to zero after the transaction."),
    "is_late_night": ("Late night", "1 if transaction occurred between midnight and 4 AM."),
    "is_high_risk_country": ("High-risk country", "1 if country is NG, RU, UA, or KE in this demo."),
    "isFraud": ("Labeled fraud", "Research label for evaluation only — not used to train the model."),
    "sar_id": ("SAR reference", "Synthetic Suspicious Activity Report ID for HIGH-risk cases."),
    "fraud_loss": ("Fraud loss ($)", "Sum of amounts where labeled fraud = 1."),
    "high_risk_volume": ("HIGH-risk exposure ($)", "Total transaction dollars in the HIGH tier — prioritization metric, not confirmed loss."),
}

TIER_HELP = """
**HIGH (score ≥ 75)** — Review first. Unusual combination of amount, timing, geography, or balance behavior.  
**MEDIUM (score ≥ 45)** — Schedule review; may be borderline or emerging patterns.  
**LOW (score < 45)** — Within normal range for this population; monitor per policy.
"""

MAP_HELP = """
Maps use **transaction origin country** from the dataset. Color intensity shows volume, fraud rate, or HIGH-risk exposure.  
Countries outside the simulation appear blank. This is illustrative — production maps would use verified geolocation and policy lists.
"""

DISCLAIMER = """
**Demo data notice:** This dashboard uses synthetic PaySim-style data for portfolio demonstration. 
Metrics illustrate workflow only — not live network or regulatory reporting. 
Confirm all decisions against your institution’s policies and verified sources.
"""

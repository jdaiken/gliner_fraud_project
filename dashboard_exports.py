"""
Dashboard exports: Excel workpaper and risk assessment (HTML + PDF).
"""

from __future__ import annotations

from datetime import datetime

import config


def workpaper_filename() -> str:
    return f"risk_analysis_workpaper_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"


def export_workpaper_bytes(regenerate: bool = True) -> tuple[bytes, str]:
    path = config.WORKPAPER_XLSX
    if regenerate or not path.exists():
        try:
            from build_workpaper import build_workpaper
        except ImportError as e:
            raise ImportError(
                "Excel workpaper requires openpyxl. In your active Python env run: pip install openpyxl"
            ) from e
        try:
            build_workpaper(path)
        except PermissionError:
            raise
        except OSError as e:
            raise OSError(
                f"Could not save workpaper to {path}. Close Excel if the file is open, then try again."
            ) from e
    if not path.exists():
        raise FileNotFoundError(f"Workpaper not found at {path}")
    return path.read_bytes(), workpaper_filename()


def export_risk_assessment_html(
    scored,
    profit_summary=None,
) -> tuple[bytes, str]:
    from risk_assessment import build_risk_assessment_html, risk_assessment_filenames

    html_name, _ = risk_assessment_filenames()
    html = build_risk_assessment_html(scored, profit_summary)
    return html.encode("utf-8"), html_name


def export_risk_assessment_pdf(
    scored,
    profit_summary=None,
) -> tuple[bytes, str]:
    from risk_assessment import build_risk_assessment_pdf, risk_assessment_filenames

    _, pdf_name = risk_assessment_filenames()
    return build_risk_assessment_pdf(scored, profit_summary), pdf_name

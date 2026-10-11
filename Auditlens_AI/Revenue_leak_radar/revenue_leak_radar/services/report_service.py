from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class ReportService:
    @staticmethod
    def export_csv(findings: List[Dict[str, Any]], filename: str = "revenue_leak_findings.csv") -> str:
        data = pd.DataFrame(findings)
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, filename)
        data.to_csv(path, index=False)
        return path

    @staticmethod
    def export_excel(findings: List[Dict[str, Any]], filename: str = "revenue_leak_findings.xlsx") -> str:
        data = pd.DataFrame(findings)
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, filename)
        data.to_excel(path, index=False)
        return path

    @staticmethod
    def export_pdf(findings: List[Dict[str, Any]], filename: str = "revenue_leak_findings.pdf") -> str:
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, filename)
        doc = SimpleDocTemplate(path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph("Revenue Leak Radar Findings", styles["Title"]))
        story.append(Spacer(1, 12))
        rows = [["transaction_id", "risk_score", "risk_level", "status"]]
        for item in findings:
            rows.append([item.get("transaction_id", ""), item.get("risk_score", ""), item.get("risk_level", ""), item.get("status", "")])
        table = Table(rows)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        doc.build(story)
        return path

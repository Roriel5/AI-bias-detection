import io
from datetime import datetime


def generate_report(metrics: dict, explanation: dict, sensitive_cols: list) -> bytes:
    """
    Generate a downloadable PDF bias report card.
    Uses reportlab if available, falls back to plain-text PDF via fpdf2.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.units import cm

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=2*cm, bottomMargin=2*cm,
                                leftMargin=2*cm, rightMargin=2*cm)
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle("title", parent=styles["Title"],
                                     fontSize=22, textColor=colors.HexColor("#1a1a2e"), spaceAfter=6)
        h2_style = ParagraphStyle("h2", parent=styles["Heading2"],
                                  fontSize=14, textColor=colors.HexColor("#534AB7"), spaceBefore=14, spaceAfter=4)
        body_style = ParagraphStyle("body", parent=styles["Normal"],
                                    fontSize=11, leading=16, spaceAfter=8)
        label_style = ParagraphStyle("label", parent=styles["Normal"],
                                     fontSize=10, textColor=colors.HexColor("#666666"))

        story = []

        # ── Header ────────────────────────────────────────────────────────
        story.append(Paragraph("Bias Autopsy Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", label_style))
        story.append(Paragraph(f"Sensitive attributes analysed: {', '.join(sensitive_cols)}", label_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#534AB7"), spaceAfter=12))

        # ── Severity score ────────────────────────────────────────────────
        score = explanation.get("severity_score", 0)
        score_color = "#E24B4A" if score >= 7 else ("#EF9F27" if score >= 4 else "#1D9E75")
        story.append(Paragraph(f'Overall Bias Severity: <font color="{score_color}"><b>{score}/10</b></font>', body_style))
        story.append(Spacer(1, 0.3*cm))

        # ── Impact ────────────────────────────────────────────────────────
        story.append(Paragraph("Real-World Impact", h2_style))
        story.append(Paragraph(explanation.get("impact", "N/A"), body_style))

        # ── Root cause ────────────────────────────────────────────────────
        story.append(Paragraph("Root Cause Analysis", h2_style))
        story.append(Paragraph(explanation.get("root_cause", "N/A"), body_style))

        # ── Metrics table ─────────────────────────────────────────────────
        story.append(Paragraph("Fairness Metrics", h2_style))

        table_data = [["Attribute", "Dem. Parity Diff", "Eq. Odds Diff", "Disparate Impact", "Verdict"]]
        for attr, data in metrics.items():
            if "error" in data:
                continue
            dp = data["demographic_parity_difference"]
            eo = data["equalized_odds_difference"]
            di = data["disparate_impact_ratio"]
            verdict = "HIGH BIAS" if abs(dp) > 0.15 else ("MODERATE" if abs(dp) > 0.05 else "LOW BIAS")
            table_data.append([attr, f"{dp:.3f}", f"{eo:.3f}", f"{di:.3f}", verdict])

        table = Table(table_data, colWidths=[4*cm, 3.5*cm, 3.5*cm, 3.5*cm, 3*cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#534AB7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F8FF")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8F8FF"), colors.white]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5*cm))

        # ── Fix recommendations ───────────────────────────────────────────
        story.append(Paragraph("Recommended Fixes", h2_style))
        effort_colors = {"low": "#1D9E75", "medium": "#EF9F27", "high": "#E24B4A"}
        for i, fix in enumerate(explanation.get("fixes", []), 1):
            effort = fix.get("effort", "unknown")
            color = effort_colors.get(effort.lower(), "#888888")
            desc = fix.get("description", str(fix))
            impact = fix.get("impact", "")
            story.append(Paragraph(
                f'<b>Fix {i}</b> <font color="{color}">[{effort.upper()} EFFORT]</font>: {desc}',
                body_style
            ))
            if impact:
                story.append(Paragraph(f"Expected outcome: {impact}", label_style))
            story.append(Spacer(1, 0.2*cm))

        # ── Footer ────────────────────────────────────────────────────────
        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Paragraph("Generated by Bias Autopsy — Solution Challenge 2026", label_style))

        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        # Fallback: minimal text-based PDF using fpdf2
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 20)
            pdf.cell(0, 12, "Bias Autopsy Report", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%B %d, %Y')}", ln=True)
            pdf.ln(6)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 10, "Impact", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, explanation.get("impact", "N/A"))
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 10, "Root Cause", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, explanation.get("root_cause", "N/A"))
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 10, "Recommended Fixes", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for i, fix in enumerate(explanation.get("fixes", []), 1):
                desc = fix.get("description", str(fix)) if isinstance(fix, dict) else str(fix)
                pdf.multi_cell(0, 6, f"Fix {i}: {desc}")
                pdf.ln(2)
            return pdf.output()
        except ImportError:
            # Last resort: return a simple text file as bytes
            content = f"""BIAS AUTOPSY REPORT
Generated: {datetime.now().strftime('%B %d, %Y')}

IMPACT
{explanation.get('impact', 'N/A')}

ROOT CAUSE
{explanation.get('root_cause', 'N/A')}

FIXES
"""
            for i, fix in enumerate(explanation.get("fixes", []), 1):
                desc = fix.get("description", str(fix)) if isinstance(fix, dict) else str(fix)
                content += f"Fix {i}: {desc}\n"
            return content.encode("utf-8")

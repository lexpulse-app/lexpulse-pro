import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

font_regular = "Helvetica"
font_bold = "Helvetica-Bold"

# Suport diacritice românești atât pe Linux (Streamlit Cloud), cât și pe macOS
font_candidates = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]

for reg_path, bold_path in font_candidates:
    if os.path.exists(reg_path) and os.path.exists(bold_path):
        try:
            pdfmetrics.registerFont(TTFont("ErrataSans", reg_path))
            pdfmetrics.registerFont(TTFont("ErrataSans-Bold", bold_path))
            font_regular = "ErrataSans"
            font_bold = "ErrataSans-Bold"
            break
        except Exception:
            pass


def curata_text(val):
    if not val or str(val).strip().lower() in ("none", "null"):
        return "-"
    return str(val).strip()


def genereaza_raport_dosar_pdf(firma_nume, numar_dosar, client_nume, institutie, stadiu, solutie_sumar, analiza):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    style_brand = ParagraphStyle(
        'Brand',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#E2C792")
    )
    style_titlu = ParagraphStyle(
        'Titlu',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#FFFFFF")
    )
    style_subtitlu = ParagraphStyle(
        'Subtitlu',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#94A3B8")
    )
    style_label = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A")
    )
    style_valoare = ParagraphStyle(
        'Valoare',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )
    style_sectiune = ParagraphStyle(
        'Sectiune',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0F172A")
    )
    style_footer = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B")
    )

    story = []

    # Antet executiv Errata (Bleumarin + Auriu)
    antet_data = [[
        Paragraph("ERRATA • ASISTENT JURIDIC", style_brand),
        Paragraph(f"Generat la {datetime.now().strftime('%d.%m.%Y %H:%M')}", style_subtitlu)
    ], [
        Paragraph(f"FIȘĂ JURIDICĂ — DOSAR {curata_text(numar_dosar)}", style_titlu),
        ""
    ], [
        Paragraph(f"Cabinet: {curata_text(firma_nume)}", style_subtitlu),
        ""
    ]]
    t_antet = Table(antet_data, colWidths=[370, 145])
    t_antet.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 14),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('LINEBELOW', (0, -1), (-1, -1), 2.5, colors.HexColor("#C5A059")),
    ]))
    story.append(t_antet)
    story.append(Spacer(1, 16))

    # Tabel date dosar
    date_tabel = [
        [Paragraph("Număr Dosar:", style_label), Paragraph(curata_text(numar_dosar), style_valoare)],
        [Paragraph("Client Reprezentat:", style_label), Paragraph(curata_text(client_nume), style_valoare)],
        [Paragraph("Instanță:", style_label), Paragraph(curata_text(institutie), style_valoare)],
        [Paragraph("Stadiu Procesual:", style_label), Paragraph(curata_text(stadiu), style_valoare)],
        [Paragraph("Tip Soluție:", style_label), Paragraph(curata_text(analiza.get("tip_solutie")), style_valoare)],
        [Paragraph("Următorul Termen:", style_label), Paragraph(curata_text(analiza.get("noul_termen")), style_valoare)],
    ]

    t = Table(date_tabel, colWidths=[130, 385])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#FFFFFF")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # Minută instanță
    story.append(Paragraph("Minuta Pronunțată pe Portal Just:", style_sectiune))
    story.append(Spacer(1, 6))
    text_minuta = curata_text(solutie_sumar)
    t_minuta = Table([[Paragraph(text_minuta, style_valoare)]], colWidths=[515])
    t_minuta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_minuta)
    story.append(Spacer(1, 16))

    # Sarcini procedurale
    story.append(Paragraph("Evaluare Procedurală & Sarcini Cabinet:", style_sectiune))
    story.append(Spacer(1, 6))
    sarcini = curata_text(analiza.get("sarcini_avocat")).replace("\n", "<br/>")
    t_sarcini = Table([[Paragraph(sarcini, style_valoare)]], colWidths=[515])
    t_sarcini.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FAF8F5")),
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#C5A059")),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_sarcini)
    story.append(Spacer(1, 16))

    # Comunicare client
    story.append(Paragraph("Notă Informativă pentru Client:", style_sectiune))
    story.append(Spacer(1, 6))
    msg_client = curata_text(analiza.get("mesaj_client")).replace("\n", "<br/>")
    t_msg = Table([[Paragraph(msg_client, style_valoare)]], colWidths=[515])
    t_msg.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#0F172A")),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_msg)
    story.append(Spacer(1, 20))

    story.append(Paragraph("Document generat prin platforma Errata (errata.ro) — Securitate. Integritate. Rapiditate.", style_footer))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Înregistrare font cu diacritice pe macOS
font_regular = "Helvetica"
font_bold = "Helvetica-Bold"

cale_font_mac = "/System/Library/Fonts/Helvetica.ttc"
if os.path.exists(cale_font_mac):
    try:
        pdfmetrics.registerFont(TTFont("CustomHelvetica", cale_font_mac, subfontIndex=0))
        pdfmetrics.registerFont(TTFont("CustomHelvetica-Bold", cale_font_mac, subfontIndex=1))
        font_regular = "CustomHelvetica"
        font_bold = "CustomHelvetica-Bold"
    except Exception:
        pass

def curata_text(val):
    if not val or str(val).strip().lower() == "none" or str(val).strip().lower() == "null":
        return "-"
    return str(val).strip()

def genereaza_raport_dosar_pdf(firma_nume, numar_dosar, client_nume, institutie, stadiu, solutie_sumar, analiza):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    style_titlu = ParagraphStyle(
        'Titlu',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1A2B4C")
    )
    style_firma = ParagraphStyle(
        'Firma',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#4B5563")
    )
    style_label = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#374151")
    )
    style_valoare = ParagraphStyle(
        'Valoare',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937")
    )
    style_sectiune = ParagraphStyle(
        'Sectiune',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1A2B4C")
    )

    story = []
    
    # Antet
    story.append(Paragraph(curata_text(firma_nume).upper(), style_firma))
    story.append(Spacer(1, 4))
    story.append(Paragraph("FIȘĂ JURIDICĂ & RAPORT SOLUȚIE", style_titlu))
    story.append(Spacer(1, 14))
    
    # Tabel date dosar
    date_tabel = [
        [Paragraph("Număr Dosar:", style_label), Paragraph(curata_text(numar_dosar), style_valoare)],
        [Paragraph("Client:", style_label), Paragraph(curata_text(client_nume), style_valoare)],
        [Paragraph("Instanță:", style_label), Paragraph(curata_text(institutie), style_valoare)],
        [Paragraph("Stadiu Procesual:", style_label), Paragraph(curata_text(stadiu), style_valoare)],
        [Paragraph("Tip Soluție:", style_label), Paragraph(curata_text(analiza.get("tip_solutie")), style_valoare)],
        [Paragraph("Următorul Termen:", style_label), Paragraph(curata_text(analiza.get("noul_termen")), style_valoare)],
    ]
    
    t = Table(date_tabel, colWidths=[120, 390])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F9FAFB")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E5E7EB")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))
    
    # Minută instanță
    story.append(Paragraph("Minuta Pronunțată:", style_sectiune))
    story.append(Spacer(1, 5))
    text_minuta = curata_text(solutie_sumar)
    t_minuta = Table([[Paragraph(text_minuta, style_valoare)]], colWidths=[510])
    t_minuta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F3F4F6")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_minuta)
    story.append(Spacer(1, 14))
    
    # Sarcini procedurale
    story.append(Paragraph("Aprecieri Procedurale & Sarcini:", style_sectiune))
    story.append(Spacer(1, 5))
    sarcini = curata_text(analiza.get("sarcini_avocat")).replace("\n", "<br/>")
    story.append(Paragraph(sarcini, style_valoare))
    story.append(Spacer(1, 14))

    # Comunicare client
    story.append(Paragraph("Notă Informativă pentru Client:", style_sectiune))
    story.append(Spacer(1, 5))
    msg_client = curata_text(analiza.get("mesaj_client")).replace("\n", "<br/>")
    t_msg = Table([[Paragraph(msg_client, style_valoare)]], colWidths=[510])
    t_msg.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#BFDBFE")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_msg)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
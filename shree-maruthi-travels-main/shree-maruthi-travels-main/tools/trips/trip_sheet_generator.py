import os
import re

import pandas as pd
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader


COLUMN_ALIASES = {
    'END LOACTION': 'END LOCATION',
    'END LOCATIONS': 'END LOCATION',
    'PLANNED START': 'PLAND START',
    'MOBILE NO': 'MOBIL NO',
    'MOBILE': 'MOBIL NO',
    'EMPLOYEE NAME': 'EMP NAME',
    'DRIVER NAME': 'NAME',
}


def _norm_header(value):
    return re.sub(r'\s+', ' ', str(value or '').strip().upper())


def _prepare_frame(excel_file_path):
    df = pd.read_excel(excel_file_path)
    df.columns = [_norm_header(column) for column in df.columns]
    df = df.rename(columns=COLUMN_ALIASES)
    if 'SL NO' not in df.columns:
        raise ValueError(
            'Excel is missing a SL NO column. Use the same trip-sheet Excel headers as usual.'
        )
    df = df[df['SL NO'].astype(str).str.isnumeric()]
    return df.reset_index(drop=True)


def cell(row, *names):
    for name in names:
        if name in row.index:
            value = row[name]
            if not pd.isna(value):
                return value
    return ''


# -------------------------------------------------
# SAFE NUMBER HANDLER
# -------------------------------------------------
def safe_number(value):
    try:
        if pd.isna(value):
            return 0
        return float(str(value).strip())
    except:
        return 0


# -------------------------------------------------
# MAIN PDF GENERATION FUNCTION
# -------------------------------------------------
def generate_trip_sheets(excel_file_path, output_pdf_path, watermark_image_path):

    df = _prepare_frame(excel_file_path)

    # ---------- WATERMARK ----------
    def draw_watermark(canvas, doc):
        if not os.path.exists(watermark_image_path):
            return

        canvas.saveState()
        canvas.setFillAlpha(0.07)

        img = ImageReader(watermark_image_path)
        w, h = A4

        img_w = 120 * mm
        img_h = 120 * mm

        canvas.drawImage(
            img,
            (w - img_w) / 2,
            (h - img_h) / 2,
            img_w,
            img_h,
            mask="auto"
        )

        canvas.restoreState()

    # ---------- DOCUMENT ----------
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="CompanyTitle",
        fontSize=16,
        alignment=1,
        fontName="Helvetica-Bold"
    ))

    styles.add(ParagraphStyle(
        name="CenterSmall",
        fontSize=9,
        alignment=1
    ))

    styles.add(ParagraphStyle(
        name="Label",
        fontSize=9,
        fontName="Helvetica-Bold"
    ))

    styles.add(ParagraphStyle(
        name="Value",
        fontSize=9
    ))

    styles.add(ParagraphStyle(
        name="SignatureRight",
        fontSize=9,
        fontName="Helvetica-Bold",
        alignment=2
    ))

    def P(text, style="Value"):
        return Paragraph("" if pd.isna(text) else str(text), styles[style])

    story = []

    # ---------- LOOP EACH RECORD ----------
    for _, r in df.iterrows():

        parking = safe_number(cell(r, "PARKING"))
        toll = safe_number(cell(r, "TOLL"))
        parking_toll = parking + toll

        table_data = [
            [P("SHREE MARUTHI TRAVELS", "CompanyTitle"), "", "", "", ""],
            [P(
                "No.374C, 1st Floor, 4th Cross, 9th Main, 1st Stage, "
                "Gubbalala, Jayanagar Housing Society Layout, Bangalore - 560061",
                "CenterSmall"
            ), "", "", "", ""],
            [P("Mob. No.: +91 96326 53666", "CenterSmall"), "", "", "", ""],

            [P("Trip Sheet No:", "Label"), P(cell(r, "SL NO")),
             P("TRIP SHEET", "Label"), P("Date:", "Label"), P(cell(r, "DATE"))],

            [P("Guest Name:", "Label"), P(cell(r, "EMP NAME")), "", "", ""],

            [P("Cab Booked:", "Label"), P(cell(r, "CAB TYPE")),
             P("Car No:", "Label"), P(cell(r, "CAB REG NO")), ""],

            [P("Driver Name:", "Label"), P(cell(r, "NAME")),
             P("Driver Mob:", "Label"), P(cell(r, "MOBIL NO")), ""],

            [P("Reporting Time:", "Label"), P(cell(r, "PICKUP TIME")),
             P("Duty Type:", "Label"), P(cell(r, "DUTY TYPE")), ""],

            [P("Start Location:", "Label"), P(cell(r, "PLAND START")),
             P("End Location:", "Label"), P(cell(r, "END LOCATION")), ""],

            [P("Start Time:", "Label"), P(cell(r, "PICKUP TIME")),
             P("End Time:", "Label"), P(cell(r, "END TIME")),
             P(cell(r, "TOTAL HRS SMT"))],

            [P("Start Km:", "Label"), P(cell(r, "START KM")),
             P("End Km:", "Label"), P(cell(r, "END KM")),
             P(cell(r, "SMT TOTAL KM"))],

            [P("Parking / Toll:", "Label"), P(parking_toll),
             P("Service City:", "Label"), P("Bengaluru"), ""],
        ]

        col_widths = [32*mm, 38*mm, 28*mm, 42*mm, 30*mm]
        table = Table(table_data, colWidths=col_widths)

        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, colors.black),

            ("SPAN", (0, 0), (-1, 0)),
            ("SPAN", (0, 1), (-1, 1)),
            ("SPAN", (0, 2), (-1, 2)),

            ("SPAN", (2, 3), (2, 3)),
            ("SPAN", (1, 4), (-1, 4)),
            ("SPAN", (3, 5), (-1, 5)),
            ("SPAN", (3, 6), (-1, 6)),
            ("SPAN", (3, 7), (-1, 7)),
            ("SPAN", (3, 8), (-1, 8)),
            ("SPAN", (3, 11), (-1, 11)),

            ("ALIGN", (0, 0), (-1, 2), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))

        story.append(table)

        # ---------- SIGNATURE ----------
        story.append(Spacer(1, 6 * mm))
        signature_table = Table(
            [[Paragraph("Signature", styles["SignatureRight"])]],
            colWidths=[170 * mm]
        )
        signature_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT")
        ]))

        story.append(signature_table)
        story.append(PageBreak())

    # ---------- BUILD ----------
    doc.build(
        story,
        onFirstPage=draw_watermark,
        onLaterPages=draw_watermark
    )

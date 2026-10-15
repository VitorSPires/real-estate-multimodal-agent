"""Two-page broker brochure as a PDF with a real (native) text layer, built with reportlab."""

from io import BytesIO
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from dataset.spec import AMENITY_NAMES, Listing

rl_config.invariant = 1  # no timestamps/random IDs: same input -> byte-identical PDF

_styles = getSampleStyleSheet()
TITLE = ParagraphStyle("title", parent=_styles["Title"], alignment=0, fontSize=22, spaceAfter=4)
SUBTITLE = ParagraphStyle("subtitle", parent=_styles["Normal"], fontSize=11, textColor=colors.grey)
PRICE = ParagraphStyle("price", parent=_styles["Heading2"], textColor=colors.HexColor("#1f5f99"))
CAPTION = ParagraphStyle("caption", parent=_styles["Italic"], fontSize=8.5, textColor=colors.grey)
BODY = _styles["BodyText"]
HEADING = _styles["Heading3"]


def render_brochure(listing: Listing, hero_photo: BytesIO, price_chart: BytesIO | None, path: Path) -> None:
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, title=listing.title,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    story = [
        Paragraph(listing.title, TITLE),
        Paragraph(f"{listing.neighborhood} · Floor {listing.floor}", SUBTITLE),
        Spacer(1, 8),
        Paragraph(f"USD {listing.price_usd:,}", PRICE),
        Image(hero_photo, width=17 * cm, height=9.6 * cm),
        Paragraph(listing.photo_caption, CAPTION),
        Spacer(1, 12),
        Paragraph("Key facts", HEADING),
        _facts_table(listing),
        PageBreak(),
        Paragraph("About this home", HEADING),
        Paragraph(listing.description, BODY),
        Spacer(1, 8),
        Paragraph("Building amenities", HEADING),
        *[Paragraph(f"• {AMENITY_NAMES[a]}", BODY) for a in sorted(listing.brochure_amenities)],
    ]
    if price_chart is not None:
        story += [
            Spacer(1, 12),
            Paragraph("The neighborhood", HEADING),
            Image(price_chart, width=15 * cm, height=8.2 * cm),
        ]
    story += [Spacer(1, 18), Paragraph("Information provided by the seller. Subject to change.", CAPTION)]
    doc.build(story)


def _facts_table(listing: Listing) -> Table:
    rows = [
        ["Private area", f"{listing.area_m2} m²"],
        ["Bedrooms", str(listing.bedrooms)],
        ["Suites", str(listing.suites)],
        ["Bathrooms", str(listing.bathrooms)],
        ["Parking", f"{listing.parking_spots} spot(s)" if listing.parking_spots else "None"],
    ]
    if listing.fees_in_brochure:
        rows += [
            ["Condo fee", f"USD {listing.condo_fee_usd:,} / month"],
            ["Property tax", f"USD {listing.property_tax_usd:,} / year"],
        ]
    if listing.stated_price_per_m2:
        rows.append(["Price per m²", f"USD {listing.stated_price_per_m2:,}"])

    table = Table(rows, colWidths=[5 * cm, 7 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table

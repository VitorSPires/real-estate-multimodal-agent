"""Turning uploaded files into *regions*: the units the models read.

A PDF with a text layer becomes one text region (all pages, read for free with PyMuPDF) plus one
image region per meaningful embedded picture. A scanned PDF or a photo becomes image regions only.
Page renders are saved so the UI can show where every fact came from.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf
from PIL import Image

PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

MIN_TEXT_CHARS = 50  # below this a PDF page is treated as scanned (no usable text layer)
MIN_IMAGE_SHARE = 0.05  # ignore embedded images smaller than 5% of the page (logos, icons)
PAGE_DPI = 110  # page renders for the evidence viewer
REGION_DPI = 150  # crops sent to vision models
MAX_IMAGE_SIDE = 2000  # larger uploads are downscaled before going to a model


@dataclass
class SourceDocument:
    name: str
    path: Path
    kind: Literal["pdf", "image"]
    has_text_layer: bool = False
    pages: int = 1


@dataclass
class Region:
    key: str  # unique per run, e.g. "harbor-view-1104-brochure.pdf#p2-img1"
    document: str
    kind: Literal["pdf_text", "image"]
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None  # normalized 0–1 on the page
    image_path: Path | None = None  # what a vision model reads
    evidence_image: Path | None = None  # what the UI shows (page render or the image itself)
    text: str | None = None  # page-marked text, for pdf_text regions


def classify(path: Path) -> SourceDocument:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return SourceDocument(path.name, path, "image")
    if suffix not in PDF_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.name}")
    with pymupdf.open(path) as pdf:
        text_chars = sum(len(page.get_text().strip()) for page in pdf)
        return SourceDocument(
            path.name, path, "pdf", has_text_layer=text_chars >= MIN_TEXT_CHARS * pdf.page_count, pages=pdf.page_count
        )


def parse_pdf(document: SourceDocument, work_dir: Path) -> list[Region]:
    regions: list[Region] = []
    page_texts: list[str] = []
    with pymupdf.open(document.path) as pdf:
        for number, page in enumerate(pdf, start=1):
            page_render = _render_page(page, work_dir / "pages" / f"{document.name}-p{number}.png")

            if not document.has_text_layer:  # scanned PDF: the whole page is an image
                regions.append(Region(
                    key=f"{document.name}#p{number}", document=document.name, kind="image",
                    page=number, image_path=page_render, evidence_image=page_render,
                ))
                continue

            page_texts.append(f"--- Page {number} ---\n{page.get_text().strip()}")
            regions += _embedded_images(document, page, number, page_render, work_dir)

    if page_texts:
        regions.insert(0, Region(
            key=f"{document.name}#text", document=document.name, kind="pdf_text",
            evidence_image=work_dir / "pages" / f"{document.name}-p1.png", text="\n\n".join(page_texts),
        ))
    return regions


def prepare_image(document: SourceDocument, work_dir: Path) -> Region:
    """Copy the image next to the run's files, downscaling very large photos."""
    target = work_dir / "images" / document.name
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(document.path) as image:
        if max(image.size) > MAX_IMAGE_SIDE:
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            image.save(target)
        else:
            shutil.copyfile(document.path, target)
    return Region(key=document.name, document=document.name, kind="image", image_path=target, evidence_image=target)


def locate_quote(pdf_path: Path, quote: str) -> tuple[int, tuple[float, float, float, float]] | None:
    """Find a quote in the PDF text layer → (page number, normalized bbox). None if not found."""
    if not quote:
        return None
    with pymupdf.open(pdf_path) as pdf:
        for number, page in enumerate(pdf, start=1):
            hits = page.search_for(quote)
            if hits:
                return number, _normalize(hits[0], page.rect)
    return None


def _embedded_images(document, page, number, page_render, work_dir) -> list[Region]:
    regions = []
    page_area = page.rect.width * page.rect.height
    for index, info in enumerate(page.get_image_info(), start=1):
        rect = pymupdf.Rect(info["bbox"])
        if rect.width * rect.height < MIN_IMAGE_SHARE * page_area:
            continue
        crop = work_dir / "regions" / f"{document.name}-p{number}-img{index}.png"
        crop.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=REGION_DPI, clip=rect).save(crop)
        regions.append(Region(
            key=f"{document.name}#p{number}-img{index}", document=document.name, kind="image",
            page=number, bbox=_normalize(rect, page.rect), image_path=crop, evidence_image=page_render,
        ))
    return regions


def _render_page(page, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(dpi=PAGE_DPI).save(path)
    return path


def _normalize(rect, page_rect) -> tuple[float, float, float, float]:
    w, h = page_rect.width, page_rect.height
    return (round(rect.x0 / w, 4), round(rect.y0 / h, 4), round(rect.x1 / w, 4), round(rect.y1 / h, 4))

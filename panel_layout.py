"""
Comic Panel Layout Node
Arranges multiple images into comic-style page layouts with configurable
grid patterns, gutters, and borders.
"""

from enum import Enum
from typing import Optional

from PIL import Image, ImageDraw

from invokeai.invocation_api import (
    BaseInvocation,
    ImageField,
    ImageOutput,
    InputField,
    InvocationContext,
    invocation,
)


class LayoutPreset(str, Enum):
    GRID_2X2 = "2x2"
    GRID_2X3 = "2x3"
    GRID_3X3 = "3x3"
    VERTICAL_STACK = "vertical_stack"
    HORIZONTAL_STRIP = "horizontal_strip"
    MANGA_RIGHT = "manga_right"
    CUSTOM = "custom"


# Predefined layout grids.
# Each layout is a list of (row, col, row_span, col_span) tuples
# on a 6x6 sub-grid for flexibility.
LAYOUT_DEFINITIONS: dict[str, list[tuple[int, int, int, int]]] = {
    "2x2": [
        (0, 0, 3, 3),
        (0, 3, 3, 3),
        (3, 0, 3, 3),
        (3, 3, 3, 3),
    ],
    "2x3": [
        (0, 0, 3, 2),
        (0, 2, 3, 2),
        (0, 4, 3, 2),
        (3, 0, 3, 2),
        (3, 2, 3, 2),
        (3, 4, 3, 2),
    ],
    "3x3": [
        (0, 0, 2, 2), (0, 2, 2, 2), (0, 4, 2, 2),
        (2, 0, 2, 2), (2, 2, 2, 2), (2, 4, 2, 2),
        (4, 0, 2, 2), (4, 2, 2, 2), (4, 4, 2, 2),
    ],
    "vertical_stack": [
        (0, 0, 2, 6),
        (2, 0, 2, 6),
        (4, 0, 2, 6),
    ],
    "horizontal_strip": [
        (0, 0, 6, 2),
        (0, 2, 6, 2),
        (0, 4, 6, 2),
    ],
    "manga_right": [
        (0, 0, 3, 4),
        (0, 4, 3, 2),
        (3, 0, 3, 2),
        (3, 2, 3, 4),
    ],
}


def fit_image_to_cell(img: Image.Image, cell_w: int, cell_h: int) -> Image.Image:
    """Resize and center-crop an image to fill a cell exactly."""
    iw, ih = img.size
    scale = max(cell_w / iw, cell_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - cell_w) // 2
    top = (new_h - cell_h) // 2
    return resized.crop((left, top, left + cell_w, top + cell_h))


@invocation(
    "comic_panel_layout",
    title="Comic Panel Layout",
    tags=["comic", "layout", "grid", "panels", "page"],
    category="Comic Creator",
    version="1.0.0",
)
class ComicPanelLayoutInvocation(BaseInvocation):
    """Arranges a collection of panel images into a comic page layout.
    Supports preset grid patterns (2x2, 2x3, 3x3, vertical stack,
    horizontal strip, manga) and custom row definitions. Images are
    center-cropped to fill their assigned cells."""

    images: list[ImageField] = InputField(
        description="Collection of panel images to arrange on the page"
    )
    layout: LayoutPreset = InputField(
        default=LayoutPreset.GRID_2X2,
        description="Page layout pattern",
    )
    page_width: int = InputField(default=2480, ge=600, le=6000, description="Page width in pixels (2480 = A4 at 300dpi)")
    page_height: int = InputField(default=3508, ge=600, le=8000, description="Page height in pixels (3508 = A4 at 300dpi)")
    gutter: int = InputField(default=20, ge=0, le=100, description="Space between panels in pixels")
    border: int = InputField(default=40, ge=0, le=200, description="Page border/margin in pixels")
    bg_color: str = InputField(default="#FFFFFF", description="Page background color as hex")
    panel_border_width: int = InputField(default=3, ge=0, le=20, description="Black border around each panel (0 to disable)")
    custom_rows: str = InputField(
        default="",
        description="For CUSTOM layout only. Define rows as comma-separated panel counts per row. Example: '1,2,3' means row 1 has 1 panel, row 2 has 2, row 3 has 3.",
    )

    def invoke(self, context: InvocationContext) -> ImageOutput:
        # Parse background color
        bg = self._parse_hex(self.bg_color)

        # Create page canvas
        page = Image.new("RGB", (self.page_width, self.page_height), bg)

        if not self.images:
            image_dto = context.images.save(page)
            return ImageOutput.build(image_dto)

        # Load all panel images
        panels: list[Image.Image] = []
        for img_field in self.images:
            pil_img = context.images.get_pil(img_field.image_name).convert("RGB")
            panels.append(pil_img)

        # Determine cell positions
        if self.layout == LayoutPreset.CUSTOM and self.custom_rows.strip():
            cells = self._build_custom_cells()
        else:
            layout_key = self.layout.value
            if layout_key == "custom":
                layout_key = "2x2"
            cells = self._build_preset_cells(layout_key)

        # Usable area
        area_x = self.border
        area_y = self.border
        area_w = self.page_width - self.border * 2
        area_h = self.page_height - self.border * 2

        # Grid unit size (6x6 sub-grid)
        unit_w = area_w / 6
        unit_h = area_h / 6

        draw = ImageDraw.Draw(page) if self.panel_border_width > 0 else None

        for i, panel in enumerate(panels):
            if i >= len(cells):
                break

            row, col, row_span, col_span = cells[i]

            # Cell position and size with gutters
            cx = int(area_x + col * unit_w + self.gutter / 2)
            cy = int(area_y + row * unit_h + self.gutter / 2)
            cw = int(col_span * unit_w - self.gutter)
            ch = int(row_span * unit_h - self.gutter)

            if cw <= 0 or ch <= 0:
                continue

            fitted = fit_image_to_cell(panel, cw, ch)
            page.paste(fitted, (cx, cy))

            if draw and self.panel_border_width > 0:
                draw.rectangle(
                    [(cx, cy), (cx + cw - 1, cy + ch - 1)],
                    outline=(0, 0, 0),
                    width=self.panel_border_width,
                )

        image_dto = context.images.save(page)
        return ImageOutput.build(image_dto)

    def _build_preset_cells(self, key: str) -> list[tuple[int, int, int, int]]:
        return LAYOUT_DEFINITIONS.get(key, LAYOUT_DEFINITIONS["2x2"])

    def _build_custom_cells(self) -> list[tuple[int, int, int, int]]:
        """Parse custom_rows string like '1,2,3' into cell definitions."""
        try:
            row_counts = [int(x.strip()) for x in self.custom_rows.split(",") if x.strip()]
        except ValueError:
            return LAYOUT_DEFINITIONS["2x2"]

        if not row_counts:
            return LAYOUT_DEFINITIONS["2x2"]

        total_rows = len(row_counts)
        row_height = 6 / total_rows
        cells = []

        for r_idx, count in enumerate(row_counts):
            if count <= 0:
                continue
            col_width = 6 / count
            for c_idx in range(count):
                cells.append((
                    int(r_idx * row_height),
                    int(c_idx * col_width),
                    max(1, int(row_height)),
                    max(1, int(col_width)),
                ))

        return cells

    @staticmethod
    def _parse_hex(color: str) -> tuple[int, int, int]:
        color = color.lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))

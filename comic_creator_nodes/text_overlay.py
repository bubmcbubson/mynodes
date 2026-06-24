"""
Text Overlay Node
Adds captions, narration boxes, or speech text to comic panel images.
"""

from enum import Enum
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from invokeai.invocation_api import (
    BaseInvocation,
    ImageField,
    ImageOutput,
    InputField,
    InvocationContext,
    invocation,
)


class TextPosition(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"


class TextStyle(str, Enum):
    CAPTION = "caption"
    NARRATION = "narration"
    SPEECH = "speech"
    PLAIN = "plain"


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width and current_line:
            current_line = test_line
        elif line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def get_default_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a default font. Falls back to Pillow default if no system fonts found."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


@invocation(
    "comic_text_overlay",
    title="Comic Text Overlay",
    tags=["comic", "text", "overlay", "caption", "narration"],
    category="Comic Creator",
    version="1.0.0",
)
class TextOverlayInvocation(BaseInvocation):
    """Adds styled text overlays to comic panel images. Supports captions,
    narration boxes, speech text, and plain text with configurable position,
    size, color, and background styling."""

    image: ImageField = InputField(description="The panel image to overlay text on")
    text: str = InputField(default="", description="Text content to overlay on the image")
    position: TextPosition = InputField(
        default=TextPosition.BOTTOM,
        description="Where to place the text on the image",
    )
    style: TextStyle = InputField(
        default=TextStyle.CAPTION,
        description="Visual style: caption (white on dark bar), narration (yellow box), speech (white bubble), plain (raw text)",
    )
    font_size: int = InputField(default=28, ge=8, le=120, description="Font size in pixels")
    text_color: str = InputField(default="#FFFFFF", description="Text color as hex (e.g. #FFFFFF)")
    bg_color: str = InputField(default="#000000", description="Background box color as hex")
    bg_opacity: int = InputField(default=180, ge=0, le=255, description="Background opacity (0=transparent, 255=opaque)")
    padding: int = InputField(default=16, ge=0, le=100, description="Padding around text in pixels")
    margin: int = InputField(default=12, ge=0, le=100, description="Margin from image edges in pixels")
    custom_font_path: str = InputField(default="", description="Optional: absolute path to a .ttf font file")

    def invoke(self, context: InvocationContext) -> ImageOutput:
        # Load source image
        source = context.images.get_pil(self.image.image_name).convert("RGBA")
        img_w, img_h = source.size

        # Skip overlay if text is empty
        if not self.text.strip():
            image_dto = context.images.save(source.convert("RGB"))
            return ImageOutput.build(image_dto)

        # Load font
        if self.custom_font_path:
            try:
                font = ImageFont.truetype(self.custom_font_path, self.font_size)
            except (OSError, IOError):
                font = get_default_font(self.font_size)
        else:
            font = get_default_font(self.font_size)

        # Create overlay layer
        overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Apply style presets
        text_color = self._parse_hex(self.text_color)
        bg_color = self._parse_hex(self.bg_color)

        if self.style == TextStyle.CAPTION:
            text_color = self._parse_hex("#FFFFFF")
            bg_color = self._parse_hex("#000000")
            bg_opacity = 200
        elif self.style == TextStyle.NARRATION:
            text_color = self._parse_hex("#1A1A1A")
            bg_color = self._parse_hex("#FFF4B0")
            bg_opacity = 230
        elif self.style == TextStyle.SPEECH:
            text_color = self._parse_hex("#000000")
            bg_color = self._parse_hex("#FFFFFF")
            bg_opacity = 240
        else:
            bg_opacity = self.bg_opacity

        # Calculate available text width
        max_text_width = img_w - (self.margin * 2) - (self.padding * 2)
        lines = wrap_text(draw, self.text, font, max_text_width)

        # Measure text block
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        line_spacing = 4
        total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1) if lines else 0
        max_line_w = max(line_widths) if line_widths else 0

        # Box dimensions
        box_w = max_line_w + self.padding * 2
        box_h = total_text_h + self.padding * 2

        # Position the box
        bx, by = self._compute_box_position(img_w, img_h, box_w, box_h)

        # Draw background
        bg_rgba = (*bg_color, bg_opacity)
        if self.style == TextStyle.SPEECH:
            # Rounded rectangle for speech style
            r = 12
            draw.rounded_rectangle(
                [(bx, by), (bx + box_w, by + box_h)],
                radius=r,
                fill=bg_rgba,
            )
            # Small triangle tail
            tail_x = bx + box_w // 3
            tail_y = by + box_h
            draw.polygon(
                [(tail_x, tail_y), (tail_x + 20, tail_y), (tail_x + 5, tail_y + 18)],
                fill=bg_rgba,
            )
        else:
            draw.rectangle([(bx, by), (bx + box_w, by + box_h)], fill=bg_rgba)

        # Draw text lines
        current_y = by + self.padding
        for i, line in enumerate(lines):
            text_x = bx + self.padding
            draw.text((text_x, current_y), line, fill=(*text_color, 255), font=font)
            current_y += line_heights[i] + line_spacing

        # Composite and save
        result = Image.alpha_composite(source, overlay).convert("RGB")
        image_dto = context.images.save(result)
        return ImageOutput.build(image_dto)

    def _compute_box_position(self, img_w: int, img_h: int, box_w: int, box_h: int) -> tuple[int, int]:
        """Returns (x, y) for top-left corner of the text box."""
        m = self.margin
        positions = {
            TextPosition.TOP: ((img_w - box_w) // 2, m),
            TextPosition.BOTTOM: ((img_w - box_w) // 2, img_h - box_h - m),
            TextPosition.TOP_LEFT: (m, m),
            TextPosition.TOP_RIGHT: (img_w - box_w - m, m),
            TextPosition.BOTTOM_LEFT: (m, img_h - box_h - m),
            TextPosition.BOTTOM_RIGHT: (img_w - box_w - m, img_h - box_h - m),
            TextPosition.CENTER: ((img_w - box_w) // 2, (img_h - box_h) // 2),
        }
        return positions.get(self.position, positions[TextPosition.BOTTOM])

    @staticmethod
    def _parse_hex(color: str) -> tuple[int, int, int]:
        """Parse a hex color string to (R, G, B)."""
        color = color.lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))

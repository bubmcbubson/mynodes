"""
Images to PDF Node
Compiles a collection of comic page images into a multi-page PDF file.
"""

import os
from datetime import datetime
from pathlib import Path

from PIL import Image

from invokeai.invocation_api import (
    BaseInvocation,
    ImageField,
    ImageOutput,
    InputField,
    InvocationContext,
    invocation,
)


@invocation(
    "comic_images_to_pdf",
    title="Comic Images to PDF",
    tags=["comic", "pdf", "export", "compile"],
    category="Comic Creator",
    version="1.0.0",
)
class ImagesToPDFInvocation(BaseInvocation):
    """Compiles a collection of page images into a multi-page PDF.
    The PDF is saved to the specified output directory. Returns the
    first page as a preview image. Check the InvokeAI log for the
    full PDF file path after execution."""

    images: list[ImageField] = InputField(
        description="Collection of finished comic page images, in order"
    )
    filename: str = InputField(
        default="comic",
        description="PDF filename (without .pdf extension). Timestamp is appended automatically.",
    )
    output_dir: str = InputField(
        default="",
        description="Directory to save the PDF. Leave empty to use InvokeAI's default outputs folder. Supports absolute paths.",
    )
    dpi: int = InputField(
        default=300,
        ge=72,
        le=600,
        description="PDF resolution in DPI",
    )
    jpeg_quality: int = InputField(
        default=92,
        ge=50,
        le=100,
        description="JPEG compression quality for pages inside the PDF (higher = larger file, better quality)",
    )

    def invoke(self, context: InvocationContext) -> ImageOutput:
        if not self.images:
            # Return a blank page if no images provided
            blank = Image.new("RGB", (2480, 3508), (255, 255, 255))
            image_dto = context.images.save(blank)
            return ImageOutput.build(image_dto)

        # Load all page images
        pages: list[Image.Image] = []
        for img_field in self.images:
            pil_img = context.images.get_pil(img_field.image_name).convert("RGB")
            pages.append(pil_img)

        # Determine output directory
        if self.output_dir.strip():
            out_dir = Path(self.output_dir)
        else:
            # Default: write next to InvokeAI's outputs
            # Try common InvokeAI root locations
            invokeai_root = os.environ.get("INVOKEAI_ROOT", "")
            if invokeai_root:
                out_dir = Path(invokeai_root) / "outputs" / "comics"
            else:
                out_dir = Path.home() / "invokeai" / "outputs" / "comics"

        out_dir.mkdir(parents=True, exist_ok=True)

        # Build filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in self.filename)
        pdf_filename = f"{safe_name}_{timestamp}.pdf"
        pdf_path = out_dir / pdf_filename

        # Save as multi-page PDF using Pillow
        first_page = pages[0]
        remaining = pages[1:] if len(pages) > 1 else []

        first_page.save(
            str(pdf_path),
            format="PDF",
            save_all=True,
            append_images=remaining,
            resolution=self.dpi,
            quality=self.jpeg_quality,
        )

        context.logger.info(f"Comic PDF saved: {pdf_path}")
        context.logger.info(f"Total pages: {len(pages)}")

        # Return the first page as preview
        image_dto = context.images.save(first_page)
        return ImageOutput.build(image_dto)

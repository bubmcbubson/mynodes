"""
Comic Creator Node Pack for InvokeAI
=====================================
Custom nodes for generating AI comic books entirely within InvokeAI.

Nodes included:
  - Text Overlay: Add captions, narration boxes, and speech bubbles to images
  - Comic Panel Layout: Arrange multiple images into comic page grids
  - Images to PDF: Compile finished pages into a downloadable PDF
  - Prompt List: Load a batch of prompts from a text file for iteration

Installation:
  Copy this folder into your InvokeAI nodes directory and restart.
  See README.md for full workflow instructions.
"""

from .text_overlay import TextOverlayInvocation
from .panel_layout import ComicPanelLayoutInvocation
from .images_to_pdf import ImagesToPDFInvocation
from .prompt_list import PromptListInvocation

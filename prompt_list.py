"""
Prompt List Node
Reads prompts from a text file (one per line) and outputs them as a
string collection for use with InvokeAI's Iterate node.

Also supports inline prompt entry as a fallback.
"""

from pathlib import Path

from invokeai.invocation_api import (
    BaseInvocation,
    BaseInvocationOutput,
    InputField,
    InvocationContext,
    OutputField,
    invocation,
    invocation_output,
)


@invocation_output("comic_prompt_list_output")
class PromptListOutput(BaseInvocationOutput):
    """Output containing parallel collections of prompts and captions."""

    prompts: list[str] = OutputField(description="Collection of image generation prompts")
    captions: list[str] = OutputField(description="Collection of caption/narration texts (parallel to prompts)")
    count: int = OutputField(description="Number of prompts loaded")


@invocation(
    "comic_prompt_list",
    title="Comic Prompt List",
    tags=["comic", "prompt", "list", "batch", "file"],
    category="Comic Creator",
    version="1.0.0",
)
class PromptListInvocation(BaseInvocation):
    """Loads panel prompts and captions from a text file or inline text.

    Each line becomes one entry. Use || to separate the image prompt
    from its caption text. Lines starting with # are comments. Empty
    lines are skipped.

    The prompts and captions outputs are parallel collections that
    feed into Iterate nodes for batch generation.

    File format example:
        # Panel 1: Opening scene
        A woman standing on a rooftop at sunset || Later that evening, she knew.
        # Panel 2: No caption (leave off the ||)
        Close-up portrait, dramatic expression
        # Panel 3: Caption only scenario
        The woman leaping between buildings || She had no choice but to run.
    """

    file_path: str = InputField(
        default="",
        description="Path to a .txt file with one prompt per line. Use || to separate prompt from caption.",
    )
    inline_prompts: str = InputField(
        default="",
        description="Alternative: paste prompts directly here, one per line. Used if file_path is empty.",
    )
    prefix: str = InputField(
        default="",
        description="Text prepended to every image prompt (e.g. character description or style tag).",
    )
    suffix: str = InputField(
        default="",
        description="Text appended to every image prompt (e.g. 'high detail, 8k').",
    )

    def invoke(self, context: InvocationContext) -> PromptListOutput:
        raw_lines: list[str] = []

        # Load from file if provided
        if self.file_path.strip():
            path = Path(self.file_path.strip())
            if path.exists() and path.is_file():
                raw_lines = path.read_text(encoding="utf-8").splitlines()
                context.logger.info(f"Loaded {len(raw_lines)} raw lines from {path}")
            else:
                context.logger.warning(f"Prompt file not found: {path}")

        # Fall back to inline prompts
        if not raw_lines and self.inline_prompts.strip():
            raw_lines = self.inline_prompts.strip().splitlines()

        # Parse: skip comments and empty lines, split on ||
        prompts = []
        captions = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Split prompt from caption on ||
            if "||" in stripped:
                parts = stripped.split("||", 1)
                prompt_text = parts[0].strip()
                caption_text = parts[1].strip()
            else:
                prompt_text = stripped
                caption_text = ""

            # Apply prefix/suffix to the image prompt only
            if self.prefix.strip():
                prompt_text = f"{self.prefix.strip()}, {prompt_text}"
            if self.suffix.strip():
                prompt_text = f"{prompt_text}, {self.suffix.strip()}"

            prompts.append(prompt_text)
            captions.append(caption_text)

        context.logger.info(f"Comic Prompt List: {len(prompts)} prompts, {sum(1 for c in captions if c)} captions")

        return PromptListOutput(prompts=prompts, captions=captions, count=len(prompts))

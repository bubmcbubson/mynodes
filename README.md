# Comic Creator Node Pack for InvokeAI

Custom nodes for producing AI-generated comics entirely within InvokeAI's workflow editor.
Tested on InvokeAI v6.13+. Uses Flux 2 Klein for all image generation.

## What's Included

| Node | Purpose |
|------|---------|
| **Comic Prompt List** | Loads panel prompts and captions from a text file. Outputs parallel collections for Iterate. |
| **Comic Text Overlay** | Adds styled captions, narration boxes, or speech text to panel images. |
| **Comic Panel Layout** | Arranges panels into page grids (2x2, 2x3, 3x3, manga, vertical, custom). |
| **Comic Images to PDF** | Compiles finished pages into a multi-page PDF saved to disk. |


## Installation

1. Locate your InvokeAI nodes directory at the root of your InvokeAI install:
   ```
   <YOUR_INVOKEAI_ROOT>/nodes/
   ```
   If the `nodes` folder does not exist, create it.

2. Copy the entire `comic_creator_nodes` folder into it:
   ```
   <YOUR_INVOKEAI_ROOT>/nodes/comic_creator_nodes/
   ```

3. Restart InvokeAI. The four nodes appear under the **Comic Creator** category
   in the workflow editor's node picker.

4. No extra Python packages required. Everything uses Pillow, which ships with InvokeAI.


## Models You Need

| Model | Role | Notes |
|-------|------|-------|
| **Flux 2 Klein** (4B or 9B) | All image generation | Install via Model Manager starter pack. |
| **Flux 2 Klein LoRAs** | Style and character tuning | Supported in v6.12+. Install via Model Manager. |
| **FLUX VAE** | Latent decoding | Included in the Klein starter pack. |
| **FLUX Qwen3 Text Encoder** | Text encoding for Klein | Included in the Klein starter pack. Use the 8B encoder for 9B models. |

One model, one set of LoRAs, used for every image in the comic. No model switching.


## Workflow Architecture

The workflow has four stages. Build them left to right in the workflow editor.

```
STAGE 1                 STAGE 2                    STAGE 3              STAGE 4
Reference Character --> Panel Generation     -->   Page Layout    -->   PDF Export
(Klein + LoRAs)         (Klein + LoRAs + Iterate)  (Grid node)          (Save PDF)
```

Character consistency depends on three things working together:
  - The same Klein model and LoRA stack across every generation
  - A precise character description baked into every panel prompt via the prefix field
  - Matching generation settings (steps, CFG, scheduler) locked across the run

Stage 1 exists so you nail down the character description and model config before
committing to a full batch. Get the reference right, then the same config drives
every panel in Stage 2.


### STAGE 1: Generate the Reference Character

This produces one high-quality full-body image of your character. It is your
visual proof that the character description and model settings are correct.
Run this stage alone, generate candidates, pick the winner, lock the seed.

**Nodes to place:**

1. **FLUX Model Loader** - Select your Flux 2 Klein model
2. **FLUX LoRA Loader** (one per LoRA) - Chain them: first LoRA output connects
   to second LoRA input, and so on.
3. **FLUX Text Encode** - Your full character description prompt. Write in Flux
   prose style (Subject + Setting + Details + Lighting + Atmosphere):

   > "A beautiful woman in her late twenties with long dark hair and vivid green
   > eyes. She has a slim athletic build and high cheekbones. She is wearing a
   > fitted black cocktail dress and silver earrings. Full body shot, standing
   > pose, studio lighting, neutral gray background, fashion photography, 8k
   > detail, sharp focus."

4. **FLUX Denoise** - Connect model output from the LoRA chain.
   Recommended: 20+ steps, CFG 3.5 for Klein Base; 4 steps for quantized.
5. **FLUX VAE Decode** - Connect to denoise output.
6. **Save Image** - Saves the reference to your gallery.

**Wiring:**
```
FLUX Model Loader --> LoRA 1 --> LoRA 2 --> FLUX Denoise
FLUX Text Encode -----------------------> FLUX Denoise
FLUX Denoise --> FLUX VAE Decode --> Save Image
```

> **TIP:** Run this stage repeatedly until the character looks exactly right.
> Record the seed. The character description you finalize here becomes the
> `prefix` value in Stage 2, ensuring every panel inherits the same identity.
>
> The model loader and LoRA chain from this stage feed directly into Stage 2.
> In the workflow editor, the same FLUX Model Loader and LoRA nodes connect
> to BOTH the reference denoise node and the panel denoise node. One model
> config drives everything.


### STAGE 2: Generate All Panels

Each panel is an independent txt2img generation using the same Klein + LoRA
config from Stage 1. The character description from Stage 1 is prepended to
every panel prompt automatically via the Prompt List prefix field.

**Nodes to place:**

1. **Comic Prompt List** - Point `file_path` to your prompts .txt file.

   Set `prefix` to your finalized character description (the same one from
   Stage 1, shortened to the essential identity markers):
   > "A woman in her late twenties with long dark hair, vivid green eyes,
   > slim athletic build, fitted black cocktail dress, silver earrings"

   Set `suffix` to quality tags:
   > "high detail, cinematic lighting, sharp focus, 8k"

2. **Iterate** (prompts) - Connect the `prompts` output from Prompt List.
   Loops through each prompt one at a time.

3. **FLUX Text Encode** - Takes the current prompt from Iterate.

4. **FLUX Denoise** - Connected to the SAME model loader and LoRA chain
   from Stage 1. Same steps, same CFG, same scheduler.

5. **FLUX VAE Decode** - Decode the denoised latent into a panel image.

6. **Iterate** (captions) - Connect the `captions` output from Prompt List.
   Runs in parallel with the prompts Iterate.

7. **Comic Text Overlay** - Takes the decoded panel image and the current
   caption string. Configure style (narration, caption, speech, plain),
   position, font size, etc.

8. **Collect** - Gathers all finished captioned panels into one collection.

**Wiring:**
```
                                  (same model + LoRAs from Stage 1)
                                              |
                                              v
Comic Prompt List --[prompts]--> Iterate --> Text Encode --> FLUX Denoise
                                                             |
                                                             v
                                                        VAE Decode
                                                             |
                                                             v
Comic Prompt List --[captions]--> Iterate ----------> Text Overlay
                                                             |
                                                             v
                                                          Collect
```

**Key detail:** The FLUX Model Loader and LoRA chain are shared between
Stage 1 and Stage 2. In the workflow editor, draw edges from the same
model/LoRA output to both denoise nodes (the reference one and the panel
one). This guarantees identical model behavior across every image.

> **IMPORTANT:** The two Iterate nodes (prompts and captions) must be
> synchronized. In InvokeAI v6.13, collection iteration is deterministic
> and preserves order, so the Nth prompt pairs with the Nth caption
> automatically when both come from the same Prompt List node.


### STAGE 3: Arrange Panels into Pages

**Nodes to place:**

1. **Comic Panel Layout** - Connect the Collect output from Stage 2.
   - Choose a `layout` preset (2x2, 2x3, 3x3, manga_right, etc.)
   - Set `page_width` and `page_height` (2480x3508 for A4 at 300dpi)
   - Adjust `gutter` (space between panels) and `border` (page margins)

   If you have more panels than one layout holds (e.g. 6 panels but a
   2x2 layout), split across multiple Layout nodes, one per page.

2. **Collect** - If you have multiple pages, collect them into one collection.

**Wiring:**
```
Collect (Stage 2) --> Panel Layout (page 1)
                  --> Panel Layout (page 2)  --> Collect (all pages)
                  --> Panel Layout (page 3)
```

For the `custom_rows` field, define your grid as comma-separated panel
counts per row. Example: "1,2,3" means 1 wide panel on top, 2 in the
middle row, 3 across the bottom.


### STAGE 4: Export PDF

**Nodes to place:**

1. **Comic Images to PDF** - Connect the page collection.
   - Set `filename` (e.g. "my_comic_issue_1")
   - Set `output_dir` for a specific save location, or leave blank for default
   - Set `dpi` to 300 for print quality

**Wiring:**
```
Collect (all pages) --> Comic Images to PDF --> [preview image]
```

The PDF file path is logged in InvokeAI's console output. The preview
image returned to the workflow is the first page.


## Prompt File Format

Create a plain .txt file. One prompt per line. Use `||` to attach a caption:

```
# Comments start with #
A woman on a rooftop at sunset || The city never sleeps, but tonight she wished it would.
Close-up of her face, tears forming || She had promised herself she wouldn't cry.
Wide shot, the woman running down a street at night
```

Prompts with no `||` get no caption overlay. The prefix and suffix fields
on the Prompt List node are applied to the image prompt only, not the caption.

See `sample_prompts.txt` for a full example.


## Node Reference

### Comic Prompt List
| Input | Type | Default | Description |
|-------|------|---------|-------------|
| file_path | string | "" | Path to prompts .txt file |
| inline_prompts | string | "" | Paste prompts here if no file |
| prefix | string | "" | Prepended to every image prompt (your character description) |
| suffix | string | "" | Appended to every image prompt (quality tags) |

| Output | Type | Description |
|--------|------|-------------|
| prompts | string collection | Image generation prompts |
| captions | string collection | Caption texts (parallel to prompts) |
| count | int | Total number of entries |


### Comic Text Overlay
| Input | Type | Default | Description |
|-------|------|---------|-------------|
| image | image | required | Panel image |
| text | string | "" | Text to overlay |
| position | enum | bottom | top, bottom, top_left, top_right, bottom_left, bottom_right, center |
| style | enum | caption | caption (white/dark), narration (dark/yellow), speech (black/white bubble), plain |
| font_size | int | 28 | 8 to 120 |
| text_color | hex | #FFFFFF | Override text color |
| bg_color | hex | #000000 | Override background color |
| bg_opacity | int | 180 | 0 to 255 |
| padding | int | 16 | Inner padding |
| margin | int | 12 | Distance from image edge |
| custom_font_path | string | "" | Path to a .ttf file |


### Comic Panel Layout
| Input | Type | Default | Description |
|-------|------|---------|-------------|
| images | image collection | required | Panel images |
| layout | enum | 2x2 | 2x2, 2x3, 3x3, vertical_stack, horizontal_strip, manga_right, custom |
| page_width | int | 2480 | Page width px |
| page_height | int | 3508 | Page height px |
| gutter | int | 20 | Space between panels |
| border | int | 40 | Page margin |
| bg_color | hex | #FFFFFF | Page background |
| panel_border_width | int | 3 | Black border on each panel (0 to disable) |
| custom_rows | string | "" | For custom layout: "1,2,3" = 1 panel top row, 2 middle, 3 bottom |


### Comic Images to PDF
| Input | Type | Default | Description |
|-------|------|---------|-------------|
| images | image collection | required | Finished page images |
| filename | string | "comic" | PDF filename (timestamp auto-appended) |
| output_dir | string | "" | Save directory (blank = InvokeAI outputs/comics/) |
| dpi | int | 300 | PDF resolution |
| jpeg_quality | int | 92 | Compression quality |


## Consistency Tips for Klein-Only Workflow

Without a reference-image model like Kontext, character consistency with Klein
depends entirely on your prompting discipline:

1. **Prefix is everything.** The character description in the Prompt List prefix
   field must be specific: hair color and style, eye color, face shape, build,
   clothing, accessories. Vague descriptions produce drift.

2. **Lock your model config.** Same Klein model, same LoRAs at the same weights,
   same steps, same CFG, same scheduler across every panel. Any deviation
   introduces variation.

3. **Avoid contradictory prompts.** If your character has black hair in the
   prefix, don't describe windblown blonde hair in a panel prompt. The model
   will interpolate unpredictably.

4. **LoRAs are your best tool.** A character-trained LoRA gives far stronger
   consistency than text description alone. If you have a LoRA trained on your
   character, use it.

5. **Seed variance.** Different seeds produce different faces. This is expected.
   You can use InvokeAI's Seed Variance Enhancer (v6.11+) to get diversity
   in composition while keeping the same base seed, which helps consistency.


## Troubleshooting

**Nodes don't appear after restart:**
Check that the folder structure is exactly `nodes/comic_creator_nodes/__init__.py`.
The `__init__.py` must import all four node classes.

**Font looks wrong or tiny:**
Install DejaVu Sans Bold on your system, or set `custom_font_path` to a .ttf
file you prefer.

**PDF not saving:**
Check the InvokeAI console log for the exact error. Common issue: the output
directory does not exist or lacks write permissions. Set `output_dir` to an
absolute path you control.

**Captions not appearing:**
Make sure your prompts file uses `||` (double pipe) as the separator,
not `|` (single pipe).

**Character looks different across panels:**
Review the consistency tips above. The most common cause is a prefix that is
too short or too vague. Second most common: different LoRA weights between
the reference and panel generations.

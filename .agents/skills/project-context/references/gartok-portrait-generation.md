# Portrait generation (local Stable Diffusion + style LoRA)

New portraits come from `scripts/gen_portrait.py`, driven by the `/gen-portrait` skill
(`.claude/skills/gen-portrait/`). Setup and measured times: `scripts/portrait_lora/README.md`.

## What was decided

- **Free and local on a GTX 1050 Ti (4 GB):** AUTOMATIC1111 + SD 1.5 with `--medvram --no-half
  --opt-sdp-attention` (PyTorch 2.1.2+cu118; newer CUDA builds drop Pascal). Without
  `--opt-sdp-attention` the card spilled into shared memory and took 265 s an image instead of ~100 s.
- **The style comes from a LoRA trained on the game's own portraits** (230 images, 200 px upscaled to
  512, trigger `gartokstyle`, trained free on a Colab T4 with kohya sd-scripts, ~1 h). Epoch 6 of 10
  is the one in use; all five checkpoints looked alike.
- **Recipe:** text -> 512 px candidates (~2 min) -> pick from a contact sheet -> img2img refine at
  768 px, denoising 0.4 (~4.5 min, brings back the hatching) -> crop a 200 px circle with transparent
  corners. The first two NPC/pool uses were the Aurochs (`npc/aurochs.png`) and `orc/12.png`.

## What NOT to redo

- **Public LoRAs from Civitai** (woodcut, etching, engraving styles): all drift to pencil, linocut or
  digital ink; none matched the pool. Only the self-trained one did.
- **DreamShaper 8** as base: better anatomy and menace, but a loose modern ink style; with the
  engraving LoRA it turned 3D and metallic.
- **img2img from an existing portrait to make a new subject** (ox -> Aurochs): it keeps the pose and
  props (the harness stayed). New subjects start from text.
- **Prompting scars, torn ears or broken horns:** SD 1.5 deforms the face. Keep the subject plain.

## Limits

- The LoRA only knows what the pool looks like; retrain (`portrait_lora/build_dataset.py` + the Colab
  notebook) once the pool has grown a lot. The pool's images are 200 px, so hatching is softer than a
  hand-made engraving.
- The webui, checkpoint and LoRA live outside the repo (`C:\dev\sd`); the 38 MB LoRA is not committed.
- A race's numbered pool growing shifts `portrait_id % len(files)`: existing units may swap faces.

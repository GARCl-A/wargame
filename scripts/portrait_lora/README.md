# Portrait generator setup

`scripts/gen_portrait.py` drives a local AUTOMATIC1111 webui. Everything lives outside the repo.

## One-time setup (Windows, GTX 1050 Ti 4 GB was enough)

1. Python 3.10 venv (`uv python install 3.10`), PyTorch **2.1.2 + cu118** (newer CUDA builds drop Pascal GPUs).
2. Clone `AUTOMATIC1111/stable-diffusion-webui` to `C:\dev\sd\stable-diffusion-webui`.
   `webui-user.bat` args: `--medvram --no-half --no-half-vae --opt-sdp-attention --api`
   (the bat also sets `STABLE_DIFFUSION_REPO=https://github.com/w-e-w/stablediffusion.git`; install CLIP
   with `pip install --no-build-isolation` if the build fails on `pkg_resources`).
3. Base checkpoint `v1-5-pruned-emaonly.safetensors` in `models/Stable-diffusion/`
   (the first launch downloads it).
4. The style LoRA in `models/Lora/` (`gartok_style-000006.safetensors` by default, `GARTOK_LORA` overrides).

## Training the LoRA (free, Colab T4, ~1 h)

```
python scripts/portrait_lora/build_dataset.py        # -> scratch/portrait_lora/gartok_style.zip (230 images + captions)
```
Open `gartok_style_lora.ipynb` in Colab (T4 runtime), upload the zip when asked, run all cells, download the
`.safetensors` files. Retrain after the portrait pool grows a lot: the LoRA learns the pool's look.

## Measured on the 1050 Ti

- 512 px candidate: ~2 min. 768 px refine pass (img2img 0.4): ~4.5 min.
- Rejected: SD 1.5 without the LoRA (anatomy, wrong style), DreamShaper 8 (loses the engraving look),
  img2img from an existing portrait (inherits its pose and props).

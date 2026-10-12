"""Overnight batch generation script for GARTOK art using local Stable Diffusion + LoRA.

Executes all requested batches in sequence, saves candidate PNGs and generates
contact sheets under scratch/portrait_gen/<batch_name>/.
"""

import base64
import os
import sys
import time

# Ensure gartok root is in sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.gen_portrait import WORK, _post, _slug, sheet, PROMPT, NEG, LORA, status

BATCHES = [
    # 1. Ovelhas (12 opções)
    {
        "name": "sheep_domestic",
        "category": "Ovelhas (Doméstica)",
        "subject": "a domestic sheep with thick woolly fleece, gentle animal face",
        "n": 6,
        "seed": 2001,
    },
    {
        "name": "sheep_ram",
        "category": "Ovelhas (Carneiro com chifres)",
        "subject": "a horned ram sheep, medieval livestock with curved horns and dense wool",
        "n": 6,
        "seed": 2011,
    },
    # 2. Esqueletos (12 opções em 3 blocos de 4)
    {
        "name": "skeleton_warrior",
        "category": "Esqueletos (Guerreiro / Crânio antigo)",
        "subject": "an undead human skeleton warrior, cracked aged skull, dark empty eye sockets",
        "n": 4,
        "seed": 3001,
    },
    {
        "name": "skeleton_helmet",
        "category": "Esqueletos (Elmo de ferro enferrujado)",
        "subject": "a skeletal soldier wearing an ancient rusty iron helmet, decaying bones",
        "n": 4,
        "seed": 3011,
    },
    {
        "name": "skeleton_knight",
        "category": "Esqueletos (Cavaleiro aterrorizante)",
        "subject": "a terrifying skeleton knight with battle-worn armor, jagged teeth, dark fantasy",
        "n": 4,
        "seed": 3021,
    },
    # 3. Lobos (12 opções em 2 blocos de 6)
    {
        "name": "wolf_ferocious",
        "category": "Lobos (Feroz / Rosnando)",
        "subject": "a wild ferocious wolf snarling with bared sharp teeth, wild beast",
        "n": 6,
        "seed": 4001,
    },
    {
        "name": "wolf_alpha",
        "category": "Lobos (Alfa cicatrizado)",
        "subject": "a scarred alpha dire wolf, thick shaggy fur, watchful predatory gaze",
        "n": 6,
        "seed": 4011,
    },
    # 4. Carroça de Carga (8 artes)
    {
        "name": "wagon_cargo_cart",
        "category": "Carroça de Carga",
        "subject": "a heavy medieval cargo cart, rustic wooden two-wheeled freight cart laden with sacks and barrels, dark fantasy woodcut",
        "n": 8,
        "seed": 5001,
    },
    # 5. Carroça de Viagem (8 artes)
    {
        "name": "wagon_travel_carriage",
        "category": "Carroça de Viagem",
        "subject": "a covered medieval travel carriage, four-wheeled wooden passenger wagon with canvas canopy, expedition wagon",
        "n": 8,
        "seed": 5101,
    },
    # 6. Cobras (12 opções em 2 blocos de 6)
    {
        "name": "snake_coiled",
        "category": "Cobras (Enrolada / Predatória)",
        "subject": "a venomous coiled snake, menacing serpent head with tongue out and slit eyes",
        "n": 6,
        "seed": 6001,
    },
    {
        "name": "snake_viper",
        "category": "Cobras (Víbora atacando / Presas)",
        "subject": "a striking pit viper serpent with sharp bared venom fangs, aggressive pose",
        "n": 6,
        "seed": 6011,
    },
    # 7. Boi (8 opções em 2 blocos de 4)
    {
        "name": "ox_sturdy",
        "category": "Boi (Musculoso / Chifres maciços)",
        "subject": "a sturdy muscular ox with massive horns, draft beast, heavy burden animal",
        "n": 4,
        "seed": 7001,
    },
    {
        "name": "ox_working",
        "category": "Boi (Animal de arado rústico)",
        "subject": "a weathered working ox with large curved horns and broad snout, strong farm beast",
        "n": 4,
        "seed": 7011,
    },
    # 8. Goblins (12 opções em 3 blocos de 4)
    {
        "name": "goblin_rogue",
        "category": "Goblins (Ladino / Sorrateiro)",
        "subject": "a sneaky goblin rogue with long pointed ears and crooked sharp teeth",
        "n": 4,
        "seed": 8001,
    },
    {
        "name": "goblin_warrior",
        "category": "Goblins (Guerreiro com elmo rústico)",
        "subject": "a fierce goblin warrior wearing a crude iron cap, jagged grin, scarred skin",
        "n": 4,
        "seed": 8011,
    },
    {
        "name": "goblin_shaman",
        "category": "Goblins (Xamã astuto)",
        "subject": "an old cunning goblin shaman with wrinkled skin, squinting eyes, tribal beads",
        "n": 4,
        "seed": 8021,
    },
    # 9. Mestre da Arena (Goliath - 12 artes em 2 blocos de 6)
    {
        "name": "arena_master_goliath",
        "category": "Mestre da Arena (Goliath Gladiador / Pit Master)",
        "subject": "a powerful scarred goliath arena pit master, bald stone-skin giant with ruthless battle scars, spiked leather collar",
        "n": 6,
        "seed": 9001,
    },
    {
        "name": "arena_bookie_goliath",
        "category": "Mestre da Arena (Goliath Bookie / Chefe do Fosso)",
        "subject": "a grim goliath arena bookie and master of the fighting pits, chiseled rock-like jaw, braided beard, intimidating gaze",
        "n": 6,
        "seed": 9011,
    },
]


def run_batch():
    status(None)
    total_images = sum(b["n"] for b in BATCHES)
    print(f"=== Starting GARTOK Overnight Generation: {len(BATCHES)} batches, {total_images} total images ===")
    start_total = time.time()
    generated_count = 0

    for b_idx, batch in enumerate(BATCHES, 1):
        name = batch["name"]
        subject = batch["subject"]
        n = batch["n"]
        base_seed = batch["seed"]
        cat = batch.get("category", name)

        out_dir = os.path.join(WORK, _slug(name))
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n[{b_idx}/{len(BATCHES)}] {cat} ({name}): generating {n} images (seed {base_seed}+)...")
        paths = []
        for i in range(n):
            seed = base_seed + i
            t0 = time.time()
            prompt = PROMPT.format(lora=LORA, subject=subject)
            img_b64 = _post(
                "/sdapi/v1/txt2img",
                {
                    "prompt": prompt,
                    "negative_prompt": NEG,
                    "steps": 25,
                    "width": 512,
                    "height": 512,
                    "cfg_scale": 7,
                    "sampler_name": "Euler a",
                    "seed": seed,
                },
            )
            path = os.path.join(out_dir, f"cand_{seed}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            paths.append(path)
            generated_count += 1
            dt = round(time.time() - t0, 1)
            print(f"  [{generated_count}/{total_images}] seed {seed}: {dt}s -> {path}", flush=True)

        sheet_path = os.path.join(out_dir, "sheet.png")
        sheet(paths, sheet_path)
        print(f"  Contact sheet saved: {sheet_path}")

    elapsed_min = round((time.time() - start_total) / 60, 1)
    print(f"\n=== Batch complete! {generated_count} images generated in {elapsed_min} minutes. ===")


if __name__ == "__main__":
    run_batch()

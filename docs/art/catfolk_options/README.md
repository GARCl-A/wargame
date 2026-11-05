# Catfolk portraits: Gemini prompts

The Catfolk has no portrait folder yet (`gartok/assets/portraits/catfolk/`), so it shows the initial of its
name. Other races hold 12 to 18 faces; start with 8 and grow to 12.

## How to send it

1. Attach **all four** images in [references/](references/) to **every** request (Gnoll 10, Grippli 13,
   Kenku 4, Ogre 0: the style anchor). Never attach a floor texture or a Catfolk you already made:
   Gemini copies what it is given.
2. One request per portrait: the **base prompt** below, then **one line from the variants table**.
3. Ask for 1:1. If the result has a frame ring, a caption or a full body, regenerate; do not crop it.
4. Save the ones you like in this folder (`catfolk_<n>.png`) and tell me. `scripts/gen_portrait.py install
   <file> --race Catfolk` cuts the 200 px circle and numbers it in the race's pool.

## Base prompt

```
Using the four attached images only as a STYLE reference (a sepia ink engraving on cream parchment, dense
crosshatching, bold clean outlines, a head-and-shoulders character portrait), draw a NEW portrait of a
CATFOLK: an upright, humanoid cat person, a fantasy traveller and trader. A real feline head (short muzzle,
nose, whiskers, pointed ears, slit-pupil eyes, fur drawn with fine engraved strokes), with human-like
shoulders and clothing. Alert, sly, self-assured expression. Three-quarter view, head and shoulders, the
face large and centred.

Do not copy the species, clothing or pose of the attached portraits (a raven, a hyena, a frog, an ogre):
they show the drawing style only.

Medieval fantasy clothing, practical and worn: leather, cloth, a scarf or hood, one or two small personal
details (an earring, a charm, a buckle). Nothing modern.

Style rules: 2D engraving only, sepia ink on flat cream parchment filling the whole square, no colour other
than sepia and cream, no gradients, no 3D, no isometric, no pixel art, no cartoon or cute "furry" look,
no painted shading. Square 1:1 image. The whole parchment is the picture: NO border ring, NO frame, NO
text, NO caption, NO signature. Keep the head and shoulders inside the largest circle that fits the
square, with nothing important in the four corners (the game cuts a round medallion out of it).

VARIANT: <paste one line from the table>
```

## Variants

Vary coat, age, build and gear so a guild of Catfolk does not look like one cat. Mix of men and women.

| # | Variant line |
|---|---|
| 1 | a young woman, short tabby coat with striped cheeks, a loose hood pushed back, a small hoop earring, a confident half-smile |
| 2 | an old man, long grey fur and a bristling mane of whiskers, a patched travelling cloak, a worn leather strap across the chest, calm knowing eyes |
| 3 | a middle-aged man, solid black short fur, a plain scarf wound twice around the neck, one ear notched at the tip, a wary stare |
| 4 | a woman with a tuxedo coat (dark back, white muzzle and chest), a merchant's leather jerkin with a brass clasp, a coin charm on a cord |
| 5 | a young man, spotted ocelot-like coat, a bandolier of small pouches, a lopsided grin showing one fang |
| 6 | a woman with a calico coat in patches (draw the patches as bold hatched areas), a headscarf tied at the back, a narrow necklace |
| 7 | a broad older man, thick long fur around the face like a mane, a sleeveless leather vest, heavy eyebrows, a stern look |
| 8 | a slender woman, short pale fur with darker face and ears (siamese-like), a high collar, ears pierced twice, a cool, appraising look |
| 9 | a young woman, ginger short fur, bright wide eyes, a travelling cap pulled over the ears, a satchel strap on the shoulder |
| 10 | a lean man, scruffy and sharp, short ragged fur, a bandana over the brow, a thin scar drawn as one engraved line over a whisker pad |
| 11 | a woman, sleek hairless-looking short coat with fine stripes, a scholar's hood and a small ink-stained collar, one raised eyebrow |
| 12 | a gentle elder woman, white fur with a few grey strokes, a shawl with a simple border, kind half-closed eyes |

## If it goes wrong

- It draws a cat's whole body, a sitting pet or a chibi face: add "head and shoulders only, the proportions
  of the Kenku and Gnoll references".
- It copies the raven's scarf or the hyena's armour: repeat the "do not copy" sentence and name what it
  copied ("no shoulder spikes").
- It adds colour: add "pure sepia monochrome, no other hue".
- Record here the prompts that worked, and under each failed one, what went wrong.

# Demon portraits: Gemini prompts

The Demon is the Cult's quest boss (`npcs/the-demon.json`, "The Pale Tenant", Large, level 22) and a race of its
own (`data.DEMONS`). It has no portrait folder yet (`gartok/assets/portraits/demon/`), so it borrows the
Kobold glyph and shows its initial. Plan: generate **4**, pick the best for the Pale Tenant
(`scripts/gen_portrait.py install <file> --npc the-demon`, then `"portrait_file": "the-demon.png"` in its JSON),
and install the other 3 in the race pool (`--race Demon`).

## How to send it

1. Attach **all four** images in [../../web_ui/references/](../../web_ui/references/) to **every** request
   (`gnoll_10.png`, `grippli_13.png`, `kenku_4.png`, `ogre_0.png`: the style anchor). Never attach a floor
   texture or a portrait you already made of this subject: Gemini copies what it is given.
2. One request per portrait: the **base prompt** below, then **one line from the variants table**.
3. Ask for 1:1. If the result has a frame ring, a caption or a full body, regenerate; do not crop it.
4. Save the ones you like here (`demon_<n>.png`).

## Base prompt

```
Using the four attached images only as a STYLE reference (a sepia ink engraving on cream parchment, dense
crosshatching, bold clean outlines, a head-and-shoulders character portrait), draw a NEW portrait of a
DEMON: a towering infernal being called up by a cult, the strongest creature in the world. A heavy,
bone-pale, hairless head with a broad brow, two thick curved horns, deep-set eyes that glow as plain white
(leave the eye whites unhatched), a wide mouth with the lips closed or slightly parted over blunt teeth,
skin drawn with fine engraved strokes and cracked like old plaster. Powerful neck and shoulders, much larger
than a man. Calm, patient, absolutely certain: it does not snarl. It looks like something that has all the
time in the world. Three-quarter view, head and shoulders, the face large and centred.

Do not copy the species, clothing or pose of the attached portraits (a raven, a hyena, a frog, an ogre):
they show the drawing style only. It is not a goblin, not an ogre and not a cartoon imp.

Almost no clothing: bare skin, perhaps one iron collar, a rag of dark cloth or a few ritual marks cut or
branded into the skin. Nothing modern. No fire, no flames, no wings, no pitchfork, no bat-devil cliche.

Style rules: 2D engraving only, sepia ink on flat cream parchment filling the whole square, no colour other
than sepia and cream, no gradients, no 3D, no isometric, no pixel art, no painted shading. Square 1:1 image.
The whole parchment is the picture: NO border ring, NO frame, NO text, NO caption, NO signature. Keep the head
and shoulders inside the largest circle that fits the square, with nothing important in the four corners
(the game cuts a round medallion out of it).

VARIANT: <paste one line from the table>
```

## Variants

The Pale Tenant (the boss) should be the most memorable one; the others fill the Demon pool, so they should
read as the same kind of creature, not the same face.

| # | Variant line |
|---|---|
| 1 | THE PALE TENANT: two long horns sweeping back and up, a smooth cracked brow, a single iron collar cut into the neck, a faint ritual circle branded on the forehead, an expression of calm contempt |
| 2 | broad and heavy, four short horns (two at the temples, two lower at the jaw), a scarred cheek, a rag of dark cloth over one shoulder, a slow, appraising stare |
| 3 | long and gaunt, one horn broken to a stump and the other a tall spiral, ritual marks in lines across the cheeks and chest, a thin, patient smile |
| 4 | massive, a wide flat head with a ridge of small horns along the brow like a crown, no neck visible, eyes half closed as if bored |

## If it goes wrong

- It draws wings, flames or a red devil: add "no wings, no fire, no horns longer than the head, pure sepia
  monochrome".
- It looks like an ogre or a goblin: say "the head is bone-pale and hairless, the proportions of a statue,
  not a brute".
- It copies the raven's scarf or the ogre's pose: repeat the "do not copy" sentence and name what it copied.
- It adds colour or glowing red eyes: add "pure sepia monochrome, no other hue; the eyes are blank white".
- Record here the prompts that worked, and under each failed one, what went wrong.

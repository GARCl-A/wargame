# GARTOK Tactical — Design System Specification

> **Source of truth:** `map_render.py` (Tokens `T` & canonical render functions).  
> **Status:** Absolute canonical standard. Any deviation in screens or UI components is a lint/architectural violation.

---

## 1. Principles & Tenets

1. **One Single Palette (`T`):** No ad-hoc, invented, or hardcoded RGB tuples in drawing routines. If a color is not in `T`, it does not exist.
2. **Color is Semantic:** Color ONLY appears when it conveys explicit state or meaning (player focus, danger, critical resource shortage, safety). Base surfaces, structural lines, and neutral objects must remain muted and neutral.
3. **Strict 8px Grid Scale (`T.S = 8`):** All margins, paddings, gaps, offsets, and component dimensions must be multiples of `8` (`T.S * n`).
4. **Three Font Sizes, Two Weights:** Only three font sizes exist in the design system (`12`, `15`, `26`) across two weights (Regular, Bold).
5. **Layered Depth & Readability:** Every mark inked on the world map or chrome must carry its own contrast layer (e.g., roads have an underlying casing; text on varied backgrounds has a procedural outline; travel tags are drawn as opaque chips).

---

## 2. Color Palette Tokens (`T`)

```python
class T:
    # --- Surfaces (depth ramp: deepest to nearest)
    VOID      = (22, 18, 14)     # Outer background, screen clear, outer separation
    FIELD     = (42, 33, 24)     # The map surface
    FIELD_HI  = (56, 45, 33)     # Terrain relief, texture blobs, primary road sheen
    PANEL     = (31, 26, 20)     # Sidebar body, topbar body, node inner disk
    LINE      = (64, 53, 40)     # Structural dividers, borders, ghost button outlines

    # --- Ink (typography)
    INK       = (232, 223, 204)  # Primary text, active readouts
    INK_MUTED = (154, 140, 116)  # Labels, captions, descriptions
    INK_FAINT = (104, 92, 74)    # Structural labels, headers, tertiary metadata

    # --- Roads & Connections
    ROAD      = (156, 130, 90)   # Road core
    ROAD_DARK = (28, 22, 16)     # Road under-casing / shadow

    # --- State & Semantics (Used ONLY when meaningful)
    BRASS     = (217, 164, 65)   # Player location, selection, primary CTA
    DANGER    = (181, 69, 58)    # Threat, zero rations, critical warning
    SAFE      = (95, 138, 90)    # Friendly / fortified / safe node
```

### Neutral Node Color
- Neutral nodes (`plain`) use `(126, 111, 90)` — they do not have their own saturated semantic color.

---

## 3. Spatial Scale (`T.S = 8`)

All spatial arithmetic derives strictly from `T.S`:
- `T.S * 1 = 8px`: Small inner gap, tight padding, divider offset.
- `T.S * 2 = 16px`: Standard element padding, topbar row margin.
- `T.S * 3 = 24px`: Section gap, cluster indentation.
- `T.S * 4 = 32px`: Inter-section spacing.
- `T.S * 5 = 40px`: Large grouping separation.

*Arbitrary pixel offsets (e.g., 3px, 5px, 7px, 9px, 10px, 13px, 14px, 17px, 22px, 27px, 30px, 34px, 38px, 42px, 44px, 46px, 52px, 92px) violate the design system unless derived from `T.S` or font height metrics.*

---

## 4. Typography Scale

| Token | Size (px) | Role | Weights Allowed |
|---|---|---|---|
| `T.SIZE_LABEL` | **12** | Uppercase headers, tags, status pills, subtitles | Regular |
| `T.SIZE_BODY` | **15** | Standard copy, node names, card descriptions | Regular, Bold |
| `T.SIZE_TITLE` | **26** | Screen titles, key metric numbers (stat readouts) | Bold |

*Any font loaded with sizes like 10, 11, 13, 14, 16, 18, 20, 22, 24, 28, 32 is strictly prohibited.*

---

## 5. Standard Component Functions (`map_render.py`)

Every screen representing graph/map and chrome MUST adopt these canonical functions:

### 1. Graph Auto-Fitting (`fit_transform`)
```python
fit_transform(nodes, rect, padding=0.08, max_zoom=6.0) -> (world_to_screen, zoom)
```
Calculates zoom and translation so the node graph automatically fits inside the assigned screen viewport without manual arbitrary clamping or letterbox drift.

### 2. Layered Roads (`draw_road`)
```python
draw_road(surf, a, b, primary=False)
```
Dual-pass drawing:
- Bottom casing: `w + 4` width using `T.ROAD_DARK`.
- Core line: `w` (`3px` or `5px` if primary) using `T.ROAD`.
- Optional highlight: `1px` center sheen using `T.FIELD_HI`.

### 3. Cost / Value Chips (`draw_chip`)
```python
draw_chip(surf, font, text, center, fg=T.INK_MUTED, bg=T.VOID)
```
Draws travel hours or metric chips rendered with an opaque fill (`bg=T.VOID`), a 1px border (`T.LINE`, radius 3), and padding of 12x6. Always drawn **after** roads so text never collides with road lines.

### 4. Canonical Node Glyphs (`draw_node`)
```python
draw_node(surf, fonts, node, center, selected=False)
```
- Radius: `NODE_R = 19px`.
- Selection ring: `NODE_R + 7`, width 2, in `T.BRASS`.
- Background separator: `NODE_R + 3` solid circle in `T.VOID`.
- Base disk: `NODE_R` solid circle in `T.PANEL`.
- Semantic rim: `NODE_R` circle outline (width 3) in `KIND_COLOR[node.kind]`.
- Icon: centered bold character/glyph in node semantic color.
- Outlined label: `draw_outlined` placed at `(x, y + NODE_R + 14)` with `T.INK` and `outline=T.VOID`.

### 5. Standard Topbar (`draw_topbar`)
```python
draw_topbar(surf, fonts, rect)
```
Single unified banner (`T.PANEL` fill, `T.LINE` bottom border). Displays grouped metric clusters (Time, Resources, Score) with uppercase `T.INK_FAINT` labels and large `T.SIZE_TITLE` numbers in `T.INK` (or semantic tint like `T.DANGER` on 0 rations). Clusters separated by 1px vertical `T.LINE`.

### 6. Buttons & Sidebar (`draw_button`, `draw_sidebar`)
```python
draw_button(surf, fonts, rect, text, primary=False, hint=None)
```
- Exactly **one primary button** per view: solid `T.BRASS` fill, `T.VOID` text.
- Secondary buttons: ghost style, `1px` border in `T.LINE`, `T.INK` text.
- Optional hint rendered underneath in `T.INK_FAINT`.

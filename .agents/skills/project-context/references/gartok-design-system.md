---
name: gartok-design-system
description: "GARTOK Tactical canonical Design System — T tokens, 8px grid scale, 3 font sizes, and canonical map/chrome rendering"
metadata:
  node_type: memory
  type: project
  originSessionId: dc6d02d1-584f-4293-bc58-7219951404e9
  modified: 2026-09-15T22:45:00.000Z
---

# GARTOK Tactical — Canonical Design System

The canonical visual design system for GARTOK Tactical is defined in `map_render.py` (and specified in `DESIGN_SYSTEM.md`). It supersedes legacy ad-hoc styles in `theme.py` and establishes hard visual constraints across the application.

## 1. Tokens (`T`)

- **Surfaces:**
  - `T.VOID = (22, 18, 14)`
  - `T.FIELD = (42, 33, 24)`
  - `T.FIELD_HI = (56, 45, 33)`
  - `T.PANEL = (31, 26, 20)`
  - `T.LINE = (64, 53, 40)`
- **Inks:**
  - `T.INK = (232, 223, 204)`
  - `T.INK_MUTED = (154, 140, 116)`
  - `T.INK_FAINT = (104, 92, 74)`
- **Roads:**
  - `T.ROAD = (156, 130, 90)`
  - `T.ROAD_DARK = (28, 22, 16)`
- **Semantic State (Use only when meaningful):**
  - `T.BRASS = (217, 164, 65)` (Player, selection, primary CTA)
  - `T.DANGER = (181, 69, 58)` (Combat threat, zero rations, critical alert)
  - `T.SAFE = (95, 138, 90)` (Safe zone, fortified claim)
  - Plain node rim: `(126, 111, 90)`

## 2. Spatial Scale (`T.S = 8`)

All UI geometry, padding, margin, row height, and spacing must be multiples of 8 (`T.S * 1 = 8`, `T.S * 2 = 16`, `T.S * 3 = 24`, `T.S * 4 = 32`, `T.S * 5 = 40`). Arbitrary odd offsets are strictly forbidden.

## 3. Typography Scale

Only 3 sizes and 2 weights are permitted:
- `T.SIZE_LABEL = 12` (regular)
- `T.SIZE_BODY = 15` (regular and bold)
- `T.SIZE_TITLE = 26` (bold)

## 4. Canonical Rendering Pipeline

- `fit_transform(nodes, rect, padding, max_zoom)` for viewport graph fitting.
- `draw_road(surf, a, b, primary)` for dual-line layered roads.
- `draw_chip(surf, font, text, center, fg, bg)` for solid opaque travel cost labels.
- `draw_node(surf, fonts, node, center, selected)` with `NODE_R = 19`, outer `T.VOID` ring, `T.PANEL` fill, semantic colored rim, bold icon, and `draw_outlined` label.
- `draw_topbar(surf, fonts, rect)` for grouped metrics without card box bloat.
- `draw_button(surf, fonts, rect, text, primary, hint)` with exactly one primary CTA and ghost secondary buttons.

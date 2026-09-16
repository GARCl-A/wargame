"""
GARTOK Tactical - war table v3

Redesign from scratch. The screen is organised around MANAGEMENT, not the
map.

Zones (see gartok/ui/ for the component behind each one):
  COMMAND (top)        clock + whatever could end the run (people alive/hurt)
  ROSTER (left)        work queue: one card per group, brass = needs you
  MAP (centre)         paper on the table. viewport with pan/zoom + minimap
  INSPECTOR (right)    the only place with descriptive text
  CLOCK (footer)       24 h timeline + the action that unlocks the clock

This file now only holds the mock world/group data and the render/event
loop; every panel it draws is a component from gartok.ui, so plugging real
`world`/`guild` data in place of the dicts below is the whole migration.

Generates PNGs: python war_table_v3.py --shot
"""

import pygame

from gartok.ui.camera import MapCamera
from gartok.ui.command_bar import draw_command
from gartok.ui.inspector_panel import draw_inspector
from gartok.ui.map_panel import draw_map
from gartok.ui.roster_panel import draw_roster
from gartok.ui.tokens import T, fonts

# ---------------------------------------------------------------- world
NODES = {
    "ankareth": dict(pos=(0, 0),     name="Ankareth",    terrain="town",  icon="town"),
    "prison":   dict(pos=(-22, -25), name="Prison",      terrain="rock",  icon="keep"),
    "tavern":   dict(pos=(-50, 2),   name="Tavern",      terrain="town",  icon="town"),
    "lumber":   dict(pos=(-22, 28),  name="Lumber Yard", terrain="green", icon="camp"),
    "market":   dict(pos=(22, 28),   name="Market",      terrain="town",  icon="town"),
    "arena":    dict(pos=(30, -38),  name="Arena",       terrain="rock",  icon="keep"),
    "oldroad":  dict(pos=(88, 2),    name="Old Road",    terrain="rock",  icon="camp"),
    "wilds":    dict(pos=(170, -30), name="The Wilds",   terrain="green", icon="camp"),
    "claim":    dict(pos=(196, -48), name="The Claim",   terrain="rock",  icon="keep"),
    "ledger":   dict(pos=(120, 52),  name="Ledger Hold", terrain="town",  icon="keep"),
}

EDGES = [
    ("ankareth", "prison",  1), ("ankareth", "tavern", 1),
    ("ankareth", "lumber",  1), ("ankareth", "market", 1),
    ("ankareth", "arena",   2), ("ankareth", "oldroad", 4),
    ("arena", "oldroad", 3), ("oldroad", "wilds", 6),
    ("oldroad", "ledger", 5), ("wilds", "claim", 2),
]

WASH = {"green": T.WASH_GREEN, "rock": T.WASH_ROCK, "town": T.WASH_TOWN}
REGION_R = {"wilds": 44, "oldroad": 26, "ankareth": 22, "claim": 22,
            "lumber": 22, "arena": 20, "ledger": 20, "prison": 18,
            "tavern": 18, "market": 16}

STATE_LABEL = {"idle": "NO ORDERS", "travel": "TRAVELLING",
               "work": "WORKING", "fight": "IN COMBAT"}
STATE_COLOR = {"idle": T.BRASS, "travel": T.TX_MUTED,
               "work": T.TX_MUTED, "fight": T.BLOOD}


def _adapt_group(g):
    """gartok.ui components take ready-to-draw status (label/colour/busy/
    alert), not the mock's own `state` shorthand -- this is the one place
    that translates between them, standing in for the real adapter a
    screen driving this off `Group`/`Order` objects would need."""
    sub = g["order"] or f"idle at {NODES[g['at']]['name']}" \
        if not isinstance(g["at"], tuple) else g["order"]
    if g["eta"]:
        sub = f"{sub} · {g['eta']}"
    return {**g,
           "state_label": STATE_LABEL[g["state"]],
           "state_color": STATE_COLOR[g["state"]],
           "busy": g["state"] != "idle",
           "needs_orders": g["state"] == "idle",
           "alert": g["state"] == "fight",
           "detail": sub,
           "rations_label": "RATIONS: 3",
           "roster_members": [(name, name, "") for name, _, _ in g["party"]]}


def _inspector_content(g, F):
    blocks = [{"type": "section", "label": "orders"}]
    if g["state"] == "idle":
        if g["at"] == "ankareth":
            blocks += [{"type": "button", "key": "take_work", "label": "take work"},
                      {"type": "button", "key": "bank", "label": "bank"},
                      {"type": "button", "key": "forge", "label": "forge"}]
        elif g["at"] == "lumber":
            blocks.append({"type": "button", "key": "work_shift", "label": "work shift"})
        else:
            blocks.append({"type": "button", "key": "investigate", "label": "investigate"})
    else:
        blocks.append({"type": "button", "key": "recall", "label": "recall",
                       "sub": "turn back to Ankareth", "height": T.S * 6})
    return blocks


def _inspector_bottom(g, F):
    items = [{"type": "button", "key": "manage_gear", "label": "manage gear"},
            {"type": "button", "key": "maintenance", "label": "maintenance  ·  1 h"}]
    if g["state"] == "fight":
        items.append({"type": "button", "key": "resolve_ambush", "label": "resolve the ambush",
                     "sub": f"{g['name']} · the clock is held", "height": T.S * 6,
                     "primary": True, "danger": True, "font": F["bodyb"], "gap_before": T.S * 2})
    return items


# --- groups: the work queue -----------------------------------------
# state: idle (needs orders) | travel | work | fight (holds the clock)
GROUPS = [
    dict(key="mourn",  name="Mourn's escort", lead="Mourn", state="fight",
         at="oldroad", order="Ambushed on the Old Road", eta=None,
         party=[("Mourn", "vanguard", 0.42), ("Isa", "archer", 0.18),
                ("Oder", "hand", 0.70)]),
    dict(key="thal",   name="Thalthrog's band", lead="Thalthrog", state="idle",
         at="ankareth", order=None, eta=None,
         party=[("Thalthrog", "vanguard", 1.0), ("Bren", "hand", 0.55),
                ("Sella", "healer", 1.0)]),
    dict(key="sable",  name="Sable & Iron", lead="Sable", state="idle",
         at="lumber", order=None, eta=None,
         party=[("Sable", "hand", 0.88), ("Iron", "vanguard", 0.95)]),
    dict(key="vey",    name="Vey's outriders", lead="Vey", state="travel",
         at=("ankareth", "oldroad", 0.62), order="to Old Road", eta="09:00",
         party=[("Vey", "archer", 1.0), ("Hask", "hand", 1.0),
                ("Rill", "hand", 0.8), ("Tam", "vanguard", 0.9)]),
    dict(key="korren", name="Korren's diggers", lead="Korren", state="work",
         at="claim", order="Working the seam", eta="14:00",
         party=[("Korren", "hand", 1.0), ("Bel", "hand", 0.9),
                ("Ost", "hand", 1.0)]),
]

EVENTS = [
    ("mourn",  4.0,  4.0,  "Ambush", T.BLOOD),
    ("vey",    4.0, 14.0,  "reaches Old Road", T.TX_MUTED),
    ("korren", 4.0, 14.0,  "seam worked out", T.TX_MUTED),
    ("thal",   4.0, 22.0,  "forged gear ready", T.TX_MUTED),
    ("sable",  4.0, 18.0,  "work shift ends", T.TX_MUTED),
]


# ---------------------------------------------------------------- render
def render(scr, size, cam, selected, split_target=None, mpos=(0, 0)):
    scr.fill(T.TABLE)
    F = fonts()

    cmd = pygame.Rect(0, 0, size[0], T.S * 9)
    margin = T.S * 2
    bh = size[1] - cmd.bottom - margin
    left = pygame.Rect(0, cmd.bottom, T.S * 38, bh)
    right = pygame.Rect(size[0] - T.S * 40, cmd.bottom, T.S * 40, bh)
    mid = pygame.Rect(left.right, cmd.bottom, right.x - left.right, bh)

    adapted = [_adapt_group(g) for g in GROUPS]

    minimap_box, minimap_params = draw_map(scr, F, mid, cam, NODES, EDGES, WASH, REGION_R,
                                           adapted, selected, mpos)

    messages = [
        ("Title defense due in 2 days", T.BLOOD),
        ("Contract expiring today", T.BRASS),
    ]
    metrics = [("members", "12"), ("gold", "59"), ("reputation", "2")]
    cmd_hover, _cmd_buttons = draw_command(scr, F, cmd, "1", "04:00", messages, metrics, mpos)

    roster_rects, _split_member_rects, _split_confirm_rect, _merge_rects = draw_roster(
        scr, F, left, adapted, EVENTS, selected, split_target, mpos=mpos)

    g_sel = next(g for g in GROUPS if g["key"] == selected)
    g_sel_adapted = next(g for g in adapted if g["key"] == selected)
    where = NODES[g_sel["at"]]["name"] if not isinstance(g_sel["at"], tuple) \
        else f"between {NODES[g_sel['at'][0]]['name']} and {NODES[g_sel['at'][1]]['name']}"
    draw_inspector(scr, F, right, g_sel["name"], g_sel_adapted["state_label"],
                   g_sel_adapted["state_color"], where, g_sel["party"],
                   _inspector_content(g_sel, F), _inspector_bottom(g_sel, F), mpos)

    # tooltips on top of everything
    for h_data in [cmd_hover]:
        if h_data:
            hx, hy, htxt, hcol = h_data
            t_img = F["body"].render(htxt, True, T.TX)
            t_rect = t_img.get_rect(midbottom=(hx, hy - 12))
            t_bg = t_rect.inflate(16, 16)

            if t_bg.right > size[0] - T.S:
                t_bg.right = size[0] - T.S
            if t_bg.left < T.S:
                t_bg.left = T.S
            t_rect.center = t_bg.center

            pygame.draw.rect(scr, T.TABLE, t_bg)
            pygame.draw.rect(scr, hcol, t_bg, 1)
            scr.blit(t_img, t_rect)

    return roster_rects, minimap_box, minimap_params


def main():
    pygame.init()
    size = (1600, 900)
    win = pygame.display.set_mode(size, pygame.RESIZABLE)
    pygame.display.set_caption("GARTOK — war table v3 prototype")

    cam = MapCamera(NODES)
    selected = "thal"
    split_target = None
    pan_anchor = None

    run = True
    while run:
        frame = pygame.Surface(size).convert()
        mpos = pygame.mouse.get_pos()
        roster_rects, minimap_box, (ox, oy, mz) = render(frame, size, cam, selected, split_target, mpos)

        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                run = False
            elif e.type == pygame.VIDEORESIZE:
                size = e.size
            elif e.type == pygame.MOUSEWHEEL:
                cam.zoom_at(pygame.mouse.get_pos(), e.y)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button in (2, 3):  # middle/right click to pan
                    if cam.rect.collidepoint(e.pos):
                        pan_anchor = (e.pos, list(cam.cam))
                elif e.button == 1:     # left click
                    if minimap_box.collidepoint(e.pos):
                        # minimap pixel -> world coord: e.pos = (ox + wx*mz, oy + wy*mz)
                        wx = (e.pos[0] - ox) / mz
                        wy = (e.pos[1] - oy) / mz
                        cam.recenter(wx, wy)
                    else:
                        for card_rect, group_key, gear_rect in roster_rects:
                            if gear_rect.collidepoint(e.pos):
                                split_target = group_key if split_target != group_key else None
                                break
                            elif card_rect.collidepoint(e.pos):
                                selected = group_key
                                break
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button in (2, 3):
                    pan_anchor = None
            elif e.type == pygame.MOUSEMOTION:
                if pan_anchor is not None:
                    (ax, ay), cam0 = pan_anchor
                    cam.cam = list(cam0)
                    cam.pan_px(e.pos[0] - ax, e.pos[1] - ay)

        win.blit(frame, (0, 0))
        pygame.display.flip()
        pygame.time.wait(16)

    pygame.quit()


if __name__ == "__main__":
    main()

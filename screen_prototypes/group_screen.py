"""
GARTOK Tactical - tela de GRUPO (v6)

Uma tela, duas visoes, o mesmo trilho lateral:

  BAGS   - o personagem como compartimento. 3 colunas fixadas, mochila visivel,
           arrastar entre colunas ou clicar o item e escolher o destino.
  CARGO  - a mesma banda vista como carga: tudo em uma tabela, ordenavel por
           peso, com selecao em lote pra preparar venda ou redistribuicao.

Trocar de visao nao perde selecao nem quem esta fixado.
Mercado e strongbox NAO vivem aqui: sao lugares, tem tela propria.

  python group_v6.py --shot
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pygame

from screens_v4 import (T, fonts, mix, text, caps, hline, header, footer,
                        load_bar, role_mark, hp_color)
from gartok.ui.primitives import draw_button, contained

# ---------------------------------------------------------------- dados
MEMBERS = [
    dict(k="grokvyr",  nm="Grokvyrdrixek", role="vanguard", kg=8.5,  cap=9.0,
         hp=(3, 10), hand="Club", off=None, body=None,
         pack=[("Iron shackles", "tool", 1.0, 1), ("Rope, 50 ft", "tool", 3.0, 1),
               ("Tinderbox", "camp", 0.5, 1)]),
    dict(k="grokhrom", nm="Grokhromlysfel", role="healer", kg=2.5, cap=6.0,
         hp=(1, 9), hand="Quarterstaff", off=None, body=None,
         pack=[("Holy symbol", "relic", 0.5, 1)]),
    dict(k="vyrkael",  nm="Vyrkaelbrae", role="hand", kg=1.5, cap=23.0,
         hp=(8, 8), hand="Dagger", off=None, body="Cloak",
         pack=[("Lockpicks", "tool", 0.3, 1)]),
    dict(k="sella",    nm="Sella Vond", role="archer", kg=14.0, cap=15.0,
         hp=(6, 7), hand="Shortbow", off="Quiver", body="Leather",
         pack=[("Arrows", "ammo", 0.05, 24), ("Bedroll", "camp", 2.0, 1)]),
    dict(k="bren",     nm="Bren Oduld", role="hand", kg=31.0, cap=24.0,
         hp=(9, 11), hand="Felling axe", off="Shield", body="Mail",
         pack=[("Pick", "tool", 4.0, 1)]),
    dict(k="tam",      nm="Tam Reddle", role="hand", kg=46.0, cap=20.0,
         hp=(5, 9), hand="Spear", off=None, body="Padded",
         pack=[("Iron ore", "goods", 1.0, 40), ("Silver candlesticks", "loot", 2.0, 3),
               ("Felling axe", "tool", 6.0, 1)]),
    dict(k="oder",     nm="Oder Vash", role="vanguard", kg=12.0, cap=18.0,
         hp=(7, 12), hand="Mace", off="Shield", body="Mail", pack=[]),
    dict(k="isa",      nm="Isa Quill", role="archer", kg=5.0, cap=12.0,
         hp=(4, 8), hand="Sling", off=None, body=None, pack=[]),
    dict(k="rill",     nm="Rill", role="hand", kg=3.0, cap=14.0,
         hp=(6, 6), hand="Knife", off=None, body=None, pack=[]),
    dict(k="hask",     nm="Hask Dun", role="hand", kg=9.0, cap=21.0,
         hp=(9, 9), hand="Hammer", off=None, body="Padded", pack=[]),
]
BY_KEY = {m["k"]: m for m in MEMBERS}
PINNED = ["grokvyr", "bren", "tam"]
SELECTED = "tam"
SELECTED_ITEMS = {("tam", 0): 5, ("tam", 1): 1} # mock de bulk selection
LOCKED_ITEMS = {("tam", 2)}                     # mock de itens trancados
COLUMN_SCROLL = {}                  # scroll da mochila por membro -- estado de tela, nao do personagem
OPEN_MENU = None                    # menu de contexto aberto: (u_key, idx, x, y)

TAG_COLOR = {"goods": T.TX_FAINT, "tool": T.BRASS_DIM, "armor": T.TX_MUTED,
             "weapon": T.TX_MUTED, "ammo": T.TX_FAINT, "loot": T.BRASS,
             "relic": T.BRASS, "wear": T.TX_FAINT, "camp": T.TX_FAINT}

MISSIONS = [
    dict(uid="m1", unit_uid="grokvyr", name="Clear the Warrens", goal_qty=12, goal_item="Goblin ear",
         deadline_day=14, current_day=12, prog=8),
    dict(uid="m2", unit_uid="bren", name="Bankers' Trust", goal_qty=0, goal_item="",
         deadline_day=20, current_day=12, prog=0)
]


def short(nm):
    return nm.split()[0][:8]


def _reindex_after_pop(u_key, popped_idx):
    """pack.pop(popped_idx) shifts every later stack down by one slot --
    keep SELECTED_ITEMS/LOCKED_ITEMS pointing at the same physical item."""
    for k in [k for k in SELECTED_ITEMS if k[0] == u_key and k[1] > popped_idx]:
        SELECTED_ITEMS[(u_key, k[1] - 1)] = SELECTED_ITEMS.pop(k)
    for k in [k for k in LOCKED_ITEMS if k[0] == u_key and k[1] > popped_idx]:
        LOCKED_ITEMS.discard(k)
        LOCKED_ITEMS.add((u_key, k[1] - 1))


# ---------------------------------------------------------------- trilho
def rail(s, F, rect, view):
    """
    O trilho e o que faz a tela escalar pra 10 e o que torna o arrastar util:
    todo nome aqui e um alvo de soltar, esteja a coluna aberta ou nao.
    """
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.line(s, T.STEEL_LINE, (rect.right - 1, rect.y),
                     (rect.right - 1, rect.bottom), 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2
    caps(s, F["micro"], "band  ·  6 of 10", (x, y), T.TX_FAINT)
    overextension = 2 # mock penalty
    if overextension > 0:
        caps(s, F["microb"], f"(-{overextension} mental def)", (x + w, y), T.BLOOD, right=True)
    else:
        caps(s, F["micro"], "free", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 3

    hits = {}
    for m in MEMBERS:
        pinned = m["k"] in PINNED
        r = pygame.Rect(x, y, w, T.S * 7)
        hits[m["k"]] = r
        pygame.draw.rect(s, T.STEEL_HI if pinned else T.TABLE, r)
        pygame.draw.rect(s, T.BRASS if m["k"] == SELECTED else T.STEEL_LINE, r, 1)
        if pinned:                       # marca de fixado: a coluna esta aberta
            pygame.draw.rect(s, T.BRASS, pygame.Rect(r.x, r.y, 3, r.h))
        role_mark(s, (r.x + T.S * 2, r.y + T.S * 2), m["role"], T.TX_MUTED)
        text(s, F["body"], short(m["nm"]), (r.x + T.S * 4, r.y + T.S - 2),
             T.TX if pinned else T.TX_MUTED)
        free = m["cap"] - m["kg"]
        caps(s, F["micro"], f"{free:+.1f}", (r.right - T.S, r.y + T.S), 
             T.BLOOD if free < 0 else T.GREEN if free > 4 else T.TX_MUTED, right=True)
        load_bar(s, pygame.Rect(r.x + T.S, r.y + T.S * 4, r.w - T.S * 2, 6),
                 m["kg"] / m["cap"], m["kg"] > m["cap"])
        y = r.bottom + 4

    y += T.S
    hline(s, x, x + w, y)
    return hits


def view_switch(s, F, pos, view, mpos=(-1, -1)):
    rects = {}
    for i, lab in enumerate(("bags", "cargo")):
        w = T.S * 14
        r = pygame.Rect(pos[0] + i * w, pos[1], w, T.S * 4)
        rects[lab] = r
        on = lab == view
        draw_button(s, F, r, lab, ghost=not on, mpos=mpos)
        if on:
            pygame.draw.line(s, T.BRASS, (r.x, r.bottom - 2), (r.right, r.bottom - 2), 2)
    return rects


# ---------------------------------------------------------------- visao BAGS
def slot(s, F, rect, label, val, note=None):
    caps(s, F["micro"], label, (rect.x, rect.y - 13), T.TX_FAINT)
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    with contained(s, rect.inflate(-16, 0)):
        text(s, F["body"], val or "empty", (rect.x + T.S, rect.centery - 8),
             T.TX_FAINT if not val else T.TX)
    if note:
        caps(s, F["micro"], note, (rect.right - T.S, rect.centery - 5), T.BRASS,
             right=True)
    return rect.bottom + T.S * 3


def item_row(s, F, rect, it, selected_qty=0, is_locked=False, mpos=(-1, -1)):
    nm, tag, kg, qty = it
    pygame.draw.rect(s, mix(T.BRASS, T.STEEL, .85) if selected_qty > 0 else T.TABLE, rect)
    pygame.draw.rect(s, T.BRASS if selected_qty > 0 else T.STEEL_LINE, rect, 1)
    
    if is_locked:
        text(s, F["body"], "🔒", (rect.x + T.S, rect.centery - 13), T.TX)
        text(s, F["body"], nm, (rect.x + T.S + 20, rect.centery - 13), T.TX_FAINT)
        caps(s, F["micro"], tag, (rect.x + T.S + 20, rect.centery + 3), TAG_COLOR[tag])
    else:
        text(s, F["body"], nm, (rect.x + T.S, rect.centery - 13), T.TX)
        caps(s, F["micro"], tag, (rect.x + T.S, rect.centery + 3), TAG_COLOR[tag])
    
    dots_r = pygame.Rect(rect.right - T.S * 3, rect.centery - 10, 20, 20)
    draw_button(s, F, dots_r, "⋮", ghost=True, mpos=mpos)

    if selected_qty > 0:
        caps(s, F["microb"], f"{selected_qty} / {qty}", (rect.right - T.S * 7, rect.centery - 12),
             T.BRASS, right=True)
    elif qty > 1:
        caps(s, F["microb"], f"×{qty}", (rect.right - T.S * 7, rect.centery - 12),
             T.TX_MUTED, right=True)

    total = kg * qty
    caps(s, F["micro"], f"{total:.1f} kg", (rect.right - T.S * 7, rect.centery + 2),
         T.BLOOD if total >= 10 else T.TX_FAINT, right=True)

    return dots_r


def member_column(s, F, rect, m, mpos=(-1, -1), item_hits=None, column_scroll=None):
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    over = m["kg"] > m["cap"]
    x, w = rect.x + T.S * 2, rect.w - T.S * 4

    head = pygame.Rect(rect.x, rect.y, rect.w, T.S * 11)
    pygame.draw.rect(s, T.STEEL_HI, head)
    hline(s, head.x, head.right, head.bottom)
    role_mark(s, (x + 8, head.y + T.S * 2 + 2), m["role"], T.TX_MUTED)
    text(s, F["nameb"], m["nm"], (x + T.S * 3, head.y + T.S), T.TX)
    btn_r = pygame.Rect(head.right - T.S * 2 - 20, head.y + T.S + 2, 20, 20)
    draw_button(s, F, btn_r, "?", ghost=True, mpos=mpos)
    load_bar(s, pygame.Rect(x, head.y + T.S * 5, w, 8), m["kg"] / m["cap"], over)
    caps(s, F["micro"], f"{m['kg']:.1f} / {m['cap']:.0f} kg",
         (x, head.y + T.S * 7 + 2), T.BLOOD if over else T.TX_MUTED)
    if over:
        caps(s, F["micro"], f"+{m['kg'] - m['cap']:.1f} kg",
             (head.right - T.S * 2, head.y + T.S * 7 + 2), T.BLOOD, right=True)

    y = head.bottom + T.S * 4
    hw = (w - T.S) // 2
    r1 = pygame.Rect(x, y, hw, T.S * 5)
    slot(s, F, r1, "main hand", m["hand"])
    r2 = pygame.Rect(x + hw + T.S, y, hw, T.S * 5)
    y = slot(s, F, r2, "off hand", m["off"])
    y = slot(s, F, pygame.Rect(x, y, w, T.S * 5), "armor", m["body"])

    carried = sum(kg * q for _, _, kg, q in m["pack"])
    caps(s, F["micro"], f"pack  ·  {len(m['pack'])} stacks", (x, y), T.TX_FAINT)
    caps(s, F["micro"], f"{carried:.1f} kg", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 3

    list_rect = pygame.Rect(x, y, w, rect.bottom - T.S * 2 - y)

    if m["pack"]:
        column_scroll = column_scroll if column_scroll is not None else {}
        scroll = column_scroll.get(m["k"], 0)
        content_h = len(m["pack"]) * (T.S * 6 + T.S)
        max_scroll = max(0, content_h - list_rect.h)
        scroll = column_scroll[m["k"]] = max(0, min(scroll, max_scroll))

        with contained(s, list_rect):
            iy = list_rect.y - scroll
            for i, it in enumerate(m["pack"]):
                r = pygame.Rect(x, iy, w - (8 if max_scroll > 0 else 0), T.S * 6)
                eff_mpos = mpos if list_rect.collidepoint(mpos) else (-1, -1)
                sel_qty = SELECTED_ITEMS.get((m["k"], i), 0)
                is_lock = (m["k"], i) in LOCKED_ITEMS
                dots_r = item_row(s, F, r, it, selected_qty=sel_qty, is_locked=is_lock, mpos=eff_mpos)
                if item_hits is not None:
                    item_hits.append((r, m["k"], i, dots_r, it[3], None))
                iy = r.bottom + T.S
                
        if max_scroll > 0:
            sb_bg = pygame.Rect(list_rect.right - 4, list_rect.y, 4, list_rect.h)
            pygame.draw.rect(s, T.STEEL_LINE, sb_bg)
            sb_h = max(20.0, list_rect.h * (list_rect.h / content_h))
            sb_y = list_rect.y + (list_rect.h - sb_h) * (scroll / max_scroll)
            pygame.draw.rect(s, T.BRASS, pygame.Rect(sb_bg.x, sb_y, 4, sb_h))
    else:
        caps(s, F["micro"], "carrying nothing", (x, y), T.TX_FAINT)


def context_menu(s, F, anchor, u_key, idx, mpos=(-1, -1)):
    hit_zones = []
    source_m = BY_KEY[u_key]
    it = source_m["pack"][idx]
    nm, tag, kg, total_qty = it
    
    sel_qty = SELECTED_ITEMS.get((u_key, idx), 0)
    qty = sel_qty if sel_qty > 0 else total_qty
    
    drawn_members = [m for m in MEMBERS[:6] if m["k"] != u_key]
    h = T.S * 14 + len(drawn_members) * (T.S * 4 + 2) + T.S * 2
    w = T.S * 30
    
    px, py = anchor[0] + 16, anchor[1] + 16
    if px + w > s.get_width():
        px = anchor[0] - w - 16
    if py + h > s.get_height():
        py = anchor[1] - h - 16
        
    r = pygame.Rect(px, py, w, h)
    
    pygame.draw.rect(s, (8, 9, 11), r.move(4, 5))
    pygame.draw.rect(s, T.STEEL_HI, r)
    pygame.draw.rect(s, T.BRASS, r, 1)
    
    y = r.y + T.S * 2
    is_locked = (u_key, idx) in LOCKED_ITEMS
    lock_r = pygame.Rect(r.x + T.S, y, r.w - T.S * 2, T.S * 4)
    draw_button(s, F, lock_r, "🔒 Unlock Item" if is_locked else "🔓 Lock Item", ghost=True, mpos=mpos)
    hit_zones.append((lock_r, "lock"))
    y += T.S * 5
    
    drop_r = pygame.Rect(r.x + T.S, y, r.w - T.S * 2, T.S * 4)
    draw_button(s, F, drop_r, "Drop", ghost=True, mpos=mpos)
    hit_zones.append((drop_r, "drop"))
    y += T.S * 5
    
    hline(s, r.x, r.right, y)
    y += T.S * 2
    
    label = f"{nm} ×{qty}" if qty > 1 else nm
    caps(s, F["microb"], f"hand {label} to", (r.x + T.S * 2, y), T.TX)
    caps(s, F["micro"], f"{kg * qty:.1f} kg", (r.x + T.S * 2, y + T.S * 2), T.TX_FAINT)
    y += T.S * 5
    
    for m in drawn_members:
        free = m["cap"] - m["kg"]
        ok = free >= (kg * qty)
        row = pygame.Rect(r.x + T.S, y, r.w - T.S * 2, T.S * 4)
        
        bg_col = T.STEEL_HI if not row.collidepoint(mpos) else T.STEEL
        pygame.draw.rect(s, bg_col, row)
        
        text(s, F["body"], short(m["nm"]), (row.x + T.S, row.centery - 8),
             T.TX if ok else T.TX_FAINT)
        caps(s, F["micro"], f"{free:+.1f} kg free" if ok else f"only {free:+.1f} kg",
             (row.right - T.S, row.centery - 5), T.GREEN if ok else T.TX_FAINT,
             right=True)
        hit_zones.append((row, ("transfer", m["k"], qty)))
        y = row.bottom + 2
        
    return hit_zones


# ---------------------------------------------------------------- visao CARGO
def cargo_view(s, F, rect, mpos=(-1, -1), item_hits=None):
    rows = []
    for m in MEMBERS:
        for idx, it in enumerate(m["pack"]):
            rows.append((it, m, idx))
    rows.sort(key=lambda t: -t[0][2] * t[0][3])

    hd = pygame.Rect(rect.x, rect.y, rect.w, T.S * 3)
    pygame.draw.rect(s, T.TABLE, hd)
    for lab, dx in (("item", T.S * 5), ("weight", T.S * 40), ("carried by", T.S * 52)):
        caps(s, F["micro"], lab, (rect.x + dx, hd.centery - 5), T.TX_FAINT)
    caps(s, F["micro"], "↓", (rect.x + T.S * 49, hd.centery - 5), T.BRASS)
    hline(s, rect.x, rect.right, hd.bottom)

    y = hd.bottom
    sel_count, sel_kg = 0, 0.0
    for it, m, idx in rows:
        nm, tag, kg, qty = it
        r = pygame.Rect(rect.x, y, rect.w, T.S * 5)
        sel_qty = SELECTED_ITEMS.get((m["k"], idx), 0)
        is_lock = (m["k"], idx) in LOCKED_ITEMS
        if sel_qty > 0:
            sel_count += sel_qty
            sel_kg += kg * sel_qty
            
        pygame.draw.rect(s, mix(T.BRASS, T.STEEL, .88) if sel_qty > 0 else T.STEEL, r)
        hline(s, r.x, r.right, r.bottom - 1)
        cb = pygame.Rect(r.x + T.S * 2, r.centery - 6, 12, 12)
        pygame.draw.rect(s, T.BRASS if sel_qty > 0 else T.STEEL_LINE, cb, 1)
        if sel_qty > 0:
            pygame.draw.lines(s, T.BRASS, False, [(cb.x + 3, cb.centery),
                              (cb.centerx, cb.bottom - 4), (cb.right - 3, cb.y + 3)], 2)
                              
        label = f"{nm} ({sel_qty}/{qty})" if sel_qty > 0 else (f"{nm} ×{qty}" if qty > 1 else nm)
        text(s, F["body"], label, (r.x + T.S * 5, r.centery - 8), T.TX)
        caps(s, F["micro"], tag, (r.x + T.S * 5 + F["body"].size(label)[0] + T.S,
             r.centery - 5), TAG_COLOR[tag])
             
        dots_r = pygame.Rect(r.right - T.S * 3, r.centery - 10, 20, 20)
        draw_button(s, F, dots_r, "⋮", ghost=True, mpos=mpos)
        cc = pygame.Rect(r.x + T.S * 52, r.centery - 12, T.S * 13, T.S * 3)

        if item_hits is not None:
            item_hits.append((r, m["k"], idx, dots_r, qty, cc))

        total = kg * qty
        text(s, F["bodyb"] if total >= 10 else F["body"], f"{total:.1f} kg",
             (r.x + T.S * 48, r.centery - 8), T.BLOOD if total >= 10 else T.TX_MUTED,
             right=True)
        pygame.draw.rect(s, T.TABLE, cc)
        pygame.draw.rect(s, T.STEEL_LINE, cc, 1)
        caps(s, F["micro"], short(m["nm"]), (cc.x + T.S, cc.centery - 5), T.TX_MUTED)
        caps(s, F["micro"], "▾", (cc.right - T.S, cc.centery - 5), T.TX_FAINT, right=True)
        y = r.bottom

    if sel_count > 0:
        bulk = pygame.Rect(rect.x, rect.bottom - T.S * 7, rect.w, T.S * 7)
        pygame.draw.rect(s, T.TABLE, bulk)
        hline(s, bulk.x, bulk.right, bulk.y, T.BRASS)
        caps(s, F["microb"], f"{sel_count} selected  ·  {sel_kg:.1f} kg",
             (bulk.x + T.S * 3, bulk.centery - 6), T.BRASS)
        bx = bulk.right - T.S * 3
        for lab, prim in (("hand to…", True), ("split stack", False), ("drop", False)):
            w = T.S * 16
            draw_button(s, F, pygame.Rect(bx - w, bulk.y + T.S * 2, w, bulk.h - T.S * 4), lab,
                   primary=prim, mpos=mpos)
            bx -= w + T.S


# ---------------------------------------------------------------- telas
def screen(size, view="bags", main_tab="gear", mpos=(-1, -1), bags_scroll=0):
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    head = pygame.Rect(0, 0, size[0], T.S * 9)
    bar = pygame.Rect(0, head.bottom, size[0], T.S * 7)
    left = pygame.Rect(0, bar.bottom, T.S * 32, size[1] - bar.bottom - T.S * 2)
    mid = pygame.Rect(left.right, bar.bottom, size[0] - left.right, size[1] - bar.bottom - T.S * 2)

    tab_rects = header(s, F, head, "Grokvyrdrixek's Band",
           "6 / 10 members  ·  ankareth  ·  no orders",
           ["gear", "quests"], main_tab, mpos=mpos)

    # Rename button mock
    tw = F["titleb"].size("Grokvyrdrixek's Band")[0]
    draw_button(s, F, pygame.Rect(T.S * 6 + tw + T.S * 2, T.S * 2 + 4, T.S * 3, T.S * 3), "✎", ghost=True, mpos=mpos)

    rail_hits = {}
    item_hits = []
    view_rects = {}

    if main_tab == "gear":
        # barra de estado da banda + troca de visao
        pygame.draw.rect(s, T.TABLE, bar)
        hline(s, bar.x, bar.right, bar.bottom - 1)
        view_rects = view_switch(s, F, (T.S * 2, bar.y + T.S * 2), view, mpos=mpos)
        x = T.S * 32
        for lab, val, col, sub in (("band load", "103 / 97 kg", T.BLOOD, ""),
                                   ("rations", "0 days", T.BLOOD, "hunger in 6 h")):
            caps(s, F["micro"], lab, (x, bar.centery - 13), T.TX_FAINT)
            text(s, F["bodyb"], val, (x, bar.centery), col)
            if sub:
                caps(s, F["micro"], sub, (x + F["bodyb"].size(val)[0] + T.S, bar.centery + 3),
                     T.TX_FAINT)
            x += T.S * 34
        draw_button(s, F, pygame.Rect(bar.right - T.S * 24, bar.y + T.S * 2, T.S * 22,
                                 bar.h - T.S * 4), "distribute load", mpos=mpos)

        rail_hits = rail(s, F, left, view)

        if view == "bags":
            gap = T.S * 2
            n = len(PINNED)
            if n > 0:
                n_vis = min(n, 6)
                cw = (mid.w - gap * (n_vis + 1)) // n_vis

                max_scroll = max(0, n * (cw + gap) + gap - mid.w)
                bags_scroll = max(0, min(bags_scroll, max_scroll))

                with contained(s, mid):
                    for i, k in enumerate(PINNED):
                        x = mid.x + gap + i * (cw + gap) - bags_scroll
                        r = pygame.Rect(x, mid.y + gap, cw, mid.h - gap * 2)

                        if r.right > mid.x and r.left < mid.right:
                            member_column(s, F, r, BY_KEY[k], mpos=mpos, item_hits=item_hits,
                                          column_scroll=COLUMN_SCROLL)

                if max_scroll > 0:
                    sb_bg = pygame.Rect(mid.x + gap, mid.bottom - gap + 2, mid.w - gap * 2, 4)
                    pygame.draw.rect(s, T.STEEL_LINE, sb_bg)
                    sb_w = max(40.0, sb_bg.w * (mid.w / (n * (cw + gap) + gap)))
                    sb_x = sb_bg.x + (sb_bg.w - sb_w) * (bags_scroll / max_scroll)
                    pygame.draw.rect(s, T.BRASS, pygame.Rect(sb_x, sb_bg.y, sb_w, sb_bg.h))

        else:
            cargo_view(s, F, mid.inflate(-T.S * 2, -T.S * 2), mpos=mpos, item_hits=item_hits)

        # Draw "back to map" floating at bottom left
        draw_button(s, F, pygame.Rect(T.S * 2, size[1] - T.S * 8, T.S * 28, T.S * 4), "back to map", primary=True, mpos=mpos)
    elif main_tab == "quests":
        y = head.bottom + T.S * 4
        area = pygame.Rect(T.S * 4, y, size[0] - T.S * 8, size[1] - head.bottom - T.S * 8)
        
        if not MISSIONS:
            text(s, F["body"], "No active quests for this group.", area.center, T.TX_MUTED, center=True)
        else:
            for m in MISSIONS:
                r = pygame.Rect(area.x, y, min(600, area.w), 80)
                pygame.draw.rect(s, T.TABLE, r)
                pygame.draw.rect(s, T.STEEL_LINE, r, 1)
                
                text(s, F["titleb"], m["name"], (r.x + T.S * 3, r.y + T.S * 2), T.TX)
                uname = BY_KEY.get(m["unit_uid"], {}).get("nm", "Unknown")
                text(s, F["body"], f"Accepted by {uname}", (r.x + T.S * 3, r.y + 40), T.TX_FAINT)
                
                days_left = m["deadline_day"] - m["current_day"]
                dcol = T.BLOOD if days_left <= 1 else T.BRASS if days_left <= 3 else T.GREEN
                text(s, F["body"], f"{max(0, days_left)} day(s) left", (r.right - T.S * 3, r.y + T.S * 2), dcol, right=True)
                
                if m["goal_qty"] > 0:
                    text(s, F["body"], f'{m["prog"]} / {m["goal_qty"]} {m["goal_item"]}', (r.right - T.S * 3, r.y + 40), 
                         T.GREEN if m["prog"] >= m["goal_qty"] else T.TX, right=True)
                else:
                    text(s, F["body"], "Delivery", (r.right - T.S * 3, r.y + 40), T.TX, right=True)
                     
                y += r.h + T.S * 3

        draw_button(s, F, pygame.Rect(T.S * 2, size[1] - T.S * 8, T.S * 28, T.S * 4), "back to map", primary=True, mpos=mpos)

    # Toast mock
    notice = "Tam picks the lock -- 5 gems inside."
    if notice:
        tw = F["body"].size(notice)[0] + T.S * 6
        tr = pygame.Rect((size[0] - tw) // 2, size[1] - T.S * 16, tw, 40)
        pygame.draw.rect(s, T.STEEL_HI, tr)
        pygame.draw.rect(s, T.BRASS, tr, 1)
        text(s, F["body"], notice, tr.center, T.TX, center=True)

    return s, tab_rects, rail_hits, item_hits, view_rects


def main():
    global SELECTED_ITEMS, LOCKED_ITEMS, OPEN_MENU
    pygame.init()
    size = (1600, 900)
    if "--shot" in sys.argv:
        pygame.display.set_mode(size, pygame.HIDDEN)
        pygame.image.save(screen(size, "bags")[0], "gartok_v6_bags.png")
        pygame.image.save(screen(size, "cargo")[0], "gartok_v6_cargo.png")
        pygame.quit()
        return
    win = pygame.display.set_mode(size, pygame.RESIZABLE)
    view = "bags"
    main_tab = "gear"
    bags_scroll = 0
    run = True
    while run:
        size = win.get_size()
        mpos = pygame.mouse.get_pos()
        surf, tab_rects, rail_hits, item_hits, view_rects = screen(size, view, main_tab, mpos, bags_scroll=bags_scroll)
        menu_hits = []
        if OPEN_MENU:
            u_key, idx, mx, my = OPEN_MENU
            menu_hits = context_menu(surf, fonts(), (mx, my), u_key, idx, mpos=mpos)
            
        win.blit(surf, (0, 0))
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                run = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    run = False
            elif e.type == pygame.MOUSEWHEEL:
                mpos = pygame.mouse.get_pos()
                gap = T.S * 2
                n = len(PINNED)
                if n > 0:
                    n_vis = min(n, 6)
                    cw = (size[0] - T.S * 32 - gap * (n_vis + 1)) // n_vis
                    mid_x = T.S * 32
                    mid_y = T.S * 16
                    mid_w = size[0] - mid_x
                    mid_h = size[1] - T.S * 16 - T.S * 2
                    
                    mods = pygame.key.get_mods()
                    is_shift = mods & pygame.KMOD_SHIFT
                    
                    if getattr(e, 'x', 0) != 0:
                        bags_scroll += e.x * 60
                    elif is_shift and view == "bags":
                        bags_scroll -= getattr(e, 'y', 0) * 60
                    else:
                        for i, k in enumerate(PINNED):
                            x = mid_x + gap + i * (cw + gap) - bags_scroll
                            r = pygame.Rect(x, mid_y + gap, cw, mid_h - gap * 2)
                            if r.collidepoint(mpos) and r.right > mid_x and r.left < mid_x + mid_w:
                                COLUMN_SCROLL[k] = COLUMN_SCROLL.get(k, 0) - getattr(e, 'y', 0) * 30
                    
                    max_scroll = max(0, n * (cw + gap) + gap - mid_w)
                    bags_scroll = max(0, min(bags_scroll, max_scroll))
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button in (1, 3):
                    mpos = e.pos
                    mods = pygame.key.get_mods()
                    is_shift = mods & pygame.KMOD_SHIFT
                    amt = 10 if is_shift else 1
                    
                    clicked_item = False
                    
                    if OPEN_MENU:
                        u_key, idx, _, _ = OPEN_MENU
                        clicked_menu = False
                        for zone_r, action in menu_hits:
                            if zone_r.collidepoint(mpos):
                                clicked_menu = True
                                if action == "lock":
                                    pair = (u_key, idx)
                                    if pair in LOCKED_ITEMS:
                                        LOCKED_ITEMS.remove(pair)
                                    else:
                                        LOCKED_ITEMS.add(pair)
                                elif action == "drop":
                                    pass # mock
                                elif isinstance(action, tuple) and action[0] == "transfer":
                                    target_k = action[1]
                                    trans_qty = action[2]
                                    
                                    source_m = BY_KEY[u_key]
                                    it = source_m["pack"][idx]
                                    nm, tag, kg, total_qty = it
                                    
                                    target_m = BY_KEY[target_k]
                                    
                                    # Add to target
                                    found = False
                                    for t_idx, t_it in enumerate(target_m["pack"]):
                                        if t_it[0] == nm and t_it[1] == tag:
                                            target_m["pack"][t_idx] = (nm, tag, kg, t_it[3] + trans_qty)
                                            found = True
                                            break
                                    if not found:
                                        target_m["pack"].append((nm, tag, kg, trans_qty))
                                        
                                    target_m["kg"] += kg * trans_qty
                                    source_m["kg"] -= kg * trans_qty
                                    
                                    if trans_qty >= total_qty:
                                        source_m["pack"].pop(idx)
                                        pair = (u_key, idx)
                                        if pair in SELECTED_ITEMS:
                                            del SELECTED_ITEMS[pair]
                                        if pair in LOCKED_ITEMS:
                                            LOCKED_ITEMS.remove(pair)
                                        _reindex_after_pop(u_key, idx)
                                    else:
                                        source_m["pack"][idx] = (nm, tag, kg, total_qty - trans_qty)
                                        SELECTED_ITEMS.pop((u_key, idx), None)
                                        
                                OPEN_MENU = None
                                break
                                
                        if not clicked_menu:
                            OPEN_MENU = None
                        continue

                    for r, u_key, idx, dots_r, max_qty, cc in item_hits:
                        if dots_r.collidepoint(mpos) and e.button == 1:
                            clicked_item = True
                            OPEN_MENU = (u_key, idx, mpos[0], mpos[1])
                            break
                        elif cc and cc.collidepoint(mpos):
                            # "carried by" reassignment isn't wired up yet --
                            # swallow the click instead of silently changing selection
                            clicked_item = True
                            break
                        elif r.collidepoint(mpos):
                            clicked_item = True
                            pair = (u_key, idx)
                            cur = SELECTED_ITEMS.get(pair, 0)
                            if e.button == 1:
                                SELECTED_ITEMS[pair] = min(max_qty, cur + amt)
                            elif e.button == 3:
                                new_val = max(0, cur - amt)
                                if new_val == 0 and pair in SELECTED_ITEMS:
                                    del SELECTED_ITEMS[pair]
                                elif new_val > 0:
                                    SELECTED_ITEMS[pair] = new_val
                            break
                    if clicked_item:
                        continue

                    for k, r in rail_hits.items():
                        if r.collidepoint(mpos):
                            if k in PINNED:
                                PINNED.remove(k)
                            else:
                                PINNED.append(k)
                            break
                    for t, r in tab_rects.items():
                        if r.collidepoint(mpos):
                            main_tab = t
                            break
                    for lab, r in view_rects.items():
                        if r.collidepoint(mpos):
                            view = lab
                            break
        pygame.time.wait(16)
    pygame.quit()


if __name__ == "__main__":
    main()
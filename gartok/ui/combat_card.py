import pygame
from .tokens import T, mix, fonts
from .primitives import text, caps

def draw_combat_card(s, rect, ch, action="PICK", hovered=False, selected=False, disabled=False, state_msg=None, extra_lines=None):
    """
    Desenha o card de combate padronizado para telas de escolha (squad, taverna, prison).
    Retorna uma lista de tuplas (hit_rect, tooltip_text) para a tela pai checar colisoes e renderizar tooltips, e (bottom_rect, action_hovered)
    """
    F = fonts()
    border = T.BRASS if selected else T.STEEL_HI if hovered else T.STEEL_LINE
    if disabled:
        border = T.STEEL_LINE
        
    bg = mix(T.BRASS, T.TABLE, 0.9) if selected else T.STEEL if hovered else T.TABLE
    if disabled:
        bg = mix(T.TABLE, (10, 10, 10), 0.5)

    pygame.draw.rect(s, bg, rect)
    pygame.draw.rect(s, border, rect, 2 if (selected or hovered) and not disabled else 1)

    pad = T.S * 3
    tooltips = []
    
    # Header: Token + Name + Race/Occ
    tok_r = T.S * 4
    tok_c = (rect.x + pad + tok_r, rect.y + pad + tok_r)
    
    # Token
    pygame.draw.circle(s, T.STEEL_HI, tok_c, tok_r)
    pygame.draw.circle(s, border, tok_c, tok_r, 1)
    text(s, F["nameb"], ch["name"][0], tok_c, T.BRASS, center=True)
    
    tx = tok_c[0] + tok_r + T.S * 3
    text(s, F["nameb"], ch["name"], (tx, rect.y + pad), T.TX if not disabled else T.TX_FAINT)
    caps(s, F["micro"], f"{ch['race']} · {ch['occ']}", (tx, rect.y + pad + 24), T.TX_MUTED)
    
    y = rect.y + pad + tok_r * 2 + T.S * 2
    
    # Vitals + Weapon
    caps(s, F["micro"], "COMBAT", (rect.x + pad, y), T.TX_FAINT)
    y += 18
    
    vit_str = f"HP {ch['hp']}   AC {ch['ac']}   Speed {ch['spd']}"
    if "md" in ch:
        vit_str = f"HP {ch['hp']}   AC {ch['ac']}   MD {ch['md']}   Speed {ch['spd']}"
        
    t_surf = F["bodyb"].render(vit_str, True, T.TX)
    t_rect = t_surf.get_rect(topleft=(rect.x + pad, y))
    s.blit(t_surf, t_rect)
    # The whole vitals line is a tooltip zone
    tooltips.append((t_rect, f"HP: {ch.get('hp_max', ch['hp'])} max, AC: {ch['ac']} armor class, Speed: {ch['spd']} squares"))
    
    y += 24
    
    w_str = f"{ch['weapon']}  ·  {ch['dmg']}"
    text(s, F["body"], w_str, (rect.x + pad, y), T.TX_MUTED)
    y += 32
    
    # Extra fields for taverna/prison (CHA, langs, tags)
    if extra_lines:
        for lbl, val, col in extra_lines:
            if lbl:
                caps(s, F["micro"], lbl, (rect.x + pad, y), T.TX_FAINT)
                y += 18
            text(s, F["body"], val, (rect.x + pad, y), col)
            y += 26
            
    # Bottom Action / State
    b_h = 40
    b_r = pygame.Rect(rect.x, rect.bottom - b_h, rect.w, b_h)
    pygame.draw.rect(s, T.STEEL, b_r)
    pygame.draw.rect(s, border, b_r, 1)
    
    if state_msg:
        msg, col = state_msg
        caps(s, F["microb"], msg, b_r.center, col, center=True)
    elif action:
        caps(s, F["microb"], action, b_r.center, T.BRASS if hovered else T.TX_FAINT, center=True)
        
    return tooltips, b_r


def draw_party_row(s, rect, ch, state=None, hovered=False):
    """
    Desenha a tira do membro do grupo na Taverna / Prisao.
    Retorna a area do card para cliques.
    """
    F = fonts()
    border = T.GREEN if (state and state[0] in ("CAN SPEAK", "CAN BAIL") and hovered) else T.BLOOD if (state and state[0] not in ("CAN SPEAK", "CAN BAIL") and hovered) else T.STEEL_LINE
    bg = T.STEEL if hovered else T.TABLE
    pygame.draw.rect(s, bg, rect)
    pygame.draw.rect(s, border, rect, 2 if hovered else 1)
    
    pad = T.S * 2
    tok_r = T.S * 2
    tok_c = (rect.x + pad + tok_r, rect.y + pad + tok_r)
    
    pygame.draw.circle(s, T.STEEL_HI, tok_c, tok_r)
    pygame.draw.circle(s, border, tok_c, tok_r, 1)
    text(s, F["micro"], ch["name"][0], tok_c, T.BRASS, center=True)
    
    text(s, F["bodyb"], ch["name"], (tok_c[0] + tok_r + T.S * 2, rect.y + pad), T.TX)
    caps(s, F["micro"], f"CAR {ch['cha']:+}", (tok_c[0] + tok_r + T.S * 2, rect.y + pad + 20), T.BRASS)
    
    text(s, F["body_sm"], ", ".join(ch["langs"]), (rect.x + pad, rect.y + pad + 38), T.TX_MUTED)
    
    slots_col = T.BLOOD if ch["free"] <= 0 else T.TX_FAINT
    caps(s, F["micro"], f"{ch['free']} slot(s) free", (rect.x + pad, rect.bottom - pad - 12), slots_col)
    
    if state:
        st, col = state
        caps(s, F["microb"], st, (rect.right - pad, rect.bottom - pad - 12), col, right=True)
        
    return rect

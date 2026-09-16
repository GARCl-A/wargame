"""
Renderizador de mapa para GARTOK Tactical.

Roda sozinho:  python map_render.py
Pra portar, os pedaços que interessam sao, nessa ordem de impacto:
  1. fit_transform()      -> preenche a tela com o grafo
  2. draw_road()          -> estrada com contorno, some o "fio bege no bege"
  3. draw_chip()          -> rotulo com fundo solido
  4. draw_node()          -> no maior, cor so quando significa algo
  5. T (tokens)           -> paleta e escala unicas pro jogo inteiro
"""

import math
import pygame

# ---------------------------------------------------------------- tokens
# Uma paleta so. Nada de cor inventada no meio do codigo de desenho.
class T:
    # superficies, do mais fundo pro mais perto
    VOID      = (22, 18, 14)     # fora do mapa
    FIELD     = (42, 33, 24)     # o mapa
    FIELD_HI  = (56, 45, 33)     # textura / relevo
    PANEL     = (31, 26, 20)     # sidebar, barra do topo
    LINE      = (64, 53, 40)     # divisorias

    # tinta
    INK       = (232, 223, 204)  # texto principal
    INK_MUTED = (154, 140, 116)  # label, legenda
    INK_FAINT = (104, 92, 74)    # quase invisivel, so pra estrutura

    # estradas
    ROAD      = (156, 130, 90)
    ROAD_DARK = (28, 22, 16)     # contorno por baixo

    # estado — cor SO aparece quando quer dizer alguma coisa
    BRASS     = (217, 164, 65)   # voce / selecionado / acao primaria
    DANGER    = (181, 69, 58)
    SAFE      = (95, 138, 90)

    # escala de espaco: tudo e multiplo de 8
    S = 8

    # escala de tipo: 3 tamanhos, 2 pesos. So.
    SIZE_LABEL = 12
    SIZE_BODY  = 15
    SIZE_TITLE = 26


def load_fonts():
    """Uma familia so. Troque por pygame.font.Font('sua.ttf', n) quando tiver."""
    f = pygame.font.SysFont("dejavuserif,georgia,serif", T.SIZE_BODY)
    return {
        "label": pygame.font.SysFont("dejavusans,arial", T.SIZE_LABEL),
        "body":  f,
        "bold":  pygame.font.SysFont("dejavuserif,georgia,serif", T.SIZE_BODY, bold=True),
        "title": pygame.font.SysFont("dejavuserif,georgia,serif", T.SIZE_TITLE, bold=True),
    }


# ---------------------------------------------------------------- dados
# Coordenadas em unidades do MUNDO, nao em pixels. Isso e o que permite
# reescalar o mapa sem mexer nos dados.
NODES = {
    "ankareth":   dict(pos=(0, 0),      name="Ankareth",   kind="home",   icon="G"),
    "prison":     dict(pos=(-22, -25),  name="Prison",     kind="plain",  icon="P"),
    "tavern":     dict(pos=(-50, 2),    name="Tavern",     kind="plain",  icon="T"),
    "lumber":     dict(pos=(-22, 28),   name="Lumber Yard",kind="plain",  icon="L"),
    "market":     dict(pos=(22, 28),    name="Market",     kind="plain",  icon="M"),
    "arena":      dict(pos=(30, -38),   name="Arena",      kind="danger", icon="X"),
    "oldroad":    dict(pos=(88, 2),     name="Old Road",   kind="plain",  icon="R"),
    "wilds":      dict(pos=(170, -30),  name="The Wilds",  kind="safe",   icon="W"),
    "claim":      dict(pos=(196, -48),  name="The Claim",  kind="plain",  icon="C"),
    "ledger":     dict(pos=(120, 52),   name="Ledger Hold",kind="plain",  icon="H"),
}

# (a, b, horas, principal?)
EDGES = [
    ("ankareth", "prison",  1, False),
    ("ankareth", "tavern",  1, False),
    ("ankareth", "lumber",  1, False),
    ("ankareth", "market",  1, False),
    ("ankareth", "arena",   2, False),
    ("ankareth", "oldroad", 4, True),
    ("arena",    "oldroad", 3, False),
    ("oldroad",  "wilds",   6, True),
    ("oldroad",  "ledger",  5, False),
    ("wilds",    "claim",   2, False),
]


# ---------------------------------------------------------------- 1. fit
def fit_transform(nodes, rect, padding=0.08, max_zoom=6.0):
    """
    O item #1: calcula escala + offset pra que o grafo PREENCHA o rect.
    Retorna world_to_screen(pos) -> (x, y) em pixels.
    """
    xs = [n["pos"][0] for n in nodes.values()]
    ys = [n["pos"][1] for n in nodes.values()]
    w = max(max(xs) - min(xs), 1e-6)
    h = max(max(ys) - min(ys), 1e-6)

    pad_x, pad_y = rect.w * padding, rect.h * padding
    zoom = min((rect.w - 2 * pad_x) / w, (rect.h - 2 * pad_y) / h)
    zoom = min(zoom, max_zoom)          # nao estica demais grafo pequeno

    # centro do grafo cai no centro do rect
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

    def world_to_screen(p):
        return (rect.centerx + (p[0] - cx) * zoom,
                rect.centery + (p[1] - cy) * zoom)

    return world_to_screen, zoom


# ---------------------------------------------------------------- 2. estrada
def draw_road(surf, a, b, primary=False):
    """
    O item #3: contorno escuro por baixo + linha clara por cima.
    Isso e o que faz a estrada existir sobre qualquer fundo.
    """
    w = 5 if primary else 3
    pygame.draw.line(surf, T.ROAD_DARK, a, b, w + 4)   # contorno
    pygame.draw.line(surf, T.ROAD,      a, b, w)       # miolo
    if primary:                                        # brilho fino na principal
        pygame.draw.line(surf, T.FIELD_HI, a, b, 1)


# ---------------------------------------------------------------- 3. chip
def draw_chip(surf, font, text, center, fg=T.INK_MUTED, bg=T.VOID):
    """
    O item #4: o '1 h' nunca mais some dentro da linha.
    Fundo solido + padding de 6/3. Desenhado DEPOIS das estradas.
    """
    img = font.render(text, True, fg)
    r = img.get_rect(center=center).inflate(12, 6)
    pygame.draw.rect(surf, bg, r, border_radius=3)
    pygame.draw.rect(surf, T.LINE, r, 1, border_radius=3)
    surf.blit(img, img.get_rect(center=r.center))


# ---------------------------------------------------------------- 4. no
NODE_R = 19          # era ~10 no print. Dobre.

KIND_COLOR = {
    "home":   T.BRASS,
    "danger": T.DANGER,
    "safe":   T.SAFE,
    "plain":  (126, 111, 90),  # o normal NAO tem cor propria
}


def draw_node(surf, fonts, node, center, selected=False):
    color = KIND_COLOR[node["kind"]]
    x, y = int(center[0]), int(center[1])

    if selected:                                   # anel de selecao
        pygame.draw.circle(surf, T.BRASS, (x, y), NODE_R + 7, 2)

    pygame.draw.circle(surf, T.VOID,  (x, y), NODE_R + 3)   # separa do fundo
    pygame.draw.circle(surf, T.PANEL, (x, y), NODE_R)
    pygame.draw.circle(surf, color,   (x, y), NODE_R, 3)    # aro colorido

    icon = fonts["bold"].render(node["icon"], True, color)
    surf.blit(icon, icon.get_rect(center=(x, y)))

    # nome: texto direto com contorno, sem pilula bege
    draw_outlined(surf, fonts["body"], node["name"], (x, y + NODE_R + 14), T.INK)


def draw_outlined(surf, font, text, center, fg, outline=T.VOID, px=2):
    """Contorno barato: blita o texto escuro 8x em volta. Legivel em qualquer fundo."""
    dark = font.render(text, True, outline)
    base = dark.get_rect(center=center)
    for dx in (-px, 0, px):
        for dy in (-px, 0, px):
            if dx or dy:
                surf.blit(dark, base.move(dx, dy))
    img = font.render(text, True, fg)
    surf.blit(img, img.get_rect(center=center))


# ---------------------------------------------------------------- 5. fundo
def make_field(size, seed=7):
    """
    O item #2: campo ESCURO com relevo sutil. Quando voce tiver a textura
    de pergaminho, use:
        tex = pygame.image.load('parchment.png').convert()
        tex.set_alpha(40)              # 15-20% so
        field.blit(tex, (0,0))
    """
    import random
    rnd = random.Random(seed)
    surf = pygame.Surface(size).convert()
    surf.fill(T.FIELD)
    # manchas largas, baixo contraste — le como couro/mapa velho, nao como ruido
    for _ in range(90):
        r = rnd.randint(40, 160)
        blob = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        c = T.FIELD_HI if rnd.random() < 0.55 else T.VOID
        pygame.draw.circle(blob, (*c, 14), (r, r), r)
        surf.blit(blob, (rnd.randrange(-r, size[0]), rnd.randrange(-r, size[1])))
    pygame.draw.rect(surf, T.LINE, surf.get_rect(), 1)
    return surf


# ---------------------------------------------------------------- 6. topo
STATS = [
    ("Day", "1", None), ("Time", "00:00", None),
    ("Members", "3", None), ("Rations", "0", T.DANGER),
    ("Gold", "78", None), ("Wins", "0", None), ("Reputation", "0", None),
]


def draw_topbar(surf, fonts, rect):
    """
    O item #6: sem 7 caixas iguais. Largura pelo conteudo, agrupado,
    cor so no que esta critico (Rations 0).
    """
    pygame.draw.rect(surf, T.PANEL, rect)
    pygame.draw.line(surf, T.LINE, rect.bottomleft, rect.bottomright, 1)

    groups = [STATS[0:2], STATS[2:5], STATS[5:7]]   # tempo | recursos | placar
    x = rect.x + T.S * 3
    for gi, group in enumerate(groups):
        for label, value, tint in group:
            lab = fonts["label"].render(label.upper(), True, T.INK_FAINT)
            val = fonts["title"].render(value, True, tint or T.INK)
            surf.blit(lab, (x, rect.y + T.S * 2))
            surf.blit(val, (x, rect.y + T.S * 2 + lab.get_height() + 2))
            x += max(lab.get_width(), val.get_width()) + T.S * 5
        if gi < len(groups) - 1:                     # divisoria entre grupos
            pygame.draw.line(surf, T.LINE, (x - T.S * 3, rect.y + T.S * 2),
                             (x - T.S * 3, rect.bottom - T.S * 2), 1)
            x += T.S


# ---------------------------------------------------------------- 7. sidebar
def draw_button(surf, fonts, rect, text, primary=False, hint=None):
    """O item #7: UM botao primario. Os outros sao fantasma."""
    if primary:
        pygame.draw.rect(surf, T.BRASS, rect, border_radius=4)
        fg = T.VOID
    else:
        pygame.draw.rect(surf, T.LINE, rect, 1, border_radius=4)
        fg = T.INK
    img = fonts["bold"].render(text, True, fg)
    surf.blit(img, img.get_rect(center=rect.center))
    if hint:
        h = fonts["label"].render(hint, True, T.INK_FAINT)
        surf.blit(h, (rect.x, rect.bottom + 6))
    return rect.bottom + (26 if hint else 12)


def draw_sidebar(surf, fonts, rect):
    pygame.draw.rect(surf, T.PANEL, rect)
    pygame.draw.line(surf, T.LINE, rect.topleft, rect.bottomleft, 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 3

    def section(title):
        nonlocal y
        img = fonts["label"].render(title.upper(), True, T.INK_FAINT)
        surf.blit(img, (x, y))
        y += img.get_height() + T.S

    section("Group")
    card = pygame.Rect(x, y, w, 46)
    pygame.draw.rect(surf, T.VOID, card, border_radius=4)
    pygame.draw.rect(surf, T.BRASS, card, 1, border_radius=4)
    surf.blit(fonts["bold"].render("Drolys's band", True, T.INK), (x + T.S, y + 7))
    surf.blit(fonts["label"].render("3 members  ·  idle at Ankareth", True, T.INK_MUTED),
              (x + T.S, y + 26))
    y = card.bottom + T.S * 4                     # espaco ENTRE secoes > espaco dentro

    section("Ankareth")
    body = fonts["label"].render("The walled burg. Where the guild sets out from.",
                                 True, T.INK_MUTED)
    surf.blit(body, (x, y))
    y += body.get_height() + T.S * 4

    section("Here")
    y = draw_button(surf, fonts, pygame.Rect(x, y, w, 40), "Visit the bank",
                    primary=True, hint="rent a strongbox · stash gear")
    y = draw_button(surf, fonts, pygame.Rect(x, y, w, 36), "Visit the forge")
    y = draw_button(surf, fonts, pygame.Rect(x, y, w, 36), "2 missions here")


# ---------------------------------------------------------------- render
def render(size=(1600, 900)):
    screen = pygame.Surface(size).convert()
    screen.fill(T.VOID)
    fonts = load_fonts()

    top = pygame.Rect(0, 0, size[0], 84)
    side_w = 320
    side = pygame.Rect(size[0] - side_w, top.bottom, side_w, size[1] - top.bottom)
    map_rect = pygame.Rect(0, top.bottom, size[0] - side_w, size[1] - top.bottom)

    field = make_field(map_rect.size)
    screen.blit(field, map_rect.topleft)

    to_screen, zoom = fit_transform(NODES, map_rect)

    # ordem importa: estrada -> chip -> no -> nome
    for a, b, hours, primary in EDGES:
        pa, pb = to_screen(NODES[a]["pos"]), to_screen(NODES[b]["pos"])
        draw_road(screen, pa, pb, primary)

    for a, b, hours, primary in EDGES:
        pa, pb = to_screen(NODES[a]["pos"]), to_screen(NODES[b]["pos"])
        mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
        draw_chip(screen, fonts["label"], f"{hours} h", mid)

    for key, node in NODES.items():
        draw_node(screen, fonts, node, to_screen(node["pos"]),
                  selected=(key == "ankareth"))

    draw_topbar(screen, fonts, top)
    draw_sidebar(screen, fonts, side)
    return screen


def main():
    pygame.init()
    size = (1600, 900)
    win = pygame.display.set_mode(size)
    pygame.display.set_caption("GARTOK Tactical — map")
    frame = render(size)
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
        win.blit(frame, (0, 0))
        pygame.display.flip()
        pygame.time.wait(16)
    pygame.quit()


if __name__ == "__main__":
    main()

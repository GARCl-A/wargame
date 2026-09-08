# Assets — Dungeon Tileset

Fonte: `16x16dungeon.png` (sheet promo "16x16 Dungeon", tiles de 16px soltos:
título, duas salas de exemplo e fileiras de tiles/objetos avulsos).

## Gerado

| Arquivo | O que é |
|---|---|
| `dungeon_tileset.png` | atlas empacotado, grade de 16px |
| `dungeon_tileset.json` | manifesto `nome -> {x, y, w, h}` + `tile_size`, `columns` |
| `tiles/*.png` | cada tile isolado, fundo transparente |

Regenera tudo com:

```
python gartok/assets/build_tileset.py
```

## Uso (pygame)

```python
from gartok.tileset import Tileset
ts = Tileset.load(target=44)          # escala nearest pra célula de 44px
screen.blit(ts["floor"], (x, y))
```

## Inventário (32 tiles)

- **Piso** (16x16): `floor`, `floor_alt`, `floor_studs`, `floor_bars`;
  `floor_medallion` (48x48, mosaico 3x3 do centro da sala).
- **Parede**: `wall_top`, `wall_bottom`, `wall_left`, `wall_right`,
  `wall_corner_tl/tr/bl/br`, `wall_left_chain`, `wall_brick` (16x16);
  `wall_door_top` (16x32).
- **Objetos**: `barrel`, `ladder`, `chair`, `chest_open`, `gravestone`,
  `fence`, `bar`, `rubble`, `anvil` (16x16); `table`, `torch`, `archway`
  (16x32); `weapon_rack` (32x32).
- **Inimigos**: `slime_green`, `slime_blue`, `slime_pink` (16x16).

Tiles de 16x32 / 32x32 são alinhados pelo canto superior-esquerdo no blit;
para encostar os pés numa célula, desenhe em `y - (h - 16)*escala`.

> A fonte é um sheet promo de baixa resolução, então alguns objetos (mesa,
> conjunto de cadeiras, estante de armas) são recortes estilizados do próprio
> mockup, não sprites limpos de um atlas oficial.

# GARTOK Tactical

Wargame tático por turnos baseado no **GARTOK RPG**, construído a partir do
gerador de personagens em [Gerenciador-Gartok](https://github.com/GARCl-A/Gerenciador-Gartok).

Cada unidade é um personagem GARTOK gerado aleatoriamente (raça + ocupação + 3d6).

**Draft:** o jogo começa numa tela de seleção — são sorteados 3 personagens, você
escolhe 1, três vezes. Esses 3 formam a **guilda**.

**Campanha:** a guilda roda o mapa-múndi como um token. Cada lugar é uma batalha,
um mercado ou uma parada. Numa batalha você monta o **esquadrão** (1 a 3 membros),
cai num grid e vence eliminando o time inimigo. Viajar gasta o relógio (dia/noite,
fome); morte é permanente; um wipe total encerra a run. Salva por slot.

## Rodar

```
pip install -r requirements.txt
python main.py
```

Testes: `python test_gartok.py` (regras) e `python sim_test.py` (200 batalhas IA vs IA).

## Controles

| Ação | Como |
|---|---|
| Escolher personagem (draft) | clique num dos 3 cards |
| Editar candidato (draft) | botão **EDITAR** (canto sup. dir.) → clique em "trocar" num card para mudar raça/ocupação; **EDITANDO** de novo volta a escolher |
| Andar (1 ponto) | clique numa casa verde — o caminho até o cursor aparece; o trajeto já andado no turno fica marcado |
| Atacar (1 ponto) | clique num inimigo com contorno vermelho |
| Arremessar / Desmoralizar / Estabilizar / Primeiros socorros / Pegar / Defender / Fugir | botões no painel (Arremessar, Desmoralizar e Estabilizar pedem um clique no alvo) |
| Alternar visão personagem ↔ esquadrão | `L` |
| Inspecionar ficha | clique em qualquer unidade |
| Terminar turno | `Espaço` ou botão |
| Sair | `Esc` |

Ao fim da batalha, um clique volta ao mapa (ou às telas de espólio / recompensa).

Cada unidade tem **2 pontos de ação por turno**; toda ação custa 1 ponto (menos
Terminar turno). Andar move até o deslocamento e pode ser fracionado em vários
cliques. **Regra central:** bônus do mesmo tipo não se acumulam (vale o maior);
bônus sem tipo e todas as penalidades somam.

**Visão é por personagem, não por jogador:** o mapa é escuro; no seu turno você
vê só o que o personagem ativo enxerga (tochas, itens de luz, visão no escuro).
O esquadrão inimigo (vermelho) é uma IA simples.

## O que veio do gerador e o que foi projetado

Portado das planilhas `.xlsx` originais (`gartok/data.py`):
atributos 3d6, 18 raças com mods e habilidades, 31 ocupações com arma+item,
9 tendências, tamanhos/deslocamento/carga, fórmulas de CA / PV / modificadores.

Projetado para o wargame (não existia no gerador):

- **Combate d20**: iniciativa `d20 + mod Des`; ataque `d20 + mods` vs CA;
  dano = dado da arma + mod Força (corpo-a-corpo); crítico no 20, erro no 1.
- **Pontos de ação** (2/turno) e **bônus tipados** (`data.resolve_bonus`).
- **Ações** (`gartok/actions.py`): Andar, Atacar, Defender, Arremessar, Pegar,
  Desmoralizar, Estabilizar, Primeiros socorros, Fugir.
- **Cair / estabilizar / morte** (morrendo → estável | morto), permadeath.
- **Condições** temporárias — Defendendo, Desmoralizado (`gartok/conditions.py`).
- **Efeito mecânico das habilidades raciais** (`gartok/abilities.py`).
- **Visão e luz**, paredes, objetos no chão, tochas.
- **Munição** (besta + aljava) e **arma improvisada**; **flanco** e "luta em bando".
- **Tabela de armas** (`WEAPONS` em `data.py`). **1 casa = 1,5 m**.

Sistemas de mundo, fora do combate:

- **Campanha**: guilda roda o mapa como um token; relógio + dia/noite; permadeath
  e save por slot (`world.py`, `clock.py`, `guild.py`, `persist.py`).
- **Fome**: uma refeição por dia; sem comida, penalidades crescentes até a morte.
- **Economia**: cobre no personagem (sem tesouraria); mercado com negociação por
  idioma e tendência; arena de apostas não-letal; espólio de campo.

Detalhes e a reconstrução completa das regras: [`GARTOK-regras.md`](GARTOK-regras.md).

## Estrutura

Identificadores são em inglês; o conteúdo do domínio (nomes de raça, ocupação,
tendência, tamanho, idioma, arma e item) fica em português, igual à
`GARTOK-regras.md` e à tela.

```
gartok/
  # domínio + regras de combate
  data.py           tabelas do GARTOK (portadas) + armas/pesos/constantes (projetados),
                    dado, bônus tipados, eixos de alinhamento
  abilities.py      habilidades raciais: passivo numérico e/ou gancho de cada uma
  conditions.py     estados temporários de um combatente (Defending, Demoralized, …)
  actions.py        ações de combate (cost, target, can/execute) + registro PANEL_ACTIONS
  board.py          grade, paredes, pathfinding (BFS), linha de visão
  vision.py         luz + o que cada personagem enxerga (visão de tela)
  ground.py         objetos no chão (GroundObject) e criaturas neutras (Creature)
  scenario.py       monta o mapa de uma batalha: terreno, deployment, tochas
  unit.py           Unit = o personagem persistente (raça/ocupação/atributos/fome/loadout)
  combatant.py      Combatant = uma Unit dentro de uma batalha (PV/PA/posição/condições/mãos)
  battle.py         estado da batalha (envolve as unidades em Combatant), iniciativa, morte
  ai.py             IA do esquadrão inimigo (sobre actions.py); tendência tempera as bordas
  loot.py           junta o espólio de campo depois de uma vitória letal

  # mundo + campanha
  world.py          grafo do mapa: nós, arestas (horas), rota (Dijkstra), ofertas da arena
  clock.py          relógio da campanha (segundos), dia/noite
  guild.py          a guilda = o roster; tempo/fome diária, ouro somado, reputação de arena
  campaign.py       dobra o resultado de uma batalha de volta na guilda (permadeath, espólio)
  economy.py        preços, estoque do mercado e negociação (idioma + carisma + tendência)
  persist.py        slots de save (JSON); só o roster + meta da campanha vão pro disco

  # telas (Screen base: handle_event / update(dt) / draw(surface), lê self.mouse)
  screen.py         classe base das telas (dispatch de clique -> self._click)
  menu_screen.py    slots de save (Novo / Continuar / Apagar)
  draft_screen.py   montagem do roster inicial (cards + modo EDITAR)
  map_screen.py     o hub: dirige a guilda pelo mapa, dia/noite, atalhos p/ arena e mercado
  guild_screen.py   roster + equipamento (mãos e mochila); abre a ficha completa (modal)
  squad_screen.py   quem sai numa batalha ou vai ao mercado (+ tiers de aposta na arena)
  battle_screen.py  tela de batalha (grade, iniciativa, painel de ação, log)
  loot_screen.py    dividir o espólio entre os sobreviventes
  reward_screen.py  escolher quem embolsa a bolsa de uma vitória de arena
  market_screen.py  comprar/vender por cobre; bolsa comum, negociação por idioma+tendência

  # apresentação compartilhada
  theme.py          design system: escala de espaço (SP), paleta, 2 famílias de fonte,
                    widgets (panel, chip, section, pips, Stack, token_badge)
  icons.py          ícones vetoriais (pygame.draw) das ações — sem arquivo de asset
  lighting.py       LightRenderer: camada de escuridão + buracos de luz radiais
  sheet.py          formata uma Unit em linhas de texto (usada na inspeção da batalha)
  sheet_panel.py    ficha completa desenhada (modal da tela de guilda)

  app.py            shell pygame: janela redimensionável (canvas fixo + letterbox),
                    loop, troca de telas e o laço campanha ⇄ batalha
main.py             ponto de entrada
test_gartok.py      testes de regras (rodam sob pytest ou `python test_gartok.py`)
sim_test.py         simulação headless (200 batalhas IA vs IA)
```

> `tileset.py` e `gartok/assets/` estão órfãos — a renderização é 100% procedural
> desde a repaginação visual. Mantidos em disco caso props (barris, baús) voltem.

### Como adicionar um sistema novo

- **Nova ação** (ex.: Empurrar, Agarrar): uma classe `Action` em `actions.py` e
  uma entrada em `PANEL_ACTIONS`. A UI e a IA passam a enxergá-la sozinhas.
- **Novo estado de combate** (ex.: veneno, caído, cego): uma classe `Condition` em
  `conditions.py`; quem aplica chama `combatant.add_condition(...)`.
- **Nova habilidade racial**: uma `Ability` em `abilities.py`. Se ela reaproveita
  os passivos e ganchos que já existem (`hp_max`, `speed`, …, `on_turn_start`,
  `on_attack_miss`, …), basta editar esse arquivo. Um **tipo novo de gancho**
  ainda exige um ponto de chamada no núcleo (`combatant.py` para combate,
  `unit.py` para derivação) — não há um barramento de plugins.
- **Novo estado persistente do personagem** (ex.: XP, ferimentos, fadiga): campo
  em `unit.py`, aplicado em `Unit._derive_combat` se afeta os números, salvo em
  `persist.unit_to_dict` / `Unit.from_save`. O `Combatant` lê tudo isso de graça.
- **Novo tipo de objeto no chão**: um `kind` novo em `ground.GroundObject` e onde
  a regra reage a ele (os consumidores perguntam `obj.kind` / `obj.is_weapon`).
- **Novo cenário de batalha** (mapa pré-montado, zonas de deployment, lighting):
  uma subclasse de `Scenario` com `build(battle)` em `scenario.py`; aponte um
  `world.Node` pra ela. Objetivo que não seja "elimine todos" ainda **não** tem
  seam — `battle._check_winner` decide vitória sozinho.
- **Novo lugar no mapa**: um `Node` em `world.NODES` + arestas em `world.EDGES`
  (custo em horas). `app` transforma o `kind` do nó na atividade (batalha /
  mercado / parada).
- **Novo sistema de mundo** (fora do combate): a rotina que passa o tempo em
  `guild.pass_time` / `_daily_upkeep`; resultado de batalha que volta pro roster
  em `campaign.absorb_battle`.
- **Nova fonte de luz**: `vision.unit_light` / `ground_light`.

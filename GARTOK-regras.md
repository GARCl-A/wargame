# GARTOK — regras reconstruídas a partir do gerador

Este documento reconstrói o sistema **GARTOK** a partir do único artefato que
sobrou: o gerador de personagens (`Gerenciador-Gartok`). Está dividido em:

- 🟢 **Recuperado** — está literalmente no código/planilhas do gerador.
- 🟡 **Projetado** — não existia; foi criado para o wargame, no estilo d20 do resto.

> **Coluna `Status` nas tabelas (§4 raças, §6 ocupações):** marca manual do autor.
> `OK` = essa linha foi **revisitada e o efeito/item é o desejado** — não é mais a
> primeira inferência. Em branco = ainda o palpite inicial, sujeito a revisão.
> O efeito 🟡 de cada habilidade racial (§7) segue a mesma marca na linha da raça.

---

## 1. Atributos 🟢

Seis atributos, cada um rolado com **3d6** (valores 3–18):

`Força · Destreza · Constituição · Inteligência · Sabedoria · Carisma`

**Modificador** = ⌊(valor − 10) / 2⌋

| Valor | 3 | 4–5 | 6–7 | 8–9 | 10–11 | 12–13 | 14–15 | 16–17 | 18 |
|---|---|---|---|---|---|---|---|---|---|
| Mod | −4 | −3 | −2 | −1 | 0 | +1 | +2 | +3 | +4 |

Depois de rolar, somam-se os **modificadores raciais** (tabela §4).

---

## 2. Criação de personagem 🟢

Ordem exata do gerador:

1. Rola os 6 atributos (3d6 cada).
2. Rola **raça** (d100) → aplica mods raciais, define dado de vida, tamanho, idioma, habilidade racial e faixa etária.
3. Rola **ocupação** (d100) → define a arma inicial e um item inicial.
4. Rola **tendência** (d100).
5. Rola **ouro inicial**: **5d10 moedas de cobre**.
6. Personagem começa em **Nível 0, XP 1000**. 🟢 *(o significado da progressão não sobreviveu — ver §9)*

---

## 3. Valores derivados 🟢

| Derivado | Fórmula | Observação |
|---|---|---|
| **CA** (Classe de Armadura) | `10 + mod Destreza` | sem armadura |
| **Defesa Mental** 🟡 | `10 + mod Sabedoria` | alvo da ação Desmoralizar |
| **PV** | `1d(dado de vida) + mod Constituição` | mínimo 1 |
| **Idade** | `d100 × multiplicador racial` | ver tabela §4 |
| **Deslocamento** | pelo tamanho | ver tabela §5 |
| **Capacidade de carga (normal)** | `(mod Força + 5) × mult. de carga do tamanho` | Golias ("Corpo forte") usa a mult. de Grande |
| **Capacidade de carga (alta)** | `(mod Força + 10) × mult. de carga do tamanho` | idem |
| **Ataque desarmado** 🟡 | dado pelo tamanho: Pequeno/Diminuto 1d2 · Médio 1d3 · Grande 1d4 | todo personagem tem; soma mod Força no dano |

> Quirk do gerador: o PV usa `randrange(1, dado_de_vida)`, ou seja rola de **1 a (dado−1)**.
> Na reconstrução do wargame usei o dado cheio (1 a dado), que é o comportamento
> presumido pelo design.

---

## 4. Raças 🟢

O `Valor` é o limite superior num rolamento de **d100** (faixas cumulativas:
Anão = 01–15, Autômato = 16–17, Centauro = 18–19, Elfo = 20–34, …).

Mods na ordem **For / Des / Con / Int / Sab / Car**. `HD` = dado de vida.
`Idade` = multiplicador aplicado a um d100.

| d100 | Raça | For | Des | Con | Int | Sab | Car | HD | Tamanho | Idioma | Idade× | Habilidade | Status
|---:|---|--:|--:|--:|--:|--:|--:|--:|---|---|--:|---|---|
| 15 | Anão | +1 | 0 | +2 | 0 | −1 | −2 | d10 | Médio | Enânico | 5.0 | Visão no escuro | OK |
| 17 | Autômato | +1 | +1 | 0 | 0 | −1 | −1 | d8 | Médio | Ankarin | 1.0 | Corpo inorgânico | OK
| 19 | Centauro | +1 | −2 | 0 | 0 | +2 | −1 | d10 | Grande | Élfico | 2.5 | Galopar | OK
| 34 | Elfo | −2 | +2 | −1 | +1 | 0 | 0 | d8 | Médio | Élfico | 8.75 | Imunidade a sono |
| 35 | Gnoll | 0 | 0 | +2 | −1 | 0 | −1 | d8 | Médio | Órquico | 0.625 | Estômago forte |
| 36 | Gnomo | −2 | +1 | −1 | 0 | +1 | +1 | d8 | Pequeno | Gnômico | 6.25 | Sangue primal |
| 51 | Goblin | −1 | +2 | +1 | −1 | 0 | −1 | d6 | Pequeno | Goblínico | 0.625 | Luta em bando | OK
| 54 | Golias | +2 | +1 | 0 | −1 | −1 | −1 | d10 | Médio | Jotun | 1.0 | Corpo forte | OK
| 57 | Grippli | −1 | +1 | 0 | 0 | +1 | −1 | d8 | Pequeno | Silvestre | 1.5 | Anfíbio |
| 60 | Halfling | −2 | +2 | −2 | 0 | +1 | +1 | d6 | Pequeno | Pequine | 1.5 | Audição aguçada |
| 64 | Hobgoblin | +1 | +1 | +1 | −1 | −2 | 0 | d8 | Médio | Goblínico | 0.625 | Visão no escuro | OK 
| 74 | Homem Lagarto | +1 | +1 | 0 | −1 | 0 | −1 | d10 | Médio | Dracônico | 0.875 | Escalador |
| 89 | Humano | 0 | 0 | 0 | 0 | 0 | 0 | d8 | Médio | Ankarin | 1.0 | Idioma adicional | OK
| 92 | Kenku | −3 | +1 | −1 | 0 | +1 | +2 | d6 | Médio | Silvestre | 1.0 | Imitar sons | OK
| 95 | Kobold | −2 | +1 | 0 | +1 | −1 | +1 | d6 | Pequeno | Dracônico | 2.5 | Sangue ancestral |
| 96 | Leshy | −1 | 0 | +1 | −1 | +1 | 0 | d6 | Pequeno | Planti | 1.0 | Autótrofo | OK
| 99 | Orc | +2 | +1 | +1 | −1 | 0 | −3 | d10 | Médio | Órquico | 0.625 | Ferocidade | OK
| 100 | Sprite | −2 | 0 | −2 | 0 | +2 | +2 | d6 | Diminuto | Gnômico | 1.5 | Vôo |

**Idiomas mencionados:** Ankarin, Dracônico, Élfico, Enânico, Gnômico, Goblínico,
Jotun, Órquico, Pequine, Planti, Silvestre. 🟢 *(nomes apenas; sem descrição)*

O nome das habilidades é 🟢; **o que cada uma faz é 🟡** — ver §7.

---

## 5. Tamanhos 🟢

| Tamanho | Deslocamento | Mult. de carga | Footprint |
|---|---:|---:|---:|
| Diminuto | 4,5 m | 0,5 | 1 casa |
| Pequeno | 6,0 m | 1,0 | 1 casa |
| Médio | 9,0 m | 1,0 | 1 casa |
| Grande | 9,0 m | 2,0 | **2×2 = 4 casas** |

No wargame: **1 casa = 1,5 m** → Diminuto 3, Pequeno 4, Médio 6, Grande **6** casas. 🟡

- O **deslocamento base não muda com o tamanho**: uma criatura **Grande** anda o
  mesmo que uma **Média** (9 m / 6 casas). Se um Grande anda mais que isso, é por
  **habilidade** — o **Centauro** chega a 12 m (8 casas) só por causa de **Galopar**
  (+3 m), não por ser grande.
- **Criaturas Grandes ocupam 2×2 casas.** A posição guardada é a **âncora** (canto
  superior esquerdo); o footprint são as 4 casas a partir dela. Vale para tudo:
  colisão e pathfinding (só pousa onde as 4 casas cabem e estão livres),
  **alcance** (corpo-a-corpo = footprint encostado, distância mínima entre casas),
  **linha de visão** e **luz** (enxerga / ilumina de qualquer casa do footprint).
  Implementado em `board.cells` / `board.fits` e nos helpers `Battle.cells_of`,
  `units_distance`, `los_between`, `reachable(..., footprint)`.

---

## 6. Ocupações 🟢

d100, faixas cumulativas. Cada ocupação dá **uma arma** e **um item** iniciais.

| d100 | Ocupação | Arma | Item | Status
|---:|---|---|---|---|
| 5 | Açougueiro | Machadinha | 1kg Carne |
| 11 | Agricultor | Machadinha | 1kg Batata |
| 14 | Artesão | Martelo Leve | Cinzel |
| 19 | Barbeiro | Adaga | Tesoura |
| 21 | Besteiro | Besta Leve | Aljava |
| 25 | Caçador | Lança Curta | Corda |
| 27 | Carcereiro | Clava | Algemas de ferro |
| 28 | Cartógrafo | Adaga | Mapa |
| 29 | Cervejeiro | Adaga | 1L Cerveja |
| 32 | Comerciante | Adaga | Saco |
| 35 | Construtor | Martelo | Tijolo de pedra |
| 38 | Coureiro | Adaga | 1 m² Couro |
| 40 | Coveiro | Picareta Leve | Pá |
| 42 | Escravo | Clava | Correntes |
| 43 | Escriba | Adaga | Pergaminho |
| 46 | Ferreiro | Martelo | Barra de ferro |
| 48 | Guarda | Clava | Lanterna | OK
| 51 | Guia | Bordão | Bússola |
| 55 | Jogador | Adaga | Baralho |
| 61 | Ladrão | Adaga | Capa |
| 67 | Lenhador | Machado | 1kg Lenha |
| 68 | Linguista | Adaga | Dicionário |
| 69 | Médico | Adaga | Kit de primeiros socorros | OK
| 72 | Mensageiro | Bordão | Saco |
| 77 | Mercenário | Machado | Corda |
| 81 | Minerador | Picareta | 1kg Carvão |
| 85 | Músico | Adaga | Instrumento musical |
| 88 | Ourives | Adaga | Balança |
| 91 | Padre | Bordão | Símbolo Religioso |
| 96 | Pastor | Bordão | Ovelha |
| 100 | Taverneiro | Adaga | Balde |

**Armas citadas** (11): Adaga, Besta Leve, Bordão, Clava, Lança Curta, Machadinha,
Machado, Martelo, Martelo Leve, Picareta, Picareta Leve.

---

## 7. Habilidades raciais — efeitos 🟡

Só o **nome** veio do gerador. Efeitos abaixo foram desenhados para o wargame
(cada um é um `Ability` em `gartok/abilities.py`: passivos numéricos e/ou ganchos)
e são o palpite mais razoável dado o estilo d20:

| Habilidade | Efeito no wargame |
|---|---|
| Visão no escuro | enxerga **12 casas (18 m)** no escuro como se fosse claro |
| Corpo inorgânico | reduz todo dano recebido em 1; a 0 PV fica **quebrado** em vez de morrendo — ver §Cair, estabilizar e morte |
| Galopar | +3 m (2 casas) de deslocamento — é daqui que vem o Centauro a 12 m |
| Imunidade a sono | +1 CA [natural] (a imunidade a atordoamento em si não faz nada: não há atordoamento no jogo) |
| Estômago forte | +3 PV máximos |
| Sangue primal | 1×/batalha, rerrola um ataque que errou |
| Luta em bando | dispensa o "lados opostos" do Flanquear: basta o atacante e um aliado adjacentes ao alvo para contar como flanco (+2 [circunstância] no ataque) |
| Corpo forte | é uma habilidade de **carga**: só para calcular a capacidade de carga (normal e alta), o Golias conta como criatura **Grande** (mult. de carga 2,0 em vez de 1,0). Não muda footprint, deslocamento nem alcance |
| Anfíbio | +1 casa de deslocamento |
| Audição aguçada | +3 iniciativa |
| Escalador | +1 casa de deslocamento |
| Idioma adicional (Humano) | fala um segundo idioma, sorteado entre os 11 idiomas raciais — pode usar **Desmoralizar** contra quem compartilhe qualquer um dos dois (Desmoralizar exige idioma em comum, ver §Desmoralizar) |
| Imitar sons | 1×/batalha, +4 num ataque (feinte); pode **Desmoralizar sem idioma em comum** (imita a voz do alvo) — só na ofensiva: para *ser* desmoralizado, quem provoca o Kenku ainda precisa de idioma comum |
| Sangue ancestral | +2 no ataque contra alvos Grandes+ |
| Autótrofo | regenera 1 PV no início do turno |
| Ferocidade | 1×/batalha, ao receber o golpe fatal fica com **0 PV** e a condição **morrendo**, mas só **desmaia no fim do turno dele** — até lá continua agindo normalmente. O contador de morte segue normal a partir daí. Só dispara com **mais de 0 PV e sem estar morrendo** |
| Vôo | +2 deslocamento, ignora terreno, +1 CA |

---

## 8. Tendências 🟢

d100, faixas cumulativas (note os pesos — "Leal e Neutro" e "Neutro e Bom" são os mais comuns):

| d100 | Tendência |
|---:|---|
| 10 | Leal e Bom |
| 34 | Leal e Neutro |
| 39 | Leal e Mal |
| 63 | Neutro e Bom |
| 72 | Neutro e Neutro |
| 82 | Neutro e Mal |
| 92 | Caótico e Bom |
| 97 | Caótico e Neutro |
| 100 | Caótico e Mal |

Sem efeito mecânico **conhecido** (🟢). O wargame começou a dar peso a ela:
- **spread de mercado** (§ Mercado e negociação): distância entre a tendência do
  comprador e a do vendedor aperta ou afrouxa o preço;
- **comportamento de IA** (§ Fugir do combate): mau dá golpe de misericórdia,
  bom estabiliza e leva os feridos, caótico foge cedo, leal segura a linha.

---

## 9. Buracos — o que o gerador NÃO preserva

Nada disto existe no gerador; precisa ser reinventado se você quiser o RPG completo:

- **Combate**: iniciativa, ações por rodada, ataque/dano, acertos críticos, alcance.
  → o wargame propõe uma versão (§ combate abaixo).
- **Progressão**: o que fazer com Nível/XP; personagens nascem em Nível 0 / XP 1000.
  Hipótese: 1000 XP = 1 nível; ou XP é uma "reserva" que se gasta. Indeterminado.
- **Perícias / testes de atributo**: provavelmente `d20 + mod` vs dificuldade.
- **Magia**: nenhuma classe conjuradora aparece; "Sangue primal", "Símbolo religioso"
  e "Pergaminho" sugerem que magia existe, mas não há sistema.
- **Armas e equipamento**: dano, peso, preço definidos; **armaduras e escudos não**
  (o slot de armadura existe, sem dados).
- **Efeito das habilidades raciais** (ver §7).
- **Morte**: o wargame define cair / estabilizar / permadeath (§Cair, estabilizar
  e morte). Sobreviventes voltam da batalha com **PV cheio**; não há ferimentos
  persistentes, fadiga nem descanso ao longo do relógio — ainda.
- **Progressão**: sem XP/nível. `_hp_roll` é rolado uma vez e os atributos ficam
  fixos (3d6 + mods raciais). Não há onde pendurar níveis no modelo hoje.

---

## Combate do wargame 🟡 (proposta)

Onde cada parte mora no código: o personagem persistente em `gartok/unit.py`, o
combatente numa batalha (PV, PA, condições, mãos, comportamento de combate) em
`gartok/combatant.py`, ações em `gartok/actions.py`, condições em
`gartok/conditions.py`, habilidades em `gartok/abilities.py`, visão/luz em
`gartok/vision.py`, tabuleiro/pathfinding/LOS em `gartok/board.py`, objetos no
chão e criaturas neutras em `gartok/ground.py`, montagem do mapa em
`gartok/scenario.py`, fluxo de turno em `gartok/battle.py`. Identificadores são em
inglês; nomes de raça/ocupação/arma/… seguem em português.

> **Premissa de design:** as regras são escritas pensando *no mundo* — como os
> personagens interagem com ele — e não só no combate. O combate é a mecânica
> central, mas cada sistema (arremesso, objetos no chão, …) existe primeiro como
> uma coisa do mundo; se conversa com o combate, melhor. Os sistemas entram aos poucos.

### Pontos de ação

- Cada personagem tem **2 pontos de ação por turno**.
- **Atacar**, **Andar** e **Defender** custam **1 ponto** cada.
- Dá pra combinar livremente: andar+andar, atacar+atacar, andar+atacar, atacar+defender…
- **Andar** (1 ponto) = move até o deslocamento em casas (8 direções). Pode fracionar
  a caminhada em vários cliques enquanto não estourar o deslocamento; ao esgotá-lo,
  andar de novo custa outro ponto.
  - **Inimigos bloqueiam de vez:** não dá pra parar **nem atravessar** a casa de
    um personagem inimigo (nem de uma criatura neutra, como a Ovelha).
  - **Aliado dá pra atravessar**, mas **não terminar o movimento em cima** dele.
  - Implementado em `Battle.cells_by_side` → `board.reachable` /
    `path_step_toward` (inimigos entram como `blocked`, aliados como `passable`).
- **Defender** (1 ponto) = **+1 de bônus de circunstância** na CA até o começo do
  próximo turno.
- **Arremessar** (1 ponto) = arremessa a arma em mãos, se ela for **arma de
  arremesso** (por ora só a **Adaga**, alcance 9 m = 6 casas). Ver abaixo.
- **Pegar** (1 ponto) = pega um **objeto** (`ground.GroundObject`) que esteja na
  sua casa ou numa casa adjacente: arma só para quem está **desarmado**; tocha
  para qualquer um (se estiver armado, **troca**). Detalhe em §Objetos no chão.
- **Desmoralizar** (1 ponto) = provocação verbal a até **18 m (12 casas)**. Ver abaixo.
- **Estabilizar** / **Primeiros socorros** (1 ponto) = tentar trazer um aliado
  caído de volta a `estável`. Ver §Cair, estabilizar e morte.
- **Fugir** (1 ponto, encerra o turno) = sair do combate pela borda do mapa.
  Ver §Fugir do combate.

### Bônus tipados — regra central

> **Bônus do mesmo tipo não se acumulam** — vale só o maior.
> Bônus **sem tipo** e **todas as penalidades** se somam normalmente.

Implementado em `data.resolve_bonus()`. Tipos em uso: `circunstancia`, `natural`, `status`.
Exemplos: Defender (+1 circ. na CA) não acumula com nada de circunstância na CA;
"Luta em bando" (+2 circ. no ataque) e o feinte de "Imitar sons" (+4 circ.) não
somam — o Kenku flanqueando fica com +4, não +6.

### Iniciativa e ataque

- **Iniciativa**: `d20 + mod Destreza` (+ bônus racial). Ordem decrescente, fixa na batalha.
- **Ataque**: `d20 + mods` vs `CA` do alvo.
  - mod base = `mod Força` (corpo-a-corpo), `mod Destreza` (à distância / arremesso)
    ou o **melhor entre Força e Destreza** (arma *finesse*).
  - outros mods entram tipados e passam pela regra de acumulação acima.
  - **20 natural** = acerto automático + crítico (rola o dado de dano em dobro).
  - **1 natural** = erro automático.
- **Flanquear**: `+2 [circunstância]` no ataque quando o atacante **e** um aliado
  estão os dois adjacentes ao alvo e **em lados opostos** — a reta entre as casas
  dos dois cruza o footprint do alvo. A habilidade **Luta em bando** (Goblin)
  dispensa o "lados opostos": basta os dois adjacentes. Como os dois são
  `circunstância`, flanco e Luta em bando **não somam** (+2, nunca +4).
- **Dano**: `dado da arma (+ mod Força se corpo-a-corpo)`, mínimo 1, menos a redução de dano do alvo.
- **Alcance**: corpo-a-corpo = casas adjacentes; à distância = alcance da arma em
  casas. Distância entre unidades = **menor Chebyshev entre as casas dos dois
  footprints** (uma criatura Grande "encosta" por qualquer casa do seu 2×2).
- **Linha de visão**: ataque à distância e arremesso exigem **LOS livre** *e* **enxergar** o
  alvo (ver §Visão). Corpo-a-corpo (casa adjacente) não exige enxergar.
- **Cair**: PV ≤ 0 **não remove mais a unidade na hora** — ela entra em `morrendo`
  (§Cair, estabilizar e morte). Exceções: **Ferocidade** (o Orc só desmaia no fim
  do turno dele) e **Corpo inorgânico** (o Autômato fica `quebrado`, sem contador).

### Cair, estabilizar e morte 🟡

Estados e contador em `combatant.py`; ações `Stabilize` / `FirstAid` em
`actions.py`; fluxo de turno e vitória em `battle.py`.

> **Premissa de design (usuário):** nos primeiros níveis a mortalidade é
> altíssima e o esquadrão inicial é **descartável**. Quem sobreviver às primeiras
> batalhas fica valioso; daí em diante o jogador vai contratando reposições, que
> também morrem, e assim por diante. Ressurreição é assunto de um futuro distante.

**Estados de uma unidade:**

| Estado | O que é |
|---|---|
| `de pé` | lutando normalmente |
| `morrendo` | 0 PV, caído na casa, contador de morte rodando — ainda dá pra salvar |
| `estável` | 0 PV, inconsciente, fora do combate; **sobrevive** à batalha |
| `quebrado` | só Autômato: 0 PV, caído, **sem contador** — espera um aliado consertar; **sobrevive** à batalha |
| `morto` | permadeath |

Um corpo (`morrendo` ou `estável`) fica na casa e **pode ser desenhado, mirado e
atacado**, mas **não conta como combatente**: não vale para vitória, não é alvo
da IA, não bloqueia nem ocupa passagem.

**Cair.** Quando o PV chega a 0, a unidade entra em `morrendo`, o **contador zera**
e passa a contar **os turnos dela** na iniciativa. Nesses turnos ela não faz nada
além de rodar o contador.

**Contador de morte.** No **3º turno** da unidade caída: **teste de morte** —
rola `d20`, **11–20 vive** (50%).
- Falhou → `morto`.
- Passou → `estável`.

O contador é **fixo**: dispara uma única vez, no 3º turno. Toda vez que uma
unidade passa de `de pé`/`estável` para `morrendo`, ele **reinicia do zero**.

**Estabilizar (aliado, mãos vazias).** Ação de 1 ponto; alvo é um aliado
`morrendo` **adjacente**. Provoca **um teste de morte extra na hora** (`d20`,
11–20). Sucesso → `estável`. Falha → nada (só gastou a ação). Vários aliados
podem tentar em sequência, turno após turno.
- **Alvo `quebrado` (Autômato):** a mesma ação conserta, mas o teste é
  `d20 + mod Inteligência` vs **DC 15** e o sucesso o traz de volta `de pé` com
  1 PV. Sem limite de tentativas (não há contador).

**Primeiros socorros (kit).** Ação de 1 ponto; aliado `morrendo` adjacente; exige
um **Kit de primeiros socorros** em mãos com carga. Teste de **Sabedoria**:
`d20 + mod Sabedoria` vs **dificuldade 10**. Sucesso → `estável`. Falha → nada.
**Consome 1 carga em qualquer caso**; dá pra continuar tentando enquanto houver.
- O kit tem **10 cargas** e é **recarregável** — não é consumível. Hoje
  `reset_battle_state` recompõe as cargas (e a munição) **a cada batalha**;
  consumo de recursos ao longo da campanha fica para quando o equipamento
  ganhar profundidade.
- É o item inicial do Médico (§6).

**Golpe de misericórdia.** Um ataque normal (corpo-a-corpo ou à distância) pode
mirar um corpo caído:
- alvo `morrendo` → o acerto **mata na hora** (`morto`), sem rolar dano;
- alvo `estável` → o acerto causa dano normal, a unidade **volta a `morrendo`** e
  o contador reinicia.

**Vitória.** Um lado perde quando não tem mais nenhuma unidade `de pé`. As
unidades `morrendo` ainda presas no contador quando a batalha acaba fazem **um
último teste de morte** para fixar `estável`/`morto`.

A **IA** trata corpos caídos conforme a **tendência** (ver *Comportamento por
tendência* em §Fugir do combate): tendência **Má** dá o golpe de misericórdia num
`morrendo` inimigo adjacente antes de seguir lutando; tendência **Boa**
estabiliza um aliado caído adjacente antes de qualquer outra coisa. Fora isso, um
corpo não é alvo. Ainda **sem pathfinding** para ir até um aliado caído ou até a
borda — as duas ações só acontecem de onde a unidade já está.

**Ferocidade (Orc).** 1×/batalha, só quando o Orc está com **mais de 0 PV e não
está morrendo**. O golpe que o derrubaria leva o PV a **0** e dá a condição
**morrendo** (contador zerado), mas o Orc **continua de pé e agindo** até o **fim
do turno dele** — só então desmaia de fato e o contador passa a rodar
normalmente. Se levar outro golpe fatal antes disso, cai na hora. Da segunda vez
na batalha, entra em `morrendo` direto.

**Autômato quebrado (Corpo inorgânico).** O Autômato **não morre**: a 0 PV fica
`quebrado` — caído, fora do combate, **sem teste de morte e sem contador**. Fica
assim indefinidamente (tempo infinito, até termos regras de dano estrutural).
Só volta se um **aliado adjacente** o consertar com a ação **Estabilizar**:
`d20 + mod Inteligência` vs **DC 15** (em vez do teste de morte de 50%).
Sucesso → volta `de pé` com **1 PV**. O **Kit de primeiros socorros** não serve
para consertar Autômato. Numa derrota total, o Autômato `quebrado` é perdido
junto com o resto do esquadrão.

### Munição e arma improvisada 🟡

- A **Besta Leve** exige **munição**. A **Aljava** (item do Besteiro) traz
  **20 flechas**; cada tiro à distância gasta 1. Flechas **não se recuperam**.
- **Sem flecha, a besta não dispara.** Ela passa a valer como **arma improvisada**:
  ataque **corpo-a-corpo**, alcance 1, dano igual ao **ataque desarmado do
  tamanho** (Pequeno/Diminuto 1d2 · Médio 1d3 · Grande 1d4) + mod Força.
- "Arma improvisada" é um conceito reaproveitável; por ora só a besta sem flecha o aciona.

### Terreno 🟡

- Por ora só há um tipo: **parede**. Bloqueia movimento e linha de visão.
- O mapa gera alguns trechos curtos de parede no miolo; a geração garante que os
  dois lados continuam conectados (ninguém fica preso).
- **Quina diagonal:** a grade é quadrada, então volta e meia duas paredes se
  encontram numa quina. Quando **as duas casas ortogonais** de uma quina são
  parede, **não dá pra cortar a diagonal por ali** — nem andando, nem enxergando
  (ex.: `parede`/`vazio` em cima, `personagem`/`parede` embaixo → o personagem
  não anda pro `vazio` e não tem visão pra lá). **Uma parede só** na quina não
  fecha nada. Em `board.diagonal_corner_blocked`, aplicada em `reachable`,
  `path_step_toward` e `los_clear`.

### Visão e luz 🟡

Regra em `board.py` (`los_clear`) e `vision.py` (`cell_lit`, `can_see`).

- **Linha de visão (LOS):** traço reto (Bresenham) entre as casas; uma **parede**
  no meio bloqueia, e **duas paredes fechando uma quina** também bloqueiam a
  diagonal que passaria entre elas (ver *Quina diagonal* no Terreno). Um
  personagem enxerga "infinitamente" na LOS — o teto é **200 m (133 casas)**,
  mais que o tabuleiro.
- **Luminosidade:** o mapa é **sempre escuro**. Um personagem enxerga **só a
  própria casa**; o resto do mapa é **preto**, exceto:
    - casas dentro do raio de uma **fonte de luz** (com LOS até a fonte).
    - alvos dentro de **12 casas (18 m)** de quem tem **Visão no escuro** — esse vê
      como se fosse claro.
  - Toda luz revela a área **para os dois times**.
- **Fontes de luz:**
  | Fonte | Raio | Como se usa |
  |---|---|---|
  | **Lanterna** (item do Guarda) | 9 m (6 casas) | fica no slot de item, sempre acesa |
  | **Tocha** | 6 m (4 casas) | ilumina igual na mão ou caída no chão; na mão ocupa a mão da arma (ataca desarmado enquanto segura) |
- **Tochas** são **objetos no chão** (`GroundObject`, `kind = "torch"`). O mapa de
  teste espalha **6**.
  Pegar (ação Pegar, 1 ponto): quem está **desarmado** apanha; quem está **armado**
  **troca** a arma pela tocha (a arma cai no chão). Pegar uma arma depois **larga a
  tocha**.
- **A visão é do PERSONAGEM, não do jogador.**
  - **No seu turno:** a tela mostra só o que o **personagem ativo** enxerga. A
    tecla `L` alterna para a **visão do esquadrão** (união do seu time vivo) e de
    volta.
  - **No turno do inimigo:** vale sempre a **união do seu esquadrão vivo** (o time
    todo de olho enquanto o inimigo se mexe).
  - Seus próprios personagens aparecem sempre (você sabe onde sua tropa está);
    o que muda é o mapa revelado e quais inimigos você vê.
  - Uma **parede** aparece se o observador enxerga alguma casa colada nela.
- Inimigos fora da visão ficam **ocultos**: não desenhados, não podem ser
  mirados nem inspecionados.
- A **IA** enxerga pelos olhos de cada unidade dela: só ataca o que aquela unidade
  vê, mas ainda avança na direção do inimigo mais próximo. Ignora tochas (só corre
  atrás de arma caída quando desarmada).

### Arremesso 🟡

- Só funciona com **arma de arremesso**. Por ora **só a Adaga** (alcance **9 m = 6 casas**).
- **Acerto:** `d20 + mod Destreza` (+ mods típicos, mesma regra de acumulação) vs CA.
  20 natural = crítico; 1 natural = erro crítico.
- **Dano:** dado da arma **+ mod Força** (a força entra no dano, não no acerto).
- Depois de arremessar, o personagem fica **desarmado** (passa a usar o ataque
  desarmado do tamanho dele) — *independente de acertar ou errar*.
- A arma **cai no chão** numa casa livre adjacente ao alvo e vira um **objeto**.

### Desmoralizar 🟡

Regra em `actions.py` (classe `Demoralize`). Ataque **social**: mina a
confiança do alvo em vez de o ferir.

- **Custo:** 1 ponto de ação.
- **Alcance:** **18 m (12 casas)**.
- **Requisitos (todos):** os dois personagens **se enxergam** (LOS + regra de
  visão nos **dois sentidos**) **e** compartilham pelo menos **um idioma**.
  - **Exceção — Kenku ("Imitar sons"):** dispensa o idioma em comum **como
    atacante** (imita a voz do alvo). Isso não vale na defesa: para desmoralizar
    *um Kenku*, quem provoca ainda precisa de um idioma em comum com ele.
- **Acerto:** `d20 + mod Carisma` vs **Defesa Mental** do alvo (`10 + mod Sab`).
  20 natural = crítico automático; 1 natural = falha crítica. Sem dano.
- **Efeito (acerto):** o alvo fica **Desmoralizado** — penalidade de **−1 do tipo
  `status`** em **ataque, CA e Defesa Mental**.
- **Duração:** a condição expira **no fim do próprio turno de quem a sofreu**
  (`Unit.end_turn`). Ou seja, se o alvo é desmoralizado logo depois do turno
  dele, carrega o −1 pela rodada inteira até fechar o próximo turno.
- A **IA** usa Desmoralizar quando não alcança o alvo para atacar e ele ainda não
  está desmoralizado.

### Objetos no chão 🟡

- Um objeto ocupa uma casa mas **não bloqueia** movimento nem linha de tiro.
- Tipos hoje (`GroundObject.kind`): **`weapon`** (adaga arremessada / arma
  largada) e **`torch`**.
- Ação **Pegar** (1 ponto), objeto na casa ou **adjacente**:
  - **arma:** só quem está **desarmado**.
  - **tocha:** qualquer um — se estiver armado, **troca** (larga a arma).
  - o que estava na mão cai na casa do personagem.
- A IA prioriza recuperar a própria arma caída antes de voltar a atacar (ignora tochas).

### Fugir do combate 🟡

Ação em `actions.py` (classe `Flee`). Vale pros **dois lados** — jogador e IA.

- **Custo:** 1 ponto, e **encerra o turno** (você está correndo, não lutando).
- **Requisito de posição:** só dá pra fugir de uma casa **na borda do mapa**
  (qualquer casa do footprint encostada em `x = 0`, `x = COLS−1`, `y = 0` ou
  `y = ROWS−1`). Fora da borda o botão fica apagado ("chegue na borda").
- **A fuga é bem-sucedida** (determinística — o botão só acende quando dá certo)
  se **qualquer uma**:
  - seu **deslocamento** é **maior** que o do mais rápido dos inimigos vivos
    (`actor.speed > max(pursuer.speed)`); **ou**
  - você já está **longe o bastante** — a menor distância até um inimigo vivo é
    **maior** que o deslocamento do mais rápido deles (`nearest > fastest`): numa
    corrida até fora do mapa eles não fecham o vão.
  - Sem inimigos vivos, foge sempre.
- **Efeito:** o personagem vira estado `fugiu` — sai do tabuleiro (não é
  desenhado, não bloqueia, não conta pra vitória, não é alvo), mas **sobrevive**
  à batalha e volta pra guilda com o que estava carregando. Não vira loot.
- **Arrasta os caídos adjacentes.** Ao fugir, todo aliado **caído** (morrendo /
  estável / quebrado) numa casa **adjacente** ao fugitivo também sai (vira
  `fugiu`, sobrevive). Quem estava longe **fica pra trás**: se o último de pé
  foge, o outro lado "vence" e os corpos deixados são **perdidos com a derrota**
  (`_wipe_side`). Para salvar o amigo, posicione-se ao lado dele antes de fugir.
- Se **todos os inimigos** fogem/caem, a vitória é do jogador normalmente.

**Comportamento por tendência (IA)** — a tendência (§8) tempera as bordas da IA,
principalmente no eixo moral:

- **Mau:** dá o **golpe de misericórdia** num inimigo caído adjacente (mata o
  `morrendo` na hora, impede o jogador de estabilizar) antes de seguir lutando.
  Só em combate **letal** — na arena já derruba sem matar.
- **Bom:** **estabiliza** um aliado caído adjacente antes de qualquer outra coisa
  e, quando foge, leva o ferido junto (regra de arrastar acima).
- **Caótico:** quebra e corre **mais cedo** (PV ≤ 50%, basta estar em menor
  número). **Leal:** só foge quando **nenhum aliado de pé** resta.
- Ainda **sem pathfinding pra fugir**: a IA só foge de uma borda onde já está.
  Correr proativamente até a borda fica pra depois.

### Tabela de armas 🟡

| Arma | Dano | Alcance | Finesse | Arremesso |
|---|---|---|---|---|
| Adaga | 1d4 | corpo-a-corpo | sim | 6 casas (9 m) |
| Martelo Leve | 1d4 | corpo-a-corpo | sim | — |
| Picareta Leve | 1d4 | corpo-a-corpo | sim | — |
| Machadinha | 1d6 | corpo-a-corpo | não | — |
| Clava | 1d6 | corpo-a-corpo | não | — |
| Bordão | 1d6 | corpo-a-corpo | não | — |
| Lança Curta | 1d6 | corpo-a-corpo | não | — |
| Machado | 1d8 | corpo-a-corpo | não | — |
| Martelo | 1d8 | corpo-a-corpo | não | — |
| Picareta | 1d8 | corpo-a-corpo | não | — |
| Besta Leve | 1d8 | 11 casas | não | — |

> Machadinha, Lança Curta e Martelo Leve são candidatos óbvios a arma de arremesso
> mais adiante; por decisão de design começamos só com a Adaga.
>
> A **Besta Leve** consome flecha (Aljava = 20). Sem flecha vira arma improvisada
> — ver §Munição e arma improvisada.

---

## Sistemas de mundo 🟡

Regras que existem **fora do combate** — a guilda no mapa, o tempo passando, a
economia. Cada uma nasce como "coisa do mundo" e só depois conversa com a luta.

### Fome 🟡

Estado em `unit.py` (`unfed_days`, propriedades `hunger_*`); a rotina diária em
`Guild.pass_time` / `Guild._daily_upkeep`, chamada quando a guilda **viaja** no
mapa ou faz uma **parada de manutenção** (o tempo de batalha é em segundos e não
conta refeição).

- **Todo personagem come uma vez por dia.** Cada dia de mapa cruzado, o
  personagem consome **1 item de comida** da mochila (`data.FOOD_ITEMS` — hoje
  `1kg Carne`, `1kg Batata`). Comeu → contador zera. O upkeep diário devolve uma
  linha de evento com quantos comeram e quantas rações sobraram, além dos avisos
  de fome/morte.
- **Manutenção (botão no mapa, `Guild.do_maintenance`):** a guilda para 1 h onde
  está; passa o tempo (que pode cruzar a meia-noite e disparar a refeição diária)
  e então **quem ainda está com fome e carrega comida come na hora**
  (`Unit.eat_now` — só alivia, nunca avança a fome). É onde outras tarefas de
  parada (descanso, conserto de equipamento) entram depois.
- **Sem comida na mochila:** o contador de dias sem comer sobe.

  | Dias sem comer | Condição | Efeito |
  |---:|---|---|
  | 1 | **com fome** | −2 em **todos os atributos** (−1 nos modificadores; o PV máx. também cai um pouco pela Constituição) |
  | 2 | **esfomeado** | −4 em todos os atributos; **PV máximo = 1** |
  | 3 | **morrendo de fome** | **incapacitado** — não pode ser mandado pra batalha (desmaiado) |
  | 4 | — | **morre** (removido da guilda) |

  > O gatilho de morte é `data.STARVATION_DEATH_DAYS = 4`: o personagem passa um
  > dia inteiro "morrendo de fome" (visível na ficha) e morre na virada seguinte
  > se ainda não comeu. Ajuste a constante pra encurtar.

- **Autótrofo (Leshy):** faz fotossíntese — **nunca come e nunca passa fome**.
  `consume_daily_food` devolve `"ate"` sem tocar na mochila.
- Comida está **à venda no mercado** (`1kg Carne` 5c, `1kg Batata` 3c). Açougueiro,
  Agricultor e afins já começam com uma refeição na mochila.
- Comer/morrer **re-deriva** os atributos do personagem (`_derive_combat`), então
  a ficha, os cartões da guilda e a próxima batalha já mostram os números certos.
  Se a guilda inteira morrer de fome na estrada, a campanha acaba (`on_wipe`).

### Madeireira: trabalho por hora 🟡

Nó `madeireira` no mapa (tipo `town` com `work=True`), a **1 h da Cidade**. Tela
em `work_screen.py`; regra em `Guild.work_shift` / `economy.lumber_pay`. É o
**piso econômico**: quem perdeu tudo na arena e ficou pelado vai lá trocar tempo
por cobre em vez de entrar nos Ermos e morrer.

- **Como funciona:** escolhe quem vai (o mesmo seletor do mercado) e o **turno**
  — 4, 8, 12 ou 16 h (`economy.LUMBER_SHIFT_HOURS`). Confirmar roda o turno:
  passa o tempo (`pass_time`, pode cruzar a meia-noite e disparar a refeição do
  dia) e paga cada trabalhador.
- **Pagamento:** `economy.LUMBER_WAGE` = **3 cobre a cada 4 h** cheias
  (`LUMBER_BLOCK_HOURS`), hora quebrada não conta. Um dia cheio de 16 h = **12
  cobre** por cabeça. O cobre cai direto na bolsa de cada um.
- **XP de trabalho:** `Unit.work_hours` acumula as horas; `Unit.work_xp` =
  `work_hours // 16` (`LUMBER_XP_HOURS`). Ou seja **1 marca a cada 16 h
  trabalhadas**. Hoje é só cosmético (como o Nível 0 / XP 1000 perdido) — um
  sistema de ofício lê isso depois.
- **Sem lenha:** o machado é emprestado e a árvore não é sua; você leva **só o
  salário pelas horas**, nenhum item.
- **Balanço:** 0,75 cobre/h é de propósito baixo. Um dia inteiro alimenta
  (Batata 3c) e sobra ~9 cobre; reconstruir um kit mínimo (~30 cobre) leva ~3
  dias. Uma bolsa de arena ganha (+11 líquido na Fossa, +40 no Ringue) ou um
  saque nos Ermos rende muito mais rápido — a madeireira é rede de segurança,
  não carreira.
- Quem está **incapacitado de fome pode trabalhar** (não é combate); é
  justamente quem mais precisa. Se um trabalhador morre de fome no meio do turno
  (turno longo cruzando a virada), ele não recebe.

### Mercado e negociação 🟡

Regra em `data.market_deal` / `data.buy_price` / `data.sell_price`; tela em
`market_screen.py`. O `Node` do tipo `market` carrega o **idioma** e a
**tendência** do vendedor (hoje: Mercado fala **Ankarin**, tendência **Leal e
Neutro**).

- **Preço tabelado** (`data.PRICES`) é a base. Compra na tabela, revenda a
  **50%** (`SELL_FACTOR`) — sempre prejuízo.
- **Negociar** aperta o spread. Vira uma fração `deal` única pra visita:
  - **Só quem fala o idioma do vendedor negocia.** Entre esses, o de **maior
    modificador de Carisma** fala pelo grupo. Ninguém fala o idioma → `deal = 0`,
    preço tabelado (é a vantagem do **Humano** com "Idioma adicional", e do
    Kenku *não* — "Imitar sons" só serve pra Desmoralizar, não pra pechinchar).
  - **Carisma:** `+0,04` de `deal` por ponto de modificador (só o positivo).
  - **Tendência:** distância entre a tendência do negociador e a do vendedor
    (0 a 4, `data.alignment_distance`): `0 → +0,10 · 1 → +0,05 · 2 → 0 ·
    3 → −0,05 · 4 → −0,10`. Igual ajuda, oposta cobra ágio.
  - `deal` fica preso em **[−0,15 ; +0,25]**.
- Aplicação: `compra = base × (1 − deal)`, `venda = base × (0,5 + 0,4 × deal)`.
  O teto de `deal` (0,25) garante que a venda continua **abaixo** da compra
  (fatores 0,15 apart), então não dá pra fazer dinheiro comprando e revendendo.
- A tela mostra a linha "vendedor fala X · tendência Y · desconto/ágio Z%".

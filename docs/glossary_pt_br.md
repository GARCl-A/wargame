# Glossary — `pt-br`

The terms every `pt-br` string uses the same way. A string that needs a term not listed here adds it here first.
The mechanics (keys, `i18n.Ref`, articles, `.f` variants, `scripts/i18n_merge.py`, `i18n_audit.py`, `i18n_leaks.py`) are in
the i18n recipe of [../README.md](../README.md). Status: **approved** by the author (2026-11-05); **proposed** is the translator's
pick, waiting for the author's read in play.

## Voice and grammar

- The player is addressed as "você"; a button is an imperative ("Atacar"), a tab a noun ("Guilda").
- No sentence is built by joining translated fragments: one key per sentence, with placeholders.
- A noun that changes an article carries its `gender` in its catalog entry; an adjective that agrees is a `.f` variant of the key.
- Composed names are rules, not entries: `Large X` / `Huge X` = base + size (Grande / Enorme), `Scroll of X` = scroll + spell,
  `Dictionary of X` = dictionary + language; race items are written out with gender ("enânica" / "enânico").
- Beast epithets have a masculine and a feminine form (`name.epithet.<id>`, `name.epithet_f.<id>`), listed below.

## Rules and attributes

| English | Portuguese | Status |
|---|---|---|
| STR / DEX / CHA | FOR / DES / CAR | approved |
| CON / INT / WIS | CON / INT / SAB | proposed |
| AC / MD / HP | CA / DM / PV | approved |
| DC | CD | proposed |
| SPD / INIT | VEL / INIC | approved |
| Mental Defense | Defesa Mental | proposed |
| Initiative, Round, Turn | iniciativa, rodada, turno | proposed |
| Reach, Range | alcance, distância | proposed |
| Square (sq) | casa | proposed |
| Flanked, Off-guard, Prone, Downed | flanqueado, desprevenido, caído, incapacitado | proposed |
| Damage, To hit | dano, para acertar | proposed |
| Armour, Shield | armadura, escudo | proposed |
| pt / pts (action points) | pt / pts | proposed |
| Weapon trait | traço da arma | approved |
| Racial ability, Talent | habilidade racial, talento | proposed |
| Tongue (the Grippli's limb) | Língua | approved |

## Actions

| English | Portuguese | Status |
|---|---|---|
| Takedown, Grab, Escape Grapple | Derrubar, Agarrar, Desagarrar | approved |
| Brutal | Brutal | approved |
| Attack, Defend, Flee, Push, Throw, Reload | Atacar, Defender, Fugir, Empurrar, Arremessar, Recarregar | proposed |
| Demoralize, Stand Up, Non-lethal | Desmoralizar, Levantar, Não letal | proposed |
| Sneak Attack, Precise Thrust, Long Thrust | Ataque Furtivo, Estocada Precisa, Estocada Longa | proposed |
| Cleave, Repel Strike, Maiming Strike | Ceifar, Rechaçar, Golpe Mutilante | proposed |
| Armor Pierce, Power Shot, Extreme Shot | Perfurar Armadura, Tiro Poderoso, Tiro Extremo | proposed |
| Hook Shield, Javelin Charge, Parry & Strike | Prender Escudo, Arremesso em Corrida, Aparar e Golpear | proposed |
| Wrest, Pick up, Stabilize, First Aid | Arrancar, Pegar, Estabilizar, Primeiros Socorros | proposed |
| Drink Potion, Mount / Dismount | Beber Poção, Montar / Desmontar | proposed |
| Wake Up, End Turn, Delay | Acordar, Encerrar Turno, Adiar | proposed |
| Assess, Investigate | Avaliar, Investigar | proposed |
| Disarm Trap, Capture | Desarmar Armadilha, Capturar | proposed |
| Move, Climb, Jump, Swim | Mover, Escalar, Saltar, Nadar | proposed |

## World

| English | Portuguese | Status |
|---|---|---|
| Guild, Charter, Loyalty | Guilda, Estatuto, Lealdade | approved |
| Band | Grupo | approved |
| Vocation | Vocação | approved |
| Warband, Delvers, Wanderers (id `wilds`), Scholars, Caravan, Survivors (id `marsh`) | Bando de Guerra, Exploradores, Andarilhos, Eruditos, Caravaneiros, Sobreviventes | approved |
| Faction, Reputation, Deed, Mission, Node | facção, reputação, feito, missão, local | proposed |
| Pack, Copper Coin, Gold Coin | mochila, Moeda de Cobre, Moeda de Ouro | proposed |
| The Wilds (the place) | os Ermos | proposed |
| Dwarf (race) | Anão (adjective: enânico / enânica) | approved |
| Large / Huge (size) | Grande / Enorme | approved |
| Tiny / Small / Medium (size) | Minúsculo / Pequeno / Médio | proposed |
| Aurochs | Auroque | approved |

Factions: The Pits = As Fossas, The Bankers = Os Banqueiros, The Library = A Biblioteca, The Apothecary = O Boticário,
The Tanners = Os Coureiros, The Blood Cult = O Culto do Sangue, The Nature Coven = O Clã da Natureza, The Faith Order = A Ordem da Fé,
Field Command (id `ledger_hold`) = Posto de Comando.

Labels the server writes as words (`ui.lab.*`, approved): Cart = Carroça, Carriage = Carruagem, Tack = Arreios, Rides / Walks = Cavalga / Anda,
Squatting = ocupação, Bays = vagas, Herd = rebanho, Feed = Comida, Purse = Bolsa, Load = Carga, Crowd (recruiting penalty) = Lotação,
Hungry / Sick / fed = Com fome / Doente / alimentado.

Claim stages (approved): Scouted = Reconhecido, Swept = Vasculhado, Cleared = Liberado, Fenced = Cercado, Sustaining = Sustentado,
Established = Estabelecido. Traps (approved): Bear trap = Armadilha de Urso, Alarm trap = Armadilha de Alarme, Web = Teia.
Archetypes (approved): LÍDER, FORTE, RESISTENTE, SAUDÁVEL, ÁGIL, GÊNIO, SÁBIO, ARRISCADO.

Banner colours (proposed): Steel = Aço, Teal = Turquesa, Forest = Floresta, Amber = Âmbar, Crimson = Carmesim, Violet = Violeta, Rose = Rosa,
Slate = Ardósia. Banner emblems (proposed): Shield = Escudo, Bulwark = Baluarte, Vigil = Vigília, Blade = Lâmina, Wolf Cry = Uivo do Lobo,
Wolf = Lobo, Serpent = Serpente, Flame = Chama, Stars = Estrelas, Storm = Tempestade.

## Languages

Draconic = Dracônico, Dwarvish = Enânico, Elvish = Élfico, Gnomish = Gnômico, Orcish = Orc, Sylvan = Silvestre, Verdant = Verdejante,
Common = Comum; Ankarin, Goblin, Halfling and Jotun stay (proposed). Any Dictionary = Qualquer Dicionário (approved).

## Names

| English | Portuguese | Status |
|---|---|---|
| The Snake Dragon | A Dragobra | approved |
| Sanctum Spider | Aranha do Santuário | approved |
| Ruin Sentry | Sentinela das Ruínas | approved |
| The Ancient Archivist | O Arquivista Ancestral | approved |
| Kharzuul the Ember-Old | Kharzuul, a Brasanciã | approved |
| Oskar Vell, the Gravecaller | Oskar Vell, o Levanta-Corpos | approved |
| Grumbold the Builder | Grumbold, o Konstrutor (misspelt on purpose) | approved |
| Adelio Small-Knife | Adelio Facadinha | approved |
| Biwolf | Grão-Lobo | approved |
| Signal Horn | Trompa Sinalizadora | approved |

Beast epithets (masculine / feminine), approved: Marcado/a, Pálido/a, Descarnado/a, Velho/a, Jovem, Negro/a, Cinzento/a, Ligeiro/a, Esguio/a,
Magro/a, Troncudo/a, Arisco/a, Inquieto/a, Carrancudo/a, Soturno/a, Nervoso/a, Faminto/a, Definhado/a, Selvagem, Surrado/a, Audaz, Astuto/a.
"Lustroso" and "Taciturno" were rejected.

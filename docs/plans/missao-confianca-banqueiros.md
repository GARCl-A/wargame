# Plano: a missão de confiança dos Banqueiros (cofre, Crime, Old Road, fortaleza)

Escrito em 2026-09-12, numa sessão de desenho que não chegou a implementar nada
disso — só as 3 deeds do bloco "já implementado" abaixo. Este documento existe
pra uma sessão futura (com zero memória desta conversa) conseguir pegar o
trabalho de onde parou, sem precisar re-perguntar o que já foi decidido.

## Contexto: por que isso existe

Visão de longo prazo do jogo: a guilda vai poder construir uma base própria.
Antes de construir, precisa de um lugar — e isso abre dois caminhos: comprar
propriedade na cidade (legal, via reputação com os Banqueiros) ou limpar um
pedaço da natureza (ilegal, tem que defender). Este plano cobre só o primeiro
caminho até o ponto de destravar a compra da propriedade; o caminho da
natureza fica para depois.

O gate de compra de propriedade é **reputação 4 com os Banqueiros**. As 3
deeds "econômicas" (já implementadas) valem 1 rep cada = 3. A 4ª deed
(`bankers_trust`, ainda não implementada) fecha em +1 vindo de uma missão
especial de "teste de confiança": levar um cofre da Cidade até uma fortaleza,
trazer de volta uma carta confirmando a entrega. O cofre pode ser aberto no
caminho (rouba o conteúdo, mas falha a missão e te deixa marcado como
criminoso). Isso trouxe pra mesa dois sistemas novos e independentes: viagem
perigosa (a Old Road) e um sistema de Crime/autoridades.

## Já implementado — não mexer, só referência

Commit ainda não feito (rodar `/pre-commit` nisso é a outra parte deste pedido),
mas o código já está na árvore de trabalho:

- `gartok/factions.py`: 3 deeds novas na facção `bankers` — `bankers_good_for_business`,
  `bankers_steady_customer`, `bankers_diverse_portfolio`. `Event` ganhou o campo `tag`.
- `gartok/missions.py`: `MissionTemplate` ganhou `tag` (ex. `"economic"` no
  `TANNER_HIDES`); `turn_in()` agora dispara `factions.settle` e retorna as
  deeds ganhas.
- `gartok/guild.py` / `gartok/persist.py`: `guild.total_spent` e
  `guild.items_sold_kinds` (contadores vitalícios que as deeds dos Bankers leem
  direto, sem precisar do evento carregar o dado).
- `gartok/market_screen.py`: `_buy`/`_sell` atualizam os contadores acima e
  chamam `factions.settle`, via um helper novo `_settle_market()`.
- `gartok/tanner_screen.py`: turn-in mostra a deed ganha junto do pagamento.
- `tests/test_screens.py`: ajustado pra passar `guild`/`node` no teste de
  compra do mercado (agora obrigatório, as deeds leem `self.guild`).

A 4ª deed (`bankers_trust`) **não existe ainda** — ela é parte do Sistema 4
abaixo e depende da missão especial estar implementada.

## Sistema 1 — implementado (2026-09-12, sessão 2)

Commitado (rodar `git log` pra achar o commit; passou por `/pre-commit`).
Tudo da seção "Sistema 1" abaixo está feito e testado
(`tests/test_justice.py`, `tests/test_justice_integration.py`, mais um
round-trip de save em `tests/test_persistence.py`). Detalhes pra quem for
mexer nisso depois:

- `gartok/justice.py` (novo): `guard_test`/`catch` (o teste), `jail`/
  `release_due` (prisão, mesmo padrão do `taverna_pool` — `guild.jailed`),
  `patrol_pack`/`patrol_level` (a patrulha escalada), `resolve_fight_crime`.
- `Unit.crime`, `world.Node.jurisdiction` (city/market/tavern/arena; o
  lumber_yard ficou de fora -- decisão do usuário), `Guild.jailed` -- tudo
  persistido (`persist.py`, `SAVE_VERSION` foi pra 12).
- `campaign.advance()` testa jurisdição em toda chegada (waypoint ou destino
  final) e, se pega alguém, pausa o grupo numa `Order(kind="guard", ...)`
  (campos novos em `orders.Order`: `caught`, `prev_node`, `resume_path`).
  `campaign.resolve_guard_prison` / `resolve_guard_flee` /
  `resolve_guard_fight_aftermath` resolvem as 3 escolhas e devolvem a rota
  interrompida (ou tocam a rota adiante, ou deixam o grupo idle).
- `justice_screen.GuardScreen` (nova tela) + `app.py` (`_open_guard_check`,
  `_start_guard_battle`, e um branch novo em `_battle_end`) -- "lutar" cai no
  pipeline de batalha normal (`campaign.absorb_battle`), num `Scenario()`
  genérico quando o nó não tem um próprio (city/market/tavern nunca tinham
  luta antes disso).

Decisões tomadas dentro do espaço que o doc original deixava em aberto (não
foi preciso perguntar de novo, mas registrando pra não parecerem arbitrárias):
- **Só a unidade originalmente pega banca crime na luta** (`+1` + guardas
  mortos) -- quem mais brigar do lado dela não ganha crime. Era uma pergunta
  em aberto no doc original; ficou o default mais simples.
- **Fugir só funciona uma vez por prisão**: se pega de novo no nó anterior
  (`prev_node`), a nova ordem de guarda nasce sem `prev_node` (`None`) --
  `GuardScreen` esconde o botão RUN nesse caso, só resta lutar ou aceitar
  prisão. Não estava no doc original; é uma simplificação deliberada pra não
  precisar rastrear o nó anterior ao anterior.
- Fórmulas ainda placeholder, como o doc já avisava: `prison_days = crime * 2`,
  patrulha = 2 guardas em `mean_level = min(6, crime)`.

**Próximo passo, se for continuar a partir daqui: Sistema 2 (Old Road
"unsafe")** -- ver a seção correspondente abaixo, que ainda não foi tocada.

## Decisões já fechadas (não é pra re-perguntar ao usuário)

- **Crime é por personagem** (`Unit.crime`, como `gold`), não da guilda inteira.
- **O teste da guarda roda em TODO nó de jurisdição visitado**, mesmo em
  movimentos internos à cidade (mercado -> banco -> taverna), não só ao cruzar
  a fronteira vindo de fora.
- **Perder a luta contra a polícia segue a regra letal normal** — permadeath
  possível, corpo saqueado, igual qualquer outra luta letal do jogo. Não tem
  rede de segurança.
- **Prisão só remove o criminoso do grupo**, temporariamente. O resto do grupo
  segue livre — "não tem porque punir todo mundo se eles estão agindo de boa
  fé" (palavras do usuário).
- **A emboscada da Old Road é um risco novo permanente daquele nó** (não é
  algo que só existe enquanto a missão do cofre está ativa) — rola uma vez por
  viagem que passa por ali, não por hora (diferente do Hunt).
- **A emboscada perto da fortaleza é exclusiva da missão do cofre** — bandidos
  sabem que a carga é valiosa e emboscam por causa disso, não é um risco
  permanente daquele trecho do mapa.
- **Fugir do teste da guarda** volta o grupo pro nó anterior da rota, que
  re-testa se também for jurisdição.

## Sistema 1 — Crime, jurisdição e o evento da guarda

### Dados novos
- `Unit.crime: int = 0` — campo novo, mesmo tratamento que `gold` (ver
  `unit_to_dict`/`Unit.from_save` em `persist.py` e `unit.py`).
- `world.Node` ganha `jurisdiction: str | None = None` no `__init__` (mesmo
  padrão dos flags que já existem: `work`, `bank`, `tanner`, `arena`).
  - `jurisdiction="the_city"` nos nós: `city`, `market`, `tavern`, `arena`
    ("nas celas sob a cidade", já é território dela).
  - **Decisão em aberto** (não foi perguntada ainda): `lumber_yard` fica "fora
    dos muros" segundo o próprio blurb do nó — decidir se conta como
    jurisdição da cidade ou não antes de implementar esse campo. `road` e
    `wilds` definitivamente ficam de fora.
- Um novo registro de quem está preso e quando sai. Não dá pra só remover o
  `Unit` de todo `Group` — `Guild.roster` é a lista achatada sobre
  `guild.groups`, então sumiria de tudo (upkeep diário, fome, etc.) sem um
  lugar pra "guardar" o personagem enquanto isso. Solução: seguir o mesmo
  padrão de `guild.taverna_pool` (uma lista de `Unit` fora de qualquer grupo,
  mas ainda pertencendo à guilda) — algo como
  `guild.jailed: list[(Unit, released_day)]`, persistido em `persist.py` do
  jeito que `taverna_pool` já é.

### O gatilho
No loop de resolução de viagem (`campaign.py`, dentro de `advance()` — onde
hoje `order.kind == "travel"` resolve e chama `factions.settle(..., Event("travel", ...))`
para as deeds de "chegou em tal lugar"): depois de mover o grupo pro nó, se
`world.node(g.node).jurisdiction` não for `None`, iterar os membros do grupo
com `unit.crime > 0` e rolar o teste pra cada um.

### O teste
`data.d20() + unit.crime >= 11` — mesmo idioma que `DEATH_SAVE_MIN = 11` já
usa em `data.py` (base 50%, cada ponto de crime soma reto no d20, sem
inventar um sistema de probabilidade novo).

### O evento (quando o teste acerta)
Precisa de uma tela nova (modal, parecido com `reward_screen.py`) oferecendo 3
escolhas pra unidade pega:

1. **Aceitar prisão**: `unit.crime = 0`; a unidade sai do(s) `Group`(s) atual
   (mesmo mecanismo que remoção por morte usa, mas reversível) e entra em
   `guild.jailed` com uma data de soltura. Fórmula de dias de prisão ainda não
   definida — sugestão de placeholder: `dias = crime_no_momento_da_prisao * 2`
   (ajustar depois de jogar). Um passo em `Guild._daily_upkeep` (mesmo lugar
   que já chama `missions.expire_overdue`) libera quem completou a pena,
   devolvendo a `Unit` pra um grupo na Cidade (ex.: um grupo solo novo lá, ou
   junta no primeiro grupo que estiver no nó `city`).
2. **Lutar com a polícia**: uma luta letal contra uma patrulha escalada por
   crime — reaproveitar `encounters.build_enemy`/`roll_pack` com
   `mean_level ~ min(6, unit.crime)` (placeholder, ajustar). Resolvida pelo
   mesmo pipeline de `campaign.absorb_battle` que qualquer luta letal já usa.
   Depois do resultado: sobreviventes com o `crime` original ganham
   `+1` (por ter brigado) `+ outcome.player_kos` (por guarda morto —
   `BattleOutcome.player_kos` já conta "enemies the squad put down", não
   precisa de campo novo). Se a unidade morreu na luta, não há o que
   incrementar — é só uma morte permanente normal.
3. **Fugir**: redireciona a ordem do grupo de volta pro nó anterior da rota
   (reaproveitar `orders.py`), o que ao chegar lá roda o mesmo teste de novo
   se aquele nó também tiver jurisdição.

### O que falta decidir na hora de implementar
- Fórmula exata de dias de prisão e de nível da patrulha (marcados como
  placeholder acima).
- Se outros membros do grupo que lutam ao lado do criminoso também ganham
  crime por matar guarda, ou só a unidade originalmente pega.
- Onde exatamente a `Unit` presa reaparece ao ser solta.

## Sistema 2 — Old Road como nó "unsafe"

### Dados novos
- `world.Node` ganha `unsafe: bool = False` e
  `encounter_table: tuple | None = None`.
- O nó `road` ("Old Road") recebe `unsafe=True, encounter_table=OLD_ROAD_TABLE`.
- Nova tabela em `encounters.py`:
  ```python
  OLD_ROAD_TABLE = (
      EncounterEntry(70, None),                    # bandido -- humanoide comum
      EncounterEntry(30, tuple(data.BEAST_POOL)),   # lobo, por enquanto o único da pool
  )
  ```
  Note que "bandido" não é uma raça própria — é exatamente o mesmo truque que
  a `WILDS_TABLE` já usa pro seu 30% de humanoide comum (`race_pool=None` cai
  em `data.roll_race()` sem filtro). Só está invertendo os pesos e trocando o
  nó.

### O gatilho
Mesmo ponto de resolução de viagem do Sistema 1. Se `world.node(g.node).unsafe`,
rolar uma chance fixa por viagem (não por hora) — propor uma constante nova,
ex. `ROAD_AMBUSH_CHANCE = 0.35` em algum lugar como `world.py` ou
`encounters.py`, tunável depois. Se acertar, interromper a viagem com uma luta
letal contra `encounters.roll_encounter(OLD_ROAD_TABLE)`. Depois da luta (se
sobreviveram), a viagem continua normalmente.

Isso é o mesmo padrão de "shift interrompido por emboscada" que `hunt.py` já
faz (`hunt_stretch`), só que acoplado à resolução de uma perna de viagem em vez
de um turno parado. Vale olhar como `app.py` guarda o estado de uma emboscada
de Hunt em andamento (`app._hunt`) pra montar o equivalente aqui — provavelmente
um `app._road_ambush` ou reaproveitar o mesmo `pending` que já existe pra
paradas interativas (arena/mercado/banco/recrutamento/hunt) em `campaign.py`.

## Sistema 3 — Cofre genérico com fechadura

- Um item novo do tipo "cofre", com uma dificuldade de fechadura (DC).
- Ação: `data.d20() + unit.mod_dexterity >= dc_da_fechadura` — mesmo idioma de
  teste que `actions.py` já usa em todo lugar (`FIRST_AID_DC`, etc.).
- Falha não tem custo automático (pode tentar de novo) — decisão default,
  ninguém pediu pra mudar isso.
- O cofre da missão é uma instância desse mesmo tipo, só com uma flag de "item
  de missão" a mais (visto que `missions.py` já trata itens especiais
  diferente de itens empilháveis comuns).
- As "pedras preciosas" de dentro precisam existir em `data.py` como item
  vendável (preço em `economy.py`).
- **Decisão em aberto**: onde a ação de abrir mora na UI — provavelmente um
  botão novo na tela de equipamento/mochila (parecido com `gear_screen.py`),
  mas isso é decisão de tela, não de regra.

## Sistema 4 — a missão da Confiança (fecha o arco)

Amarra os 3 sistemas acima. Estrutura:

1. **Aceitar**: uma nova `MissionTemplate` (giver ligado aos Banqueiros, nó
   `city`) que, ao aceitar, também dá o item único do cofre pro signatário
   (hoje `missions.accept` só cria o registro do `Mission` — vai precisar de
   uma variante ou de um passo extra que dê o item, já que essa missão não é
   "junte N de X" como a do coureiro).
2. **Ida**: o caminho até a fortaleza passa pela Old Road (Sistema 2 já cobre
   o risco genérico do trecho).
3. **Emboscada da fortaleza**: ao chegar perto do nó da fortaleza, se essa
   missão específica está ativa e a emboscada ainda não foi resolvida (`Mission`
   precisa de um campo novo, ex. `ambush_done: bool = False`), força uma luta
   num mapa autoral — mesmo padrão dos bosses do arena (`Bout.map_slug`,
   `map_lib`). **O mapa em si o usuário vai desenhar depois** — estruturar o
   código pra o `map_slug`/scenario ser plugável (referência a um slug que
   ainda não existe, sem travar o resto da missão por causa disso).
4. **Troca na fortaleza**: uma tela nova (parecido com `tanner_screen.py`) onde
   um NPC troca o cofre fechado por uma "Carta de Recebimento".
5. **Entrega**: levar a carta de volta pra Cidade fecha a missão — dispara
   `factions.Event("mission", tag="trust")` (ou tag equivalente) via
   `missions.turn_in` (mesmo mecanismo que já existe).
6. **A 4ª deed dos Bankers**, ainda não escrita em `factions.py`:
   ```python
   Deed("bankers_trust", "bankers", "Earned Trust",
        "...", rep=1,
        check=lambda g, e: (
            e.kind == "mission" and e.tag == "trust"
            and {"bankers_good_for_business", "bankers_steady_customer",
                 "bankers_diverse_portfolio"} <= set(g.deeds_done))),
   ```
   (não usa `requires`, porque `requires` só encadeia 1 pré-requisito — aqui
   são 3 -- o `check` lê `guild.deeds_done` direto, mesmo truque discutido
   antes de escrever este documento.)
7. **Abrir o cofre no caminho** (Sistema 3): sucesso rende as gemas, mas
   `mission.state = "failed"` na hora e `+1` de `crime` pra quem abriu — nunca
   chega a virar a deed de confiança.

### Bloqueios reais (não é falta de decisão, é dependência externa)
- Precisa de um nó novo (fortaleza) além da Old Road no grafo do `world.py` —
  nome, posição, blurb, aresta a partir de `road`.
- Precisa de um nome próprio pra "The City" (hoje é só `"The City"` em
  `world.py`) — mencionado pelo usuário como parte da mesma leva de conteúdo,
  mas ele não escolheu o nome ainda.
- O mapa autoral da emboscada da fortaleza — o usuário disse que vai
  desenhá-lo depois (`map_editor_screen.py`/`map_lib`). Até lá, dá pra
  implementar e testar o resto da missão com um `Bout`/cenário provisório e
  trocar o `map_slug` depois sem mexer no resto.

## Ordem de implementação sugerida

1. ~~**Sistema 1** (Crime/jurisdição/guarda)~~ -- **feito**, ver a seção logo
   acima ("Sistema 1 — implementado").
2. **Sistema 2** (Old Road unsafe) — pequeno, reaproveita quase tudo de
   `encounters.py`, independente do Sistema 1. **Próximo a implementar.**
3. **Sistema 3** (Cofre genérico) — mecânica isolada, só teste de destreza +
   um item novo.
4. **Sistema 4** (a missão em si) — amarra os 3 anteriores; a parte da
   emboscada autoral fica com um placeholder até o mapa existir, mas o resto
   (aceitar / trocar / entregar / a deed `bankers_trust`) pode ser implementado
   e testado de ponta a ponta antes disso.

## Testes a cobrir quando for implementar

- Teste da guarda: `crime == 0` nunca dispara; a chance sobe linearmente com
  `crime` (`d20()+crime>=11`); roda em todo nó de jurisdição, não só na
  entrada.
- Prisão: dia de soltura correto, unidade some do grupo e reaparece depois,
  crime zera, resto do grupo intocado.
- Luta com a polícia: derrota é letal de verdade (permadeath); crime sobe por
  guarda morto + o +1 fixo da briga.
- Old Road: a emboscada dispara em viagens que passam por lá e não trava a
  viagem indefinidamente; não dispara em nós fora da tabela.
- Cofre: teste de destreza abre/não abre conforme o DC; abrir o cofre da
  missão falha a missão e soma crime.
- Missão de ponta a ponta: aceitar dá o cofre, emboscada da fortaleza dispara
  uma vez só, trocar por carta, entregar fecha `bankers_trust`, reputação chega
  a 4.

# Holy Symbol: a quest do Fazendeiro (a filha do Edric)

Escrito em portugues a pedido do autor. Status: **em construcao** na branch `quest-holy-symbol` (fases 1 a 6 feitas). A chave de lancamento
`missions.FARMER_QUEST_LIVE` (hoje `False`) mantem a quest inteira apagada: o job, a aba Jobs da Farm e a loja fechada.

## Por que existe

O rito da Fe (`gartok/rite.py`) consome um Holy Symbol, mas nenhuma loja vende o item e nenhum recrutado
comeca com ele. Duas fontes:

1. **Drop de bandido**, 1% por bando (`encounters.BANDIT_HOLY_SYMBOL_DROP_CHANCE`). Feito.
2. **Esta quest**, a fonte confiavel. Entregue **inteira**, construida por fases: o template so entra em
   `missions.TEMPLATES` na ultima fase, entao o jogador nao ve nada antes.

## O design

**Abertura.** Dia 50 ou depois **e** a Faith Cathedral ja achada (quem vier por ultimo abre a quest). O Edric
Ashvale a oferece numa aba Jobs nova na Farm: a filha foi a igreja e nao manda noticia. Prazo de 20 dias.
Recompensa: 300 copper e o Holy Symbol que a filha carrega.

**Farm fechada.** A loja da Farm nao vende nada enquanto a quest esta ativa (Edric de luto) e, depois de um
fracasso, enquanto o demonio estiver solto. Reabre quando ele morre.

**Perguntar por aí (Gather Information).** Botao **dentro do no, na aba Jobs**, em cada cartao de job ativo.
- Custa ~1 h, pelo mesmo caminho das horas de um hub (`HubSession._spent` -> `MapSession.spend`, a regra do
  relogio unico). Rolagem de CAR do melhor falante do grupo.
- Falhou: gasta a hora e da para tentar de novo. Passou: a guild marca o no como resolvido para aquele job
  (o botao vira "ja perguntado" e mostra a resposta de novo).
- **Todo job ativo tem o botao** e todos caem no fallback "ninguem sabe nada sobre isso por aqui", exceto este.
  Nos sem aba Jobs (Country Roads, Old Road) nao tem botao.
- Pistas: a **Catedral** (ela foi visitar os pais e nao voltou) e o **posto de comando do Ledger Hold** (ela nao
  passou por aqui). Cada pista conta como **uma pista**.

**Contador de pistas.** O job guarda so o numero de pistas. Cada consumidor tem o seu multiplicador, porque uma
coisa futura pode usar outro: a busca ganha `+2 x pistas`; o proprio Perguntar por aí `+1 x pistas` (a calibrar).

**Busca nas Country Roads.** Ordem de 2 h, SAB do melhor do grupo, **DC 22** (a do Aurochs, `ox.py`, e DC 10).
Repetivel. Revela o Cult Site. Com SAB +2: 0 pistas ~5% (so nat 20), 1 pista 15%, 2 pistas 25%.

**Cult Site.** No oculto com arestas para as Country Roads e para a Catedral, atalho Farm -> Igreja para sempre.

**O Demon Cult.** 6 NPCs autorais com builds diferentes e **niveis fixos**, em **nivel racial** (`racial_level`:
combate, magia e trabalho):
- 1 lider, conjurador, nivel 10, livre.
- 2 lutadores, nivel 7, livres.
- 3 canalizadores, conjuradores de escolas diferentes, nivel 7, **presos** nas 3 pontas de um **triangulo**.
- A filha (`farmers_daughter`) amarrada no centro.
- Para comparar: o necromante e racial 15 (5 de combate), Ogre e Biwolf 10, Aurochs 13, Dragon 20.

**Conversa antes da luta** (`dialogue.Encounter`):
- *Deixar o ritual seguir* e sempre valido: sem luta, o ritual completa e vale o fracasso, sem nocaute.
- *Persuadir* fechado. *Blefe* da surpresa. *Intimidar* por margem faz os cultistas comecarem desmoralizados
  (`Opening.demoralized`); so fogem os que a moral zerar (`Routed`). Falhar da vantagem na barra.

**Ritual (barra em passos).** Os cultistas nao gastam acoes para enche-la, senao a luta fica facil.
- **Passivo:** quem sabe o rito (canalizador ou o lider), numa ponta, no comeco da vez e **apto a agir**, soma 1,
  sem PA. Os canalizadores nao saem da ponta por vontade propria, mas **podem ser empurrados**: fora dela nao
  canalizam, e gastam movimento para voltar.
- **Barra em 3 passos de 6** (18): ~6 rodadas com 3 canalizadores e ninguem atrapalhado. Valores iniciais.
- **Ritual Final:** barra cheia, o lider vai ao **centro** e gasta **um turno inteiro**, com aviso. Interrompido
  (cai, dorme ou Routed), **a barra volta um passo**. Se os canalizadores ja cairam, o lider sai do centro, canaliza
  numa ponta vazia e volta para finalizar: ele e o alvo que vale perseguir.
- **Apto a agir** = vivo, de pe, nao Dormindo, nao Routed. Desmoralizado nao impede (so tira defesas e mobilidade);
  o que quebra a canalizacao e a moral zerada, que o Demoralize empurra (`morale.py`).

**Vitoria.** Os cultistas caem com a filha viva. Ela vai com o grupo a Farm (cativa especial, `ward`); o Edric paga
e ela entrega o Holy Symbol.

**Fracasso** (ritual completo, ritual deixado seguir, ou o prazo de 20 dias):
- A filha morre. O demonio aparece e **nocauteia** os jogadores e os cultistas restantes, todos estaveis, **ninguem
  morre**; a luta acaba como derrota nao letal.
- Quem morreu antes fica no chao: corpos e kit ficam no no. Voltando, o ritual esta abandonado e da para saquear o
  corpo da filha (Holy Symbol) e o kit dos mortos do grupo.
- **15 dias depois** o demonio volta e transforma o no em **covil do demonio**.
- Prazo estourado sem achar o Cult Site: o no se revela sozinho com um aviso, no mesmo estado.
- O demonio e o **mob mais forte do jogo**, acima do Dragon: nivel racial 22, 251 PV e criatura lendaria (age duas vezes por rodada); e um problemao de proposito, nao se calibra para a guilda vencer. Mata-lo solta o
  Holy Symbol e reabre a Farm.

**Luz.** O cenario e `outdoor`: a luz segue o relogio (`battle.daylight`). O triangulo tem braseiros fixos acesos.

## Fases

Cada fase e um commit no `main`.

1. **O documento** (este) e o ponteiro no backlog.
2. **Portao e quadro (feita).** `MissionTemplate` ganha `min_day` e `needs_revealed` (`offers_at`); template
   `FARMER_DAUGHTER` (giver `farmer`, no `farm`, 20 dias, `goal_captive`, 300 de reward, `reward_items` com o
   simbolo) em `TEMPLATES` mas **atras da chave `FARMER_QUEST_LIVE`**; a Farm ganha a funcao `farmer` (sem botao no mapa), `FarmerBoard` em
   `job_board.BOARDS` (+ `tests/test_desks.py`), aba Jobs em `hub_session._node_tabs`; loja fechada lendo
   `Guild.cult`; textos en e pt-br.
3. **Perguntar por aí (feita; o botao ficou numa secao "Perguntar por aí" da aba Jobs que lista TODO job ativo da guilda, de qualquer quadro, porque a pista da Catedral e do Ledger Hold e sobre um job que nao esta no quadro delas; DC 10 e +1 por pista, a calibrar).** `gartok/investigation.py` (`CLUES`, `ask`, `bonus`); ordem `ask_around` por `_spent` com
   o job perguntado num campo novo da `Order`; botao no cartao da aba Jobs; `Guild.investigation` em
   `PAYLOAD_DEFAULTS` (sem bump de `SAVE_VERSION`).
4. **Busca, Cult Site e arestas (feita; o no e efemero, como os do wildfire: so entra no mapa e nas rotas depois de achado, senao o atalho Farm-Igreja vazaria o no; o no ainda nao tem funcao nem tela: `cult_ritual` vem na fase 6).** No oculto `cult_site` (`world.free_spot`), arestas, funcao `cult_ritual`, glifo
   em `map_view.NODE_ICON`; `search_cult` em `campaign.SEARCHES` com botao nas Country Roads.
5. **Raca Demon e NPCs (feita; nomes dos NPCs e do demonio sao provisorios: Maren Voss, Brann, Kessa Thorn, Ilsa, Orrin, Tavish, Wynn Ashvale, "O Inquilino Palido"; o glifo do Demon e um emprestimo do Kobold ate o autor dar arte; Demon: racial 22 derivado (combate 16, trabalho 14, magia 14: o teste proibe pinar), PV derivados da Constituicao (251, sem pino), bonus FOR+4 DES0 CON+2 INT+4 SAB+2 CAR+4, Enorme, d10, darkvision + ferocity, lendario (2 turnos por rodada), luta desarmado com Garras, so conhece Hex e Dragonfire por ora (as outras escolas virao com magias novas), talentos raciais Garras Infernais, Garras Ceifadoras, Asas Infernais e Presenca Infernal (teste de SAB contra 10 + CAR dele, ou -1 de moral), build de Carisma e depois Forca; `python scripts/make_cult_npcs.py` regenera os 8 arquivos).** Raca `Demon` (`kind: demon`, posta a mao como o Skeleton) e glifo em `art_files.RACE_ICON`;
   os 8 NPCs em `npcs/*.json` por um script (modelo `necromancer.json`); drop do demonio em `loot.UNIQUE_DROPS`.
6. **O cenario (feito; mapa 36x24 aberto, `outdoor`; triangulo (18,5),(11,17),(25,17), centro (18,13), a filha amarrada ao lado do centro como prop `bound` desenhado, nao como unidade, entao a IA nunca a mira e nao conta para a vitoria; barra de 18 (3 passos de 6), +1 por turno de quem sabe o rito numa ponta, o lider comeca o Rito Final ao fim do turno no centro com a barra cheia e fecha no inicio do turno seguinte; interrompido (caiu, dormiu, Routed ou empurrado) a barra volta um passo; o demonio NAO e uma unidade na luta: o rito fechando deita todos (`stable`, `Scenario.spares_the_squad` pula o `_wipe_side`) e a filha morre; vitoria marca `guild.cult["state"]="won"`, fracasso `"failed"` com o Simbolo e o kit dos mortos em `guild.cult["remains"]`, que `cult_ritual` entrega uma vez ao voltar; ordem `cult_ritual` + `campaign_fight.cult_ritual`; o HUD da barra sai em `state["ritual"]` e vai na linha de dica; falta a entrega da filha viva como cativa: fase 8).** `gartok/cult_site.py`, `CultSiteScenario` (modelo `ox_fields.py` e `necromancer.py`): mapa
   aberto `outdoor`, triangulo, a filha como `ai_ally` dormente; barra e Ritual Final em `on_round`, no `CombatLog`;
   o fim nao letal (hoje `win_check` devolver `"enemy"` apaga o esquadrao, `battle.py:812`); os restos em
   `Guild.cult`.
7. **A IA (feito: `_channel` em `ai/scripted.py` ligado em `ai/turn.py` antes de `_necromancy`; `cult_site.ai_post`/`ai_must_stay` dizem a ponta de cada um e quem nao pode sair dela; canalizador fora da ponta anda de volta antes de agir, ja na ponta so ataca o que alcanca com o feitico; o lider assume a ponta vazia quando um canalizador cai.)** `_channel` em `ai/scripted.py` (modelo `_necromancy`); o lider faz o Ritual Final e canaliza numa
   ponta vazia; os lutadores protegem os canalizadores; a IA inimiga ignora a filha.
8. **Conversa, resgate e entrega (feito: `dialogue.CultTalk` kind `cult`, verbos persuadir (fechado), blefar (surpresa), intimidar (cultistas Demoralized), deixar seguir (sem luta, `cult_site.let_proceed`: estado `failed`, filha perdida, so o Simbolo nos restos) e atacar; blefe ou intimidacao falhos dao ao rito a vantagem de um passo na barra (`head_start`); `dialogue_session.cult_talk` abre antes de `campaign_fight.cult_fight`; vitoria cria a cativa `ward` `farmers_daughter` (`cult_site.free_daughter`, uma vez) e a linha da aba Bandos mostra "sob protecao"; falta so a entrega na Farm, que ja funciona pelo `goal_captive` e e testada na fase 9).** `CultTalk` (modelo `Challenge` e `WildfireTalk`); a filha como cativa `ward`
   (ignora os 7 dias de `captives.daily`) e entrega pelo `goal_captive` que ja existe.
9. **Fracasso e lancamento (feito, menos o lancamento: `cult_site.daily` em `guild_upkeep` apos `expire_overdue`: prazo estourado revela o sitio e abandona o rito como se tivesse fechado, "uma coluna de luz vermelha"; 15 dias apos a falha o estado vira `lair` e o no troca a funcao para `demon_lair`; `demon_lair.py` e a luta letal so contra o demonio (arena 28x18, `ERRAND_NATURE`); a morte dele marca `demon_dead`, solta o Simbolo (`UNIQUE_DROPS`) e reabre a Farm (`missions.shop_closed` fecha em `failed` e `lair`); teste ponta a ponta da oferta ao Simbolo na mochila em `tests/test_cult_scenario.py`; o switch `FARMER_QUEST_LIVE` segue `False`, o backlog nao foi tocado, o demonio segue sem emboscada, o no mantem o nome "Demon Cult Site" no covil).** `Guild.cult` e o `daily` do `cult_site` em `guild_upkeep` (15 dias, prazo estourado); o no
   mostra `cult_ritual` ou `demon_lair`; demonio autoral; registrar o template em `TEMPLATES`; `python -m
   gartok.reference`; wiki; tier `balance`; jogar de ponta a ponta; apagar a entrada do backlog.

## Decisoes do autor (2026-11-11, de manha)

- **O Simbolo e da filha, nao do demonio.** Sai da recompensa da entrega (`reward_items`) ou, no fracasso, do
  corpo dela em `guild.cult["remains"]`; o demonio nao dropa nada (`loot.UNIQUE_DROPS` sem `the-demon`). Os restos
  tambem podem ser revistados depois que o demonio morre (`demon_dead`).
- **Emboscada do demonio: 30% por chegada** nas Country Roads e na Farm, enquanto ele viver (estados `failed` e
  `lair`): `cult_site.ambush` + `forced.demon_ambush_catch`, a primeira do evento `ambush`. Matar o demonio ali o
  encerra como no covil (`cult_site.demon_slain`).
- **Faixa da guilda: nivel 6 a 8 com 6 a 8 membros.** A calibracao abaixo usa 7 membros.
- **A quest abre a partir do dia 50 (inclusive).**
- Sobrenome do Edric: Ashvale (a filha, Wynn Ashvale).

## Calibracao headless (so relato)

IA generica dos dois lados (a IA do jogador NAO conhece o rito: nao persegue o lider nem os canalizadores, entao
subestima um humano atento). `encounters.build_enemy` no nivel indicado.

- Esquadrao de 4, 20 lutas (primeira rodada de numeros): rito 0/20 vitorias em L3 a L6 (o rito fecha 16 a 20 de
  20); covil 1/20 em L3 a L5 e 0/20 em L6.
- **Esquadrao de 7, 12 lutas (a faixa decidida):**

  | nivel | rito: vitorias | rito fecha | covil: vitorias | mortos de 7 no covil |
  |---|---|---|---|---|
  | L6 | 0/12 | 12/12 | 7/12 | 4.2 |
  | L7 | 0/12 | 12/12 | 6/12 | 4.8 |
  | L8 | 1/12 | 11/12 | 8/12 | 2.8 |

- O covil fica perto de 50% a 65% na faixa (cada luta custa de 3 a 5 mortos de 7, so letal). O rito e o que
  esta duro: a barra enche em ~6 rodadas e a IA generica nao quebra o circulo. Alavancas se um humano tambem
  sofrer: barra maior, passos de 8, ou menos canalizadores no inicio.

## Em aberto

- Validar jogando o rito (a barra de 18, passos de 6): a simulacao nao tem um jogador que leia a barra, entao o numero real e do autor. O combate bruto dos cultistas ja esta nivelado para uma guilda de nivel 6 a 8 (5/12, 6/12, 8/12).
- Nomes do lider e do covil. Todos os numeros (barra, DCs, niveis, `+1` do Perguntar por aí) sao iniciais.
- Arte pedida ao autor: portrait do demonio e dos cultistas, chao do Cult Site.

# Backlog — everything still open

The one place for open work. It folds the playtest review (2026-10-05), the wagon and
camp to-do list and the later playtest notes. What is already built is in the code, its
tests and the git log; the long-range AI plan is
[campaign_ai_roadmap.md](campaign_ai_roadmap.md).

Ease and impact are estimates, not checked against the code. When an item is done, delete
it here and, if it changed a design premise, record it in `AGENTS.md` or the doc that owns it.

## Medium

- **Medic, quick treatment (B1).** A tab in the Apothecary hub: the answer to rest healing
  being slow (1 HP per 8 h at CON mod 0). A hospital that treats with healing potions and
  antidotes at a discount, priced as the *expected* potions and antidotes needed to leave
  cured, at catalogue price x 0.7 (a constant in `economy.py`). It is a transaction: pick
  the patients from the party present, pay, and the clock advances for the whole group.
  - HP: always up to max, 1 h. Cost = `ceil((hp_max - hp) / 3.5)` Minor Healing Potions.
  - Sickness: 8 h, cost = one First Aid Kit charge (price / charges).
  - Poison: assume every Antidote save passes; stacks fall about 2 a day (natural + dose),
    so N stacks take 24 h x `ceil((N - 1) / 2)` (at least 1 h) and `ceil(N / 2)` doses.
    Only treatments up to 24 h belong here; longer ones are B2.
- **Medic, hospital stay (B2).** After B1. A treatment of 24 h or more admits the patient:
  they split off into a new Group on a new order kind (saved with the groups), locked like
  any group with an order. With no free group slot the whole group waits with them instead.
  On discharge the patient is a loose group and the player merges by hand.
- **Economy sim catch-up.** `scripts/economy_sim.py` models a trader against its own
  `Vendor` class, so it never sees what changed the economy in the game: the market's
  finite cash (`Guild.market_cash`: $100 to start, +$25/day up to $500), coins as items
  (`$`, gold, the bank exchange), the Medic and upkeep that now drain money (house tax,
  garrison, wagon wear, animal feed, group rest), and a squad pooling one market instead
  of a lone trader. First decide what question it answers (can one character earn a
  living? can a guild?), then have it drive the real `Guild`, market and daily upkeep
  instead of a parallel model. Until then a change to wages, purses or loot is checked by
  hand.
- **Combat info modal.** Hide part of it by default and rework it: it carries information
  that should not be there and lacks some that would help. Define what goes in and out first.

## Larger

- **Specialised shops.** Split the single general market into shops, each its own node
  with a walking distance between them, so the player has to go around. The market's
  finite cash is built (`Guild.market_cash`, keyed by node id), so each shop gets its own.
  The production chain (lumberjack -> carpenter, smith) and restocking tied to the world
  are a later arc; this task is the structure with a fixed restock.
  - **Shops:** Smith, Apothecary and Tanner are new nodes outside the city (today `forge`,
    `apothecary` and `tanner` are flags on `city`). The Smith and the Apothecary take their
    crafting with them, as tabs. Farm (today only the stables), Tavern, Lumber Yard (a shop
    *and* a work node) and Market already exist. Rough split: Smith = weapons, shields,
    metal armour, Iron Bar, Coal; Tanner = leather armour, Cloak, Hide, Quiver; Apothecary =
    potions, Vial, First Aid Kit; Farm = raw food and Salt; Tavern = Beer and Jerky (the only
    ready-made food today); Lumber Yard = Lumber; Market = the rest (Torch, Lantern, traps).
  - **Prices and stock:** one base price everywhere. Every item is finite in every shop. A
    shop buys any item at 50% and puts it on its shelf to resell at 100%. Each item has a
    target count per shop and the shop walks back to it a little each day.
  - **To do first:** define the stock target per item and per shop (and the daily refill
    rate). Since every shop resells everything, the targets are what makes each one
    specialised.
  - The Library joins the same rule (stock target, finite cash, buys anything at 50%) and
    keeps its other tabs.
  - Every shop may end up holding anything the player sells; the stock targets are what
    keeps each one specialised.
  - Open: AI and tests.
- **Adjust the map node distances.** The new shop nodes (Smith, Apothecary, Tanner) need
  a walking distance from Ankareth, and the existing ones (Market and Library 1 h, Farm
  2 h) should be reviewed together with them, since the distance is the cost of going
  around between shops.
- **Found-the-guild screen** (`draft_screen.py`). Founding the guild should be the
  heaviest choice of the run: squad members die, the guild does not, and the player *is*
  the guild. Today it is a colour, an icon and a leader pick, and the screen looks
  off-pattern. Redesign in two phases around a founding charter:
  - **Before the picks:** pick a *vocation* from a curated list of 5-8. It biases the
    candidates' race, age, occupation and tendency; it never locks the pool. Pick the
    *oath* (separate from the vocation): a short list, each with a mechanical effect,
    built on `cohesion.py` and `factions.py`. An oath cannot be broken, but it can be
    changed. Name and banner may also go here.
  - **Draft:** a pool of 9 candidates, pick 3 (replaces 3 rounds of 1 of 3). The 3
    Commission Tokens stay, now spent to reroll one of the 9 before choosing.
  - **After the picks:** choose the guild leader.
  - **Presentation:** a richer composed banner (more shapes, colours and patterns), a
    live preview of the guild as choices are made, and an opening scene: a founding
    charter that writes itself line by line as the player decides, signed at the end
    with the banner and the oath, and kept as the first entry of the guild's chronicle.
  - Open: the vocation list and each one's bias; the oath list, effects and the cost of
    changing one; whether Commission Tokens still shape archetypes or only reroll; AI
    and tests for the new generation bias.

## Starting items

Each occupation starts with one item (`data.OCCUPATIONS`) and about half the recruits got
one with no use at all. Rule: every occupation's item is useful and **unique to it**, as
an occupation is only a weapon and an item. Items that already work: Meat, Potato, Quiver,
1L Beer, 1sqm Hide, Iron Bar, Lumber, 1kg Coal, First Aid Kit, Lantern, Scroll, Dictionary,
Salt, Ink, Rope, Bear Trap. Amethyst is only a store of value, and Rotten Food is the
Slave's on purpose (eating it makes you sick).
The rest each need a mechanic, or a swap to an item that has one:

- **Crafting tools.** Crafting consumes everything today. Let a recipe also require a tool
  that is not consumed (a cart needs wood, nails and a saw). Gives Chisel, Scissors, Shovel,
  and the Goldsmith's Pliers a job (and jewellery crafting, when it exists). Shapes the
  future wagon recipe.
- **Prisoners.** Non-lethal attacks that knock a unit out even in lethal zones, then
  capture it. Chains are what holds the captive. Needs the AI to know it too.
- **Claim construction: oven.** Built at the Claim with time and Stone Brick; like the
  campfire but always lit. First thing to build there, and the start of a general
  build-at-the-Claim system.
- **Animals in combat.** The Shepherd's Sheep only stands still on the board today.
  Controllable and AI-driven animals share the *Riding and mounts* arc below.
- **Inventory containers.** Decide whether the inventory should be split into containers
  at all. Sack and Iron Shackles were removed from the catalogue; bring a container back
  when this is decided.
- **Signal Horn** (new item, not a starting item: too strong). A combat action that warns
  allies, for example extra movement or drawing attention. Talks to the Alarm Trap and the
  Alert talent. Needs the action, AI support and tests.
- **Map.** Finds treasures and secret zones. Waits for those systems.
- **Compass.** Avoids getting lost on very long trips through unknown paths. Waits for a
  getting-lost system.
- **Deck of Cards.** A card minigame at the tavern, among others. Its own arc.
- **Holy Symbol.** Required, together with everything else, to start in faith magic.

## Big / structural

- **Auto battler with priority programming** (Siralim Ultimate style). Its own arc and
  branch: UI, AI and tests.

## Wagons, animals and camp

Nothing here blocks anything; each item waits for a reason to build it. Constraints to keep
while building them:

- The game is meant to get big (many groups, animals and wagons): shape these systems for
  that now and prefer the general model over a patch for the small case.
- Storage trades capacity for something: pack is free and goes to combat; chest and house
  are static and safe; a wagon is mobile, lost with the group, needs animals that eat and
  sets the trip's pace; pack animals sit between pack and wagon.
- Tack decides an animal's role (Pack Saddle carries, Harness pulls, a riding saddle later);
  the wagon is a box and transport is derived.
- Wagons never enter a battle map: when combat starts, passengers get off and fight.

- **Riding and mounts** (separate arc). A riding saddle enters `animals.TACK`; the rider and
  animal pair goes into combat. The creature abstraction should not make it harder.


-------------

Anotações manuais pra serem colocadas na estrutura do resto do backlog depois

Na tela de gerenciar grupo, aparece na carroça quantos estão "riding" nela, mas n da pra ver quem.

Se eu tiro tudo de dentro do carrinho ele ta aparecendo na marcação de peso dele 0/3kg, ta beeem confusa essa visualização.

O "until full" nao deveria mostrar "3 comidas cada" deveria mostrar o custo total de comida

Quando um grupo entra numa tela de craft, o inventario pode ser visto como compartilhado no requisito dos ingredientes pra evitar eu ter q colocar os itens no inventario do mesmo cara. Dito isos, se o item tiver com o cadeadinho, ele nao pode ser usado em craft algum.

Em um sustaining da "The claim" se eu iniciar a guarnição, depois tirar o pessoal, o menu fica travado sem eu poder fazer nada. Da um check ate no save que eu to usando agora que ele ta nesse estado de travado. Nomeei ele como "The Claim Travada"

Carroça nao aparece como inventario no market e deveria.

Na prioridade de mostrar o por que o cara não pode recrutar alguem, a informação mais importante é que ele tem 0 slots de recrutamento disponíveis.

tem que colocar musical instrument pra vender no mercado.

na fazenda, se eu abrir o menu do the stables, no meu save "The Claim Travada" a carga ta exibindo um ponto flutuante de 32.199999...

na guild, seria bom eu ver o ox com o card de ficha dele la, igual um player

pra apostar na arena, vale combinar a bolsa do grupo, nao so de quem ta indo lutar. 

performar na taverna parece nao dar xp de work corretamente.

eu posso ficar dando delay indefinidamente. o certo seria somente 1 elay por rodada.

Reestruturar o backlog pra deixar mais organizado. "pronto pra fazer" que seriam as tarefas já bem estruturadas e ai categorizar elas por tamanho: pequena, média, grande, épico. E "precisa de mais informação pra catalogar"
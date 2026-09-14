# Planejamento de Melhorias - Playtest 1

Este documento agrupa e analisa os problemas encontrados durante o playtest de ~1h, dividindo-os por domínio e arquivos, além de categorizar o esforço e definir estratégias de prevenção de erros futuros.

## 1. Correções Instantâneas (Sem necessidade de design/decisões complexas)
Estas tarefas são de implementação direta, não exigindo debates, apenas correções no código existente.

### UI & Layout (Fixes Rápidos)
- **[1] Ícone de Tutorial (?)**: Mover para o canto superior direito (padrão de header) para evitar sobreposição de textos.
- **[7, 8] Overflow de texto em Quests (Banqueiro e Tanner)**: Aplicar quebra de linha (text wrap) na descrição dos cards.
- **[9] Tela de Guild/Gear**: Remover botão inútil de "sheet". As informações devem estar sempre visíveis na esquerda.
- **[13] Mercado - Clareza de Preço**: Mostrar "Preço Original" rasurado ao lado do preço com modificador.
- **[30] Texto no Banco**: Ajustar o componente de item no banco para não mostrar "+6 in the pack". (No mercado o comportamento está certo, mas no banco está errado/não faz sentido).
- **[Novo] Banco (Capacidade/Preço)**: 10kg é muito pouco. Aumentar o preço do armazenamento no banco para 100 moedas e aumentar o limite para guardar 30kg.

### Dados & Itens
- **[12] Beer**: Mudar para categoria Comida, adicionar expiração (30 dias) e ajustar o preço de acordo.
- **[15] Nova Arma - Rapieira**: 1d6 dano, finesse, custo de 65 cp (progressão para melees de Destreza).
- **[10, 26] Ícones Faltantes**: Atribuir ícones (se existirem nos assets) para habilidades raciais e lobos.

### Lógica & Bugs Críticos
- **[6] "Visit the property"**: Travar atrás de reputação mínima com banqueiros e aumentar o custo para 1.000 copper.
- **[18] Bug de Visão e Ataque**: O jogo permite atacar inimigos invisíveis para o personagem caso a "Visão de Grupo (L)" esteja ativada. A validação de ataque deve sempre checar a visão do *personagem atacante*, não a da câmera atual do jogador.
- **[22] HP e Constituição**: O HP atual e máximo não estão sendo recalculados quando o Modificador de CON é alterado. É necessário chamar um `recalculate_hp()` no momento em que a CON sofrer alteração (ou fazer o HP ser uma propriedade dinâmica).
- **[23] Arena (Lone Wolf block)**: Derrotar o Champion of the Pit impede lutar na arena fácil e bloqueia a deed "lone wolf". A correção é simples: apenas remover o desafio ao campeão da lista, mantendo as lutas normais.

---

## 2. Decisões e Desenvolvimentos Maiores (Necessitam de Escolhas de Design)
Estas tarefas exigem aprofundamento, criação de novas lógicas ou definição de como a UI deve se comportar.

### Combat UI & Action Bar
- **[17] Action Bar Inchada**: Condicionar ações específicas (Mount/Dismount, Reload, Wake Up, Share Magic).
  - *Decisão*: Adicionar método `is_applicable(combatant, battle)` na classe base de `Action`. A interface filtra usando esse método, e haverá um botão toggle "show non applicable actions" para que o jogador veja o que está bloqueado e por quê.
- **[19] Botão de "Atacar" (UI)**: Adicionar um botão físico além do double-click para facilitar visualizar alvos atacáveis (similar a demoralize/stabilize).

### Tooltips & UX Educacional
- **[2] Hover para Tags**: Explicar termos como "Tough", "Brute".
- **[3] Hover de Idiomas**: Mover o aviso "demoralize needs a shared language" para um hover explicativo na aba "Languages".
- **[11] Tela de Nível**: Hover ou pop-up explicando ganho de XP e leveling.
- **[16] Recompensas de Reputação**: Mostrar preview do que será liberado nos próximos tiers das facções.
- **[24] Preview da Arena**: Mostrar *Level Range* dos inimigos na UI de entrada da arena.

### Draft & UI de Recrutamento
- **[4, 5] Melhorias na Tela de Draft**:
  - *Decisão*: Aumentar o tamanho dos textos e apresentar as informações com mais qualidade visual, aproveitando melhor o espaço do card (inserindo mais informações nele em vez de depender de uma tela separada para a ficha).

### Gerenciamento de Inventário e Mercado
- **[14] "Distribute Load"**: 
  - *Decisão*: Adicionar o botão no cabeçalho do inventário do Grupo na tela de *Guild/Gear* e também na tela do *Mercado*.
- **[28] Inventário Cheio no Loot**: 
  - *Decisão*: Permitir arrastar um item do inventário do jogador de volta para o inventário da cena (loot/chão) para ganhar flexibilidade e liberar espaço.
- **[29] Mercado - Bulk Sell**: Implementar venda em massa (atualmente só há bulk buy).
- **[25] Revisão de Itens Inúteis**: Fazer uma varredura para identificar e retrabalhar itens que não têm uso.

### Missões e NPCs
- **[20] Recrutar Adelio Facadinha**: 
  - *Decisão*: Mostrar um popup logo após fechar a tela de vitória perguntando se o jogador deseja recrutar o NPC. Se sim, abre a tela de recrutamento (Cha vs Cha). Se não, volta pro hub.
- **[27] Tela de Missões Ativas**: Criar um *Quest Log*.
  - *Decisão*: A tela será acessada a partir da tela de gerenciamento de Grupo (Guild/Gear), visto que as missões pertencem aos grupos em campo, e não à guilda de forma global.

### Personagem (Títulos)
- **[21] Títulos de Personagens**: Mostrar na tela de Guild/Gear e formatar o nome na engine como `[NOME], [TÍTULO]`.

---

## 3. Prevenção e Origem dos Erros (Lições Aprendidas)

- **Overflows de Texto (7, 8)**: Textos em PyGame não quebram linha automaticamente. Foram introduzidos novos blocos de texto sem um componente que lide com formatação (wrap). *Solução futura*: Padronizar o uso de um componente `UITextBox` ou função de `word_wrap` em vez de renderizar fontes diretamente em todos os cards que usarem dados variáveis.
- **Reuso Indevido de Componentes (30)**: O inventário do Banco reutilizou o componente de slot de loja sem sobrescrever os textos estáticos (o "+6 in the pack"). *Solução futura*: Parametrizar a exibição de avisos extras nos componentes de slot, permitindo desligá-los fora do contexto do mercado.
- **Separação UI vs Core no Combate (18)**: O atalho `L` apenas mudava o que a câmera e o mouse percebiam, mas a engine confiou nessa percepção para validar o ataque. *Solução futura*: `action.is_valid()` NUNCA deve depender de estados da UI (como "visão atual do jogador"). Ela deve rodar as contas matemáticas da visão usando a posição e a visibilidade no mapa puramente do ponto de vista da Entidade.
- **Dependência de Dados Não Reativa (22)**: Atributos derivados (Max HP) não reagem quando os primitivos (CON) são atualizados (ex. debuffs, itens ou level up). *Solução futura*: Padronizar `properties` do Python ou um método `update_stats()` chamado sempre que um atributo primário mudar no `unit.py` ou `combatant.py`.

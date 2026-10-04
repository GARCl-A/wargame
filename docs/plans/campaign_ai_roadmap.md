# GARTOK — Campaign AI & Genetic Algorithm (GA) Roadmap

## 1. Executive Summary

This document outlines the design, feasibility, and step-by-step roadmap for developing an AI capable of playing the **Campaign / Macro layer** of GARTOK. 

The goal of this AI is not just to play, but to:
1. Optimize character builds, talent trees, and equipment loadouts.
2. Maximize roster XP, survivability, and faction reputation.
3. Stress-test the game rules and automatically discover unintended mathematical exploits or broken metas.

---

## 2. Technical Feasibility & Engine Advantages

GARTOK is uniquely suited for AI training and fast simulation due to key architectural decisions:
- **Headless Core by Design:** The core game logic ([battle.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/battle.py), [campaign.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/campaign.py), [guild.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/guild.py), [orders.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/orders.py), [progression.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/progression.py)) is pure Python with **zero** `pygame` dependencies.
- **Blazing Fast Simulation:** While a human playthrough takes hours, a headless simulation of an entire 30-day campaign (with combat auto-resolved by [ai.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/ai.py)) executes in **~1 to 3 seconds** on CPU.
- **Deterministic & Seedable:** Simulations can be seeded (`random.seed`) for exact reproducibility.

---

## 3. Technology Comparison: Why Genetic Algorithms (GA)?

| Approach | Learns on its own? | Setup Complexity | Best For |
|---|:---:|:---:|---|
| **Scripted Bot (Heuristics)** | No | Low | Simple automated sanity checks. Only does what you hardcode. |
| **Pure RL (PPO / DQN)** | Yes | Very High | Micro/Tactical combat. Suffers from sparse rewards and combinatorial action spaces on the macro map. |
| **LLM Agent (Tool Calling)** | Yes (In-Context) | Medium | Roleplay, narrative explanations, and human-like strategic reasoning. Slower execution. |
| **Genetic Algorithm + Utility AI** | **Yes (Evolutionary)** | **Moderate (1-2 days)** | **The sweet spot for finding exploits, broken builds, and optimal campaign paths.** |

---

## 4. Known Mathematical Exploits for the AI to Test

When evaluating fitness and observing agent behaviors, the following rule interactions are expected to emerge:

1. **The "Last-Hit Funnel" (Combat XP Exploit):**
   - *Rule:* `xp_award(attacker, victim) = (victim - attacker) + 1` if `victim >= attacker` else `0`. Only the unit delivering the lethal blow receives XP.
   - *Exploit:* Strong veterans soften tough enemies down to 1-2 HP, and Level 0 recruits deliver the final blow to gain massive XP leaps (e.g., Level 0 killing a Level 3 boss earns 4 XP instantly).
2. **"Mean-Level Twinking" (Encounter Difficulty Scaling):**
   - *Rule:* Encounter scaling relies on `mean_level = sum(track_levels) // len(track_levels)`.
   - *Exploit:* Bringing 1 high-level veteran (Level 3) + 3 sacrificial Level 0 recruits results in `(3 + 0 + 0 + 0) // 4 = 0`. The game generates Level 0 enemies while the squad has a Level 3 juggernaut.
3. **"Cross-Training" Safe HP Farming (Racial Track):**
   - *Rule:* Hit Dice and base HP scale with Racial Level, which is `combat_level + work_level`.
   - *Exploit:* Gaining Work XP via safe day-labour (Lumber Yard with an Axe to hit Lv 1, then Hunting) allows units to accumulate high HP before risking permadeath in combat.
4. **Market Churning & Untouchable CTF (Reputation Deeds):**
   - *Rule:* Reputation is earned through one-shot deeds ([factions.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/factions.py)).
   - *Exploit:* Buying and immediately reselling 5 cheap items fulfills "Diverse Portfolio"; deploying an unarmored, high-movement runner in CTF achieves the "Untouchable" deed (+1 rep with no kills).

---

## 5. Proposed Architecture: Utility AI Parametrized by Genome

The AI does not write code from scratch; rather, the **Genotype** controls the weights and decision thresholds of a **Utility Engine**.

### A. The Genotype (DNA)
```python
genome = {
    # Economic / Risk weights
    "work_preference": 0.75,         # Likelihood of working vs adventuring
    "risk_tolerance": 0.25,          # Min squad HP % before attempting arena/hard battles
    "reserve_copper_target": 60,     # Gold buffer kept before buying gear
    "tool_buying_priority": 0.85,    # Willingness to buy axes/shovels for work efficiency
    
    # Gear & Progression preferences
    "weapon_type_bias": 0.10,        # 0.0 = Range/Reach (Spear), 1.0 = Pure Damage (Axe)
    "armor_investment_bias": 0.70,   # Prioritize defensive armor over offensive weapons
    "talent_tree_focus": "defense",  # Bias towards survivability vs burst damage
}
```

### B. The Decision Loop
At each map node or day transition:
1. Evaluate potential orders (`Order.march`, `Order.work`, `Order.arena`, `Order.rest`).
2. Score each option:
   $$\text{Utility}(\text{Option}) = f(\text{Game State}, \text{Genome})$$
3. Pick the highest utility action and dispatch it via [orders.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/orders.py).
4. Run combat automatically with [ai.py](file:///c:/Users/lucas/Documents/Projects/wargame/gartok/ai.py).

### C. The Fitness Function
```python
fitness = (
    (guild.total_reputation * 100)
    + (total_roster_combat_xp * 10)
    + (total_roster_work_xp * 5)
    + (guild.total_copper * 0.1)
    - (fallen_members_count * 50)
)
```

---

## 6. Implementation Roadmap

### Phase 1: Headless Campaign Runner (~1 - 2 hours)
- Create `sim_campaign.py` (analogous to [sim_test.py](file:///c:/Users/lucas/Documents/Projects/wargame/sim_test.py)).
- Initialize a `Guild`, assign basic orders, call `campaign.advance()`, and simulate 30 campaign days in a simple loop without GUI.

### Phase 2: Campaign Agent & Genotype Evaluator (~2 - 3 hours)
- Implement `CampaignAgent(genome)` with utility scoring for:
  - Traveling to nodes (using `world.route`).
  - Purchasing tools and optimal weapons.
  - Choosing when to enter the Arena or accept missions.
- Implement auto-equip and talent selection based on genome biases.

### Phase 3: Evolutionary Loop (GA) (~1 - 2 hours)
- Population size: 30 to 50 guilds.
- Generations: 20 to 30.
- Selection: Top 20% elite survivor retention.
- Crossover: Blend of parent weights.
- Mutation: Small Gaussian perturbation ($\pm 5\%$).

### Phase 4: Telemetry & Reporting (~1 hour)
- Output convergence logs:
  - Best score per generation.
  - Dominant builds (e.g., spear vs sword, lumber vs rush).
  - Unlocked deeds and average roster survival rate.

---

## 7. Estimated Development Time

- **Functional Prototype (MVP):** 3 to 5 hours.
- **Polished System with reporting & balance stats:** 1 to 2 days.

---

## 8. When You Are Ready to Resume

To start development when the time is right:
1. Review this document.
2. Begin with **Phase 1** by creating a minimal headless campaign runner script.
3. Validate that 30 campaign ticks complete cleanly without UI dependencies.

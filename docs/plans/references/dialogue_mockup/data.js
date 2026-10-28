window.DATA={
 "guild": "RecebiHerança",
 "day": 70,
 "time": "13:58",
 "ambush": {
  "leader": {
   "name": "Bexgrok",
   "caption": "Goblin Mercenary",
   "race": "Goblin",
   "portrait": 3512586408
  },
  "line": "\"Your purse or your blood.\" 4 of them block the way.",
  "foes": [
   "Bexgrok · Goblin",
   "Garulnmunek · Human",
   "Senkorruther · Goblin",
   "Rigthal · Automaton"
  ],
  "speakers": [
   {
    "id": "d9e926b5d8404e7196b643ed19dd8932",
    "name": "Tikrom",
    "selected": false,
    "caption": "CHA -1 · INT +1 · Dwarvish"
   },
   {
    "id": "e97654247b2e450dbc6e3f1a7187929a",
    "name": "Vokoranyr",
    "selected": true,
    "caption": "CHA +2 · INT -1 · Ankarin, Goblin"
   },
   {
    "id": "5c5cc4450f2a48eaad52d8e1742889c2",
    "name": "Ylhel",
    "selected": false,
    "caption": "CHA -1 · INT +2 · Ankarin, Dwarvish"
   },
   {
    "id": "a191e540a1284ae1a89525317ae859d1",
    "name": "Adelio Small-Knife",
    "selected": false,
    "caption": "CHA +0 · INT -2 · Halfling, Ankarin"
   },
   {
    "id": "751ba69fbef34b3295abe6a055f8f29a",
    "name": "Irduntikorn",
    "selected": false,
    "caption": "CHA +0 · INT -3 · Dwarvish"
   },
   {
    "id": "db2a997815834e1db2e0d765aa787d1f",
    "name": "Vashmorza",
    "selected": false,
    "caption": "CHA +0 · INT -1 · Draconic"
   }
  ],
  "options": [
   {
    "id": "persuade",
    "label": "Persuade",
    "note": "talk them out of it: no fight · a miss and it is a fight",
    "check": "CHA +2 vs DC 13",
    "odds": 0.5,
    "block": ""
   },
   {
    "id": "bluff",
    "label": "Bluff",
    "note": "send them off on a lie · a miss and they strike first",
    "check": "CHA +2 vs DC 10",
    "odds": 0.65,
    "block": ""
   },
   {
    "id": "intimidate",
    "label": "Intimidate",
    "note": "shake them: they start demoralized, or run · a miss gives them the jump",
    "check": "CHA +2 vs DC 10",
    "odds": 0.65,
    "block": ""
   },
   {
    "id": "bribe",
    "label": "Bribe",
    "note": "pay them off: no fight",
    "check": "$24",
    "odds": null,
    "block": ""
   },
   {
    "id": "attack",
    "label": "Attack",
    "note": "roll initiative",
    "check": "",
    "odds": null,
    "block": ""
   }
  ],
  "result": null,
  "title": "AMBUSHED ON THE ROAD",
  "kind": "ambush",
  "leader_unit": {
   "id": "d15dd0a8d76644a3ba2a643a0defc87c",
   "name": "Bexgrok",
   "race": "Goblin",
   "occ": "Mercenary",
   "lvl": 1,
   "hp": [
    5,
    5
   ],
   "face": "img/goblin_0.png",
   "cha": 1,
   "int": 2,
   "langs": [
    "Goblin"
   ],
   "align": "Neutral and Evil",
   "money": 30,
   "crime": 0
  },
  "foe_units": [
   {
    "id": "d15dd0a8d76644a3ba2a643a0defc87c",
    "name": "Bexgrok",
    "race": "Goblin",
    "occ": "Mercenary",
    "lvl": 1,
    "hp": [
     5,
     5
    ],
    "face": "img/goblin_0.png",
    "cha": 1,
    "int": 2,
    "langs": [
     "Goblin"
    ],
    "align": "Neutral and Evil",
    "money": 30,
    "crime": 0
   },
   {
    "id": "f83949cdd8e2420bb73e957c623f0ed7",
    "name": "Garulnmunek",
    "race": "Human",
    "occ": "Jailer",
    "lvl": 1,
    "hp": [
     13,
     13
    ],
    "face": "img/human_13.png",
    "cha": 1,
    "int": 1,
    "langs": [
     "Ankarin",
     "Sylvan"
    ],
    "align": "Neutral and Evil",
    "money": 28,
    "crime": 0
   },
   {
    "id": "0dab2e72dfab4b839f3b3043ce871d52",
    "name": "Senkorruther",
    "race": "Goblin",
    "occ": "Thief",
    "lvl": 1,
    "hp": [
     6,
     6
    ],
    "face": "img/goblin_2.png",
    "cha": 0,
    "int": -4,
    "langs": [
     "Goblin"
    ],
    "align": "Lawful and Neutral",
    "money": 20,
    "crime": 0
   },
   {
    "id": "f3a78b0e9f554d8db5c57518f1ace07d",
    "name": "Rigthal",
    "race": "Automaton",
    "occ": "Cartographer",
    "lvl": 1,
    "hp": [
     10,
     10
    ],
    "face": "img/automaton_7.png",
    "cha": -1,
    "int": 2,
    "langs": [
     "Ankarin"
    ],
    "align": "Chaotic and Neutral",
    "money": 23,
    "crime": 0
   }
  ],
  "band": [
   {
    "id": "d9e926b5d8404e7196b643ed19dd8932",
    "name": "Tikrom",
    "race": "Dwarf",
    "occ": "Woodcutter",
    "lvl": 4,
    "hp": [
     19,
     47
    ],
    "face": "img/dwarf_1.png",
    "cha": -1,
    "int": 1,
    "langs": [
     "Dwarvish"
    ],
    "align": "Chaotic and Evil",
    "money": 184,
    "crime": 0
   },
   {
    "id": "e97654247b2e450dbc6e3f1a7187929a",
    "name": "Vokoranyr",
    "race": "Human",
    "occ": "Hunter",
    "lvl": 3,
    "hp": [
     10,
     25
    ],
    "face": "img/human_4.png",
    "cha": 2,
    "int": -1,
    "langs": [
     "Ankarin",
     "Goblin"
    ],
    "align": "Chaotic and Good",
    "money": 84,
    "crime": 0
   },
   {
    "id": "5c5cc4450f2a48eaad52d8e1742889c2",
    "name": "Ylhel",
    "race": "Human",
    "occ": "Merchant",
    "lvl": 2,
    "hp": [
     1,
     20
    ],
    "face": "img/human_5.png",
    "cha": -1,
    "int": 2,
    "langs": [
     "Ankarin",
     "Dwarvish"
    ],
    "align": "Neutral and Neutral",
    "money": 83,
    "crime": 0
   },
   {
    "id": "a191e540a1284ae1a89525317ae859d1",
    "name": "Adelio Small-Knife",
    "race": "Halfling",
    "occ": "Thief",
    "lvl": 3,
    "hp": [
     9,
     9
    ],
    "face": "img/halfling_adelio.png",
    "cha": 0,
    "int": -2,
    "langs": [
     "Halfling",
     "Ankarin"
    ],
    "align": "Neutral and Evil",
    "money": 283,
    "crime": 0
   },
   {
    "id": "751ba69fbef34b3295abe6a055f8f29a",
    "name": "Irduntikorn",
    "race": "Dwarf",
    "occ": "Innkeeper",
    "lvl": 2,
    "hp": [
     5,
     5
    ],
    "face": "img/dwarf_0.png",
    "cha": 0,
    "int": -3,
    "langs": [
     "Dwarvish"
    ],
    "align": "Neutral and Neutral",
    "money": 223,
    "crime": 0
   },
   {
    "id": "db2a997815834e1db2e0d765aa787d1f",
    "name": "Vashmorza",
    "race": "Lizardfolk",
    "occ": "Goldsmith",
    "lvl": 4,
    "hp": [
     34,
     34
    ],
    "face": "img/lizardfolk_6.png",
    "cha": 0,
    "int": -1,
    "langs": [
     "Draconic"
    ],
    "align": "Lawful and Good",
    "money": 171,
    "crime": 0
   }
  ],
  "band_name": "Vokoranyr's Band",
  "place": "Old Road",
  "edge": 4,
  "dc_base": 15,
  "leader_wis": -1,
  "speaker": "e97654247b2e450dbc6e3f1a7187929a",
  "options_by": {
   "d9e926b5d8404e7196b643ed19dd8932": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA -1 vs DC 13",
     "odds": 0.35,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "e97654247b2e450dbc6e3f1a7187929a": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +2 vs DC 13",
     "odds": 0.5,
     "block": "",
     "open": true
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +2 vs DC 10",
     "odds": 0.65,
     "block": "",
     "open": true
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +2 vs DC 10",
     "odds": 0.65,
     "block": "",
     "open": true
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "5c5cc4450f2a48eaad52d8e1742889c2": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA -1 vs DC 13",
     "odds": 0.35,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "a191e540a1284ae1a89525317ae859d1": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +0 vs DC 13",
     "odds": 0.4,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "751ba69fbef34b3295abe6a055f8f29a": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +0 vs DC 13",
     "odds": 0.4,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "db2a997815834e1db2e0d765aa787d1f": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +0 vs DC 13",
     "odds": 0.4,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ]
  }
 },
 "result": {
  "leader": {
   "name": "Bexgrok",
   "caption": "Goblin Mercenary",
   "race": "Goblin",
   "portrait": 3512586408
  },
  "line": "\"Your purse or your blood.\" 4 of them block the way.",
  "foes": [
   "Bexgrok · Goblin",
   "Garulnmunek · Human",
   "Senkorruther · Goblin",
   "Rigthal · Automaton"
  ],
  "speakers": [
   {
    "id": "d9e926b5d8404e7196b643ed19dd8932",
    "name": "Tikrom",
    "selected": false,
    "caption": "CHA -1 · INT +1 · Dwarvish"
   },
   {
    "id": "e97654247b2e450dbc6e3f1a7187929a",
    "name": "Vokoranyr",
    "selected": true,
    "caption": "CHA +2 · INT -1 · Ankarin, Goblin"
   },
   {
    "id": "5c5cc4450f2a48eaad52d8e1742889c2",
    "name": "Ylhel",
    "selected": false,
    "caption": "CHA -1 · INT +2 · Ankarin, Dwarvish"
   },
   {
    "id": "a191e540a1284ae1a89525317ae859d1",
    "name": "Adelio Small-Knife",
    "selected": false,
    "caption": "CHA +0 · INT -2 · Halfling, Ankarin"
   },
   {
    "id": "751ba69fbef34b3295abe6a055f8f29a",
    "name": "Irduntikorn",
    "selected": false,
    "caption": "CHA +0 · INT -3 · Dwarvish"
   },
   {
    "id": "db2a997815834e1db2e0d765aa787d1f",
    "name": "Vashmorza",
    "selected": false,
    "caption": "CHA +0 · INT -1 · Draconic"
   }
  ],
  "options": [
   {
    "id": "persuade",
    "label": "Persuade",
    "note": "talk them out of it: no fight · a miss and it is a fight",
    "check": "CHA +2 vs DC 13",
    "odds": 0.5,
    "block": ""
   },
   {
    "id": "bluff",
    "label": "Bluff",
    "note": "send them off on a lie · a miss and they strike first",
    "check": "CHA +2 vs DC 10",
    "odds": 0.65,
    "block": ""
   },
   {
    "id": "intimidate",
    "label": "Intimidate",
    "note": "shake them: they start demoralized, or run · a miss gives them the jump",
    "check": "CHA +2 vs DC 10",
    "odds": 0.65,
    "block": ""
   },
   {
    "id": "bribe",
    "label": "Bribe",
    "note": "pay them off: no fight",
    "check": "$24",
    "odds": null,
    "block": ""
   },
   {
    "id": "attack",
    "label": "Attack",
    "note": "roll initiative",
    "check": "",
    "odds": null,
    "block": ""
   }
  ],
  "result": null,
  "title": "AMBUSHED ON THE ROAD",
  "kind": "ambush",
  "leader_unit": {
   "id": "d15dd0a8d76644a3ba2a643a0defc87c",
   "name": "Bexgrok",
   "race": "Goblin",
   "occ": "Mercenary",
   "lvl": 1,
   "hp": [
    5,
    5
   ],
   "face": "img/goblin_0.png",
   "cha": 1,
   "int": 2,
   "langs": [
    "Goblin"
   ],
   "align": "Neutral and Evil",
   "money": 30,
   "crime": 0
  },
  "foe_units": [
   {
    "id": "d15dd0a8d76644a3ba2a643a0defc87c",
    "name": "Bexgrok",
    "race": "Goblin",
    "occ": "Mercenary",
    "lvl": 1,
    "hp": [
     5,
     5
    ],
    "face": "img/goblin_0.png",
    "cha": 1,
    "int": 2,
    "langs": [
     "Goblin"
    ],
    "align": "Neutral and Evil",
    "money": 30,
    "crime": 0
   },
   {
    "id": "f83949cdd8e2420bb73e957c623f0ed7",
    "name": "Garulnmunek",
    "race": "Human",
    "occ": "Jailer",
    "lvl": 1,
    "hp": [
     13,
     13
    ],
    "face": "img/human_13.png",
    "cha": 1,
    "int": 1,
    "langs": [
     "Ankarin",
     "Sylvan"
    ],
    "align": "Neutral and Evil",
    "money": 28,
    "crime": 0
   },
   {
    "id": "0dab2e72dfab4b839f3b3043ce871d52",
    "name": "Senkorruther",
    "race": "Goblin",
    "occ": "Thief",
    "lvl": 1,
    "hp": [
     6,
     6
    ],
    "face": "img/goblin_2.png",
    "cha": 0,
    "int": -4,
    "langs": [
     "Goblin"
    ],
    "align": "Lawful and Neutral",
    "money": 20,
    "crime": 0
   },
   {
    "id": "f3a78b0e9f554d8db5c57518f1ace07d",
    "name": "Rigthal",
    "race": "Automaton",
    "occ": "Cartographer",
    "lvl": 1,
    "hp": [
     10,
     10
    ],
    "face": "img/automaton_7.png",
    "cha": -1,
    "int": 2,
    "langs": [
     "Ankarin"
    ],
    "align": "Chaotic and Neutral",
    "money": 23,
    "crime": 0
   }
  ],
  "band": [
   {
    "id": "d9e926b5d8404e7196b643ed19dd8932",
    "name": "Tikrom",
    "race": "Dwarf",
    "occ": "Woodcutter",
    "lvl": 4,
    "hp": [
     19,
     47
    ],
    "face": "img/dwarf_1.png",
    "cha": -1,
    "int": 1,
    "langs": [
     "Dwarvish"
    ],
    "align": "Chaotic and Evil",
    "money": 184,
    "crime": 0
   },
   {
    "id": "e97654247b2e450dbc6e3f1a7187929a",
    "name": "Vokoranyr",
    "race": "Human",
    "occ": "Hunter",
    "lvl": 3,
    "hp": [
     10,
     25
    ],
    "face": "img/human_4.png",
    "cha": 2,
    "int": -1,
    "langs": [
     "Ankarin",
     "Goblin"
    ],
    "align": "Chaotic and Good",
    "money": 84,
    "crime": 0
   },
   {
    "id": "5c5cc4450f2a48eaad52d8e1742889c2",
    "name": "Ylhel",
    "race": "Human",
    "occ": "Merchant",
    "lvl": 2,
    "hp": [
     1,
     20
    ],
    "face": "img/human_5.png",
    "cha": -1,
    "int": 2,
    "langs": [
     "Ankarin",
     "Dwarvish"
    ],
    "align": "Neutral and Neutral",
    "money": 83,
    "crime": 0
   },
   {
    "id": "a191e540a1284ae1a89525317ae859d1",
    "name": "Adelio Small-Knife",
    "race": "Halfling",
    "occ": "Thief",
    "lvl": 3,
    "hp": [
     9,
     9
    ],
    "face": "img/halfling_adelio.png",
    "cha": 0,
    "int": -2,
    "langs": [
     "Halfling",
     "Ankarin"
    ],
    "align": "Neutral and Evil",
    "money": 283,
    "crime": 0
   },
   {
    "id": "751ba69fbef34b3295abe6a055f8f29a",
    "name": "Irduntikorn",
    "race": "Dwarf",
    "occ": "Innkeeper",
    "lvl": 2,
    "hp": [
     5,
     5
    ],
    "face": "img/dwarf_0.png",
    "cha": 0,
    "int": -3,
    "langs": [
     "Dwarvish"
    ],
    "align": "Neutral and Neutral",
    "money": 223,
    "crime": 0
   },
   {
    "id": "db2a997815834e1db2e0d765aa787d1f",
    "name": "Vashmorza",
    "race": "Lizardfolk",
    "occ": "Goldsmith",
    "lvl": 4,
    "hp": [
     34,
     34
    ],
    "face": "img/lizardfolk_6.png",
    "cha": 0,
    "int": -1,
    "langs": [
     "Draconic"
    ],
    "align": "Lawful and Good",
    "money": 171,
    "crime": 0
   }
  ],
  "band_name": "Vokoranyr's Band",
  "place": "Old Road",
  "edge": 4,
  "dc_base": 15,
  "leader_wis": -1,
  "speaker": "e97654247b2e450dbc6e3f1a7187929a",
  "options_by": {
   "d9e926b5d8404e7196b643ed19dd8932": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA -1 vs DC 13",
     "odds": 0.35,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "e97654247b2e450dbc6e3f1a7187929a": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +2 vs DC 13",
     "odds": 0.5,
     "block": "",
     "open": true
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +2 vs DC 10",
     "odds": 0.65,
     "block": "",
     "open": true
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +2 vs DC 10",
     "odds": 0.65,
     "block": "",
     "open": true
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "5c5cc4450f2a48eaad52d8e1742889c2": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA -1 vs DC 13",
     "odds": 0.35,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA -1 vs DC 10",
     "odds": 0.5,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "a191e540a1284ae1a89525317ae859d1": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +0 vs DC 13",
     "odds": 0.4,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "751ba69fbef34b3295abe6a055f8f29a": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +0 vs DC 13",
     "odds": 0.4,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "db2a997815834e1db2e0d765aa787d1f": [
    {
     "verb": "persuade",
     "label": "Persuade",
     "note": "talk them out of it: no fight · a miss and it is a fight",
     "check": "CHA +0 vs DC 13",
     "odds": 0.4,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "send them off on a lie · a miss and they strike first",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "intimidate",
     "label": "Intimidate",
     "note": "shake them: they start demoralized, or run · a miss gives them the jump",
     "check": "CHA +0 vs DC 10",
     "odds": 0.55,
     "block": "needs Goblin",
     "open": false
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "pay them off: no fight",
     "check": "$24",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "roll initiative",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ]
  },
  "roll": {
   "verb": "bluff",
   "speaker": "e97654247b2e450dbc6e3f1a7187929a",
   "kind": "fight",
   "text": "Bexgrok sees through it (d20(5) +2 = 7 vs DC 10) and strikes first!",
   "paid": 0,
   "opening": {
    "surprised": "player",
    "demoralized": null,
    "initiative": {}
   }
  }
 },
 "guard": {
  "leader": {
   "name": "Lysmirgrok",
   "caption": "Human Priest",
   "race": "Human",
   "portrait": 2604540894
  },
  "line": "\"Surshohromskel, in the name of the City -- you will come with us.\"",
  "foes": [
   "Lysmirgrok · Human",
   "Manim · Lizardfolk",
   "Othmunvelek · Elf"
  ],
  "speakers": [
   {
    "id": "8d19564ac59542518dc2799584ead542",
    "name": "Surshohromskel",
    "selected": true,
    "caption": "CHA +2 · INT +0 · Ankarin, Halfling"
   },
   {
    "id": "4bead963780045f0a91a38141a611565",
    "name": "Gormdral",
    "selected": false,
    "caption": "CHA +0 · INT -1 · Dwarvish"
   },
   {
    "id": "f65f69cd8abb41d19b514321f55a6e03",
    "name": "Branhel",
    "selected": false,
    "caption": "CHA -1 · INT +0 · Ankarin, Halfling"
   }
  ],
  "options": [
   {
    "id": "surrender",
    "label": "Surrender",
    "note": "crime clears to 0: time served in the City's cells",
    "check": "",
    "odds": null,
    "block": ""
   },
   {
    "id": "bluff",
    "label": "Bluff",
    "note": "the wrong man: they let you go, the crime stays · a miss and they strike first",
    "check": "CHA +2 vs DC 15",
    "odds": 0.4,
    "block": ""
   },
   {
    "id": "bribe",
    "label": "Bribe",
    "note": "they look away: the crime stays",
    "check": "$30",
    "odds": null,
    "block": ""
   },
   {
    "id": "attack",
    "label": "Attack",
    "note": "lethal; living through it adds to the rap sheet",
    "check": "",
    "odds": null,
    "block": ""
   },
   {
    "id": "leave",
    "label": "Run",
    "note": "fall back the way the group came",
    "check": "",
    "odds": null,
    "block": ""
   }
  ],
  "result": null,
  "title": "THE GUARD",
  "kind": "guard",
  "leader_unit": {
   "id": "9b3e23de8b024fcfbab7293d5d192983",
   "name": "Lysmirgrok",
   "race": "Human",
   "occ": "Priest",
   "lvl": 3,
   "hp": [
    13,
    13
   ],
   "face": "img/human_14.png",
   "cha": -1,
   "int": 0,
   "langs": [
    "Ankarin",
    "Dwarvish"
   ],
   "align": "Chaotic and Neutral",
   "money": 40,
   "crime": 0
  },
  "foe_units": [
   {
    "id": "9b3e23de8b024fcfbab7293d5d192983",
    "name": "Lysmirgrok",
    "race": "Human",
    "occ": "Priest",
    "lvl": 3,
    "hp": [
     13,
     13
    ],
    "face": "img/human_14.png",
    "cha": -1,
    "int": 0,
    "langs": [
     "Ankarin",
     "Dwarvish"
    ],
    "align": "Chaotic and Neutral",
    "money": 40,
    "crime": 0
   },
   {
    "id": "1d68497a54cd4602bd291533f00c8cc7",
    "name": "Manim",
    "race": "Lizardfolk",
    "occ": "Shepherd",
    "lvl": 3,
    "hp": [
     16,
     16
    ],
    "face": "img/lizardfolk_3.png",
    "cha": 1,
    "int": 1,
    "langs": [
     "Draconic"
    ],
    "align": "Neutral and Evil",
    "money": 23,
    "crime": 0
   },
   {
    "id": "b1149a0fa3be408e8285346b50b435b6",
    "name": "Othmunvelek",
    "race": "Elf",
    "occ": "Messenger",
    "lvl": 3,
    "hp": [
     23,
     23
    ],
    "face": "img/elf_6.png",
    "cha": 0,
    "int": 2,
    "langs": [
     "Elvish"
    ],
    "align": "Neutral and Good",
    "money": 22,
    "crime": 0
   }
  ],
  "band": [
   {
    "id": "8d19564ac59542518dc2799584ead542",
    "name": "Surshohromskel",
    "race": "Human",
    "occ": "Woodcutter",
    "lvl": 2,
    "hp": [
     14,
     14
    ],
    "face": "img/human_10.png",
    "cha": 2,
    "int": 0,
    "langs": [
     "Ankarin",
     "Halfling"
    ],
    "align": "Neutral and Good",
    "money": 7,
    "crime": 3
   },
   {
    "id": "4bead963780045f0a91a38141a611565",
    "name": "Gormdral",
    "race": "Dwarf",
    "occ": "Guide",
    "lvl": 1,
    "hp": [
     3,
     12
    ],
    "face": "img/dwarf_8.png",
    "cha": 0,
    "int": -1,
    "langs": [
     "Dwarvish"
    ],
    "align": "Lawful and Neutral",
    "money": 20,
    "crime": 0
   },
   {
    "id": "f65f69cd8abb41d19b514321f55a6e03",
    "name": "Branhel",
    "race": "Human",
    "occ": "Mercenary",
    "lvl": 1,
    "hp": [
     2,
     2
    ],
    "face": "img/human_13.png",
    "cha": -1,
    "int": 0,
    "langs": [
     "Ankarin",
     "Halfling"
    ],
    "align": "Chaotic and Good",
    "money": 37,
    "crime": 0
   }
  ],
  "band_name": "2th Band",
  "place": "Ankareth",
  "edge": 0,
  "dc_base": 15,
  "leader_wis": 0,
  "speaker": "8d19564ac59542518dc2799584ead542",
  "options_by": {
   "8d19564ac59542518dc2799584ead542": [
    {
     "verb": "surrender",
     "label": "Surrender",
     "note": "crime clears to 0: time served in the City's cells",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "the wrong man: they let you go, the crime stays · a miss and they strike first",
     "check": "CHA +2 vs DC 15",
     "odds": 0.4,
     "block": "",
     "open": true
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "they look away: the crime stays",
     "check": "$30",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "lethal; living through it adds to the rap sheet",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "leave",
     "label": "Run",
     "note": "fall back the way the group came",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "4bead963780045f0a91a38141a611565": [
    {
     "verb": "surrender",
     "label": "Surrender",
     "note": "crime clears to 0: time served in the City's cells",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "the wrong man: they let you go, the crime stays · a miss and they strike first",
     "check": "CHA +0 vs DC 15",
     "odds": 0.3,
     "block": "",
     "open": true
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "they look away: the crime stays",
     "check": "$30",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "lethal; living through it adds to the rap sheet",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "leave",
     "label": "Run",
     "note": "fall back the way the group came",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ],
   "f65f69cd8abb41d19b514321f55a6e03": [
    {
     "verb": "surrender",
     "label": "Surrender",
     "note": "crime clears to 0: time served in the City's cells",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "bluff",
     "label": "Bluff",
     "note": "the wrong man: they let you go, the crime stays · a miss and they strike first",
     "check": "CHA -1 vs DC 15",
     "odds": 0.25,
     "block": "",
     "open": true
    },
    {
     "verb": "bribe",
     "label": "Bribe",
     "note": "they look away: the crime stays",
     "check": "$30",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "attack",
     "label": "Attack",
     "note": "lethal; living through it adds to the rap sheet",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    },
    {
     "verb": "leave",
     "label": "Run",
     "note": "fall back the way the group came",
     "check": "",
     "odds": null,
     "block": "",
     "open": true
    }
   ]
  },
  "caught": [
   "8d19564ac59542518dc2799584ead542"
  ]
 },
 "boss": {
  "leader": {
   "name": "Ribit",
   "caption": "the eldest brother",
   "race": "Grippli",
   "portrait": "ribit.png"
  },
  "line": "Bufo holds the flag, Peep holds the water, and I hold your attention. Let's see who tires first.",
  "foes": [
   "Ribit · Grippli",
   "Bufo · Grippli",
   "Peep · Grippli"
  ],
  "speakers": [],
  "options": [],
  "result": {
   "text": "Bufo steps up.",
   "tone": "next",
   "button": "GO ON"
  },
  "title": "THE PIT: THE RIBBIT BROTHERS",
  "kind": "boss",
  "leader_unit": {
   "id": "a555ea2c865a47018b7499c0fe953b7a",
   "name": "Ribit",
   "race": "Grippli",
   "occ": "Hunter",
   "lvl": 5,
   "hp": [
    37,
    37
   ],
   "face": "img/grippli_ribit.png",
   "cha": -2,
   "int": -1,
   "langs": [
    "Sylvan",
    "Ankarin"
   ],
   "align": "Chaotic and Neutral",
   "money": 40,
   "crime": 0
  },
  "foe_units": [
   {
    "id": "a555ea2c865a47018b7499c0fe953b7a",
    "name": "Ribit",
    "race": "Grippli",
    "occ": "Hunter",
    "lvl": 5,
    "hp": [
     37,
     37
    ],
    "face": "img/grippli_ribit.png",
    "cha": -2,
    "int": -1,
    "langs": [
     "Sylvan",
     "Ankarin"
    ],
    "align": "Chaotic and Neutral",
    "money": 40,
    "crime": 0
   },
   {
    "id": "049ba8da78334b1db53c6d0fed6f7355",
    "name": "Bufo",
    "race": "Grippli",
    "occ": "Butcher",
    "lvl": 5,
    "hp": [
     44,
     44
    ],
    "face": "img/grippli_bufo.png",
    "cha": -1,
    "int": -1,
    "langs": [
     "Sylvan"
    ],
    "align": "Neutral and Neutral",
    "money": 30,
    "crime": 0
   },
   {
    "id": "e2411b0bcb7949a0bc9ed9204ad04a84",
    "name": "Peep",
    "race": "Grippli",
    "occ": "Crossbowman",
    "lvl": 5,
    "hp": [
     27,
     27
    ],
    "face": "img/grippli_peep.png",
    "cha": 0,
    "int": 0,
    "langs": [
     "Sylvan"
    ],
    "align": "Chaotic and Neutral",
    "money": 30,
    "crime": 0
   }
  ],
  "band": [
   {
    "id": "d9e926b5d8404e7196b643ed19dd8932",
    "name": "Tikrom",
    "race": "Dwarf",
    "occ": "Woodcutter",
    "lvl": 4,
    "hp": [
     19,
     47
    ],
    "face": "img/dwarf_1.png",
    "cha": -1,
    "int": 1,
    "langs": [
     "Dwarvish"
    ],
    "align": "Chaotic and Evil",
    "money": 184,
    "crime": 0
   },
   {
    "id": "e97654247b2e450dbc6e3f1a7187929a",
    "name": "Vokoranyr",
    "race": "Human",
    "occ": "Hunter",
    "lvl": 3,
    "hp": [
     10,
     25
    ],
    "face": "img/human_4.png",
    "cha": 2,
    "int": -1,
    "langs": [
     "Ankarin",
     "Goblin"
    ],
    "align": "Chaotic and Good",
    "money": 84,
    "crime": 0
   },
   {
    "id": "5c5cc4450f2a48eaad52d8e1742889c2",
    "name": "Ylhel",
    "race": "Human",
    "occ": "Merchant",
    "lvl": 2,
    "hp": [
     1,
     20
    ],
    "face": "img/human_5.png",
    "cha": -1,
    "int": 2,
    "langs": [
     "Ankarin",
     "Dwarvish"
    ],
    "align": "Neutral and Neutral",
    "money": 83,
    "crime": 0
   },
   {
    "id": "a191e540a1284ae1a89525317ae859d1",
    "name": "Adelio Small-Knife",
    "race": "Halfling",
    "occ": "Thief",
    "lvl": 3,
    "hp": [
     9,
     9
    ],
    "face": "img/halfling_adelio.png",
    "cha": 0,
    "int": -2,
    "langs": [
     "Halfling",
     "Ankarin"
    ],
    "align": "Neutral and Evil",
    "money": 283,
    "crime": 0
   },
   {
    "id": "751ba69fbef34b3295abe6a055f8f29a",
    "name": "Irduntikorn",
    "race": "Dwarf",
    "occ": "Innkeeper",
    "lvl": 2,
    "hp": [
     5,
     5
    ],
    "face": "img/dwarf_0.png",
    "cha": 0,
    "int": -3,
    "langs": [
     "Dwarvish"
    ],
    "align": "Neutral and Neutral",
    "money": 223,
    "crime": 0
   },
   {
    "id": "db2a997815834e1db2e0d765aa787d1f",
    "name": "Vashmorza",
    "race": "Lizardfolk",
    "occ": "Goldsmith",
    "lvl": 4,
    "hp": [
     34,
     34
    ],
    "face": "img/lizardfolk_6.png",
    "cha": 0,
    "int": -1,
    "langs": [
     "Draconic"
    ],
    "align": "Lawful and Good",
    "money": 171,
    "crime": 0
   }
  ],
  "band_name": "Vokoranyr's Band",
  "place": "Old Road",
  "edge": 0,
  "dc_base": 15,
  "leader_wis": 2,
  "speaker": "e97654247b2e450dbc6e3f1a7187929a",
  "options_by": {
   "d9e926b5d8404e7196b643ed19dd8932": [],
   "e97654247b2e450dbc6e3f1a7187929a": [],
   "5c5cc4450f2a48eaad52d8e1742889c2": [],
   "a191e540a1284ae1a89525317ae859d1": [],
   "751ba69fbef34b3295abe6a055f8f29a": [],
   "db2a997815834e1db2e0d765aa787d1f": []
  },
  "lines": [
   {
    "who": {
     "id": "a555ea2c865a47018b7499c0fe953b7a",
     "name": "Ribit",
     "race": "Grippli",
     "occ": "Hunter",
     "lvl": 5,
     "hp": [
      37,
      37
     ],
     "face": "img/grippli_ribit.png",
     "cha": -2,
     "int": -1,
     "langs": [
      "Sylvan",
      "Ankarin"
     ],
     "align": "Chaotic and Neutral",
     "money": 40,
     "crime": 0
    },
    "caption": "the eldest brother",
    "line": "Bufo holds the flag, Peep holds the water, and I hold your attention. Let's see who tires first."
   },
   {
    "who": {
     "id": "049ba8da78334b1db53c6d0fed6f7355",
     "name": "Bufo",
     "race": "Grippli",
     "occ": "Butcher",
     "lvl": 5,
     "hp": [
      44,
      44
     ],
     "face": "img/grippli_bufo.png",
     "cha": -1,
     "int": -1,
     "langs": [
      "Sylvan"
     ],
     "align": "Neutral and Neutral",
     "money": 30,
     "crime": 0
    },
    "caption": "the big brother",
    "line": "Flag stays. You go."
   },
   {
    "who": {
     "id": "e2411b0bcb7949a0bc9ed9204ad04a84",
     "name": "Peep",
     "race": "Grippli",
     "occ": "Crossbowman",
     "lvl": 5,
     "hp": [
      27,
      27
     ],
     "face": "img/grippli_peep.png",
     "cha": 0,
     "int": 0,
     "langs": [
      "Sylvan"
     ],
     "align": "Chaotic and Neutral",
     "money": 30,
     "crime": 0
    },
    "caption": "the runt",
    "line": "Wade in, wade in. The water's lovely. I'll count the splashes."
   }
  ]
 }
};

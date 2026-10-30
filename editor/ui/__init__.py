"""War-table UI kit: standalone components for the "steel desk + paper map"
screen design, extracted from the war_table_v3 prototype so they can be
plugged into `map_screen.py` piece by piece instead of in one big rewrite.

Each module owns one zone of the layout (map, command bar, roster, inspector)
plus the shared tokens/primitives/camera they're built from. Components take
their data (nodes, edges, groups, ...) as function parameters rather than
reading module globals, so a caller with real `world`/`guild` data can drive
them the same way the prototype's mock data does.
"""

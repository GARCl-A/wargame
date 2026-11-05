"""Fold flat `{"dotted.key": "texto"}` chunk files into `locales/pt-br.json`, refusing a key that has no `en`
twin, a different shape (string / list / name+gender) or different `{placeholders}`.

    python scripts/i18n_merge.py chunk1.json chunk2.json ...

Keys already in `pt-br.json` are kept unless a chunk says otherwise; the file is rewritten nested like `en.json`.
"""

import json
import os
import string
import sys

LOCALES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")


def flat(node, prefix=""):
    for k, v in node.items():
        if isinstance(v, dict) and not ("name" in v and set(v) <= {"name", "gender"}):
            yield from flat(v, f"{prefix}{k}.")
        else:
            yield f"{prefix}{k}", v


def placeholders(value):
    text = "\n".join(value) if isinstance(value, list) else value["name"] if isinstance(value, dict) else value
    return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f)


def load(name):
    with open(os.path.join(LOCALES, name), encoding="utf-8") as fh:
        return dict(flat(json.load(fh)))


def main(chunks):
    sys.path.insert(0, os.path.dirname(LOCALES))
    from gartok import i18n

    en = {**load("en.json"), **i18n.catalog("en")}
    try:
        out = load("pt-br.json")
    except FileNotFoundError:
        out = {}
    bad = 0
    for path in chunks:
        with open(path, encoding="utf-8") as fh:
            chunk = json.load(fh)
        for key, value in chunk.items():
            twin = en.get(key, en.get(key[:-2]) if key.endswith(".f") else None)
            if twin is None:
                print("not in en:", key)
            elif (type(value) is not type(twin) and not (isinstance(value, dict) and isinstance(twin, str))) or (
                isinstance(value, list) and len(value) != len(twin)
            ):
                print("different shape:", key)
            elif placeholders(value) != placeholders(twin):
                print("placeholders:", key, placeholders(twin), placeholders(value))
            else:
                out[key] = value
                continue
            bad += 1
    for key in [k for k in out if k.endswith(".f") and k[:-2] in out]:
        base = out[key[:-2]]
        out[key[:-2]] = {**(base if isinstance(base, dict) else {"name": base}), "f": out.pop(key)}
    nested = {}
    for key, value in out.items():
        node = nested
        *head, last = key.split(".")
        for part in head:
            node = node.setdefault(part, {})
        node[last] = value
    with open(os.path.join(LOCALES, "pt-br.json"), "w", encoding="utf-8") as fh:
        json.dump(nested, fh, ensure_ascii=False, indent=1)
    print(f"{sum(1 for k in out if k in en)} of {len(en)} keys translated, {bad} refused")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

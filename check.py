import json, glob
for p in glob.glob('saves/*.json'):
    d=json.load(open(p))
    for u in d.get('guild',{}).get('roster',[]):
        print(u['name'], u['languages'])

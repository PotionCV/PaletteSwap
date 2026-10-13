# -*- coding: utf-8 -*-
"""把工程里的配色抄成 palettes_snapshot.json —— exe 找不到工程时用它兜底。"""
import io, json, os, sys, datetime
sys.path.insert(0, 'E:/Works/_agent_tmp/palette')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
import palette_swap as ps

g = ps.resolve_game_dir(None)
assert g, '本机找不到工程，没法生成快照'
color = json.load(open(ps.find_config(g, 'Color.json'), encoding='utf-8'))['data']
pats, order, extra = ps.load_palettes(g)

keep = {}
for name in list(order) + list(extra):
    for i in range(16):
        k = '%s%d' % (name, i)
        if k in color:
            keep[k] = color[k]
snap = {'built': datetime.date.today().isoformat(), 'from': g,
        'note': 'Driller 1.0.7 的内置配色快照；只含调色板键，不含 Level* 主题色',
        'order': order, 'extra': extra, 'colors': keep}
out = 'E:/Works/_agent_tmp/palette/palettes_snapshot.json'
json.dump(snap, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
print('写出 %s  %.1f KB  %d 个键' % (out, os.path.getsize(out) / 1024.0, len(keep)))
print('  调色板：', ', '.join('%s(%d)' % (n, pats[n].n) for n in order), '| 备用：', extra)

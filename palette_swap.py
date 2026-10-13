# -*- coding: utf-8 -*-
"""
palette_swap.py —— 把任意图片转成 Driller 游戏内调色板的样子

复刻 Construct 3 效果 federicoCalchera_paletteSwap16（就是工程里的 "PaletteSwap16"），
逐像素照抄它的 shader，包含 ditherIntensity（网点强度）与 intensity（混合强度）两个参数：

    c = front + (dither_matrix(x,y) * ditherIntensity) / 255
    c = clamp(c, 0, 1)
    c = 调色板里最近的颜色（欧氏距离，距离相同取靠前的那个）
    out = mix(front, c, intensity)

调色板直接读工程里的 files/Configs/Color.json（键 <调色板名><序号>），
可选项读 Common.json 的 PaletteList —— 和游戏里设置界面那份顺序一致，
所以游戏更新配色之后这里自动跟着变。

用法（命令行）：
    python palette_swap.py --list
    python palette_swap.py 输入.png 输出.png --palette NYX8
    python palette_swap.py 输入.png --palette EN4 --dither 50 --intensity 75
    python palette_swap.py --batch 输入目录 输出目录 --palette Paper8
    python palette_swap.py --game "E:/Works/ConstructGame/Driller/Driller1.0.7" -l

不带参数直接运行（或 palette_gui.bat）= 打开小窗口：
    把 png / jpg / gif 拖进窗口（也可以把图拖到 palette_gui.bat 图标上）
    选配色 → 两个滑块 → 并排预览 → 另存 / 拆 PNG 序列 / 批量
    滚轮缩放（以光标为锚点）· 按住左键拖动平移 · 双击或「适应窗口」复位 · 「1:1」看原像素
    动图（gif）逐帧转换，帧数 / 每帧时长 / 循环次数 / 透明全保留，窗口里按原速播放。

打包成 PaletteSwap.exe 之后（build_exe.py 生成，不需要本机装 Python）：
    双击 exe = 开窗口；把图拖到 exe 图标上 = 用这张图开窗口（一次拖几张只取第一张）；
    在 cmd/PowerShell 里带参数运行 = 命令行，例：PaletteSwap.exe 图.png out.png -p NYX8
    配色优先读工程（--game / exe 旁边 / 当前目录），都没有就用打包进去的快照。

参数单位同游戏编辑器：dither / intensity 都是百分比 0–100。**默认都是 75**（＝游戏换配色
过渡结束时的样子，也是 layouts/Title.json 附近的那一档）：
  dither=75 intensity=75   → 默认
  dither=0  intensity=100  → 纯净转换（每个像素都是调色板里的颜色）＝游戏里的静止态
  dither=50 intensity=75   → layouts/Title.json 里存的初始值
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError as e:  # pragma: no cover
    raise SystemExit('需要 numpy 和 Pillow：pip install numpy pillow  (%s)' % e)

DEFAULT_GAME = 'E:/Works/ConstructGame/Driller/Driller1.0.7'
IMG_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tga', '.webp', '.tif', '.tiff')


# --------------------------------------------------------------------------
# 1. 网点矩阵：shader 里 dither_matrix(x, y) 的原文，原样翻译成 Python 求值
# --------------------------------------------------------------------------
_DITHER_BODY = (
    'return mix(mix(mix(mix(mix(mix(0.0,32.0,step(1.0,y)),mix(8.0,40.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(2.0,34.0,step(5.0,y)),mix(10.0,42.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),'
    'mix(mix(mix(48.0,16.0,step(1.0,y)),mix(56.0,24.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(50.0,18.0,step(5.0,y)),mix(58.0,26.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),step(1.0,x)),'
    'mix(mix(mix(mix(12.0,44.0,step(1.0,y)),mix(4.0,36.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(14.0,46.0,step(5.0,y)),mix(6.0,38.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),'
    'mix(mix(mix(60.0,28.0,step(1.0,y)),mix(52.0,20.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(62.0,30.0,step(5.0,y)),mix(54.0,22.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),step(3.0,x)),step(2.0,x)),'
    'mix(mix(mix(mix(mix(3.0,35.0,step(1.0,y)),mix(11.0,43.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(1.0,33.0,step(5.0,y)),mix(9.0,41.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),'
    'mix(mix(mix(51.0,19.0,step(1.0,y)),mix(59.0,27.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(49.0,17.0,step(5.0,y)),mix(57.0,25.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),step(5.0,x)),'
    'mix(mix(mix(mix(15.0,47.0,step(1.0,y)),mix(7.0,39.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(13.0,45.0,step(5.0,y)),mix(5.0,37.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),'
    'mix(mix(mix(63.0,31.0,step(1.0,y)),mix(55.0,23.0,step(3.0,y)),step(2.0,y)),'
    'mix(mix(61.0,29.0,step(5.0,y)),mix(53.0,21.0,step(7.0,y)),step(6.0,y)),step(4.0,y)),step(7.0,x)),step(6.0,x)),step(4.0,x))'
)


def _build_bayer():
    def mix(a, b, t):
        return a + (b - a) * t

    def step(edge, v):
        return 1.0 if v >= edge else 0.0

    env = {'mix': mix, 'step': step}
    body = _DITHER_BODY[len('return '):]
    return [[int(eval(body, dict(env, x=float(x), y=float(y)))) for x in range(8)]
            for y in range(8)]


BAYER8 = _build_bayer()          # BAYER8[y % 8][x % 8] -> 0..63


# --------------------------------------------------------------------------
# 2. 调色板：从工程里读
# --------------------------------------------------------------------------
class Palette:
    def __init__(self, name, colors, slots=16):
        self.name = name
        self.real = list(colors)                      # 真实颜色
        self.slots = list(colors) + [(0, 0, 0)] * max(0, slots - len(colors))
        # 游戏里超出真实颜色的槽位被写成黑（eUI：for 0..15 先全设 0，只有 ≤BitColor 的被覆盖）
        self.padded = len(self.slots) > len(self.real)

    @property
    def n(self):
        return len(self.real)

    def __repr__(self):
        tag = '（后 %d 槽是黑）' % (len(self.slots) - self.n) if self.padded else ''
        return '%-12s %2d 色%s' % (self.name, self.n, tag)


SNAPSHOT = 'palettes_snapshot.json'
PALETTE_SOURCE = ''          # 当前这批配色是从哪来的（给界面/命令行显示）


def app_dir():
    """打包成 exe 后 = exe 所在目录；源码运行 = 本文件所在目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _resource(name):
    """随程序打包进去的资源（PyInstaller 会解到 sys._MEIPASS）。"""
    return os.path.join(getattr(sys, '_MEIPASS', app_dir()), name)


def find_config(game_dir, filename):
    for p in (os.path.join(game_dir, 'files', 'Configs', filename),
              os.path.join(game_dir, filename)):
        if os.path.isfile(p):
            return p
    return None


def resolve_game_dir(explicit=None):
    """找工程目录（里面有 files/Configs/Color.json）。找不到就返回 None，改用内置快照。"""
    cands = []
    if explicit:
        cands.append(explicit)
    cands.append(DEFAULT_GAME)
    for base in (app_dir(), os.getcwd()):
        cands.append(base)
        try:                      # exe 旁边放的就是工程（或工程的上一级）
            cands += [os.path.join(base, d) for d in sorted(os.listdir(base))
                      if os.path.isdir(os.path.join(base, d))]
        except OSError:
            pass
    for c in cands:
        if c and find_config(c, 'Color.json'):
            return c
    return None


def _colors_of(color, name):
    out = []
    for i in range(16):
        v = color.get('%s%d' % (name, i))
        if v is None:
            break
        out.append(tuple(int(t) for t in str(v).split(',')[:3]))
    return out


def _build_palettes(color, order):
    """返回 (有序字典 name -> Palette, 顺序同游戏 PaletteList)"""
    pats = {}
    for name in order:
        c = _colors_of(color, name)
        if c:
            pats[name] = Palette(name, c)
    if not pats:
        raise SystemExit('Color.json 里没找到可用调色板')
    # PaletteList 里没写、但 Color.json 里有一套完整颜色的也收进来（备用）
    extra = []
    for name in _candidate_names(color, order):
        if name not in pats:
            c = _colors_of(color, name)
            if len(c) in (2, 4, 8, 16):
                pats[name] = Palette(name, c)
                extra.append(name)
    return pats, order, extra


def load_palettes(game_dir=None):
    """优先读工程（--game / exe 旁边 / 当前目录），实在没有就用打包进来的快照。"""
    global PALETTE_SOURCE
    g = resolve_game_dir(game_dir)
    if g:
        color = json.load(open(find_config(g, 'Color.json'), encoding='utf-8'))['data']
        cp = find_config(g, 'Common.json')
        order = []
        if cp:
            common = json.load(open(cp, encoding='utf-8'))['data']
            order = [s for s in str(common.get('PaletteList', '')).split(',') if s]
        PALETTE_SOURCE = '工程 %s' % g
        return _build_palettes(color, order)

    snap = _resource(SNAPSHOT)
    if os.path.isfile(snap):
        d = json.load(open(snap, encoding='utf-8'))
        PALETTE_SOURCE = '内置快照 %s' % d.get('built', '')
        return _build_palettes(d['colors'], d.get('order', []))

    raise SystemExit('找不到工程（--game 指向工程根目录），也没有内置快照 %s' % snap)


def _candidate_names(color, order):
    """从 Color.json 的键里猜出还有哪些调色板（去掉结尾数字，长度≥2 的前缀）。"""
    seen = []
    for k in color:
        if k.startswith('Level'):
            continue
        base = k.rstrip('0123456789')
        if len(base) >= 2 and base not in seen and base not in order:
            seen.append(base)
    return seen


# --------------------------------------------------------------------------
# 3. 核心：一个像素都不差地照抄 shader
# --------------------------------------------------------------------------
def convert_image(img, pal, dither=0.0, intensity=100.0, y_from_bottom=True,
                  keep_alpha0=True, block_rows=256):
    """
    dither / intensity: 百分比 0–100（和游戏编辑器里一样）。
    y_from_bottom: shader 用 gl_FragCoord.y（GL 自下往上），默认与之对齐；
                   图省事可以设 False 用图片自己的行号。
    keep_alpha0: 完全透明的像素不改色（做素材更安全；游戏里那些像素也看不见）。
    """
    src = img.convert('RGBA')
    W, H = src.size
    arr = np.asarray(src, dtype=np.uint8)
    # float64 全程：4 色配色下常有"两种候选色距离几乎相等"的像素，
    # 用 float32 会因末位误差挑错颜色（实测过），所以这里比 GPU 的 mediump 还准。
    rgb = arr[..., :3].astype(np.float64) / 255.0
    alpha = arr[..., 3]

    pal_arr = np.array(pal.slots, dtype=np.float64) / 255.0     # (16,3) 0..1
    dither_frac = float(dither) / 100.0
    inten = float(intensity) / 100.0

    # 网点偏移：每个像素加 (m * ditherIntensity) / 255
    ys = (np.arange(H)[::-1] if y_from_bottom else np.arange(H)) % 8
    xs = np.arange(W) % 8
    offs = np.array(BAYER8, dtype=np.float64)[ys][:, xs]        # (H,W) 0..63
    offs = (offs * dither_frac) / 255.0

    # 大图按行分块，别让 (块高 × 宽 × 16 × 3) 的中间量把内存吃爆
    step = max(1, min(block_rows, int(48e6 / max(1, W * 16 * 3 * 8))))
    out = np.empty_like(rgb)
    for y0 in range(0, H, step):
        y1 = min(H, y0 + step)
        blk = np.clip(rgb[y0:y1] + offs[y0:y1, :, None], 0.0, 1.0)     # (h,W,3)
        d = ((blk[:, :, None, :] - pal_arr[None, None, :, :]) ** 2).sum(-1)   # (h,W,16)
        nearest = pal_arr[d.argmin(-1)]                                # argmin 取第一个最小 ⇒ 距离相同取靠前
        q = rgb[y0:y1] * (1.0 - inten) + nearest * inten
        out[y0:y1] = np.floor(q * 255.0 + 0.5) / 255.0

    res = np.empty((H, W, 4), dtype=np.uint8)
    res[..., :3] = np.clip(np.floor(out * 255.0 + 0.5), 0, 255).astype(np.uint8)
    res[..., 3] = alpha
    if keep_alpha0:
        m = alpha == 0
        res[..., :3][m] = arr[..., :3][m]
    return Image.fromarray(res, 'RGBA')


# --------------------------------------------------------------------------
# 4. 命令行
# --------------------------------------------------------------------------
def out_name(path, pal_name, outdir=None, ext=None):
    stem = os.path.splitext(os.path.basename(path))[0]
    if ext is None:
        ext = os.path.splitext(path)[1][1:].lower() or 'png'
        ext = 'gif' if ext == 'gif' else 'png'      # 动图还是动图，其余统一存 png（保留透明）
    name = '%s_%s.%s' % (stem, pal_name, ext)
    return os.path.join(outdir, name) if outdir else os.path.join(os.path.dirname(path), name)


# --------------------------------------------------------------------------
# 3.5 动图（GIF）：逐帧转换，节奏、循环次数、透明都保留
# --------------------------------------------------------------------------
def load_frames(path):
    """返回 (帧列表[RGBA], 每帧时长ms, 循环次数, 是否动图)。"""
    im = Image.open(path)
    n = int(getattr(im, 'n_frames', 1))
    frames, durations = [], []
    for i in range(n):
        im.seek(i)
        frames.append(im.convert('RGBA'))
        durations.append(int(im.info.get('duration', 100) or 100))
    loop = int(im.info.get('loop', 0) or 0)
    # 有些 gif 的帧尺寸不齐（比逻辑屏还大）——统一贴到同一张透明画布上，
    # 不统一的话存回去帧矩形会超出逻辑屏。
    W = max(f.width for f in frames)
    H = max(f.height for f in frames)
    if any(f.size != (W, H) for f in frames):
        fixed = []
        for f in frames:
            c = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            c.paste(f, (0, 0))
            fixed.append(c)
        frames = fixed
    return frames, durations, loop, n > 1


def convert_frames(frames, pal, dither, intensity, **kw):
    return [convert_image(f, pal, dither, intensity, **kw) for f in frames]


def save_gif(frames, out, durations, loop):
    """把 RGBA 帧存成动图。调色板化用 MEDIANCUT + 不抖动 ⇒ 颜色数 ≤255 时逐色保留。"""
    ps, transparent = [], False
    for f in frames:
        a = f.getchannel('A')
        trans = a.getextrema()[0] < 128
        transparent = transparent or trans
        p = f.convert('RGB').quantize(colors=255 if trans else 256,
                                      method=Image.MEDIANCUT, dither=Image.NONE)
        if trans:                                   # 预留 255 号当透明色
            pal = p.getpalette() or []
            if len(pal) < 768:
                p.putpalette(pal + [0] * (768 - len(pal)))
            p.paste(255, a.point(lambda v: 255 if v < 128 else 0))
        ps.append(p)
    kw = dict(save_all=True, append_images=ps[1:], duration=durations, loop=loop,
              disposal=2, optimize=False)
    if transparent:
        kw['transparency'] = 255
    ps[0].save(out, **kw)


def save_png_sequence(frames, out, stem_dir=None, suffix=''):
    """动图也可以选择导出成 PNG 序列（做素材用）。"""
    base = os.path.splitext(out)[0]
    paths = []
    for i, f in enumerate(frames):
        p = '%s_%03d%s.png' % (base, i, suffix)
        f.save(p)
        paths.append(p)
    return paths


def print_list(palettes, order, extra):
    print('配色来源：%s' % PALETTE_SOURCE)
    print('游戏内的调色板（顺序 = Common.json 的 PaletteList = 设置界面里的顺序）：')
    for i, name in enumerate(order):
        if name in palettes:
            print('  [%d] %s' % (i, palettes[name]))
            print('       ' + '  '.join('#%02X%02X%02X' % c for c in palettes[name].real))
    if extra:
        print('Color.json 里还有（游戏目前没列出来的）：')
        for name in extra:
            print('      %s' % palettes[name])


def convert_file(path, pal, args, outdir=None, output=None, quiet=False):
    """一个文件（含动图）走完整条路：读 → 逐帧转 → 存。返回输出路径（PNG 序列返回列表）。"""
    frames, durations, loop, animated = load_frames(path)
    kw = dict(y_from_bottom=not args.y_top, keep_alpha0=not args.alpha_too)
    if animated and not args.gif_png:
        res = convert_frames(frames, pal, args.dither, args.intensity, **kw)
        out = output or out_name(path, pal.name, outdir, ext='gif')
        save_gif(res, out, durations, loop)
        if not quiet:
            if len(set(durations)) == 1:
                dur = '%dms × %d 帧' % (durations[0], len(durations))
            else:
                dur = '%d~%dms 各帧不一' % (min(durations), max(durations))
            print('%s  →  %s   [%s  %g%% 网点 / %g%% 混合]  %d 帧 × %dx%d  %s  循环 %d'
                  % (os.path.basename(path), out, pal.name, args.dither, args.intensity,
                     len(res), res[0].width, res[0].height, dur, loop))
        return out
    if animated and args.gif_png:
        res = convert_frames(frames, pal, args.dither, args.intensity, **kw)
        out = output or out_name(path, pal.name, outdir, ext='png')
        paths = save_png_sequence(res, out)
        if not quiet:
            print('%s  →  %s   [%s]  %d 帧拆成 PNG 序列' % (os.path.basename(path), paths[0], pal.name, len(paths)))
        return paths
    single = convert_image(frames[0], pal, args.dither, args.intensity, **kw)
    if animated and args.output and args.output.lower().endswith('.gif'):
        out = args.output
        save_gif([single], out, [durations[0]], loop)
    else:
        out = output or out_name(path, pal.name, outdir, ext='png')
        single.save(out)
    if not quiet:
        print('%s  →  %s   [%s  %g%% 网点 / %g%% 混合]  %dx%d%s'
              % (os.path.basename(path), out, pal.name, args.dither, args.intensity,
                 single.width, single.height, '（动图只取第 1 帧）' if animated else ''))
    return out


def do_convert(args, palettes):
    if args.palette not in palettes:
        raise SystemExit('没有配色 %r，可用：%s' % (args.palette, ', '.join(palettes)))
    pal = palettes[args.palette]
    out = convert_file(args.input, pal, args, output=args.output)
    res = Image.open(out if isinstance(out, str) else out[0])
    if args.stats:
        a = np.asarray(res.convert('RGBA'))
        vis = a[..., 3] > 0                       # 只看看得见的像素，透明底不算
        a = a[..., :3][vis].reshape(-1, 3)
        if len(a) == 0:
            print('  （整张图都是透明的）')
            return out
        uniq, cnt = np.unique(a, axis=0, return_counts=True)
        tot = cnt.sum()
        pairs = sorted(zip(uniq.tolist(), cnt.tolist()), key=lambda t: -t[1])[:16]
        print('  用到的颜色（前 16，透明像素已排除）：')
        for c, n in pairs:
            mark = '' if tuple(c) in pal.slots else '  ← 不在调色板里（intensity < 100 混合出来的）'
            if tuple(c) == (0, 0, 0) and pal.padded and (0, 0, 0) not in pal.real:
                mark = '  ← 黑＝超出真实颜色的那些空槽'
            print('    #%02X%02X%02X  %5.2f%%%s' % (c[0], c[1], c[2], 100.0 * n / tot, mark))
    return out


def main_cli(argv):
    argv = list(argv)
    frozen = getattr(sys, 'frozen', False)
    if frozen:                   # 一次往 exe 图标上拖好几张图时，argparse 会嫌参数多
        files = [a for a in argv if os.path.isfile(a)]
        if len(files) > 1:
            argv = [a for a in argv if a not in files[1:]]

    ap = argparse.ArgumentParser(
        description='把图片转成 Driller 游戏内调色板的配色（复刻 PaletteSwap16 效果）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='例：python palette_swap.py 图.png --palette NYX8 --dither 0 --intensity 100')
    ap.add_argument('input', nargs='?', help='输入图片')
    ap.add_argument('output', nargs='?', help='输出图片（默认 <原名>_<配色>.png，存到输入图旁边）')
    ap.add_argument('--palette', '-p', default='NYX8', help='调色板名（--list 看有哪些）')
    ap.add_argument('--dither', '-d', type=float, default=75.0, help='网点强度 0-100（%%），默认 75')
    ap.add_argument('--intensity', '-i', type=float, default=75.0, help='混合强度 0-100（%%），默认 75')
    ap.add_argument('--game', '-g', default=DEFAULT_GAME, help='工程根目录（含 files/Configs/）')
    ap.add_argument('--list', '-l', action='store_true', help='列出所有调色板后退出')
    ap.add_argument('--batch', nargs=2, metavar=('INDIR', 'OUTDIR'), help='整个目录一起转')
    ap.add_argument('--gif-png', action='store_true',
                    help='动图不存成 gif，而是拆成 PNG 序列（<名>_<配色>_000.png…）')
    ap.add_argument('--y-top', action='store_true', help='网点网格从图片第一行开始（默认按 GL 从下往上）')
    ap.add_argument('--alpha-too', action='store_true', help='连全透明像素的 RGB 也一起改（默认保留）')
    ap.add_argument('--stats', action='store_true', help='转换后打印用了哪些颜色')
    ap.add_argument('--gui', action='store_true', help='打开窗口')
    args = ap.parse_args(argv)

    # 什么时候开窗口：显式 --gui；没给任何输入；exe 上只拖了一张图（没写输出路径）
    # —— 所以 exe 想纯命令行转换就得把输出路径写上，例：PaletteSwap.exe 图.png 出.png -p NYX8
    if (args.gui or (not args.input and not args.list and not args.batch)
            or (frozen and args.input and not args.output and not args.list and not args.batch)):
        return run_gui(args)

    palettes, order, extra = load_palettes(args.game)
    if args.list:
        print_list(palettes, order, extra)
        return 0

    if args.batch:
        indir, outdir = args.batch
        if args.palette not in palettes:
            raise SystemExit('没有配色 %r，可用：%s' % (args.palette, ', '.join(palettes)))
        pal = palettes[args.palette]
        os.makedirs(outdir, exist_ok=True)
        files = [f for f in sorted(os.listdir(indir)) if f.lower().endswith(IMG_EXT)]
        n = 0
        for f in files:
            p = os.path.join(indir, f)
            try:
                convert_file(p, pal, args, outdir=outdir, quiet=True)
            except Exception as e:
                print('  跳过 %s：%s' % (f, e))
                continue
            n += 1
        print('批量完成：%d/%d 张 → %s' % (n, len(files), outdir))
        return 0

    if not args.input:
        raise SystemExit('没给输入图片（或加 --list / --batch / --gui）')
    do_convert(args, palettes)
    return 0


# --------------------------------------------------------------------------
# 5. 小窗口
# --------------------------------------------------------------------------
PRESETS = [('游戏过渡', 75, 75), ('纯净转换', 0, 100), ('布局默认', 50, 75)]


def own_console():
    """这个进程是不是独占了自己的控制台（双击时 Windows 新开一个，里面只有自己；
    从 cmd/PowerShell 启动时会挂在终端那个控制台上，进程数 > 1）。

    只用来决定"开窗口时要不要把黑框藏掉"——判错了也无害，不会去碰用户在用的终端。"""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        k = ctypes.windll.kernel32
        if not k.GetConsoleWindow():
            return True
        arr = (ctypes.c_uint * 8)()
        return k.GetConsoleProcessList(arr, 8) <= 1
    except Exception:
        return False


def hide_console():
    """打包成 exe、又走窗口模式时，把自带那个黑框藏掉（源码运行不动用户的终端）。"""
    if os.name != 'nt' or not getattr(sys, 'frozen', False) or not own_console():
        return
    try:
        import ctypes
        h = ctypes.windll.kernel32.GetConsoleWindow()
        if h:
            ctypes.windll.user32.ShowWindow(h, 0)      # SW_HIDE
    except Exception:
        pass


def run_gui(args):
    hide_console()
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from PIL import ImageTk

    palettes, order, extra = load_palettes(args.game)
    names = [n for n in order if n in palettes] + [n for n in extra if n not in order]

    try:                                   # 拖拽靠 tkinterdnd2；没装就退化成只能点按钮
        from tkinterdnd2 import TkinterDnD, DND_FILES
        root = TkinterDnD.Tk()
        dnd = True
    except Exception:
        root = tk.Tk()
        DND_FILES = None
        dnd = False
    root.title('Palette Swap — Driller 游戏配色   [%s]%s'
               % (PALETTE_SOURCE, '' if dnd else '  [no-dnd]'))
    root.geometry('980x600')

    st = {'path': None, 'frames': [], 'durs': [], 'loop': 0, 'anim': False,
          'out': [], 'sheet': {}, 'photo': None, 'i': 0, 'job': None, 'tick': None,
          'zoom': 1.0, 'ox': None, 'oy': None, 'pan': None}   # ox/oy = None 表示自动居中

    # ---------------- 顶部：选图 ----------------
    top = ttk.Frame(root, padding=8)
    top.pack(side='top', fill='x')
    ttk.Button(top, text='选择图片…', command=lambda: pick()).pack(side='left')
    file_lbl = ttk.Label(top, text='把图片拖进窗口就行' if dnd else '（点左边的按钮选图）')
    file_lbl.pack(side='left', padx=8)

    # ---------------- 参数 ----------------
    mid = ttk.Frame(root, padding=(8, 0))
    mid.pack(side='top', fill='x')
    ttk.Label(mid, text='调色板').pack(side='left')
    pal_var = tk.StringVar(value=names[0] if names else '')
    pal_box = ttk.Combobox(mid, textvariable=pal_var, state='readonly', width=16,
                           values=['%s  (%d色)' % (n, palettes[n].n) for n in names])
    pal_box.current(0)
    pal_box.pack(side='left', padx=(4, 12))
    pal_box.bind('<<ComboboxSelected>>', lambda e: render())

    dith_var = tk.DoubleVar(value=args.dither)
    int_var = tk.DoubleVar(value=args.intensity)
    dith_lbl = ttk.Label(mid, text='', width=12)
    int_lbl = ttk.Label(mid, text='', width=12)

    def show_labels():
        dith_lbl.config(text='%d%%' % round(dith_var.get()))
        int_lbl.config(text='%d%%' % round(int_var.get()))

    ttk.Label(mid, text='DitherIntensity').pack(side='left')
    tk.Scale(mid, from_=0, to=100, orient='horizontal', variable=dith_var, length=140,
             command=lambda _=None: (show_labels(), debounce())).pack(side='left')
    dith_lbl.pack(side='left')
    ttk.Label(mid, text='Intensity').pack(side='left', padx=(8, 0))
    tk.Scale(mid, from_=0, to=100, orient='horizontal', variable=int_var, length=140,
             command=lambda _=None: (show_labels(), debounce())).pack(side='left')
    int_lbl.pack(side='left')

    def current_pal():
        i = pal_box.current()
        return palettes[names[i if i >= 0 else 0]]

    def apply_preset(d, i):
        dith_var.set(d)
        int_var.set(i)
        show_labels()
        render()

    for label, d, i in PRESETS:
        ttk.Button(mid, text=label, width=9,
                   command=lambda d=d, i=i: apply_preset(d, i)).pack(side='left', padx=2)

    # ---------------- 画面 ----------------
    canvas = tk.Canvas(root, bg='#222', highlightthickness=0)
    canvas.pack(side='top', fill='both', expand=True, padx=8, pady=8)
    status = ttk.Label(root, text='', anchor='w')
    status.pack(side='bottom', fill='x', padx=8, pady=(0, 4))

    def open_path(p):
        try:
            frames, durs, loop, anim = load_frames(p)
        except Exception as e:
            messagebox.showerror('打不开这张图', '%s\n%s' % (p, e))
            return
        st.update(path=p, frames=frames, durs=durs, loop=loop, anim=anim,
                  out=[], sheet={}, i=0, zoom=1.0, ox=None, oy=None)
        file_lbl.config(text='%s   %dx%d%s' % (os.path.basename(p), frames[0].width, frames[0].height,
                                              '   动图 %d 帧' % len(frames) if anim else ''))
        stop_tick()
        render()

    def pick():
        p = filedialog.askopenfilename(
            title='选一张图（也可以是 gif）',
            filetypes=[('图片', '*.png *.jpg *.jpeg *.bmp *.gif *.tga *.webp *.tif *.tiff'),
                       ('所有文件', '*.*')])
        if p:
            open_path(p)

    # ---------------- 转换 + 显示 ----------------
    def render():
        st['job'] = None
        stop_tick()
        st['sheet'] = {}
        if not st['frames']:
            return
        pal = current_pal()
        try:
            st['out'] = convert_frames(st['frames'], pal, dith_var.get(), int_var.get(),
                                       y_from_bottom=not args.y_top,
                                       keep_alpha0=not args.alpha_too)
        except Exception as e:
            status.config(text='出错：%s' % e)
            return
        st['i'] = 0
        draw()
        start_tick()

    # ---------------- 缩放 / 平移 ----------------
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.1, 40.0, 1.25

    def fit_scale():
        """1.0 倍 = 适应窗口。"""
        cw = max(canvas.winfo_width() - 24, 60)
        ch = max(canvas.winfo_height() - 54, 60)
        W, H = st['out'][0].size
        return min(cw / (W * 2 + 12), ch / H, 1.0)

    def sheet_dims(zoom=None):
        """返回当前（或指定）缩放下的 (单格宽, 高, 整张预览宽, 高)。"""
        sc = max(0.005, fit_scale() * (st['zoom'] if zoom is None else zoom))
        W, H = st['out'][0].size
        w, h = max(1, int(round(W * sc))), max(1, int(round(H * sc)))
        return w, h, w * 2 + 12, h

    def reset_view(_=None):
        st['zoom'], st['ox'], st['oy'] = 1.0, None, None
        st['sheet'] = {}
        draw()

    def set_zoom(target):
        """target = 相对原图像素的缩放（1.0 = 1:1 看像素）。"""
        if not st['out']:
            return
        st['zoom'] = min(ZOOM_MAX, max(ZOOM_MIN, target / max(1e-6, fit_scale())))
        st['ox'] = st['oy'] = None
        st['sheet'] = {}
        draw()

    def on_wheel(e):
        if not st['out']:
            return
        num = getattr(e, 'num', 0)
        up = (num == 4) or (num != 5 and getattr(e, 'delta', 0) > 0)
        z = st['zoom'] * (ZOOM_STEP if up else 1.0 / ZOOM_STEP)
        z = min(ZOOM_MAX, max(ZOOM_MIN, z))
        if abs(z - st['zoom']) < 1e-9:
            return
        ow, oh, osw, osh = sheet_dims()                 # 老尺寸
        st['zoom'] = z
        nw, nh, nsw, nsh = sheet_dims()                 # 新尺寸
        if st['ox'] is None:                            # 还没摆过就先摆一次，好算锚点
            draw()
        cx = e.x_root - canvas.winfo_rootx()
        cy = e.y_root - canvas.winfo_rooty()
        st['ox'] = int(round(cx - (cx - st['ox']) * nsw / osw))   # 光标指的那点不动
        st['oy'] = int(round(cy - (cy - st['oy']) * nsh / osh))
        draw()
        return 'break'                                  # 别让滚轮再传给别的控件

    def on_press(e):
        if not st['out']:
            return
        if st['ox'] is None:
            draw()
        st['pan'] = (e.x - st['ox'], e.y - st['oy'])
        canvas.config(cursor='fleur')

    def on_drag(e):
        if st['pan'] is None or st['ox'] is None:
            return
        nx, ny = e.x - st['pan'][0], e.y - st['pan'][1]
        canvas.move('all', nx - st['ox'], ny - st['oy'])
        st['ox'], st['oy'] = nx, ny

    def on_release(_=None):
        st['pan'] = None
        canvas.config(cursor='')

    def draw():
        if not st['out']:
            return
        i = st['i'] % len(st['out'])
        src, res = st['frames'][i], st['out'][i]
        w, h, shw, shh = sheet_dims()
        key = (i, w, h)
        if key not in st['sheet']:
            # 缓存只留当前缩放档：滚轮每走一格都会产生新尺寸，不丢旧的会吃光内存
            if st['sheet'] and (next(iter(st['sheet']))[1] != w or len(st['sheet']) > 24):
                st['sheet'].clear()
            before = src.resize((w, h), Image.NEAREST)
            after = res.resize((w, h), Image.NEAREST)
            sheet = Image.new('RGBA', (shw, h), (40, 40, 40, 255))
            sheet.paste(before, (0, 0))
            sheet.paste(after, (w + 12, 0))
            st['sheet'][key] = ImageTk.PhotoImage(sheet)
        if st['ox'] is None:                            # 适应窗口时居中
            st['ox'] = (canvas.winfo_width() - shw) // 2
            st['oy'] = max(6, (canvas.winfo_height() - shh - 30) // 2)
        ox, oy = st['ox'], st['oy']
        canvas.delete('all')
        canvas.create_image(ox, oy, image=st['sheet'][key], anchor='nw')
        canvas.create_text(ox + w / 2, oy + h + 16, text='原图', fill='#bbb')
        canvas.create_text(ox + w + 12 + w / 2, oy + h + 16, text=current_pal().name, fill='#bbb')
        pal = current_pal()
        status.config(text='%s   输出 %dx%d   用色 %d%s   缩放 %d%%%s   （滚轮缩放 / 拖动平移 / 双击复位）'
                      % (pal, res.width, res.height, pal.n,
                         '（含黑槽）' if pal.padded else '',
                         round(fit_scale() * st['zoom'] * 100),
                         '   第 %d/%d 帧' % (i + 1, len(st['out'])) if len(st['out']) > 1 else ''))

    def start_tick():
        if st['anim'] and len(st['out']) > 1:
            st['tick'] = root.after(max(20, st['durs'][st['i']]), step)

    def step():
        st['i'] = (st['i'] + 1) % len(st['out'])
        draw()
        st['tick'] = root.after(max(20, st['durs'][st['i']]), step)

    def stop_tick():
        if st['tick']:
            root.after_cancel(st['tick'])
            st['tick'] = None

    def debounce(_=None):
        if st['job']:
            root.after_cancel(st['job'])
        st['job'] = root.after(150, render)

    def on_resize(_=None):
        st['sheet'] = {}
        if abs(st['zoom'] - 1.0) < 1e-9:      # 适应窗口时窗口一变就重新居中
            st['ox'] = st['oy'] = None
        debounce()

    # ---------------- 保存 ----------------
    def ask_out(ext):
        default = out_name(st['path'], current_pal().name, ext=ext)
        return filedialog.asksaveasfilename(title='另存为', defaultextension='.' + ext,
                                            initialfile=os.path.basename(default),
                                            initialdir=os.path.dirname(default),
                                            filetypes=[(ext.upper(), '*.' + ext)])

    def save():
        if not st['out']:
            messagebox.showinfo('还没结果', '先选一张图')
            return
        p = ask_out('gif' if st['anim'] else 'png')
        if not p:
            return
        if st['anim'] and p.lower().endswith('.gif'):
            save_gif(st['out'], p, st['durs'], st['loop'])
        else:
            st['out'][st['i'] % len(st['out'])].save(p)
        status.config(text='已保存 %s' % p)

    def save_seq():
        if not st['out']:
            return
        p = ask_out('png')
        if not p:
            return
        paths = save_png_sequence(st['out'], p)
        status.config(text='已导出 %d 张：%s …' % (len(paths), os.path.basename(paths[0])))

    def batch():
        indir = filedialog.askdirectory(title='选要转换的文件夹')
        if not indir:
            return
        outdir = filedialog.askdirectory(title='输出到哪个文件夹')
        if not outdir:
            return
        pal = current_pal()
        files = [f for f in sorted(os.listdir(indir)) if f.lower().endswith(IMG_EXT)]
        n = 0
        for f in files:
            try:
                convert_file(os.path.join(indir, f), pal, args, outdir=outdir, quiet=True)
                n += 1
            except Exception:
                pass
        status.config(text='批量完成：%d/%d → %s' % (n, len(files), outdir))

    bottom = ttk.Frame(root, padding=(8, 0, 8, 8))
    bottom.pack(side='bottom', fill='x')
    ttk.Button(bottom, text='另存为…', command=save).pack(side='right')
    ttk.Button(bottom, text='拆成 PNG 序列…', command=save_seq).pack(side='right', padx=8)
    ttk.Button(bottom, text='批量转换文件夹…', command=batch).pack(side='right', padx=(0, 8))
    ttk.Button(bottom, text='适应窗口', command=reset_view).pack(side='left')
    ttk.Button(bottom, text='1:1', command=lambda: set_zoom(1.0)).pack(side='left', padx=6)

    # ---------------- 拖拽进来 ----------------
    if dnd:
        def on_drop(event):
            paths = [p for p in root.tk.splitlist(event.data)
                     if os.path.isfile(p) and p.lower().endswith(IMG_EXT)]
            if paths:
                open_path(paths[0])
            elif root.tk.splitlist(event.data):
                status.config(text='这看着不是图片文件，拖 .png / .jpg / .gif 进来')

        for w in (root, canvas):
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind('<<Drop>>', on_drop)
            except Exception:
                pass

    show_labels()
    canvas.bind('<Configure>', on_resize)
    canvas.bind('<MouseWheel>', on_wheel)          # Windows / macOS
    canvas.bind('<Button-4>', on_wheel)            # X11 滚轮
    canvas.bind('<Button-5>', on_wheel)
    root.bind('<MouseWheel>', on_wheel)            # 鼠标在滑块上时也能缩（canvas 的会先 break 掉）
    canvas.bind('<ButtonPress-1>', on_press)
    canvas.bind('<B1-Motion>', on_drag)
    canvas.bind('<ButtonRelease-1>', on_release)
    canvas.bind('<Double-Button-1>', reset_view)
    if args.input and os.path.isfile(args.input):
        open_path(args.input)
    else:
        root.after(60, lambda: status.config(text='拖图片进来，或点「选择图片…」'))
    root.mainloop()
    return 0


def main(argv=None):
    return main_cli(argv if argv is not None else sys.argv[1:])


if __name__ == '__main__':
    sys.exit(main())

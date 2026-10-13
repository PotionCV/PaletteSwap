# Palette Swap

把任意图片一键转成 **Driller** 游戏内调色板的样子（也就是游戏里那个换配色过渡的效果）。

游戏里用的是 Construct 3 效果 `federicoCalchera_paletteSwap16`（工程里叫 PaletteSwap16）。
这个工具逐像素照抄了它的 shader，所以**转出来的图和游戏里显示的一模一样**——
自己做的素材、截图、宣传图，都能先在游戏外对好色，不用反复进游戏里看效果。

```
c = front + (dither_matrix(x, y) * ditherIntensity) / 255    # 加网点
c = clamp(c, 0, 1)
c = 调色板里最近的颜色                                       # 欧氏距离，距离相同取靠前的
out = mix(front, c, intensity)                               # 按强度混合
```

---

## 装什么

```bash
pip install numpy pillow
```

想用拖拽功能再多装一个（没装也能用，只是不能拖，只能点按钮选图）：

```bash
pip install tkinterdnd2
```

Python 3.8+ 即可（自带的 tkinter 用来开窗口）。

## 怎么用

### 窗口（推荐）

双击 `palette_gui.bat`，或者：

```bash
python palette_swap.py
```

- 把 png / jpg / gif **拖进窗口**（也可以把图片拖到 `palette_gui.bat` 图标上直接打开）
- 左边选配色，两个滑块调 `DitherIntensity` 和 `Intensity`，右边并排看原图和结果
- **滚轮**缩放（以光标为锚点）、**按住左键拖动**平移、**双击**或「适应窗口」复位、「1:1」看原像素
- 动图（gif）逐帧转换，帧数 / 每帧时长 / 循环次数 / 透明全部保留，窗口里按原速播放
- 「另存为…」存图，「拆成 PNG 序列…」把动图导成一堆 png，「批量转换文件夹…」整目录一起转

### 命令行

```bash
python palette_swap.py --list                      # 看有哪些配色
python palette_swap.py in.png out.png -p NYX8      # 转一张（-p 是配色名）
python palette_swap.py in.png -p EN4 -d 50 -i 75   # 调参数，不写输出名就存 in_EN4.png
python palette_swap.py --batch in_dir out_dir -p Paper8
python palette_swap.py in.gif -p GBA               # 动图进、动图出
python palette_swap.py in.gif -p GBA --gif-png     # 动图导成 PNG 序列
```

| 参数 | 说明 |
|---|---|
| `-p, --palette` | 配色名，默认 `NYX8` |
| `-d, --dither` | DitherIntensity，0–100，默认 **75** |
| `-i, --intensity` | Intensity，0–100，默认 **75** |
| `-g, --game` | 工程根目录（含 `files/Configs/`），用来读游戏的调色板 |
| `-l, --list` | 列出所有配色 |
| `--batch 入 出` | 整个目录一起转 |
| `--gif-png` | 动图导出成 PNG 序列 |
| `--stats` | 转完打印用了哪些颜色 |
| `--y-top` | 网点网格从图片第一行开始（默认按 GL 从下往上） |
| `--alpha-too` | 连全透明像素的 RGB 也一起改（默认保留） |
| `--gui` | 打开窗口 |

### 两档常用参数

| | DitherIntensity | Intensity | 结果 |
|---|---|---|---|
| 游戏过渡 | 75 | 75 | 默认值，游戏里换配色时的过渡态 |
| 纯净转换 | 0 | 100 | 每个像素都是调色板里的颜色，游戏里的静止态 |
| 布局默认 | 50 | 75 | 游戏标题界面存的初始值 |

> `Intensity < 100` 时输出里会有**不在调色板里**的混合色，这是对的——游戏里也这样。

## 配色是从哪来的

优先**直接从游戏工程读**：`files/Configs/Color.json` 的键（`<配色名><序号>`）加
`Common.json` 的 `PaletteList`，顺序和游戏设置界面一致。所以游戏里改了配色，这里自动跟着变。
查找顺序：`--game` 指定的目录 → `palette_swap.py` / exe 所在目录 → 当前目录 → 它们的下一级子目录。

找不到工程时用自带的 `palettes_snapshot.json`（从工程抄下来的配色表，颜色与读工程完全一致）。
游戏内共有 7 套配色：

| 配色 | 色数 | | 配色 | 色数 |
|---|---|---|---|---|
| NYX8 | 8 | | RusticGB | 4 |
| EN4 | 4 | | Ammo8 | 8 |
| ErogeCopper | 16 | | GBA | 4 |
| Paper8 | 8 | | | |

想更新快照（比如游戏里加了新配色），在工程目录旁边跑：

```bash
python make_snapshot.py
```

## 打包成 exe

```bash
pip install pyinstaller
python build_exe.py
```

生成 `dist/PaletteSwap.exe`，**单文件，目标机器不用装 Python**。
双击 = 开窗口；把图片拖到 exe 图标上 = 用这张图开窗口；在终端里带参数跑 = 命令行
（命令行转换**要写出输出路径**，不然它会以为你想开窗口）。

## 已知事项

- 图片的网点是按**屏幕像素**对齐的（shader 里用 `gl_FragCoord`，y 朝上），所以转静态图时
  是从最后一行往上数的。想要反过来用 `--y-top`。
- 少于 16 色的配色，空槽在游戏里就是**纯黑**（游戏初始化时把 16 个槽全设 0 再覆盖），
  暗部像素会被压成黑。工具照做。
- 最近色搜索用的是 float64：4 色配色下两个候选色的距离可能只差最后几位，
  float32 会挑错颜色。

## 致谢

效果本体 `paletteSwap16` 来自 Construct 3 社区的 **federicoCalchera**。
这个工具只是把它的 shader 用一个 Python 脚本重新实现了一遍，方便在游戏外使用。

## 许可

MIT，见 [LICENSE](LICENSE)。

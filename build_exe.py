# -*- coding: utf-8 -*-
"""打成单文件 exe。PyInstaller 装在 E:（别往 C: 塞）：
    pip install pyinstaller --prefix "E:/Program Files/pyinstaller" --cache-dir E:/Works/_agent_tmp/pipcache
"""
import io, os, shutil, subprocess, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)

HERE = 'E:/Works/_agent_tmp/palette'
PREFIX = 'E:/Program Files/pyinstaller'
SP = os.path.join(PREFIX, 'Lib', 'site-packages')

env = dict(os.environ)
env['PYTHONPATH'] = SP + os.pathsep + env.get('PYTHONPATH', '')
env['PYTHONIOENCODING'] = 'utf-8'

cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
       '--onefile',                       # 单文件
       '--console',                       # 命令行版照常能打印；走窗口时自己把黑框藏掉
       '--name', 'PaletteSwap',
       '--collect-all', 'tkinterdnd2',    # tkdnd 的 dll 得一起带上（拖拽靠它）
       '--add-data', os.path.join(HERE, 'palettes_snapshot.json') + ';.',   # 相对路径是按 spec 目录算的，得给绝对路径
       '--distpath', os.path.join(HERE, 'dist'),
       '--workpath', os.path.join(HERE, 'build'),
       '--specpath', os.path.join(HERE, 'build'),
       'palette_swap.py']
print('$', ' '.join(cmd[:6]), '…')
r = subprocess.run(cmd, cwd=HERE, env=env)
if r.returncode:
    raise SystemExit('打包失败 %d' % r.returncode)

exe = os.path.join(HERE, 'dist', 'PaletteSwap.exe')
print('出来啦：%s  %.1f MB' % (exe, os.path.getsize(exe) / 1048576.0))

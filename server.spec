# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
a = Analysis(['server_main.py'], pathex=[], binaries=[], datas=[('server/web', 'server/web')],
             hiddenimports=['waitress', *collect_submodules('zeroconf')], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='APK Build Server', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=True, console=True,
          disable_windowed_traceback=False)

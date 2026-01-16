# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for NAI Tag Classifier Server
Usage: pyinstaller build.spec
"""

import sys
from pathlib import Path

block_cipher = None

# 프로젝트 루트
ROOT = Path(SPECPATH)

# 데이터 파일들
datas = [
    # viewer-ui 빌드 결과
    (str(ROOT / 'viewer-ui' / 'dist'), 'viewer-ui/dist'),
    # DB 스키마
    (str(ROOT / 'db' / 'schema.sql'), 'db'),
    # 캐시 폴더 (빈 폴더 생성용)
]

# 숨겨진 임포트
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'PIL',
    'PIL.Image',
    'PIL.ExifTags',
    'numpy',
]

a = Analysis(
    [str(ROOT / 'server' / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nai-classifier-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 콘솔 창 표시 (서버 로그용)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일 경로 (옵션)
)

# -*- coding: utf-8 -*-
import shutil, glob, os

src_dir = r'D:\AI-agent-world'
dst_dir = r'c:\Users\萌\CodeBuddy\20260827132531'
for f in glob.glob(os.path.join(src_dir, '*剧情*')):
    dst = os.path.join(dst_dir, os.path.basename(f))
    shutil.copy(f, dst)
    print('copied', os.path.basename(f), '->', dst)

# 把发布目录压缩为 微应用大厅.zip（UTF-8 文件名，排除缓存/日志）。
import os, zipfile

SRC = "E:/project/app_dist/微应用大厅"
OUT = "E:/project/app_dist/微应用大厅.zip"
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".git"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = {".log"}

if os.path.exists(OUT):
    os.remove(OUT)

n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f in EXCLUDE_FILES or any(f.endswith(s) for s in EXCLUDE_SUFFIX):
                continue
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                arc = os.path.relpath(fp, os.path.dirname(SRC)).replace("\\", "/")
                z.write(fp, arc)
                n += 1
print("ZIPPED_FILES", n)
print("OUT", OUT, "SIZE_MB", round(os.path.getsize(OUT)/1024/1024, 2))

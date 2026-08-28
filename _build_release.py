# 构建发布目录：复制 E:/project/app 到 E:/project/app_dist/微应用大厅/，排除内部/开发文件。
import os, shutil, stat

SRC = "E:/project/app"
DST = "E:/project/app_dist/微应用大厅"

# 需排除的目录名（任意层级）
EXCLUDE_DIRS = {".workbuddy", "__pycache__", ".pytest_cache", ".git", "node_modules", "Artifacts"}
# 需排除的文件（按名，任意层）
EXCLUDE_FILES = {
    "backend.log", "_bake6.py", "_enrich_inv.py", "verify_all.py", "xss_patch.py",
    "test_app.py", "少年开发者prompt卡片.md", "README.md",
}
# 额外按路径排除（更精确）
EXCLUDE_PATHS = {
    "backend/test_app.py",
    "backend/backend.log",
    "backend/.gitignore",
}

def rel(p):
    return os.path.relpath(p, SRC).replace("\\", "/")

def allowed(path):
    r = rel(path)
    parts = r.split("/")
    if any(seg in EXCLUDE_DIRS for seg in parts):
        return False
    base = os.path.basename(path)
    if base in EXCLUDE_FILES:
        return False
    if r in EXCLUDE_PATHS:
        return False
    if base.endswith(".log"):
        return False
    return True

if os.path.exists(DST):
    shutil.rmtree(DST)
os.makedirs(DST, exist_ok=True)

copied = 0
for root, dirs, files in os.walk(SRC):
    # 现场剪枝目录
    dirs[:] = [d for d in dirs if allowed(os.path.join(root, d))]
    for f in files:
        sp = os.path.join(root, f)
        if not allowed(sp):
            continue
        dp = os.path.join(DST, rel(sp))
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        shutil.copy2(sp, dp)
        copied += 1

print("COPIED_FILES", copied)
print("DST", DST)

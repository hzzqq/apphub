#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""桌面壳层静态校验（不需要 Rust 工具链即可跑）。

在没有 cargo/rustc 的机器上，`tauri build` 无法执行，但绝大多数「一编译就失败」的
问题其实是配置问题——JSON 写错、图标缺失、beforeDevCommand 指向的脚本不存在。
本脚本把这些提前拦下来。

用法：
    python desktop/scripts/verify.py

退出码：0 = 全部通过；1 = 存在阻断问题。
"""

import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.abspath(os.path.join(HERE, ".."))
SRC_TAURI = os.path.join(DESKTOP, "src-tauri")

fails = []
warns = []


def fail(msg):
    fails.append(msg)
    print("  [FAIL] " + msg)


def warn(msg):
    warns.append(msg)
    print("  [warn] " + msg)


def ok(msg):
    print("  [ ok ] " + msg)


def check(cond, msg_ok, msg_fail):
    if cond:
        ok(msg_ok)
    else:
        fail(msg_fail)
    return cond


def read(path):
    with open(path, "rb") as f:
        return f.read()


def is_png(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    try:
        w, h = struct.unpack(">II", data[16:24])
        return w > 0 and h > 0
    except Exception:
        return False


def main():
    print("=" * 68)
    print("App Hub 桌面壳层 · 静态校验")
    print("=" * 68)

    # 1. 工程骨架
    print("\n[1] 工程骨架")
    for rel in ("src-tauri/tauri.conf.json", "src-tauri/Cargo.toml",
                "src-tauri/build.rs", "src-tauri/src/main.rs", "package.json"):
        p = os.path.join(DESKTOP, rel)
        check(os.path.isfile(p), "%s 存在" % rel, "%s 缺失" % rel)

    # 2. tauri.conf.json
    print("\n[2] tauri.conf.json")
    cfg_path = os.path.join(SRC_TAURI, "tauri.conf.json")
    cfg = None
    if os.path.isfile(cfg_path):
        try:
            cfg = json.loads(read(cfg_path).decode("utf-8"))
            ok("JSON 可解析")
        except Exception as e:
            fail("JSON 解析失败：%s" % e)
    if cfg:
        for key in ("productName", "identifier", "version"):
            check(bool(cfg.get(key)), "%s 已设置" % key, "%s 缺失" % key)
        build = cfg.get("build") or {}
        check(bool(build.get("devUrl")), "build.devUrl = %s" % build.get("devUrl"),
              "build.devUrl 缺失（dev 不知道加载哪个地址）")
        check(bool(build.get("frontendDist")), "build.frontendDist = %s" % build.get("frontendDist"),
              "build.frontendDist 缺失（build 找不到前端产物）")
        # beforeXxxCommand 指向的文件必须真实存在
        for key in ("beforeDevCommand", "beforeBuildCommand"):
            cmd = (build.get(key) or "").strip()
            if not cmd:
                warn("build.%s 未设置" % key)
                continue
            target = cmd.split()[-1].strip('"')
            p = os.path.join(DESKTOP, target)
            check(os.path.isfile(p), "%s -> %s 存在" % (key, target),
                  "%s -> %s 不存在（Tauri 会直接失败）" % (key, target))
        # frontendDist 目录（build 后应有 index.html）
        # frontendDist 是相对 src-tauri/ 的路径（如 ../dist），必须原样 join 再 abspath，
        # 不能 lstrip("./")——那会把 "../dist" 削成 "dist"，指错目录
        dist_rel = build.get("frontendDist") or ""
        dist = os.path.abspath(os.path.join(SRC_TAURI, dist_rel)) if dist_rel else None
        if dist:
            idx = os.path.join(dist, "index.html")
            if os.path.isfile(idx):
                ok("frontendDist 已就绪：%s" % idx)
            else:
                warn("frontendDist 尚无 index.html，先跑 `npm run frontend` 再 build")

    # 3. 图标
    print("\n[3] 图标资源")
    icons = ((cfg or {}).get("bundle") or {}).get("icon") or []
    if not icons:
        fail("bundle.icon 为空")
    for rel in icons:
        p = os.path.join(SRC_TAURI, rel)
        if not os.path.isfile(p):
            fail("图标缺失：%s" % rel)
            continue
        data = read(p)
        if rel.lower().endswith(".png"):
            check(is_png(data), "%s 是合法 PNG" % rel, "%s 不是合法 PNG" % rel)
        elif rel.lower().endswith(".ico"):
            check(data[:4] == b"\x00\x00\x01\x00",
                  "%s 是合法 ICO（%d 字节）" % (rel, len(data)),
                  "%s ICO 头非法" % rel)
        else:
            ok("%s 存在（%d 字节）" % (rel, len(data)))

    # 4. Cargo.toml
    print("\n[4] Cargo.toml")
    cargo = os.path.join(SRC_TAURI, "Cargo.toml")
    if os.path.isfile(cargo):
        txt = read(cargo).decode("utf-8", "ignore")
        check('name = "apphub-desktop"' in txt, "package.name 正确", "package.name 不是 apphub-desktop")
        check("tauri-build" in txt and "[build-dependencies]" in txt,
              "含 tauri-build 构建依赖", "缺少 tauri-build 构建依赖")
        check("tauri = " in txt, "含 tauri 依赖", "缺少 tauri 依赖")

    # 5. package.json
    print("\n[5] package.json")
    pkg_path = os.path.join(DESKTOP, "package.json")
    if os.path.isfile(pkg_path):
        try:
            pkg = json.loads(read(pkg_path).decode("utf-8"))
            ok("JSON 可解析")
            dev = (pkg.get("devDependencies") or {})
            check("@tauri-apps/cli" in dev, "devDependencies 含 @tauri-apps/cli",
                  "devDependencies 缺少 @tauri-apps/cli（无法执行 tauri 命令）")
            scripts = pkg.get("scripts") or {}
            for s in ("dev", "build"):
                check(s in scripts, "scripts.%s 存在" % s, "scripts.%s 缺失" % s)
        except Exception as e:
            fail("JSON 解析失败：%s" % e)

    # 6. 工具链探测（只报告，不算失败——本机可能没装 Rust）
    print("\n[6] 工具链探测")
    for tool in ("cargo", "rustc", "node", "npm"):
        path = shutil.which(tool)
        if path:
            ok("%s -> %s" % (tool, path))
        else:
            warn("%s 未安装" % tool)
    if not (shutil.which("cargo") and shutil.which("rustc")):
        warn("缺少 Rust 工具链：本机只能跑静态校验，真编译请到装了 Rust 的机器执行（见 README）")

    # 7. 零编译启动器
    print("\n[7] 零编译启动器（无需任何工具链）")
    for rel in ("launch.py", "launcher.bat", "launcher.sh"):
        p = os.path.join(DESKTOP, rel)
        check(os.path.isfile(p), "%s 存在" % rel, "%s 缺失" % rel)

    print("\n" + "=" * 68)
    print("阻断问题 %d 个，警告 %d 个" % (len(fails), len(warns)))
    print("=" * 68)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

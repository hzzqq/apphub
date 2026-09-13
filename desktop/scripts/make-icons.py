#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 desktop/src-tauri/icons 下的占位图标（无需任何第三方库，纯标准库）。

生成的图标：32x32.png / 128x128.png / icon.ico（ICO 内嵌 PNG，Windows 打包需要）。
配色沿用 App Hub 主题渐变 #667eea → #764ba2，中心为浅色圆点。

用法：
    python desktop/scripts/make-icons.py

想要正式的精美图标时，用 Tauri 官方命令一键生成全套（含 icon.icns）：
    npx tauri icon path/to/your-1024.png
"""

import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src-tauri", "icons")

# 主题渐变色（与 App Hub UI 一致）
C1 = (0x66, 0x7E, 0xEA)  # #667eea
C2 = (0x76, 0x4B, 0xA2)  # #764ba2
DOT = (0xF0, 0xF0, 0xFA)  # 中心浅色


def _mix(t):
    return tuple(int(C1[i] + (C2[i] - C1[i]) * t) for i in range(3))


def _pixel(x, y, size):
    t = (x + y) / (2.0 * max(size - 1, 1))
    r, g, b = _mix(t)
    cx = cy = (size - 1) / 2.0
    d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / max(size / 2.0, 1.0)
    if d < 0.40:
        return DOT + (255,)
    # 圆角：角落外的像素透明
    rad = size * 0.18
    mx, my = min(x, size - 1 - x), min(y, size - 1 - y)
    if mx < rad and my < rad:
        dx, dy = rad - mx, rad - my
        if dx * dx + dy * dy > rad * rad:
            return (0, 0, 0, 0)
    return (r, g, b, 255)


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def make_png(size):
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0
        for x in range(size):
            raw.extend(_pixel(x, y, size))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def make_ico(png, size):
    """ICO 容器直接内嵌 PNG 数据（Windows 支持）。"""
    header = struct.pack("<HHH", 0, 1, 1)  # reserved=0, type=1(icon), count=1
    entry = struct.pack("<BBBBHHII",
                        size if size < 256 else 0,   # width
                        size if size < 256 else 0,   # height
                        0,                            # color count
                        0,                            # reserved
                        1,                            # planes
                        32,                           # bit count
                        len(png),                     # bytes in res
                        6 + 16)                       # image offset
    return header + entry + png


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for size in (32, 128):
        p = os.path.join(OUT_DIR, "%dx%d.png" % (size, size))
        with open(p, "wb") as f:
            f.write(make_png(size))
        print("wrote", os.path.abspath(p))
    ico = os.path.join(OUT_DIR, "icon.ico")
    with open(ico, "wb") as f:
        f.write(make_ico(make_png(128), 128))
    print("wrote", os.path.abspath(ico))


if __name__ == "__main__":
    main()

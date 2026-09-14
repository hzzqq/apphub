# -*- coding: utf-8 -*-
"""R88-10: 生态化端点回归测试（/api/gen_app、/api/submit_app、/api/export_app）。

背景: R84~R88 新增了「AI 生成 / 社区提交 / 应用导出」三条生态化端点，但门禁此前
只做了 GET 冒烟，未覆盖这三条端点的安全/边界行为——它们的回归无任何自动化守卫。

本测试用 Flask test_client 直接跑，并把模块级 APP_ROOT 重定向到临时目录，
因此生成/提交的产物都落在 temp，**绝不污染仓库**（配合 R88-6 的 .gitignore 双保险）。

用法（须用装 Flask 的解释器）:
    python backend/test_ecosystem_endpoints.py
退出码: 0=全部通过, 1=存在失败。
"""
import io
import os
import shutil
import sys
import tempfile

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)


def main():
    import app as backend  # noqa: E402

    fails = []
    tmp = tempfile.mkdtemp(prefix="apphub_eco_")
    orig_root = backend.APP_ROOT
    backend.APP_ROOT = tmp          # 产物落临时目录，不污染仓库
    try:
        c = backend.app.test_client()

        # 1) gen_app 恶意输入 → 200（规则兜底已 HTML 转义），产物不得含可执行裸标签
        r = c.post("/api/gen_app", json={
            "name": "<img src=x onerror=alert(1)>",
            "desc": "<script>evil()</script>",
            "features": ["<iframe src=http://evil>"],
            "cat": "tool",
        })
        if r.status_code != 200:
            fails.append("gen_app 恶意输入应 200(转义安全)，实得 %d" % r.status_code)
        else:
            j = r.get_json(silent=True) or {}
            fp = os.path.join(tmp, *j.get("dir", "").split("/"), "index.html")
            body = open(fp, encoding="utf-8").read() if os.path.isfile(fp) else ""
            if "<img src=x onerror" not in body.replace("&lt;", "<").replace("&gt;", ">"):
                pass  # 正文里出现转义形态是正常的，下面用裸标签判定
            if "<img src=x onerror" in body:
                fails.append("gen 产物含未转义 <img onerror>（存储型 XSS）")
            if "<script>evil" in body:
                fails.append("gen 产物含未转义 <script>evil")
            if "<iframe" in body.lower():
                fails.append("gen 产物含 <iframe>（违反零依赖）")
            if "&lt;img" not in body:
                fails.append("gen 产物未对 <img> 做 HTML 转义（期望出现 &lt;img）")

        # 2) gen_app 缺 name → 400
        if c.post("/api/gen_app", json={"desc": "x"}).status_code != 400:
            fails.append("gen_app 缺 name 应 400")

        # 3) gen_app 合法 → 200 且产物可经 GET 托管访问
        r = c.post("/api/gen_app", json={"name": "eco_smoke_app", "desc": "eco",
                                        "features": ["a"], "cat": "tool"})
        jj = r.get_json(silent=True) or {}
        if r.status_code != 200:
            fails.append("gen_app 合法输入应 200，实得 %d" % r.status_code)
        elif c.get(jj.get("path", "/nope")).status_code != 200:
            fails.append("gen 产物应可经 %s 访问" % jj.get("path"))

        # 4) submit_app 外部 <script src> → 400（零依赖门禁）
        bad = io.BytesIO(b'<html><body><script src="http://evil/x.js"></script>'
                         + b"x" * 300 + b"</body></html>")
        if c.post("/api/submit_app", data={"app": (bad, "bad.html")}).status_code != 400:
            fails.append("submit_app 外部 script src 应 400")

        # 5) submit_app <iframe> → 400（R88-8 新增门禁）
        bad2 = io.BytesIO(b'<html><body><iframe src="http://evil"></iframe>'
                          + b"x" * 300 + b"</body></html>")
        if c.post("/api/submit_app", data={"app": (bad2, "bad2.html")}).status_code != 400:
            fails.append("submit_app <iframe> 应 400（R88-8 门禁）")

        # 6) submit_app 合法零依赖单文件 → 200 且可访问
        good = io.BytesIO(b"<html><body><h1>ok</h1><script>var a=1;</script>"
                          + b"x" * 300 + b"</body></html>")
        r = c.post("/api/submit_app", data={"app": (good, "good_app.html")})
        gj = r.get_json(silent=True) or {}
        if r.status_code != 200:
            fails.append("submit_app 合法输入应 200，实得 %d" % r.status_code)
        elif c.get(gj.get("path", "/nope")).status_code != 200:
            fails.append("submit 产物应可访问")

        # 7) export_app 目录穿越 → 400；不存在 → 404
        if c.get("/api/export_app?p=../etc").status_code != 400:
            fails.append("export 目录穿越应 400")
        if c.get("/api/export_app?p=__no_such_app__").status_code != 404:
            fails.append("export 不存在应用应 404")

        # 8) export_app 合法应用 → 200 且带附件下载头
        r = c.post("/api/gen_app", json={"name": "eco_export_app", "desc": "e",
                                        "features": ["a"], "cat": "tool"})
        ej = r.get_json(silent=True) or {}
        er = c.get("/api/export_app?p=" + ej.get("dir", ""))
        if er.status_code != 200:
            fails.append("export 合法应用应 200，实得 %d" % er.status_code)
        elif "attachment" not in (er.headers.get("Content-Disposition") or "").lower():
            fails.append("export 应带 Content-Disposition: attachment")
    finally:
        backend.APP_ROOT = orig_root
        # 用 rename 把临时产物移出原位（本环境删除保护会硬拦 rmtree），失败再退回复核删除
        try:
            import time as _t
            os.replace(tmp, tmp + "_done_%d" % int(_t.time() * 1000))
        except Exception:
            try:
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass

    if fails:
        print("[生态端点回归] 失败 %d 项:" % len(fails))
        for m in fails:
            print("  ✗ " + m)
        return 1
    print("[生态端点回归] 全部通过（gen/submit/export 共 8 组断言，APP_ROOT 重定向到临时目录）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

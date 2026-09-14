# -*- coding: utf-8 -*-
"""回归测试 (R88 第5轮): refresh_one 绝不能用「抓取失败 / 抓取为空 / 日期不重叠」
整体清空真实缓存的库存列。模拟 akshare 返回异常数据, 断言缓存文件不被破坏。

用法: python backend/test_refresh_guard.py   (退出码 0=通过, 1=失败)
依赖: pandas (仅用于构造假 DataFrame, 缺失时降级为最小桩)
"""
import os
import sys
import json
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _bake_inv_em as B


def _real_nonnull(path):
    rows = json.load(open(path, encoding="utf-8"))
    return sum(1 for x in rows if x.get("inventory_total") is not None)


def main():
    src = os.path.join(HERE, "data", "futures_SHFE_CU.json")
    if not os.path.isfile(src):
        print("[skip] 缺少 data/futures_SHFE_CU.json, 跳过")
        return 0
    real_n = _real_nonnull(src)
    if real_n == 0:
        print("[skip] 源缓存本身无真实库存, 跳过(无法验证保留)")
        return 0

    tmp = tempfile.mkdtemp(prefix="refguard_")
    try:
        # 把真实缓存复制到临时 DATA, 后续 refresh_one 只动临时副本
        shutil.copy(src, os.path.join(tmp, "futures_SHFE_CU.json"))
        B.DATA = tmp

        # 桩: akshare 返回「与本地日线日期完全不重叠」的库存(模拟数据源异常/口径错位)
        try:
            import pandas as pd
            fake_df = pd.DataFrame({"日期": ["1990-01-01", "1990-01-02"], "库存": [111.0, 222.0]})
        except Exception:
            # 无 pandas: 用最小桩对象, 只要 .iterrows() 与列访问可用
            class _Row(dict):
                pass
            class _FakeDF:
                def __init__(self, rows):
                    self._r = rows
                def iterrows(self):
                    for i, r in enumerate(self._r):
                        yield i, r
            fake_df = _FakeDF([_Row({"日期": "1990-01-01", "库存": 111.0}),
                               _Row({"日期": "1990-01-02", "库存": 222.0})])

        orig = B.ak.futures_inventory_em
        B.ak.futures_inventory_em = lambda symbol: fake_df
        try:
            res = B.refresh_one("SHFE", "CU", verbose=False)
        finally:
            B.ak.futures_inventory_em = orig

        after = _real_nonnull(os.path.join(tmp, "futures_SHFE_CU.json"))
        print("  源缓存真实库存行数=%d, 异常抓取后临时副本库存行数=%d" % (real_n, after))
        print("  refresh_one 返回:", res.get("ok"), res.get("msg"))

        # 断言1: 缓存不应被清空(保留真实库存)
        if after != real_n:
            print("  [FAIL] 真实库存被清空: %d -> %d" % (real_n, after))
            return 1
        # 断言2: 抓取为空洞时不应写回(ok 必须为 False, 否则意味着落盘了)
        if res.get("ok") is True:
            print("  [FAIL] 日期不重叠却返回 ok=True(说明仍写回了库存)")
            return 1
        print("  [PASS] 异常抓取未破坏真实缓存, 且未误写回")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

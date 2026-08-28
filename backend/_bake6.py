import fetch_real_futures as F

# 用户 6 大实盘品种: 纸浆SP + 玻璃FG/纯碱SA/白糖SR(郑商所) + 鸡蛋JD/乙二醇EG(大商所)
targets = [("SHFE", "sp"), ("CZCE", "FG"), ("CZCE", "SA"),
           ("CZCE", "SR"), ("DCE", "JD"), ("DCE", "EG")]
for ex, sym in targets:
    try:
        F.fetch_one(ex, sym, 365)
    except Exception as e:
        print("FAIL", ex, sym, repr(e)[:120])
print("ALL_BAKE_DONE")

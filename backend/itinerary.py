# -*- coding: utf-8 -*-
"""
行程规划模块（itinerary）
=======================
源自 E:/project/map 项目的「AI 行程生成器」，作为 App Hub 的一个小功能模块接入，
正式取代原 trip-planner 占位卡（trip-planner 目录已于 2026-09-01 删除）。

能力：
  - 零依赖模板生成：按城市 / 天数 / 风格 / 兴趣词产出可编辑的每日行程骨架。
  - 可选接 map 项目：若配置了 map_backend_url（或环境变量 MAP_BACKEND_URL），
    后端会把请求代理到 map 项目的 /api/generate，拿到真实 POI / 路线行程（需该后端已部署且配 Key）。
  - 纯数据逻辑（encode / decode / diff / summary / 导出）放在前端，零后端依赖即可用。

供 app.py 的 /api/itinerary/generate 调用。
"""
import os
import json
import urllib.request
import urllib.error

# 风格模板：上午 / 下午 / 晚上 三段 + 一个灵活补充段
STYLE_TPL = {
    "classic": {"label": "经典观光", "am": "地标 / 老城区漫步", "pm": "博物馆或美术馆", "ev": "城市夜景 / 江边散步", "ex": "特色街区闲逛"},
    "food":    {"label": "美食探店", "am": "本地早茶 / 早餐街", "pm": "人气餐厅打卡", "ev": "夜市 / 小吃街", "ex": "甜品 / 咖啡探店"},
    "nature":  {"label": "自然户外", "am": "近郊登山 / 公园", "pm": "湖边或湿地", "ev": "露营或观星", "ex": "骑行 / 徒步线"},
    "chill":   {"label": "悠闲度假", "am": "咖啡馆慢生活", "pm": "SPA 或书店", "ev": "酒吧或 livehouse", "ex": "午后发呆"},
    "family":  {"label": "亲子同游", "am": "动物园 / 科技馆", "pm": "儿童乐园 / 手工", "ev": "亲子剧场 / 灯光秀", "ex": "绘本馆 / 沙滩"},
}

# 城市常见玩法提示（与 map 项目同源，便于模板更"像样"）
CITY_HINTS = {
    "深圳": ["莲花山", "海上世界", "华侨城创意园", "深圳湾公园", "甘坑古镇"],
    "上海": ["外滩", "武康路", "迪士尼", "豫园", "思南公馆"],
    "北京": ["故宫", "胡同", "长城", "颐和园", "798"],
    "成都": ["宽窄巷子", "熊猫基地", "锦里", "东郊记忆", "玉林路"],
    "杭州": ["西湖", "灵隐寺", "河坊街", "西溪湿地", "龙井村"],
    "广州": ["沙面", "早茶", "珠江夜游", "陈家祠", "永庆坊"],
    "重庆": ["洪崖洞", "李子坝", "磁器口", "长江索道", "南山"],
    "西安": ["城墙", "回民街", "兵马俑", "大唐不夜城", "大雁塔"],
    "南京": ["夫子庙", "中山陵", "玄武湖", "先锋书店", "老门东"],
    "厦门": ["鼓浪屿", "沙坡尾", "环岛路", "植物园", "曾厝垵"],
    "成都": ["宽窄巷子", "熊猫基地", "锦里"],
    "苏州": ["拙政园", "平江路", "山塘街", "金鸡湖", "虎丘"],
    "武汉": ["黄鹤楼", "东湖", "户部巷", "江汉路", "昙华林"],
    "长沙": ["橘子洲", "超级文和友", "岳麓山", "五一广场", "IFS"],
    "青岛": ["栈桥", "八大关", "小麦岛", "啤酒博物馆", "信号山"],
}


def _build_template(city, days, style, interests):
    """纯模板生成（零依赖）：返回 plan dict。"""
    style = (style or "classic")
    tpl = STYLE_TPL.get(style, STYLE_TPL["classic"])
    hints = CITY_HINTS.get(city, [])
    inter = [x.strip() for x in (interests or "").replace("，", ",").split(",") if x.strip()]
    day_list = []
    for d in range(1, days + 1):
        slots = [
            {"when": "上午", "plan": "%s（%s）" % (hints[(d - 1) % len(hints)] if hints else city + "景点", tpl["am"])},
            {"when": "下午", "plan": "%s（%s）" % (hints[d % len(hints)] if hints else city + "特色体验", tpl["pm"])},
            {"when": "晚上", "plan": tpl["ev"]},
            {"when": "灵活", "plan": tpl["ex"]},
        ]
        # 若有兴趣词，追加到"灵活"段
        if inter:
            slots.append({"when": "兴趣", "plan": "、".join(inter[:3]) + "（按营业时间自行安排）"})
        day_list.append({"day": "第 %d 天 · %s" % (d, city), "slots": slots})
    return {
        "city": city, "days": days, "style": style, "style_label": tpl["label"],
        "interests": inter, "days_list": day_list,
    }


def _adapt_map_plan(plan):
    """尽力把 map 项目返回的 plan 适配成本模块 schema（day_list）。"""
    if not isinstance(plan, dict):
        return None
    days_src = plan.get("days") or plan.get("itinerary") or []
    if not isinstance(days_src, list):
        return None
    out = []
    for i, dd in enumerate(days_src, 1):
        if not isinstance(dd, dict):
            continue
        title = dd.get("title") or dd.get("day") or ("第 %d 天" % i)
        slots = []
        # 常见结构：slots / pois / items
        if isinstance(dd.get("slots"), list):
            for s in dd["slots"]:
                if isinstance(s, dict):
                    slots.append({"when": s.get("when", "行程"), "plan": s.get("plan") or s.get("name") or str(s)})
                else:
                    slots.append({"when": "行程", "plan": str(s)})
        elif isinstance(dd.get("pois"), list):
            for j, p in enumerate(dd["pois"], 1):
                name = p.get("name") if isinstance(p, dict) else str(p)
                slots.append({"when": "第%d站" % j, "plan": name})
        elif isinstance(dd.get("items"), list):
            for j, it in enumerate(dd["items"], 1):
                slots.append({"when": "第%d站" % j, "plan": str(it)})
        else:
            # 兜底：把整个 day 当一段
            slots.append({"when": "行程", "plan": title})
        out.append({"day": title, "slots": slots})
    return {"city": plan.get("city", ""), "days": len(out), "style": "", "style_label": "地图AI",
            "interests": [], "days_list": out} if out else None


def generate(city, days, style="classic", interests="", map_backend_url=None, map_key=None, timeout=20):
    """生成行程。优先尝试 map 项目真实 AI（若 map_backend_url 可达），否则用本地模板。"""
    city = (city or "").strip()
    if not city:
        return {"ok": False, "error": "请输入城市名称"}
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 3
    days = max(1, min(days, 14))

    live_url = (map_backend_url or os.environ.get("MAP_BACKEND_URL") or "").strip().rstrip("/")
    if live_url:
        try:
            payload = json.dumps({
                "city": city, "days": days, "theme": style,
                "budget": "", "demo": False, "use_cache": True,
            }).encode("utf-8")
            req = urllib.request.Request(
                live_url + "/api/generate", data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok") and data.get("plan"):
                adapted = _adapt_map_plan(data["plan"])
                if adapted:
                    adapted["city"] = city
                    adapted["days"] = days
                    return {"ok": True, "source": "live", "plan": adapted,
                            "note": data.get("fallback_reason", "已接入地图项目实时生成")}
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, Exception) as e:
            # 任何失败都降级到模板，绝不让前端白屏
            pass

    plan = _build_template(city, days, style, interests)
    return {"ok": True, "source": "template", "plan": plan,
            "note": "本地模板生成（零依赖）；配置 MAP_BACKEND_URL 可接地图项目真实 POI）"}


if __name__ == "__main__":
    import pprint
    pprint.pprint(generate("深圳", 3, "food", "咖啡,海边"))

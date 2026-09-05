# -*- coding: utf-8 -*-
"""
缓存 / TTL 可配置 回归测试 (OFFLINE_MODE 下可离线跑, 用 monkeypatch 替掉真抓取 builder)。

运行 (在 backend/ 目录):
    pytest -q test_cache.py

覆盖:
  - _req_ttl 参数解析 (ttl=0 / refresh=1 / 越界钳制 / 非法回退 / 默认)
  - _cached_build 命中 / 强制刷新(ttl=0) / 陈旧回退(stale)
  - 端点级集成: /api/market_cube 经 ?ttl= / ?refresh= 真实请求走到缓存壳
"""
import pytest

import app as backend


@pytest.fixture(autouse=True)
def _clean_cache():
    backend._CACHE_STORE.clear()
    yield
    backend._CACHE_STORE.clear()


def _client():
    return backend.app.test_client()


# ── 1. _req_ttl 参数解析 ──
@pytest.mark.parametrize("url,default,expect", [
    ("/api/market_cube?ttl=0", 1800, 0),
    ("/api/market_cube?ttl=60", 1800, 60),
    ("/api/market_cube?refresh=1", 1800, 0),
    ("/api/market_cube?refresh=true", 1800, 0),
    ("/api/market_cube?ttl=99999", 1800, 86400),
    ("/api/market_cube?ttl=-5", 1800, 0),
    ("/api/market_cube?ttl=abc", 1800, 1800),
    ("/api/market_cube", 1800, 1800),
])
def test_req_ttl_parsing(url, default, expect):
    with backend.app.test_request_context(url):
        assert backend._req_ttl(default) == expect


# ── 2. _cached_build: 默认 ttl 命中缓存 ──
def test_cached_build_hit():
    calls = {"n": 0}

    def b():
        calls["n"] += 1
        return {"ok": True, "v": calls["n"]}

    r1, s1 = backend._cached_build("k_hit", 1800, b)
    r2, s2 = backend._cached_build("k_hit", 1800, b)
    assert r1.get("cached") is False and r2.get("cached") is True
    assert calls["n"] == 1 and s1 is False and s2 is False


# ── 3. _cached_build: ttl=0 每次真抓 ──
def test_cached_build_force_refresh():
    calls = {"n": 0}

    def b():
        calls["n"] += 1
        return {"ok": True, "v": calls["n"]}

    r1, _ = backend._cached_build("k_fr", 0, b)
    r2, _ = backend._cached_build("k_fr", 0, b)
    assert r1.get("cached") is False and r2.get("cached") is False
    assert calls["n"] == 2


# ── 4. _cached_build: 抓取失败回退陈旧(标 stale) ──
def test_cached_build_stale_fallback():
    backend._CACHE_STORE["k_stale"] = {"ts": 0.0, "data": {"ok": True, "old": 1}}

    def b():
        raise RuntimeError("fake fail")

    r, stale = backend._cached_build("k_stale", 1800, b)
    assert stale is True and r.get("stale") is True and r.get("old") == 1


# ── 5. 端点级集成: ?ttl=0 强制刷新 / 默认命中 / ?refresh=1 ──
def _patch_builder(monkeypatch):
    counter = {"n": 0}

    def fake():
        counter["n"] += 1
        return {"ok": True, "v": counter["n"], "built": True}

    monkeypatch.setattr(backend, "_build_market_cube", fake)
    monkeypatch.setattr(backend, "OFFLINE_MODE", False)
    return counter


def test_endpoint_ttl_force_refresh(monkeypatch):
    c = _patch_builder(monkeypatch)
    r1 = _client().get("/api/market_cube?ttl=0").get_json()
    r2 = _client().get("/api/market_cube?ttl=0").get_json()
    assert r1.get("cached") is False and r2.get("cached") is False
    assert c["n"] == 2


def test_endpoint_ttl_default_hit(monkeypatch):
    c = _patch_builder(monkeypatch)
    _client().get("/api/market_cube")           # 第1次真抓
    r2 = _client().get("/api/market_cube").get_json()  # 命中
    assert r2.get("cached") is True
    assert c["n"] == 1


def test_endpoint_refresh_param(monkeypatch):
    c = _patch_builder(monkeypatch)
    r = _client().get("/api/market_cube?refresh=1").get_json()
    assert r.get("cached") is False
    assert c["n"] == 1


def test_endpoint_ttl_out_of_range_clamped(monkeypatch):
    _patch_builder(monkeypatch)
    r = _client().get("/api/market_cube?ttl=999999").get_json()
    assert r.get("ok") is True


def test_cache_stats_counts_misses_and_clear(monkeypatch):
    _patch_builder(monkeypatch)
    for k in list(backend._CACHE_STATS):
        backend._CACHE_STATS[k] = 0
    backend._CACHE_KEY_STATS.clear()
    # 第一次真抓 -> miss
    r = _client().get("/api/market_cube").get_json()
    assert r.get("cached") is False
    s = _client().get("/api/cache/stats").get_json()
    assert s["misses"] >= 1
    assert "market_cube" in s["keys"]
    assert s["keys"]["market_cube"]["hits"] + s["keys"]["market_cube"]["misses"] >= 1
    # 清空
    cl = _client().post("/api/cache/clear").get_json()
    assert cl["ok"] is True and cl["cleared"] >= 1
    s2 = _client().get("/api/cache/stats").get_json()
    assert s2["store_keys"] == 0


def test_cache_endpoint_registered():
    # /api/info 自动发现应包含缓存可观测端点
    eps = set(_client().get("/api/info").get_json()["endpoints"])
    assert "/api/cache/stats" in eps and "/api/cache/clear" in eps

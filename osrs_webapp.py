#!/usr/bin/env python3
"""
OSRS GE Scout — Web UI v3
==============================
Webapp met tabbladen: Dashboard, Actieve Orders, Winst & Verlies, Instellingen
Opent automatisch in je browser op http://localhost:5050

Installeren:  pip3 install flask requests
Starten:      python3 osrs_webapp.py
"""

import requests
import time
import json
import os
import math
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request as flask_request

# ─────────────────────────────────────────────
#  FILES
# ─────────────────────────────────────────────
DATA_DIR = Path.home() / ".osrs_agent"
DATA_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"
TRADES_FILE   = DATA_DIR / "trades.json"
HISTORY_FILE  = DATA_DIR / "history.json"
FAVORITES_FILE = DATA_DIR / "favorites.json"

HEADERS = {"User-Agent": "OSRS GE Scout - persoonlijk gebruik"}
API_BASE = "https://prices.runescape.wiki/api/v1/osrs"

# ─────────────────────────────────────────────
#  AUTO-UPDATE
# ─────────────────────────────────────────────
APP_VERSION = "7.4"
# ⬇️ PAS DIT AAN naar je eigen GitHub repo raw URL
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/cahayaproductions/OSRS-GE-SCOUT/main/version.json"
# Het version.json bestand op GitHub moet er zo uitzien:
# {"version": "4.2", "files": {"osrs_webapp.py": "https://raw.githubusercontent.com/.../osrs_webapp.py",
#                               "osrs_app.py": "https://raw.githubusercontent.com/.../osrs_app.py"},
#  "changelog": "Nieuwe features: ..."}

# ─────────────────────────────────────────────
#  RUNE & BOLT ENCHANT DATA
# ─────────────────────────────────────────────
RUNE_IDS = {
    "nature": 561, "fire": 554, "air": 556, "water": 555,
    "earth": 557, "mind": 558, "cosmic": 564, "blood": 565,
    "law": 563, "soul": 566, "death": 560
}

BOLT_ENCHANTS = [
    {"name": "Opal", "level": 4, "runes": {"cosmic": 1, "air": 2},
     "bolt": "Opal bolts", "result": "Opal bolts (e)", "d_bolt": "Opal dragon bolts", "d_result": "Opal dragon bolts (e)"},
    {"name": "Sapphire", "level": 7, "runes": {"cosmic": 1, "water": 1, "mind": 1},
     "bolt": "Sapphire bolts", "result": "Sapphire bolts (e)", "d_bolt": "Sapphire dragon bolts", "d_result": "Sapphire dragon bolts (e)"},
    {"name": "Jade", "level": 14, "runes": {"cosmic": 1, "earth": 2},
     "bolt": "Jade bolts", "result": "Jade bolts (e)", "d_bolt": "Jade dragon bolts", "d_result": "Jade dragon bolts (e)"},
    {"name": "Pearl", "level": 24, "runes": {"cosmic": 1, "water": 2},
     "bolt": "Pearl bolts", "result": "Pearl bolts (e)", "d_bolt": "Pearl dragon bolts", "d_result": "Pearl dragon bolts (e)"},
    {"name": "Emerald", "level": 27, "runes": {"cosmic": 1, "air": 3, "nature": 1},
     "bolt": "Emerald bolts", "result": "Emerald bolts (e)", "d_bolt": "Emerald dragon bolts", "d_result": "Emerald dragon bolts (e)"},
    {"name": "Red topaz", "level": 29, "runes": {"cosmic": 1, "fire": 2},
     "bolt": "Red topaz bolts", "result": "Red topaz bolts (e)", "d_bolt": "Red topaz dragon bolts", "d_result": "Red topaz dragon bolts (e)"},
    {"name": "Ruby", "level": 49, "runes": {"cosmic": 1, "blood": 1, "fire": 5},
     "bolt": "Ruby bolts", "result": "Ruby bolts (e)", "d_bolt": "Ruby dragon bolts", "d_result": "Ruby dragon bolts (e)"},
    {"name": "Diamond", "level": 57, "runes": {"cosmic": 1, "earth": 10, "law": 2},
     "bolt": "Diamond bolts", "result": "Diamond bolts (e)", "d_bolt": "Diamond dragon bolts", "d_result": "Diamond dragon bolts (e)"},
    {"name": "Dragonstone", "level": 68, "runes": {"cosmic": 1, "soul": 1, "earth": 15},
     "bolt": "Dragonstone bolts", "result": "Dragonstone bolts (e)", "d_bolt": "Dragonstone dragon bolts", "d_result": "Dragonstone dragon bolts (e)"},
    {"name": "Onyx", "level": 87, "runes": {"cosmic": 1, "death": 1, "fire": 20},
     "bolt": "Onyx bolts", "result": "Onyx bolts (e)", "d_bolt": "Onyx dragon bolts", "d_result": "Onyx dragon bolts (e)"},
]

STAFF_ELEMENTS = {
    "none": [], "fire": ["fire"], "water": ["water"], "earth": ["earth"], "air": ["air"],
    "smoke": ["air", "fire"], "steam": ["water", "fire"], "dust": ["air", "earth"],
    "mud": ["water", "earth"], "lava": ["fire", "earth"], "mist": ["air", "water"],
}

STAFF_NAMES = {
    "none": "Geen staf", "fire": "Staff of fire", "water": "Staff of water",
    "earth": "Staff of earth", "air": "Staff of air", "smoke": "Smoke battlestaff",
    "steam": "Steam battlestaff", "dust": "Dust battlestaff", "mud": "Mud battlestaff",
    "lava": "Lava battlestaff", "mist": "Mist battlestaff", "bryophyta": "Bryophyta's staff",
}

SKILL_ORDER = ["Overall", "Attack", "Defence", "Strength", "Hitpoints", "Ranged", "Prayer", "Magic",
               "Cooking", "Woodcutting", "Fletching", "Fishing", "Firemaking", "Crafting", "Smithing",
               "Mining", "Herblore", "Agility", "Thieving", "Slayer", "Farming", "Runecraft", "Hunter", "Construction"]

_hiscores_cache = {}
HISCORES_TTL = 3600

def fetch_hiscores(rsn):
    if not rsn: return None
    now = time.time()
    if rsn in _hiscores_cache and (now - _hiscores_cache[rsn]["ts"]) < HISCORES_TTL:
        return _hiscores_cache[rsn]["data"]
    try:
        url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={rsn}"
        r = requests.get(url, headers={"User-Agent": "OSRS GE Scout"}, timeout=10)
        if r.status_code != 200: return None
        lines = r.text.strip().split('\n')
        skills = {}
        for i, line in enumerate(lines):
            if i >= len(SKILL_ORDER): break
            parts = line.split(',')
            if len(parts) >= 3:
                skills[SKILL_ORDER[i]] = {"rank": int(parts[0]), "level": int(parts[1]), "xp": int(parts[2])}
        _hiscores_cache[rsn] = {"data": skills, "ts": now}
        return skills
    except:
        return None

_name_to_id = {}
def build_name_map(mapping):
    global _name_to_id
    _name_to_id = {}
    for k, v in mapping.items():
        name = v.get("name", "")
        if name: _name_to_id[name] = k
    return _name_to_id

# ─────────────────────────────────────────────
#  SETTINGS (persistent)
# ─────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "account_name":       "",
    "capital":            100_000_000,
    "max_slots":          8,
    "max_per_slot_pct":   0.25,
    "min_roi":            2.5,
    "max_roi":            200,
    "min_buy_price":      100_000,
    "min_profit_per_trade": 1_000_000,
    "min_volume":         50,
    "min_score_for_trade": 15.0,
    "refresh_seconds":    60,
    "ge_tax_rate":        0.02,
    "ge_tax_max":         5_000_000,
    "max_age_seconds":    7200,
    "max_age_expensive":  86400,
}

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
            merged = {**DEFAULT_SETTINGS, **saved}
            return merged
    return dict(DEFAULT_SETTINGS)

def save_settings(s):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)

settings = load_settings()

# ─────────────────────────────────────────────
#  TRADES (persistent)
# ─────────────────────────────────────────────
def load_trades():
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            return json.load(f)
    return []

def save_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(h):
    with open(HISTORY_FILE, "w") as f:
        json.dump(h, f, indent=2)

def load_favorites():
    if FAVORITES_FILE.exists():
        with open(FAVORITES_FILE) as f:
            return json.load(f)
    return []

def save_favorites(favs):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favs, f, indent=2)

# ─────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────
def fetch_prices():
    r = requests.get(f"{API_BASE}/latest", headers=HEADERS, timeout=10); r.raise_for_status()
    return r.json().get("data", {})
def fetch_volumes():
    r = requests.get(f"{API_BASE}/volumes", headers=HEADERS, timeout=10); r.raise_for_status()
    return r.json().get("data", {})
def fetch_1h():
    r = requests.get(f"{API_BASE}/1h", headers=HEADERS, timeout=10); r.raise_for_status()
    return r.json().get("data", {})
def fetch_5m():
    r = requests.get(f"{API_BASE}/5m", headers=HEADERS, timeout=10); r.raise_for_status()
    return r.json().get("data", {})
def fetch_mapping():
    r = requests.get(f"{API_BASE}/mapping", headers=HEADERS, timeout=10); r.raise_for_status()
    return {str(item["id"]): item for item in r.json()}

_ts_cache = {}
TS_CACHE_TTL = 600
def fetch_timeseries(item_id, timestep="6h"):
    now = time.time(); key = f"{item_id}_{timestep}"
    if key in _ts_cache and (now - _ts_cache[key]["t"]) < TS_CACHE_TTL:
        return _ts_cache[key]["d"]
    r = requests.get(f"{API_BASE}/timeseries", params={"id": item_id, "timestep": timestep}, headers=HEADERS, timeout=15)
    r.raise_for_status(); data = r.json().get("data", [])
    _ts_cache[key] = {"d": data, "t": now}
    return data

# ─────────────────────────────────────────────
#  PREDICTIE
# ─────────────────────────────────────────────
def analyse_margin_stability(item_id):
    try: data = fetch_timeseries(item_id, "6h")
    except: return {"margin_freq": 0, "avg_margin": 0, "margin_trend": "unknown"}
    if len(data) < 4: return {"margin_freq": 0, "avg_margin": 0, "margin_trend": "unknown"}
    margins = []
    for p in data:
        h, l = p.get("avgHighPrice"), p.get("avgLowPrice")
        if h and l and l > 0:
            tax = min(int(h * 0.02), 5_000_000); margins.append(((h - l - tax) / l) * 100)
        else: margins.append(None)
    valid = [m for m in margins if m is not None]
    if not valid: return {"margin_freq": 0, "avg_margin": 0, "margin_trend": "unknown"}
    pos = [m for m in valid if m > 0]
    freq = len(pos) / len(valid); avg = sum(valid) / len(valid)
    half = len(valid) // 2
    if half >= 2:
        f1 = sum(valid[:half]) / half; f2 = sum(valid[half:]) / len(valid[half:])
        mt = "growing" if f2 - f1 > 1 else ("shrinking" if f2 - f1 < -1 else "stable")
    else: mt = "unknown"
    return {"margin_freq": round(freq, 2), "avg_margin": round(avg, 2), "margin_trend": mt}

def analyse_price_momentum(item_id):
    try: data = fetch_timeseries(item_id, "6h")
    except: return {"momentum": "unknown", "pct_change": 0, "in_dip": False}
    prices = []
    for p in data:
        h, l = p.get("avgHighPrice"), p.get("avgLowPrice")
        if h and l: prices.append((h + l) / 2)
    if len(prices) < 8: return {"momentum": "unknown", "pct_change": 0, "in_dip": False}
    old = sum(prices[:4]) / 4; new = sum(prices[-4:]) / 4
    pct = ((new - old) / old) * 100 if old > 0 else 0
    if pct > 5: mom = "strong_up"
    elif pct > 2: mom = "up"
    elif pct < -5: mom = "strong_down"
    elif pct < -2: mom = "down"
    else: mom = "stable"
    avg_all = sum(prices) / len(prices)
    return {"momentum": mom, "pct_change": round(pct, 2), "in_dip": prices[-1] < avg_all * 0.97}

def analyse_weekday_pattern(item_id):
    default = {"best_buy_day": None, "best_sell_day": None, "week_spread": 0, "today_factor": 1.0, "today_pct": 0}
    try: data = fetch_timeseries(item_id, "6h")
    except: return default
    dp = defaultdict(list)
    for p in data:
        ts = p.get("timestamp", 0); h, l = p.get("avgHighPrice"), p.get("avgLowPrice")
        if h and l: dp[datetime.fromtimestamp(ts, tz=timezone.utc).weekday()].append((h + l) / 2)
    if len(dp) < 5: return default
    da = {d: sum(p) / len(p) for d, p in dp.items()}; ov = sum(da.values()) / len(da)
    if ov <= 0: return default
    dpct = {d: ((a - ov) / ov) * 100 for d, a in da.items()}
    bb = min(dpct, key=dpct.get); bs = max(dpct, key=dpct.get)
    td = dpct.get(datetime.now(timezone.utc).weekday(), 0)
    if td <= -1: tf = 1.15
    elif td <= -0.3: tf = 1.05
    elif td >= 1: tf = 0.85
    elif td >= 0.3: tf = 0.95
    else: tf = 1.0
    return {"best_buy_day": bb, "best_sell_day": bs, "week_spread": round(dpct[bs] - dpct[bb], 2), "today_factor": tf, "today_pct": round(td, 2)}

_pred_cache = {}
PRED_TTL = 300
def get_predictions(item_id):
    now = time.time()
    if item_id in _pred_cache and (now - _pred_cache[item_id]["ts"]) < PRED_TTL:
        return _pred_cache[item_id]
    r = {"margin": analyse_margin_stability(item_id), "momentum": analyse_price_momentum(item_id),
         "weekday": analyse_weekday_pattern(item_id), "ts": now}
    _pred_cache[item_id] = r; return r

# ─────────────────────────────────────────────
#  BEREKENINGEN
# ─────────────────────────────────────────────
def ge_tax(price): return min(int(price * settings["ge_tax_rate"]), settings["ge_tax_max"])
def net_profit(buy, sell): return sell - buy - ge_tax(sell)
def roi_pct(buy, sell): return (net_profit(buy, sell) / buy * 100) if buy > 0 else 0
def format_gp(n):
    if n is None: return "?"
    n = int(n)
    if abs(n) >= 1e6: return f"{n/1e6:.2f}M"
    if abs(n) >= 1e3: return f"{n/1e3:.1f}K"
    return str(n)

def used_capital():
    return sum(t["buy_price"] * t["quantity"] for t in load_trades() if t["status"] in ("KOPEN", "AAN_HET_KOPEN", "VERKOPEN"))

def available_capital():
    return settings["capital"] - used_capital()

# ─────────────────────────────────────────────
#  SCORING
# ─────────────────────────────────────────────
def score_opportunity(item, now_ts):
    roi = item["roi"]; age = now_ts - item["oldest_time"]
    bl = item["buy_limit"]; vol = item["volume"]
    age_f = 1.0 if age < 300 else (0.85 if age < 900 else (0.65 if age < 3600 else 0.40))
    fill_f = min(1.0, vol / (bl * 6)) if isinstance(bl, int) and bl > 0 else 0.5
    trend_f = 1.1 if item.get("trend") == "up" else (0.8 if item.get("trend") == "down" else 1.0)
    pred = item.get("predictions", {})
    m = pred.get("margin", {}); freq = m.get("margin_freq", 0); mt = m.get("margin_trend", "unknown")
    margin_f = 1.2 if freq >= 0.7 else (1.0 if freq >= 0.4 else (0.7 if freq > 0 else 1.0))
    if mt == "growing": margin_f *= 1.1
    elif mt == "shrinking": margin_f *= 0.85
    mo = pred.get("momentum", {}); mom = mo.get("momentum", "unknown")
    momentum_f = {
        "strong_down": 0.6, "down": 0.8, "up": 1.05, "strong_up": 1.0
    }.get(mom, 1.0)
    if mo.get("in_dip") and mom != "strong_down": momentum_f *= 1.15
    weekday_f = pred.get("weekday", {}).get("today_factor", 1.0)
    return roi * age_f * fill_f * trend_f * margin_f * momentum_f * weekday_f

def find_opportunities(prices, volumes, mapping, data_1h, state_trades):
    now_ts = datetime.now(timezone.utc).timestamp()
    skip = {t["name"] for t in state_trades if t["status"] not in ("KLAAR", "GEANNULEERD")}
    opps = []
    for iid, pd in prices.items():
        h, l = pd.get("high"), pd.get("low")
        ht, lt = pd.get("highTime", 0), pd.get("lowTime", 0)
        if not h or not l or h <= l: continue
        if l < 10: continue  # Skip truly junk items
        oldest = min(ht, lt)
        ma = settings["max_age_expensive"] if l >= 5e6 else settings["max_age_seconds"]
        if (now_ts - oldest) > ma: continue
        d1h = data_1h.get(iid, {}); ah = d1h.get("avgHighPrice"); al_ = d1h.get("avgLowPrice")
        if ah and (h > ah * 3 or h < ah / 3): continue
        if al_ and (l > al_ * 3 or l < al_ / 3): continue
        vol = volumes.get(iid, 0)
        mv = 5 if l >= 5e6 else settings["min_volume"]
        if vol < mv: continue
        roi = roi_pct(l, h)
        if roi < settings["min_roi"]: continue
        if l >= 1e5 and roi > settings["max_roi"]: continue  # Only cap ROI for expensive items
        info = mapping.get(iid, {}); name = info.get("name", f"Item {iid}")
        bl = info.get("limit"); le = False
        if not isinstance(bl, int):
            le = True
            if l >= 5e7: bl = 8
            elif l >= 1e7: bl = 15
            elif l >= 1e6: bl = 15
            elif l >= 1e5: bl = 70
            else: bl = 150
        if name in skip: continue
        trend = "stable"
        if al_ and al_ > 0:
            if l > al_ * 1.02: trend = "up"
            elif l < al_ * 0.98: trend = "down"
        pf = int(bl * net_profit(l, h))
        opps.append({"id": iid, "name": name, "buy_price": l, "sell_price": h, "roi": round(roi, 1),
                      "volume": vol, "buy_limit": bl, "oldest_time": oldest, "now_ts": now_ts,
                      "trend": trend, "profit_flip": pf, "limit_estimated": le})
    opps.sort(key=lambda x: x["roi"], reverse=True)
    now_cache = time.time()
    # Top 40: verse predictions ophalen (API call)
    for it in opps[:40]:
        try: it["predictions"] = get_predictions(it["id"]); time.sleep(0.1)
        except: it["predictions"] = {}
        it["score"] = round(score_opportunity(it, now_ts), 1)
    # Rest: predictions uit cache lezen (geen API calls)
    for it in opps[40:]:
        sid = str(it["id"])
        if sid in _pred_cache and (now_cache - _pred_cache[sid].get("ts", 0)) < PRED_TTL:
            it["predictions"] = _pred_cache[sid]
        else:
            it["predictions"] = {}
        it["score"] = round(score_opportunity(it, now_ts), 1)
    opps.sort(key=lambda x: x["score"], reverse=True)
    return opps

def find_all_items(prices, volumes, mapping, data_1h):
    """Geeft ALLE items terug zonder filters — voor favorieten en 100M+ lijst."""
    now_ts = datetime.now(timezone.utc).timestamp()
    items = []
    for iid, pd in prices.items():
        h, l = pd.get("high"), pd.get("low")
        ht, lt = pd.get("highTime", 0), pd.get("lowTime", 0)
        if not h or not l: continue
        oldest = min(ht, lt) if ht and lt else 0
        vol = volumes.get(iid, 0)
        roi = roi_pct(l, h) if l > 0 and h > l else 0
        info = mapping.get(iid, {}); name = info.get("name", f"Item {iid}")
        bl = info.get("limit"); le = False
        if not isinstance(bl, int):
            le = True
            if l >= 5e7: bl = 8
            elif l >= 1e7: bl = 15
            elif l >= 1e6: bl = 15
            elif l >= 1e5: bl = 70
            else: bl = 150
        trend = "stable"
        al_ = data_1h.get(iid, {}).get("avgLowPrice")
        if al_ and al_ > 0:
            if l > al_ * 1.02: trend = "up"
            elif l < al_ * 0.98: trend = "down"
        pf = int(bl * net_profit(l, h)) if h > l else 0
        # Gebruik alleen CACHE — geen nieuwe API calls voor alle items
        if iid in _pred_cache and (now_ts - _pred_cache[iid].get("ts", 0)) < PRED_TTL:
            pred = _pred_cache[iid]
        else:
            pred = {"margin": {}, "momentum": {}, "weekday": {}}
        m = pred.get("margin", {}); mo = pred.get("momentum", {})
        items.append({"id": iid, "name": name, "buy_price": l, "sell_price": h, "roi": round(roi, 1),
                      "volume": vol, "buy_limit": bl, "oldest_time": oldest, "now_ts": now_ts,
                      "trend": trend, "profit_flip": pf, "limit_estimated": le,
                      "margin_freq": m.get("margin_freq", 0),
                      "momentum": mo.get("momentum", "stable"),
                      "in_dip": mo.get("in_dip", False),
                      "predictions": pred, "score": round(roi * 0.5, 1)})
    return items

# ─────────────────────────────────────────────
#  GLOBAL MARKET STATE
# ─────────────────────────────────────────────
market = {"opportunities": [], "all_items": [], "iteration": 0, "last_refresh": None, "status": "Opstarten...", "error": None, "mapping": {}}
market_lock = threading.Lock()

def _fill_missing_predictions(all_items):
    """Vul predictions voor ALLE items op de achtergrond. Favorieten + dure items eerst."""
    favs = set(load_favorites())
    now = time.time()
    uncached = []
    for it in all_items:
        iid = str(it["id"])
        if iid in _pred_cache and (now - _pred_cache[iid].get("ts", 0)) < PRED_TTL:
            continue
        uncached.append(it)
    if not uncached:
        return
    # Prioriteit: favorieten → duurste items → rest
    uncached.sort(key=lambda x: (0 if x["name"] in favs else 1, -x["buy_price"]))
    filled = 0
    for it in uncached:
        try:
            pred = get_predictions(str(it["id"]))
            it["predictions"] = pred
            it["margin_freq"] = pred.get("margin", {}).get("margin_freq", 0)
            it["momentum"] = pred.get("momentum", {}).get("momentum", "stable")
            it["in_dip"] = pred.get("momentum", {}).get("in_dip", False)
            filled += 1
            # Elke 20 items kort pauzeren zodat de API niet overbelast raakt
            if filled % 20 == 0:
                time.sleep(1)
        except:
            pass
    # Update all_items in market state met nieuwe predictions
    if filled:
        with market_lock:
            market["all_items"] = all_items

def market_scanner():
    global market
    try:
        mapping = fetch_mapping()
        with market_lock: market["mapping"] = mapping; market["status"] = f"{len(mapping)} items geladen"
    except Exception as e:
        with market_lock: market["error"] = str(e)
        return
    while True:
        try:
            with market_lock: market["status"] = "Scannen..."; market["iteration"] += 1
            prices = fetch_prices(); volumes = fetch_volumes(); d1h = fetch_1h(); fetch_5m()
            trades = load_trades()
            opps = find_opportunities(prices, volumes, mapping, d1h, trades)
            all_items = find_all_items(prices, volumes, mapping, d1h)
            with market_lock:
                market["opportunities"] = opps; market["all_items"] = all_items
                market["last_refresh"] = datetime.now().strftime("%H:%M:%S")
                market["status"] = "OK"; market["error"] = None
            # Achtergrond: vul predictions voor favorieten + dure items die nog niet gecacht zijn
            _fill_missing_predictions(all_items)
            # Update opps met nieuw gecachte predictions
            now_bg = time.time()
            for it in opps:
                sid = str(it["id"])
                if not it.get("predictions") and sid in _pred_cache and (now_bg - _pred_cache[sid].get("ts", 0)) < PRED_TTL:
                    it["predictions"] = _pred_cache[sid]
                    it["margin_freq"] = _pred_cache[sid].get("margin", {}).get("margin_freq", 0)
                    it["momentum"] = _pred_cache[sid].get("momentum", {}).get("momentum", "stable")
                    it["in_dip"] = _pred_cache[sid].get("momentum", {}).get("in_dip", False)
            with market_lock:
                market["opportunities"] = opps
        except Exception as e:
            with market_lock: market["error"] = str(e); market["status"] = f"Fout: {e}"
        time.sleep(settings["refresh_seconds"])

def notify(title, msg):
    try: os.system(f'osascript -e \'display notification "{msg}" with title "{title}"\'')
    except: pass

# ─────────────────────────────────────────────
#  FLASK
# ─────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index(): return HTML_PAGE

@app.route("/app-icon.png")
def app_icon():
    from flask import send_file
    # Zoek icon in meerdere locaties (update dir heeft geen icon)
    search_dirs = [
        os.path.dirname(os.path.abspath(__file__)),  # huidige dir
    ]
    # PyInstaller: kijk in _MEIPASS (bundled resources)
    if hasattr(sys, '_MEIPASS'):
        search_dirs.append(sys._MEIPASS)
        # Ook Resources dir van de .app bundle
        exe = os.path.realpath(sys.executable)
        resources = os.path.join(os.path.dirname(os.path.dirname(exe)), "Resources")
        search_dirs.append(resources)
    # Originele app locatie (voor dev / niet-PyInstaller)
    search_dirs.append(os.path.join(str(Path.home()), ".osrs_agent"))
    for d in search_dirs:
        for name in ["OSRS_GE_SCOUT.png", "osrs_icon.png"]:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return send_file(p, mimetype="image/png")
    return "", 404

@app.route("/api/market")
def api_market():
    with market_lock:
        opps = market["opportunities"]
        def ser(o):
            p = o.get("predictions", {})
            # Fallback: check cache als predictions leeg zijn
            if not p or (not p.get("margin") and not p.get("momentum")):
                sid = str(o["id"])
                if sid in _pred_cache:
                    p = _pred_cache[sid]
            return {"id": o["id"], "name": o["name"], "buy_price": o["buy_price"], "sell_price": o["sell_price"],
                    "roi": o["roi"], "score": o["score"], "trend": o["trend"], "buy_limit": o["buy_limit"],
                    "limit_estimated": o.get("limit_estimated", False), "profit_flip": o["profit_flip"],
                    "volume": o["volume"],
                    "margin_freq": p.get("margin", {}).get("margin_freq", 0) or o.get("margin_freq", 0),
                    "margin_trend": p.get("margin", {}).get("margin_trend", "unknown"),
                    "momentum": p.get("momentum", {}).get("momentum", "unknown") if p.get("momentum", {}).get("momentum", "unknown") != "unknown" else o.get("momentum", "stable"),
                    "in_dip": p.get("momentum", {}).get("in_dip", False) or o.get("in_dip", False),
                    "today_pct": p.get("weekday", {}).get("today_pct", 0)}
        all_items = market["all_items"]
        favs = load_favorites()
        # Favorieten uit all_items (altijd tonen, ongeacht margin/filters)
        fav_items = [ser(o) for o in all_items if o["name"] in favs]
        fav_items.sort(key=lambda x: x["name"])

        # 100M+ uit all_items (altijd tonen, ook negatieve margin)
        t5 = [ser(o) for o in all_items if o["buy_price"] >= 1e8]
        t5.sort(key=lambda x: x["roi"], reverse=True)

        # Bulk: buy limit 1000+, volume >= 20% van 6x buy limit (dag limiet)
        bulk = [ser(o) for o in opps if o["buy_limit"] >= 1000 and o["volume"] >= o["buy_limit"] * 6 * 0.2]
        bulk.sort(key=lambda x: x["profit_flip"] * x["buy_limit"], reverse=True)

        # Reguliere tiers uit gefilterde opps — ALLE items, frontend doet de slicing
        t0 = [ser(o) for o in opps if o["buy_price"] < 1e5]
        t1 = [ser(o) for o in opps if 1e5 <= o["buy_price"] < 5e5]
        t2 = [ser(o) for o in opps if 5e5 <= o["buy_price"] < 5e6]
        t3 = [ser(o) for o in opps if 5e6 <= o["buy_price"] < 1e7]
        t4 = [ser(o) for o in opps if 1e7 <= o["buy_price"] < 1e8]

        return jsonify({"status": market["status"], "error": market["error"], "iteration": market["iteration"],
                        "last_refresh": market["last_refresh"], "fav_items": fav_items,
                        "bulk": bulk, "tier0": t0, "tier1": t1, "tier2": t2, "tier3": t3, "tier4": t4, "tier5": t5,
                        "favorites": favs})

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify({**settings, "used": used_capital(), "available": available_capital()})

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    global settings
    data = flask_request.json
    for k in ("account_name", "capital", "max_slots", "min_roi", "max_roi", "min_buy_price", "min_profit_per_trade",
              "min_volume", "min_score_for_trade", "refresh_seconds"):
        if k in data:
            settings[k] = int(data[k]) if isinstance(data[k], float) and data[k] == int(data[k]) else data[k]
    save_settings(settings)
    return jsonify({"ok": True})

@app.route("/api/trades", methods=["GET"])
def api_get_trades():
    return jsonify(load_trades())

@app.route("/api/buy", methods=["POST"])
def api_buy():
    d = flask_request.json
    trade = {
        "id": str(uuid.uuid4())[:8],
        "item_id": d.get("item_id", ""),
        "name": d["name"],
        "buy_price": int(d["buy_price"]),
        "quantity": int(d["quantity"]),
        "total_cost": int(d["buy_price"]) * int(d["quantity"]),
        "status": "KOPEN",
        "sell_price": None,
        "sell_quantity": None,
        "profit": None,
        "market_sell_price": d.get("market_sell_price"),
        "roi": d.get("roi"),
        "score": d.get("score"),
        "trend": d.get("trend"),
        "buy_limit": d.get("buy_limit"),
        "limit_estimated": d.get("limit_estimated", False),
        "margin_freq": d.get("margin_freq"),
        "momentum": d.get("momentum"),
        "today_pct": d.get("today_pct"),
        "profit_flip": d.get("profit_flip"),
        "volume": d.get("volume"),
        "opened_at": datetime.now().isoformat(),
        "closed_at": None,
    }
    trades = load_trades()
    trades.append(trade)
    save_trades(trades)
    settings["capital"] = settings["capital"] - trade["total_cost"]
    save_settings(settings)
    notify("OSRS Agent", f"Koop: {trade['name']} {trade['quantity']}x @ {format_gp(trade['buy_price'])}")
    return jsonify({"ok": True, "trade": trade})

@app.route("/api/confirm_buy", methods=["POST"])
def api_confirm_buy():
    """Bevestig dat de koop (deels) is gevuld."""
    d = flask_request.json
    tid = d["trade_id"]
    filled_qty = int(d["filled_quantity"])
    trades = load_trades()
    trade = next((t for t in trades if t["id"] == tid), None)
    if not trade: return jsonify({"error": "Niet gevonden"}), 404

    unfilled = trade["quantity"] - filled_qty
    # Geef kapitaal terug voor niet-gevulde items
    if unfilled > 0:
        settings["capital"] = settings["capital"] + unfilled * trade["buy_price"]
        save_settings(settings)

    trade["quantity"] = filled_qty
    trade["total_cost"] = filled_qty * trade["buy_price"]
    trade["status"] = "VERKOPEN"  # Klaar om te verkopen
    trade["bought_at"] = datetime.now().isoformat()
    save_trades(trades)
    notify("OSRS Agent", f"{trade['name']} koop bevestigd: {filled_qty}x")
    return jsonify({"ok": True})

@app.route("/api/sell", methods=["POST"])
def api_sell():
    d = flask_request.json
    tid = d["trade_id"]
    sell_price = int(d["sell_price"])
    sell_qty = int(d["sell_quantity"])
    trades = load_trades()
    trade = next((t for t in trades if t["id"] == tid), None)
    if not trade: return jsonify({"error": "Trade niet gevonden"}), 404

    revenue = sell_qty * sell_price
    tax = sell_qty * ge_tax(sell_price)
    cost = sell_qty * trade["buy_price"]
    profit = revenue - tax - cost

    remaining = trade["quantity"] - sell_qty

    history = load_history()
    # Voeg verkocht deel toe aan history
    closed = datetime.now()
    # Bereken flip-duur in minuten
    flip_mins = None
    if trade.get("bought_at"):
        try:
            bought = datetime.fromisoformat(trade["bought_at"])
            flip_mins = int((closed - bought).total_seconds() / 60)
        except: pass
    elif trade.get("opened_at"):
        try:
            opened = datetime.fromisoformat(trade["opened_at"])
            flip_mins = int((closed - opened).total_seconds() / 60)
        except: pass
    history.append({
        **trade,
        "sell_price": sell_price,
        "sell_quantity": sell_qty,
        "profit": profit,
        "revenue": revenue,
        "tax": tax,
        "status": "KLAAR",
        "closed_at": closed.isoformat(),
        "flip_minutes": flip_mins,
    })
    save_history(history)

    # Update kapitaal: je krijgt de opbrengst minus tax terug
    settings["capital"] = settings["capital"] + revenue - tax
    save_settings(settings)

    if remaining <= 0:
        trades = [t for t in trades if t["id"] != tid]
    else:
        trade["quantity"] = remaining
        trade["total_cost"] = remaining * trade["buy_price"]
    save_trades(trades)

    notify("OSRS Agent", f"{trade['name']} verkocht! Winst: {format_gp(profit)}")
    return jsonify({"ok": True, "profit": profit})

@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    d = flask_request.json; tid = d["trade_id"]
    trades = load_trades()
    trade = next((t for t in trades if t["id"] == tid), None)
    if not trade: return jsonify({"error": "Niet gevonden"}), 404
    # Geef kapitaal terug
    settings["capital"] = settings["capital"] + trade["total_cost"]
    save_settings(settings)
    trades = [t for t in trades if t["id"] != tid]
    save_trades(trades)
    return jsonify({"ok": True})

@app.route("/api/trades_live")
def api_trades_live():
    """Trades + huidige marktprijzen."""
    trades = load_trades()
    with market_lock:
        opps = market.get("opportunities", [])
        all_it = market.get("all_items", [])
    # Maak een lookup op item naam — gebruik all_items als primaire bron (breder)
    price_lookup = {}
    for o in all_it:
        price_lookup[o["name"]] = o
    # Opportunities overschrijven (meest actuele gefilterde data)
    for o in opps:
        price_lookup[o["name"]] = o
    for t in trades:
        live = price_lookup.get(t["name"], {})
        t["live_sell_price"] = live.get("sell_price")
        t["live_buy_price"] = live.get("buy_price")
        t["live_trend"] = live.get("trend", "stable")
        t["live_margin_freq"] = live.get("margin_freq", 0)
        t["live_momentum"] = live.get("momentum", "stable")
        t["live_roi"] = live.get("roi", 0)
        # Bereken potentiele winst
        if t["live_sell_price"] and t.get("buy_price"):
            ls = t["live_sell_price"]
            tax = min(int(ls * 0.02), 5000000)
            t["live_profit"] = t["quantity"] * (ls - t["buy_price"] - tax)
            t["live_profit_pct"] = round((ls - t["buy_price"] - tax) / t["buy_price"] * 100, 1) if t["buy_price"] else 0
        else:
            t["live_profit"] = None
            t["live_profit_pct"] = None
    return jsonify(trades)

@app.route("/api/history")
def api_history():
    return jsonify(load_history())

@app.route("/api/history/delete", methods=["POST"])
def api_history_delete():
    d = flask_request.json
    idx = d.get("index")
    history = load_history()
    if idx is not None and 0 <= idx < len(history):
        history.pop(idx)
        save_history(history)
    return jsonify({"ok": True})

@app.route("/api/favorites", methods=["GET"])
def api_get_favorites():
    return jsonify(load_favorites())

@app.route("/api/favorites/toggle", methods=["POST"])
def api_toggle_favorite():
    d = flask_request.json
    name = d["name"]
    favs = load_favorites()
    if name in favs:
        favs.remove(name)
    else:
        favs.append(name)
    save_favorites(favs)
    return jsonify({"ok": True, "favorites": favs})

@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Wis alle gegevens en herstel standaard instellingen."""
    import glob as g
    for f in g.glob(os.path.join(DATA_DIR, "*.json")):
        os.remove(f)
    # Herstel standaard settings
    save_settings(DEFAULT_SETTINGS.copy())
    save_trades([])
    save_history([])
    save_favorites([])
    return jsonify({"ok": True})

@app.route("/api/search", methods=["GET"])
def api_search():
    q = flask_request.args.get("q", "").lower()
    if len(q) < 2:
        return jsonify([])
    with market_lock:
        mapping = market["mapping"]
    results = []
    for iid, info in mapping.items():
        name = info.get("name", "")
        if q in name.lower():
            results.append({"id": iid, "name": name, "limit": info.get("limit")})
            if len(results) >= 20:
                break
    return jsonify(results)

# ─────────────────────────────────────────────
#  MONEY METHODS API
# ─────────────────────────────────────────────
@app.route("/api/hiscores")
def api_hiscores():
    rsn = settings.get("account_name", "")
    if not rsn: return jsonify({"error": "no_rsn", "skills": {}})
    skills = fetch_hiscores(rsn)
    if not skills: return jsonify({"error": "not_found", "skills": {}})
    return jsonify({"error": None, "skills": skills, "rsn": rsn})

def _vwap(item_id, side="low"):
    """Volume-Weighted Average Price uit timeseries (1h stappen, laatste 24u).
    Datapunten met meer volume wegen zwaarder — filtert uitschieters effectief."""
    try:
        data = fetch_timeseries(str(item_id), "1h")
    except:
        return None
    if not data:
        return None
    price_key = "avgLowPrice" if side == "low" else "avgHighPrice"
    vol_key = "lowPriceVolume" if side == "low" else "highPriceVolume"
    total_value = 0
    total_vol = 0
    for dp in data[-24:]:  # laatste 24 datapunten (24 uur)
        p = dp.get(price_key)
        v = dp.get(vol_key, 0)
        if p and p > 0 and v and v > 0:
            total_value += p * v
            total_vol += v
    if total_vol < 5:
        return None  # te weinig volume, zelfs over 24u
    return round(total_value / total_vol)

def _fast_price(iid, prices, data_1h, data_5m, side="low"):
    """Snelle prijsbepaling ZONDER VWAP — voor bulk scans (1h avg > 5m avg > instant)."""
    sid = str(iid)
    avg_key = "avgLowPrice" if side == "low" else "avgHighPrice"
    inst_key = side
    avg_1h = data_1h.get(sid, {}).get(avg_key) if data_1h else None
    if avg_1h and avg_1h > 0:
        return avg_1h
    avg_5m = data_5m.get(sid, {}).get(avg_key) if data_5m else None
    if avg_5m and avg_5m > 0:
        return avg_5m
    inst = prices.get(sid, {}).get(inst_key)
    return inst or 0

def _best_price(iid, prices, data_1h, data_5m, side="low"):
    """Prijsbepaling met VWAP fallback. Prioriteit: 1h avg > VWAP (24u) > instant."""
    sid = str(iid)
    if side == "avg":
        # GE marktprijs: 1h gemiddelde van werkelijke trades
        sid2 = str(iid)
        avg_h = data_1h.get(sid2, {}).get("avgHighPrice") if data_1h else None
        avg_l = data_1h.get(sid2, {}).get("avgLowPrice") if data_1h else None
        if avg_h and avg_l and avg_h > 0 and avg_l > 0:
            return round((avg_h + avg_l) / 2)
        if avg_h and avg_h > 0: return avg_h
        if avg_l and avg_l > 0: return avg_l
        # Fallback naar instant prijs
        inst_h = prices.get(sid2, {}).get("high") or 0
        inst_l = prices.get(sid2, {}).get("low") or 0
        if inst_h and inst_l: return round((inst_h + inst_l) / 2)
        return inst_h or inst_l or 0
    avg_key = "avgLowPrice" if side == "low" else "avgHighPrice"
    inst_key = side

    # 1) 1h gemiddelde — meest betrouwbaar voor actief verhandelde items
    avg_1h = data_1h.get(sid, {}).get(avg_key) if data_1h else None
    if avg_1h and avg_1h > 0:
        return avg_1h

    # 2) VWAP uit timeseries — volume-gewogen, filtert uitschieters
    vwap = _vwap(iid, side)
    if vwap and vwap > 0:
        return vwap

    # 3) Instant prijs — alleen als er echt niks anders is
    inst = prices.get(sid, {}).get(inst_key)
    return inst or 0

# ─────────────────────────────────────────────
#  AUTO-UPDATE ENDPOINTS
# ─────────────────────────────────────────────
@app.route("/api/update/check")
def api_update_check():
    """Check of er een nieuwe versie beschikbaar is."""
    try:
        r = requests.get(UPDATE_CHECK_URL, timeout=5, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        remote = r.json()
        remote_ver = remote.get("version", "0")
        has_update = remote_ver != APP_VERSION
        return jsonify({"current": APP_VERSION, "remote": remote_ver,
                        "has_update": has_update,
                        "changelog": remote.get("changelog", "") if has_update else "",
                        "files": remote.get("files", {}) if has_update else {}})
    except:
        return jsonify({"current": APP_VERSION, "remote": None, "has_update": False, "error": "check_failed"})

UPDATE_DIR = Path.home() / ".osrs_agent" / "updates"

def _get_update_dir():
    """Schrijfbare map voor updates — ~/.osrs_agent/updates/"""
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    return UPDATE_DIR

@app.route("/api/update/install", methods=["POST"])
def api_update_install():
    """Download en installeer de nieuwe versie naar ~/.osrs_agent/updates/."""
    try:
        r = requests.get(UPDATE_CHECK_URL, timeout=5, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        remote = r.json()
        files = remote.get("files", {})
        if not files:
            return jsonify({"ok": False, "error": "no_files"})
        update_dir = _get_update_dir()
        updated = []
        for fname, url in files.items():
            if not fname.endswith(".py"):
                continue
            target = update_dir / fname
            dl = requests.get(url, timeout=15)
            dl.raise_for_status()
            target.write_text(dl.text, encoding="utf-8")
            updated.append(fname)
        return jsonify({"ok": True, "updated": updated, "new_version": remote.get("version", "?")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/item/<int:item_id>/history")
def api_item_history(item_id):
    """Prijsgeschiedenis voor een item — meerdere timesteps voor verschillende periodes."""
    try:
        # Haal timeseries op met verschillende resoluties
        ts_5m = fetch_timeseries(item_id, "5m")    # ~1 dag
        ts_1h = fetch_timeseries(item_id, "1h")     # ~2 weken
        ts_6h = fetch_timeseries(item_id, "6h")     # ~3 maanden
        ts_24h = []
        try: ts_24h = fetch_timeseries(item_id, "24h")  # ~1 jaar+
        except: pass
        # Item info
        with market_lock:
            mapping = market.get("mapping", {})
        info = mapping.get(str(item_id), {})
        name = info.get("name", f"Item {item_id}")
        limit = info.get("limit")
        # Huidige prijs
        try:
            prices = fetch_prices()
            current = prices.get(str(item_id), {})
        except:
            current = {}
        return jsonify({
            "id": item_id, "name": name, "limit": limit,
            "current_high": current.get("high"), "current_low": current.get("low"),
            "ts_5m": ts_5m[-300:],  # laatste ~25 uur
            "ts_1h": ts_1h,          # ~2 weken
            "ts_6h": ts_6h,          # ~3 maanden
            "ts_24h": ts_24h,        # ~1 jaar+
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/item/<int:item_id>/icon")
def api_item_icon(item_id):
    """Geeft de OSRS Wiki icon URL voor een item."""
    try:
        with market_lock:
            mapping = market.get("mapping", {})
        info = mapping.get(str(item_id), {})
        icon = info.get("icon", "")
        if not icon:
            return jsonify({"icon_url": None})
        # OSRS Wiki icon URL — spaties worden underscores
        icon_filename = icon.replace(" ", "_")
        icon_url = f"https://oldschool.runescape.wiki/images/{icon_filename}"
        return jsonify({"icon_url": icon_url})
    except:
        return jsonify({"icon_url": None})

@app.route("/api/update/restart", methods=["POST"])
def api_update_restart():
    """Herstart de app na een update via de .app bundle."""
    import subprocess, shlex
    try:
        app_bundle = None
        debug_info = []

        # Methode 1: PyInstaller — sys.executable zit in .app/Contents/MacOS/
        if hasattr(sys, '_MEIPASS'):
            exe = Path(sys.executable)
            debug_info.append(f"pyinstaller exe={exe}")
            for p in [exe.parent.parent.parent, exe.parent.parent]:
                if p.suffix == ".app" and p.exists():
                    app_bundle = str(p)
                    debug_info.append(f"found via pyinstaller: {app_bundle}")
                    break

        # Methode 2: Bekende app naam in /Applications
        if not app_bundle:
            candidate = Path("/Applications/OSRS GE Scout.app")
            if candidate.exists():
                app_bundle = str(candidate)
                debug_info.append(f"found in /Applications: {app_bundle}")

        debug_info.append(f"final app_bundle={app_bundle}")

        # Schrijf een klein restart script dat onafhankelijk draait
        restart_script = Path.home() / ".osrs_agent" / "_restart.sh"
        restart_script.parent.mkdir(parents=True, exist_ok=True)

        if app_bundle:
            restart_script.write_text(
                f'#!/bin/bash\nsleep 3\nopen -n "{app_bundle}"\nrm -f "{restart_script}"\n',
                encoding="utf-8"
            )
        elif hasattr(sys, '_MEIPASS'):
            exe_path = sys.executable
            restart_script.write_text(
                f'#!/bin/bash\nsleep 3\nexec "{exe_path}"\nrm -f "{restart_script}"\n',
                encoding="utf-8"
            )
        else:
            run_dir = str(_get_update_dir()) if (_get_update_dir() / "osrs_app.py").exists() else str(Path(__file__).parent)
            restart_script.write_text(
                f'#!/bin/bash\nsleep 3\ncd "{run_dir}" && exec python3 osrs_app.py\nrm -f "{restart_script}"\n',
                encoding="utf-8"
            )

        os.chmod(str(restart_script), 0o755)
        # Start het script volledig los van dit proces
        subprocess.Popen(
            ["/bin/bash", str(restart_script)],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True
        )
        debug_info.append("restart script launched")

        # Geef response terug VOOR we afsluiten
        response = jsonify({"ok": True, "debug": debug_info})

        # Sluit de app na 2 seconden (script wacht 3 sec)
        threading.Timer(2.0, lambda: os._exit(0)).start()
        return response
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})

# ─────────────────────────────────────────────
#  HERB RUN CALCULATOR
# ─────────────────────────────────────────────
# Seed ID → Grimy herb ID, herb name, farming level required
HERB_DATA = {
    5291: {"herb": 199,  "name": "Guam leaf",       "lvl": 9},
    5292: {"herb": 201,  "name": "Marrentill",       "lvl": 14},
    5293: {"herb": 203,  "name": "Tarromin",         "lvl": 19},
    5294: {"herb": 205,  "name": "Harralander",      "lvl": 26},
    5295: {"herb": 207,  "name": "Ranarr weed",      "lvl": 32},
    5296: {"herb": 3049, "name": "Toadflax",         "lvl": 38},
    5297: {"herb": 209,  "name": "Irit leaf",        "lvl": 44},
    5298: {"herb": 211,  "name": "Avantoe",          "lvl": 50},
    5299: {"herb": 213,  "name": "Kwuarm",           "lvl": 56},
    5300: {"herb": 3051, "name": "Snapdragon",       "lvl": 62},
    5301: {"herb": 215,  "name": "Cadantine",        "lvl": 67},
    5302: {"herb": 2485, "name": "Lantadyme",        "lvl": 73},
    5303: {"herb": 217,  "name": "Dwarf weed",       "lvl": 79},
    5304: {"herb": 219,  "name": "Torstol",          "lvl": 85},
    # Noxifer, Golpar, Buchu, Celastrus — alleen in Chambers of Xeric, niet bij normale patches
}

HERB_PATCHES = [
    {"name": "Farming Guild",   "key": "guild",    "quest": "65 Farming",
     "order": 1, "teleport": "Farming guild teleport / Jewellery box (Skills necklace)",
     "items": ["Skills necklace / Farming guild teleport"], "tip": "Dichtbij bank — begin hier om spullen te pakken"},
    {"name": "Hosidius",        "key": "hosidius",  "quest": None,
     "order": 2, "teleport": "Xeric's talisman (Xeric's Glade)",
     "items": ["Xeric's talisman"], "tip": "Loop naar het zuiden van Hosidius"},
    {"name": "Port Phasmatys",  "key": "phasmatys", "quest": None,
     "order": 3, "teleport": "Ectophial",
     "items": ["Ectophial"], "tip": "Patch ten zuiden van de pub"},
    {"name": "Harmony Island",  "key": "harmony",   "quest": "Elite Morytania Diary",
     "order": 4, "teleport": "Harmony island teleport (portaal)",
     "items": ["Harmony island teleport"], "tip": "Via Portal Nexus of tablet"},
    {"name": "Ardougne",        "key": "ardougne",  "quest": None,
     "order": 5, "teleport": "Ardougne cloak teleport / Ardougne teleport",
     "items": ["Ardougne cloak (any)"], "tip": "Patch ten noorden van het marktplein"},
    {"name": "Catherby",        "key": "catherby",  "quest": None,
     "order": 6, "teleport": "Catherby teleport / Camelot teleport",
     "items": ["Camelot teleport (tab/spellbook)"], "tip": "Camelot TP → loop oost naar patch"},
    {"name": "Falador",         "key": "falador",   "quest": None,
     "order": 7, "teleport": "Explorer's ring teleport / Falador teleport",
     "items": ["Explorer's ring (any)"], "tip": "Patch ten zuiden van Falador"},
    {"name": "Troll Stronghold", "key": "troll",    "quest": "My Arm's Big Adventure",
     "order": 8, "teleport": "Stony basalt / Trollheim teleport",
     "items": ["Stony basalt"], "tip": "TP naar dak Troll Stronghold → trap op naar patch. Geen compost nodig (disease-free)"},
    {"name": "Weiss",           "key": "weiss",     "quest": "Making Friends with My Arm",
     "order": 9, "teleport": "Icy basalt",
     "items": ["Icy basalt"], "tip": "TP direct naast patch. Geen compost nodig (disease-free)"},
]

COMPOST_IDS = {
    "none":        None,
    "compost":     6032,
    "supercompost": 6034,
    "ultracompost": 21483,
    "bottomless":  22997,  # bottomless compost bucket (not consumed)
}

# Average yield per patch: base ~5, ultracompost ~8.7, +10% magic secateurs
# Source: OSRS wiki herb farming
def _herb_yield(compost="ultracompost", secateurs=True, farming_cape=False):
    base = {"none": 5.0, "compost": 6.0, "supercompost": 7.0, "ultracompost": 8.676, "bottomless": 8.676}
    y = base.get(compost, 8.676)
    if secateurs:
        y *= 1.10
    if farming_cape:
        y *= 1.05  # ~5% extra via cape perk
    return round(y, 2)

@app.route("/api/money/herbrun")
def api_herb_run():
    """Bereken winst per herb run met live GE prijzen."""
    try:
        prices = fetch_prices()
        data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}

        compost = flask_request.args.get("compost", "ultracompost")
        secateurs = flask_request.args.get("secateurs", "true") == "true"
        cape = flask_request.args.get("cape", "false") == "true"
        avg_yield = _herb_yield(compost, secateurs, cape)

        # Compost prijs
        compost_price = 0
        cid = COMPOST_IDS.get(compost)
        if cid and compost != "bottomless":
            compost_price = round(_best_price(cid, prices, data_1h, data_5m, "low"))

        herbs = []
        for seed_id, info in HERB_DATA.items():
            herb_id = info["herb"]
            seed_price = round(_best_price(seed_id, prices, data_1h, data_5m, "low"))
            herb_price = round(_best_price(herb_id, prices, data_1h, data_5m, "high"))
            if not seed_price or not herb_price:
                continue
            # Winst per patch = (yield * herb_price) - seed_price - compost_price
            revenue_per_patch = round(avg_yield * herb_price)
            cost_per_patch = seed_price + compost_price
            profit_per_patch = revenue_per_patch - cost_per_patch
            herbs.append({
                "seed_id": seed_id,
                "herb_id": herb_id,
                "name": info["name"],
                "lvl": info["lvl"],
                "seed_price": seed_price,
                "herb_price": herb_price,
                "avg_yield": avg_yield,
                "revenue_patch": revenue_per_patch,
                "cost_patch": cost_per_patch,
                "profit_patch": profit_per_patch,
            })

        herbs.sort(key=lambda h: h["profit_patch"], reverse=True)
        return jsonify({
            "herbs": herbs,
            "avg_yield": avg_yield,
            "compost_price": compost_price,
            "patches": HERB_PATCHES,
        })
    except Exception as e:
        return jsonify({"error": str(e), "herbs": []})

# ─────────────────────────────────────────────
#  BATTLESTAFF CRAFTING CALCULATOR
# ─────────────────────────────────────────────
# Orb ID, Battlestaff (product) ID, crafting level, staff name
STAVES_DATA = [
    {"orb": 567,  "product": 1395, "name": "Water battlestaff",  "lvl": 54, "xp": 100},
    {"orb": 571,  "product": 1399, "name": "Earth battlestaff",  "lvl": 58, "xp": 112.5},
    {"orb": 569,  "product": 1397, "name": "Fire battlestaff",   "lvl": 62, "xp": 125},
    {"orb": 573,  "product": 1401, "name": "Air battlestaff",    "lvl": 66, "xp": 137.5},
]
BATTLESTAFF_ID = 1391  # Gewone battlestaff

@app.route("/api/money/staves")
def api_money_staves():
    """Bereken winst voor battlestaff crafting met live GE prijzen."""
    try:
        prices = fetch_prices()
        data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}

        bstaff_price = round(_best_price(BATTLESTAFF_ID, prices, data_1h, data_5m, "low"))
        # Zaff's daily battlestaves: 7 (geen diary) tot 120 (elite Varrock diary)
        zaff_prices = {"none": 7000, "easy": 7000, "medium": 7000, "hard": 7000, "elite": 7000}
        # Zaff verkoopt voor 7000 GP altijd, hoeveelheid varieert
        zaff_qty = {"none": 0, "easy": 16, "medium": 32, "hard": 64, "elite": 120}

        diary = flask_request.args.get("diary", "elite")
        daily_from_zaff = zaff_qty.get(diary, 0)

        results = []
        for s in STAVES_DATA:
            orb_price = round(_best_price(s["orb"], prices, data_1h, data_5m, "low"))
            sell_price = round(_best_price(s["product"], prices, data_1h, data_5m, "high"))
            if not orb_price or not sell_price:
                continue
            # Winst met GE battlestaff
            cost_ge = bstaff_price + orb_price
            profit_ge = sell_price - cost_ge
            # Winst met Zaff battlestaff (7000 GP)
            cost_zaff = 7000 + orb_price
            profit_zaff = sell_price - cost_zaff
            results.append({
                "name": s["name"],
                "lvl": s["lvl"],
                "orb_id": s["orb"],
                "product_id": s["product"],
                "orb_price": orb_price,
                "bstaff_price": bstaff_price,
                "sell_price": sell_price,
                "cost_ge": cost_ge,
                "profit_ge": profit_ge,
                "cost_zaff": cost_zaff,
                "profit_zaff": profit_zaff,
                "daily_zaff": daily_from_zaff,
                "daily_profit_zaff": profit_zaff * daily_from_zaff,
                "xp": s["xp"], "xp_hr": round(s["xp"] * 2000),
                "afk_time": "30 sec per inv",
            })
        results.sort(key=lambda x: x["profit_zaff"], reverse=True)
        return jsonify({
            "staves": results,
            "bstaff_price": bstaff_price,
            "zaff_price": 7000,
            "zaff_qty": daily_from_zaff,
            "diary": diary,
        })
    except Exception as e:
        return jsonify({"error": str(e), "staves": []})

# ─────────────────────────────────────────────
#  DRAGONHIDE BODIES
# ─────────────────────────────────────────────
DHIDE_DATA = [
    {"hide": 1745, "body": 1135, "name": "Green d'hide body",  "lvl": 63, "hides": 3, "xp": 186},
    {"hide": 2505, "body": 2499, "name": "Blue d'hide body",   "lvl": 71, "hides": 3, "xp": 210},
    {"hide": 2507, "body": 2501, "name": "Red d'hide body",    "lvl": 77, "hides": 3, "xp": 234},
    {"hide": 2509, "body": 2503, "name": "Black d'hide body",  "lvl": 84, "hides": 3, "xp": 258},
]

@app.route("/api/money/dhide")
def api_money_dhide():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        results = []
        for d in DHIDE_DATA:
            hide_price = round(_best_price(d["hide"], prices, data_1h, data_5m, "low"))
            body_price = round(_best_price(d["body"], prices, data_1h, data_5m, "high"))
            if not hide_price or not body_price: continue
            cost = hide_price * d["hides"]
            profit = body_price - cost
            rate = 1500
            results.append({"name": d["name"], "lvl": d["lvl"], "hide_price": hide_price,
                "body_price": body_price, "cost": cost, "profit": profit,
                "product_id": d["body"], "hides_needed": d["hides"],
                "xp": d["xp"], "xp_hr": round(d["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": "50 sec per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  GEM CUTTING
# ─────────────────────────────────────────────
GEM_DATA = [
    {"uncut": 1623, "cut": 1607, "name": "Sapphire",     "lvl": 20, "xp": 50},
    {"uncut": 1621, "cut": 1605, "name": "Emerald",      "lvl": 27, "xp": 67.5},
    {"uncut": 1619, "cut": 1603, "name": "Ruby",         "lvl": 63, "xp": 85},
    {"uncut": 1617, "cut": 1601, "name": "Diamond",      "lvl": 43, "xp": 107.5},
    {"uncut": 1631, "cut": 1615, "name": "Dragonstone",  "lvl": 55, "xp": 137.5},
    {"uncut": 6571, "cut": 6573, "name": "Onyx",         "lvl": 67, "xp": 167.5},
    {"uncut": 19496, "cut": 19493, "name": "Zenyte",     "lvl": 89, "xp": 200},
]

@app.route("/api/money/gems")
def api_money_gems():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        results = []
        for g in GEM_DATA:
            uncut_price = round(_best_price(g["uncut"], prices, data_1h, data_5m, "low"))
            cut_price = round(_best_price(g["cut"], prices, data_1h, data_5m, "high"))
            if not uncut_price or not cut_price: continue
            profit = cut_price - uncut_price
            rate = 2700
            results.append({"name": g["name"], "lvl": g["lvl"], "uncut_price": uncut_price,
                "cut_price": cut_price, "profit": profit,
                "product_id": g["cut"], "xp": g["xp"], "xp_hr": round(g["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": "1 min per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  STRINGING AMULETS
# ─────────────────────────────────────────────
STRING_DATA = [
    {"unstrung": 1673, "strung": 1692, "name": "Gold amulet",        "lvl": 8,  "xp": 4},
    {"unstrung": 1675, "strung": 1694, "name": "Sapphire amulet",    "lvl": 24, "xp": 4},
    {"unstrung": 1677, "strung": 1696, "name": "Emerald amulet",     "lvl": 31, "xp": 4},
    {"unstrung": 1679, "strung": 1698, "name": "Ruby amulet",        "lvl": 50, "xp": 4},
    {"unstrung": 1681, "strung": 1700, "name": "Diamond amulet",     "lvl": 70, "xp": 4},
    {"unstrung": 1683, "strung": 1702, "name": "Dragonstone amulet", "lvl": 80, "xp": 4},
    {"unstrung": 6579, "strung": 6581, "name": "Onyx amulet",        "lvl": 90, "xp": 4},
    {"unstrung": 19501, "strung": 19496, "name": "Zenyte amulet",    "lvl": 98, "xp": 4},
]
BALL_OF_WOOL_ID = 1759

@app.route("/api/money/stringing")
def api_money_stringing():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        wool_price = round(_best_price(BALL_OF_WOOL_ID, prices, data_1h, data_5m, "low"))
        results = []
        for s in STRING_DATA:
            unstrung_price = round(_best_price(s["unstrung"], prices, data_1h, data_5m, "low"))
            strung_price = round(_best_price(s["strung"], prices, data_1h, data_5m, "high"))
            if not unstrung_price or not strung_price: continue
            cost = unstrung_price + wool_price
            profit = strung_price - cost
            rate = 2700
            results.append({"name": s["name"], "lvl": s["lvl"], "unstrung_price": unstrung_price,
                "strung_price": strung_price, "wool_price": wool_price, "cost": cost, "profit": profit,
                "product_id": s["strung"], "xp": s["xp"], "xp_hr": round(s["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": "1 min per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "wool_price": wool_price})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  GOLD JEWELRY
# ─────────────────────────────────────────────
GOLD_BAR_ID = 2357
JEWELRY_DATA = [
    {"product": 1635, "name": "Gold ring",          "lvl": 5,  "gem": None,  "gem_id": None},
    {"product": 1654, "name": "Gold necklace",      "lvl": 6,  "gem": None,  "gem_id": None},
    {"product": 1637, "name": "Sapphire ring",      "lvl": 20, "gem": "Sapphire", "gem_id": 1607},
    {"product": 1656, "name": "Sapphire necklace",  "lvl": 22, "gem": "Sapphire", "gem_id": 1607},
    {"product": 1639, "name": "Emerald ring",       "lvl": 27, "gem": "Emerald",  "gem_id": 1605},
    {"product": 1658, "name": "Emerald necklace",   "lvl": 29, "gem": "Emerald",  "gem_id": 1605},
    {"product": 1641, "name": "Ruby ring",          "lvl": 34, "gem": "Ruby",     "gem_id": 1603},
    {"product": 1660, "name": "Ruby necklace",      "lvl": 40, "gem": "Ruby",     "gem_id": 1603},
    {"product": 1643, "name": "Diamond ring",       "lvl": 43, "gem": "Diamond",  "gem_id": 1601},
    {"product": 1662, "name": "Diamond necklace",   "lvl": 56, "gem": "Diamond",  "gem_id": 1601},
    {"product": 1645, "name": "Dragonstone ring",   "lvl": 55, "gem": "Dragonstone", "gem_id": 1615},
    {"product": 1664, "name": "Dragon necklace",    "lvl": 72, "gem": "Dragonstone", "gem_id": 1615},
    {"product": 6575, "name": "Onyx ring",          "lvl": 67, "gem": "Onyx",     "gem_id": 6573},
    {"product": 6577, "name": "Onyx necklace",      "lvl": 82, "gem": "Onyx",     "gem_id": 6573},
]

@app.route("/api/money/jewelry")
def api_money_jewelry():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        gold_price = round(_best_price(GOLD_BAR_ID, prices, data_1h, data_5m, "low"))
        results = []
        for j in JEWELRY_DATA:
            sell_price = round(_best_price(j["product"], prices, data_1h, data_5m, "high"))
            if not sell_price: continue
            gem_price = 0
            if j["gem_id"]:
                gem_price = round(_best_price(j["gem_id"], prices, data_1h, data_5m, "low"))
                if not gem_price: continue
            cost = gold_price + gem_price
            profit = sell_price - cost
            results.append({"name": j["name"], "lvl": j["lvl"], "gold_price": gold_price,
                "gem": j["gem"] or "Geen", "gem_price": gem_price,
                "sell_price": sell_price, "cost": cost, "profit": profit,
                "product_id": j["product"],
                "profit_hr": profit * 1800, "afk_time": "30 sec per inv"})  # ~1800/hr at furnace
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "gold_price": gold_price})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  GLASS BLOWING
# ─────────────────────────────────────────────
MOLTEN_GLASS_ID = 1775
GLASS_DATA = [
    {"product": 567,  "name": "Unpowered orb",     "lvl": 46, "xp": 52.5},
    {"product": 229,  "name": "Vial",               "lvl": 33, "xp": 35},
    {"product": 4527, "name": "Lantern lens",       "lvl": 49, "xp": 55},
    {"product": 10980, "name": "Empty light orb",   "lvl": 87, "xp": 70},
]

@app.route("/api/money/glass")
def api_money_glass():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        glass_price = round(_best_price(MOLTEN_GLASS_ID, prices, data_1h, data_5m, "low"))
        results = []
        for g in GLASS_DATA:
            sell_price = round(_best_price(g["product"], prices, data_1h, data_5m, "high"))
            if not sell_price: continue
            profit = sell_price - glass_price
            rate = 1800
            results.append({"name": g["name"], "lvl": g["lvl"], "glass_price": glass_price,
                "sell_price": sell_price, "profit": profit,
                "product_id": g["product"], "xp": g["xp"], "xp_hr": round(g["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": "1 min per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "glass_price": glass_price})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  PLANK MAKE (Magic - Lunar)
# ─────────────────────────────────────────────
PLANK_DATA = [
    {"log": 1511, "plank": 960,   "name": "Plank",          "npc_cost": 100,  "lvl": 86},
    {"log": 1521, "plank": 8778,  "name": "Oak plank",      "npc_cost": 250,  "lvl": 86},
    {"log": 1519, "plank": 8780,  "name": "Teak plank",     "npc_cost": 500,  "lvl": 86},
    {"log": 1513, "plank": 8782,  "name": "Mahogany plank", "npc_cost": 1500, "lvl": 86},
]
# Plank Make spell: 2 astral + 1 nature + 15 earth runes
ASTRAL_RUNE_ID = 9075
NATURE_RUNE_ID = 561
EARTH_RUNE_ID = 557

@app.route("/api/money/planks")
def api_money_planks():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        astral = round(_best_price(ASTRAL_RUNE_ID, prices, data_1h, data_5m, "low"))
        nature = round(_best_price(NATURE_RUNE_ID, prices, data_1h, data_5m, "low"))
        earth = round(_best_price(EARTH_RUNE_ID, prices, data_1h, data_5m, "low"))
        spell_cost = (astral * 2) + nature + (earth * 15)
        results = []
        for p in PLANK_DATA:
            log_price = round(_best_price(p["log"], prices, data_1h, data_5m, "low"))
            plank_price = round(_best_price(p["plank"], prices, data_1h, data_5m, "high"))
            if not log_price or not plank_price: continue
            cost = log_price + spell_cost
            profit = plank_price - cost
            rate = 1860  # casts/hr
            results.append({"name": p["name"], "lvl": p["lvl"], "log_price": log_price,
                "plank_price": plank_price, "spell_cost": spell_cost, "cost": cost, "profit": profit,
                "product_id": p["plank"], "xp": 90, "xp_hr": round(90 * rate),
                "profit_hr": profit * rate, "afk_time": "1 min per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "spell_cost": spell_cost,
            "runes": {"astral": astral, "nature": nature, "earth": earth}})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  TAN LEATHER (Magic - Lunar)
# ─────────────────────────────────────────────
TAN_DATA = [
    {"hide": 1739, "leather": 1741, "name": "Soft leather",       "lvl": 78},
    {"hide": 1739, "leather": 1743, "name": "Hard leather",       "lvl": 78},
    {"hide": 1753, "leather": 1745, "name": "Green d'hide leather","lvl": 78},
    {"hide": 1751, "leather": 2505, "name": "Blue d'hide leather", "lvl": 78},
    {"hide": 1749, "leather": 2507, "name": "Red d'hide leather",  "lvl": 78},
    {"hide": 1747, "leather": 2509, "name": "Black d'hide leather","lvl": 78},
]
# Tan Leather: 2 astral + 1 nature per 5 hides

@app.route("/api/money/tan")
def api_money_tan():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        astral = round(_best_price(ASTRAL_RUNE_ID, prices, data_1h, data_5m, "low"))
        nature = round(_best_price(NATURE_RUNE_ID, prices, data_1h, data_5m, "low"))
        spell_cost_per5 = (astral * 2) + nature  # tans 5 hides per cast
        spell_per_hide = spell_cost_per5 / 5
        results = []
        for t in TAN_DATA:
            hide_price = round(_best_price(t["hide"], prices, data_1h, data_5m, "low"))
            leather_price = round(_best_price(t["leather"], prices, data_1h, data_5m, "high"))
            if not hide_price or not leather_price: continue
            cost = hide_price + spell_per_hide
            profit = leather_price - cost
            rate = 5000  # hides/hr
            # 81 magic xp per cast (5 hides), so 16.2 xp per hide
            results.append({"name": t["name"], "lvl": t["lvl"], "hide_price": hide_price,
                "leather_price": leather_price, "spell_cost": round(spell_per_hide),
                "cost": round(cost), "profit": round(profit),
                "product_id": t["leather"], "xp": 16.2, "xp_hr": round(16.2 * rate),
                "profit_hr": round(profit * rate), "afk_time": "Click-intensive"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "spell_per_hide": round(spell_per_hide),
            "runes": {"astral": astral, "nature": nature}})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  CANNONBALLS (Smithing)
# ─────────────────────────────────────────────
STEEL_BAR_ID = 2353
CANNONBALL_ID = 2

@app.route("/api/money/cballs")
def api_money_cballs():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        steel_price = round(_best_price(STEEL_BAR_ID, prices, data_1h, data_5m, "low"))
        cball_price = round(_best_price(CANNONBALL_ID, prices, data_1h, data_5m, "high"))
        if not steel_price or not cball_price:
            return jsonify({"items": [], "error": "no_prices"})
        # 1 steel bar = 4 cannonballs, ~144 bars/hr (super AFK)
        profit_per_bar = (cball_price * 4) - steel_price
        # Met double ammo mould (Giants Foundry): 1 bar = 8 cballs op 50% kans → avg 6
        profit_double = (cball_price * 4.8) - steel_price  # avg met ~20% proc rate
        return jsonify({"items": [{
            "name": "Cannonballs", "lvl": 35,
            "steel_price": steel_price, "cball_price": cball_price,
            "profit_bar": profit_per_bar, "profit_hr": profit_per_bar * 144,
            "balls_per_bar": 4, "bars_per_hr": 144,
            "xp": 25.6, "xp_hr": round(25.6 * 144),
            "afk_time": "2.5 min per inventory",
        }]})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  BLAST FURNACE (Smithing)
# ─────────────────────────────────────────────
# xp = smithing xp per bar, goldsmith_xp = xp met Goldsmith gauntlets (alleen gold)
BF_DATA = [
    {"ore": 444,  "bar": 2353, "name": "Steel bar",      "lvl": 30, "coal": 1, "bars_hr": 5400, "xp": 17.5},
    {"ore": 447,  "bar": 2359, "name": "Mithril bar",    "lvl": 50, "coal": 2, "bars_hr": 4800, "xp": 30},
    {"ore": 449,  "bar": 2361, "name": "Adamantite bar",  "lvl": 70, "coal": 3, "bars_hr": 4200, "xp": 37.5},
    {"ore": 451,  "bar": 2363, "name": "Runite bar",     "lvl": 85, "coal": 4, "bars_hr": 3600, "xp": 50},
    {"ore": 442,  "bar": 2357, "name": "Gold bar",       "lvl": 40, "coal": 0, "bars_hr": 6500, "xp": 22.5, "goldsmith_xp": 56.2},
]
COAL_ID = 453

@app.route("/api/money/blastfurnace")
def api_money_blastfurnace():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        coal_price = round(_best_price(COAL_ID, prices, data_1h, data_5m, "low"))
        goldsmith = flask_request.args.get("goldsmith", "true") == "true"
        coffer_cost = 72000  # 72k/hr voor bf workers (bij 60+ smithing)
        results = []
        for b in BF_DATA:
            ore_price = round(_best_price(b["ore"], prices, data_1h, data_5m, "low"))
            bar_price = round(_best_price(b["bar"], prices, data_1h, data_5m, "high"))
            if not ore_price or not bar_price: continue
            coal_needed = b["coal"]
            cost = ore_price + (coal_price * coal_needed) + round(coffer_cost / b["bars_hr"])
            profit = bar_price - cost
            xp = b.get("goldsmith_xp", b["xp"]) if (goldsmith and "goldsmith_xp" in b) else b["xp"]
            results.append({"name": b["name"], "lvl": b["lvl"], "ore_price": ore_price,
                "bar_price": bar_price, "coal_needed": coal_needed, "coal_price": coal_price,
                "cost": cost, "profit": profit, "product_id": b["bar"],
                "xp": xp, "xp_hr": round(xp * b["bars_hr"]),
                "bars_hr": b["bars_hr"], "profit_hr": profit * b["bars_hr"],
                "goldsmith": goldsmith and "goldsmith_xp" in b,
                "afk_time": "15 sec (active)"})
        results.sort(key=lambda x: x["profit_hr"], reverse=True)
        return jsonify({"items": results, "coal_price": coal_price, "coffer_cost": coffer_cost, "goldsmith": goldsmith})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  COOKING
# ─────────────────────────────────────────────
# stop_burn = level waarop je stopt met branden (met Cooking gauntlets, Hosidius range)
# xp per cook, burn_rate bij ~90 cooking met gauntlets
COOK_DATA = [
    {"raw": 3142, "cooked": 3144, "name": "Karambwan",    "lvl": 30, "rate": 4600, "xp": 190, "stop_burn": 99, "burn_rate_90": 0.05, "gauntlet_stop": 97},
    {"raw": 383,  "cooked": 385,  "name": "Shark",         "lvl": 80, "rate": 1350, "xp": 210, "stop_burn": 99, "burn_rate_90": 0.04, "gauntlet_stop": 94},
    {"raw": 395,  "cooked": 397,  "name": "Sea turtle",    "lvl": 82, "rate": 1350, "xp": 211.3, "stop_burn": 99, "burn_rate_90": 0.05, "gauntlet_stop": 95},
    {"raw": 13439,"cooked": 13441,"name": "Anglerfish",    "lvl": 84, "rate": 1200, "xp": 230, "stop_burn": 99, "burn_rate_90": 0.06, "gauntlet_stop": 96},
    {"raw": 389,  "cooked": 391,  "name": "Manta ray",     "lvl": 91, "rate": 1350, "xp": 216.3, "stop_burn": 99, "burn_rate_90": 0.04, "gauntlet_stop": 97},
    {"raw": 11934,"cooked": 11936,"name": "Dark crab",     "lvl": 90, "rate": 1200, "xp": 215, "stop_burn": 99, "burn_rate_90": 0.05, "gauntlet_stop": 97},
]

@app.route("/api/money/cooking")
def api_money_cooking():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        gauntlets = flask_request.args.get("gauntlets", "true") == "true"
        cook_lvl = int(flask_request.args.get("level", "99"))
        results = []
        for c in COOK_DATA:
            raw_price = round(_best_price(c["raw"], prices, data_1h, data_5m, "low"))
            cooked_price = round(_best_price(c["cooked"], prices, data_1h, data_5m, "high"))
            if not raw_price or not cooked_price: continue
            # Burn rate berekening
            stop = c["gauntlet_stop"] if gauntlets else c["stop_burn"]
            if cook_lvl >= stop:
                burn_rate = 0
            elif cook_lvl >= 90:
                burn_rate = c["burn_rate_90"] * (0.5 if gauntlets else 1)
            else:
                burn_rate = min(0.3, c["burn_rate_90"] * 3 * (0.5 if gauntlets else 1))
            effective_profit = cooked_price - raw_price
            # Branden kost je de raw fish (geen output)
            avg_profit = effective_profit * (1 - burn_rate) - (raw_price * burn_rate)
            results.append({"name": c["name"], "lvl": c["lvl"], "raw_price": raw_price,
                "cooked_price": cooked_price, "profit": round(avg_profit),
                "product_id": c["cooked"], "rate": c["rate"],
                "xp": c["xp"], "xp_hr": round(c["xp"] * c["rate"]),
                "burn_rate": round(burn_rate * 100, 1),
                "gauntlet_stop": c["gauntlet_stop"],
                "profit_hr": round(avg_profit * c["rate"]),
                "afk_time": "1 min per inv" if c["rate"] <= 1500 else "15 sec per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  FLETCHING (Stringing bows)
# ─────────────────────────────────────────────
BOW_STRING_ID = 1777
FLETCH_DATA = [
    {"unstrung": 50,   "strung": 841,  "name": "Maple longbow",    "lvl": 55, "xp": 58.2},
    {"unstrung": 56,   "strung": 847,  "name": "Yew longbow",      "lvl": 70, "xp": 67.5},
    {"unstrung": 62,   "strung": 853,  "name": "Magic longbow",    "lvl": 85, "xp": 83.2},
    {"unstrung": 48,   "strung": 839,  "name": "Maple shortbow",   "lvl": 50, "xp": 50},
    {"unstrung": 54,   "strung": 845,  "name": "Yew shortbow",     "lvl": 65, "xp": 67.5},
    {"unstrung": 60,   "strung": 851,  "name": "Magic shortbow",   "lvl": 80, "xp": 83.2},
]

@app.route("/api/money/fletching")
def api_money_fletching():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        string_price = round(_best_price(BOW_STRING_ID, prices, data_1h, data_5m, "low"))
        results = []
        for f in FLETCH_DATA:
            unstrung_price = round(_best_price(f["unstrung"], prices, data_1h, data_5m, "low"))
            strung_price = round(_best_price(f["strung"], prices, data_1h, data_5m, "high"))
            if not unstrung_price or not strung_price: continue
            cost = unstrung_price + string_price
            profit = strung_price - cost
            rate = 2700
            results.append({"name": f["name"], "lvl": f["lvl"], "unstrung_price": unstrung_price,
                "strung_price": strung_price, "string_price": string_price,
                "cost": cost, "profit": profit, "product_id": f["strung"],
                "xp": f["xp"], "xp_hr": round(f["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": "1 min per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "string_price": string_price})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  BOW CUTTING (Fletching — logs → unstrung bows)
# ─────────────────────────────────────────────
KNIFE_ID = 946  # niet nodig als kosten, speler heeft er 1
BOWCUT_DATA = [
    # log_id, product_id, name, lvl, xp per bow, rate/hr
    {"log": 1517, "product": 48,  "name": "Maple shortbow (u)", "lvl": 50, "xp": 50,   "rate": 1600},
    {"log": 1517, "product": 50,  "name": "Maple longbow (u)",  "lvl": 55, "xp": 58.2, "rate": 1350},
    {"log": 1515, "product": 54,  "name": "Yew shortbow (u)",   "lvl": 65, "xp": 67.5, "rate": 1600},
    {"log": 1515, "product": 56,  "name": "Yew longbow (u)",    "lvl": 70, "xp": 75,   "rate": 1350},
    {"log": 1513, "product": 60,  "name": "Magic shortbow (u)", "lvl": 80, "xp": 83.2, "rate": 1600},
    {"log": 1513, "product": 62,  "name": "Magic longbow (u)",  "lvl": 85, "xp": 91.5, "rate": 1350},
]

@app.route("/api/money/bowcut")
def api_money_bowcut():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        results = []
        for b in BOWCUT_DATA:
            log_price = round(_best_price(b["log"], prices, data_1h, data_5m, "low"))
            bow_price = round(_best_price(b["product"], prices, data_1h, data_5m, "high"))
            if not log_price or not bow_price: continue
            profit = bow_price - log_price
            results.append({"name": b["name"], "lvl": b["lvl"], "log_price": log_price,
                "bow_price": bow_price, "profit": profit, "product_id": b["product"],
                "xp": b["xp"], "rate": b["rate"],
                "xp_hr": round(b["xp"] * b["rate"]),
                "profit_hr": profit * b["rate"], "afk_time": "1 min per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  HERBLORE (Potion making)
# ─────────────────────────────────────────────
# Crafting ALTIJD = 3-dose potion. Decanten bij Bob Barter (GE) = gratis.
# 1000 x 3-dose = 750 x 4-dose (3000 doses / 4 = 750)
VIAL_OF_WATER_ID = 227
HERBLORE_DATA = [
    # grimy herb, clean herb, unf potion, secondary, product_3dose, product_4dose
    {"grimy": 207,  "clean": 257,  "unf": 99,   "secondary": 231,  "p3": 139,  "p4": 2434,
     "name": "Prayer potion",    "lvl": 38, "xp": 87.5,  "herb_name": "Ranarr weed",    "sec_name": "Snape grass"},
    {"grimy": 3051, "clean": 3000,"unf": 3004, "secondary": 223,  "p3": 3026, "p4": 3024,
     "name": "Super restore",    "lvl": 63, "xp": 142.5, "herb_name": "Snapdragon",     "sec_name": "Red spiders' eggs"},
    {"grimy": 3049, "clean": 2998,"unf": 3002, "secondary": 6693, "p3": 6687, "p4": 6685,
     "name": "Saradomin brew",   "lvl": 81, "xp": 180,   "herb_name": "Toadflax",       "sec_name": "Crushed nest"},
    {"grimy": 219,  "clean": 269, "unf": 109,  "secondary": 245,  "p3": 169,  "p4": 2444,
     "name": "Ranging potion",   "lvl": 72, "xp": 162.5, "herb_name": "Dwarf weed",     "sec_name": "Wine of zamorak"},
    {"grimy": 217,  "clean": 2481,"unf": 2483, "secondary": 241,  "p3": 2454, "p4": 2452,
     "name": "Antifire potion",  "lvl": 69, "xp": 157.5, "herb_name": "Lantadyme",      "sec_name": "Dragon scale dust"},
    {"grimy": 209,  "clean": 259, "unf": 101,  "secondary": 221,  "p3": 149,  "p4": 2436,
     "name": "Super attack",     "lvl": 45, "xp": 100,   "herb_name": "Irit leaf",      "sec_name": "Eye of newt"},
    {"grimy": 213,  "clean": 263, "unf": 105,  "secondary": 225,  "p3": 157,  "p4": 2440,
     "name": "Super strength",   "lvl": 55, "xp": 125,   "herb_name": "Kwuarm",         "sec_name": "Limpwurt root"},
    {"grimy": 215,  "clean": 265, "unf": 107,  "secondary": 239,  "p3": 163,  "p4": 2442,
     "name": "Super defence",    "lvl": 66, "xp": 150,   "herb_name": "Cadantine",      "sec_name": "White berries"},
]

# Herb cleaning data: grimy → clean
HERB_CLEAN_DATA = [
    {"grimy": 199,  "clean": 249,  "name": "Guam leaf",      "lvl": 3,   "xp": 2.5},
    {"grimy": 201,  "clean": 251,  "name": "Marrentill",     "lvl": 5,   "xp": 3.8},
    {"grimy": 203,  "clean": 253,  "name": "Tarromin",       "lvl": 11,  "xp": 5},
    {"grimy": 205,  "clean": 255,  "name": "Harralander",    "lvl": 20,  "xp": 6.3},
    {"grimy": 207,  "clean": 257,  "name": "Ranarr weed",    "lvl": 25,  "xp": 7.5},
    {"grimy": 209,  "clean": 259,  "name": "Irit leaf",      "lvl": 40,  "xp": 8.8},
    {"grimy": 211,  "clean": 261,  "name": "Avantoe",        "lvl": 48,  "xp": 10},
    {"grimy": 213,  "clean": 263,  "name": "Kwuarm",         "lvl": 54,  "xp": 11.3},
    {"grimy": 3049, "clean": 2998, "name": "Toadflax",       "lvl": 30,  "xp": 8},
    {"grimy": 3051, "clean": 3000, "name": "Snapdragon",     "lvl": 59,  "xp": 11.8},
    {"grimy": 215,  "clean": 265,  "name": "Cadantine",      "lvl": 65,  "xp": 12.5},
    {"grimy": 217,  "clean": 2481, "name": "Lantadyme",      "lvl": 67,  "xp": 13.1},
    {"grimy": 219,  "clean": 269,  "name": "Dwarf weed",     "lvl": 70,  "xp": 13.8},
    {"grimy": 221,  "clean": 271,  "name": "Torstol",        "lvl": 75,  "xp": 15},
]

@app.route("/api/money/herblore")
def api_money_herblore():
    """Herblore potion making met avg prijzen, 3-dose/4-dose, herb vs unf."""
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        vial_price = round(_best_price(VIAL_OF_WATER_ID, prices, data_1h, data_5m, "avg"))
        qty = int(flask_request.args.get("qty", "1000"))
        results = []
        for p in HERBLORE_DATA:
            herb_price = round(_best_price(p["grimy"], prices, data_1h, data_5m, "avg"))
            unf_price = round(_best_price(p["unf"], prices, data_1h, data_5m, "avg"))
            sec_price = round(_best_price(p["secondary"], prices, data_1h, data_5m, "avg"))
            price_3 = round(_best_price(p["p3"], prices, data_1h, data_5m, "avg"))
            price_4 = round(_best_price(p["p4"], prices, data_1h, data_5m, "avg"))
            if not herb_price or not price_3: continue

            # Methode 1: Herb + vial + secondary → 3-dose
            cost_herb = herb_price + vial_price + sec_price
            profit_3_herb = price_3 - cost_herb

            # Methode 2: Unf potion + secondary → 3-dose (geen vial nodig)
            cost_unf = (unf_price + sec_price) if unf_price else 0
            profit_3_unf = (price_3 - cost_unf) if unf_price else 0

            # Decanten: 1000 x 3-dose → 750 x 4-dose (gratis bij Bob Barter)
            # Revenue per 1000 gemaakt: 750 * price_4
            revenue_4_per1k = round((qty * 0.75) * price_4) if price_4 else 0
            revenue_3_per1k = qty * price_3
            cost_herb_per1k = qty * cost_herb
            cost_unf_per1k = qty * cost_unf if unf_price else 0

            profit_3_herb_1k = revenue_3_per1k - cost_herb_per1k
            profit_4_herb_1k = revenue_4_per1k - cost_herb_per1k
            profit_3_unf_1k = (revenue_3_per1k - cost_unf_per1k) if unf_price else 0
            profit_4_unf_1k = (revenue_4_per1k - cost_unf_per1k) if unf_price else 0

            rate = 2400
            results.append({
                "name": p["name"], "lvl": p["lvl"],
                "herb_name": p["herb_name"], "herb_price": herb_price,
                "sec_name": p["sec_name"], "sec_price": sec_price,
                "unf_price": unf_price, "vial_price": vial_price,
                "price_3": price_3, "price_4": price_4 or 0,
                "cost_herb": cost_herb, "cost_unf": cost_unf,
                "profit_3_herb": profit_3_herb, "profit_3_unf": profit_3_unf,
                # Per-batch (qty)
                "qty": qty,
                "profit_3_herb_batch": profit_3_herb_1k,
                "profit_4_herb_batch": profit_4_herb_1k,
                "profit_3_unf_batch": profit_3_unf_1k,
                "profit_4_unf_batch": profit_4_unf_1k,
                "four_dose_qty": round(qty * 0.75),
                "product_id": p["p3"],
                "xp": p["xp"], "xp_hr": round(p["xp"] * rate),
                "profit_hr_herb": profit_3_herb * rate,
                "profit_hr_unf": profit_3_unf * rate,
                "afk_time": "50 sec per inv",
            })
        results.sort(key=lambda x: x["profit_3_herb"], reverse=True)
        return jsonify({"items": results, "vial_price": vial_price, "qty": qty})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

@app.route("/api/money/herbclean")
def api_money_herbclean():
    """Herb cleaning: grimy → clean voor winst."""
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        results = []
        for h in HERB_CLEAN_DATA:
            grimy_price = round(_best_price(h["grimy"], prices, data_1h, data_5m, "avg"))
            clean_price = round(_best_price(h["clean"], prices, data_1h, data_5m, "avg"))
            if not grimy_price or not clean_price: continue
            profit = clean_price - grimy_price
            rate = 5000  # ~5000 herbs/hr (1-tick cleaning)
            results.append({"name": h["name"], "lvl": h["lvl"],
                "grimy_price": grimy_price, "clean_price": clean_price,
                "profit": profit, "product_id": h["clean"],
                "xp": h["xp"], "xp_hr": round(h["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": "Click-intensive"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

@app.route("/api/money/unfpotions")
def api_money_unfpotions():
    """Unfinished potions maken: herb + vial → unf potion."""
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        vial_price = round(_best_price(VIAL_OF_WATER_ID, prices, data_1h, data_5m, "avg"))
        results = []
        for p in HERBLORE_DATA:
            clean_price = round(_best_price(p["clean"], prices, data_1h, data_5m, "avg"))
            unf_price = round(_best_price(p["unf"], prices, data_1h, data_5m, "avg"))
            if not clean_price or not unf_price: continue
            cost = clean_price + vial_price
            profit = unf_price - cost
            rate = 2400
            results.append({"name": p["name"].replace("potion","").strip() + " potion (unf)",
                "lvl": p["lvl"], "herb_name": p["herb_name"],
                "clean_price": clean_price, "vial_price": vial_price,
                "cost": cost, "sell_price": unf_price,
                "profit": profit, "product_id": p["unf"],
                "xp": 0, "xp_hr": 0,
                "profit_hr": profit * rate, "afk_time": "50 sec per inv"})
        results.sort(key=lambda x: x["profit"], reverse=True)
        return jsonify({"items": results, "vial_price": vial_price})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  RUNECRAFTING
# ─────────────────────────────────────────────
PURE_ESSENCE_ID = 7936
RC_DATA = [
    # rune_id, name, lvl, multi_lvl (level voor 2x runes), xp, rate/hr, afk
    {"rune": 556, "name": "Air rune",     "lvl": 1,  "multi_lvl": 11, "xp": 5,    "rate": 2400, "afk": "Active (running)"},
    {"rune": 558, "name": "Fire rune",    "lvl": 14, "multi_lvl": 35, "xp": 7,    "rate": 2400, "afk": "Active (running)"},
    {"rune": 564, "name": "Cosmic rune",  "lvl": 27, "multi_lvl": 59, "xp": 8,    "rate": 2000, "afk": "Active"},
    {"rune": 561, "name": "Nature rune",  "lvl": 44, "multi_lvl": 91, "xp": 9,    "rate": 1800, "afk": "Active (Abyss)"},
    {"rune": 563, "name": "Law rune",     "lvl": 54, "multi_lvl": 99, "xp": 9.5,  "rate": 1500, "afk": "Active (Trawler)"},
    {"rune": 565, "name": "Death rune",   "lvl": 65, "multi_lvl": 99, "xp": 10,   "rate": 1400, "afk": "Active (Abyss)"},
    {"rune": 566, "name": "Blood rune",   "lvl": 77, "multi_lvl": 99, "xp": 23.8, "rate": 1500, "afk": "2 min per inv"},
    {"rune": 21880, "name": "Wrath rune", "lvl": 95, "multi_lvl": 99, "xp": 8,    "rate": 1200, "afk": "Active"},
]

@app.route("/api/money/runecraft")
def api_money_runecraft():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        ess_price = round(_best_price(PURE_ESSENCE_ID, prices, data_1h, data_5m, "low"))
        rc_lvl = int(flask_request.args.get("level", "99"))
        results = []
        for r in RC_DATA:
            rune_price = round(_best_price(r["rune"], prices, data_1h, data_5m, "high"))
            if not rune_price: continue
            # Multipels: op double level krijg je 2x, op triple 3x, etc.
            multiplier = 1
            if rc_lvl >= r["multi_lvl"]:
                multiplier = max(1, rc_lvl // r["multi_lvl"])
                if multiplier > 4: multiplier = 4  # cap op 4x
            profit = (rune_price * multiplier) - ess_price
            rate = r["rate"]
            results.append({"name": r["name"], "lvl": r["lvl"],
                "rune_price": rune_price, "ess_price": ess_price,
                "multiplier": multiplier, "multi_lvl": r["multi_lvl"],
                "profit": profit, "product_id": r["rune"],
                "xp": r["xp"], "xp_hr": round(r["xp"] * rate),
                "profit_hr": profit * rate, "afk_time": r["afk"]})
        results.sort(key=lambda x: x["profit_hr"], reverse=True)
        return jsonify({"items": results, "ess_price": ess_price, "rc_level": rc_lvl})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  HUNTER (Chinchompas)
# ─────────────────────────────────────────────
HUNTER_DATA = [
    {"product": 9976,  "name": "Grey chinchompa",  "lvl": 53, "rate": 350, "xp": 198.4, "afk": "Click-intensive"},
    {"product": 10033, "name": "Red chinchompa",    "lvl": 63, "rate": 500, "xp": 265,   "afk": "Click-intensive"},
    {"product": 10034, "name": "Black chinchompa",  "lvl": 73, "rate": 600, "xp": 315,   "afk": "Click-intensive (Wilderness)"},
]

@app.route("/api/money/hunter")
def api_money_hunter():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        results = []
        for h in HUNTER_DATA:
            sell_price = round(_best_price(h["product"], prices, data_1h, data_5m, "high"))
            if not sell_price: continue
            profit_hr = sell_price * h["rate"]
            results.append({"name": h["name"], "lvl": h["lvl"],
                "sell_price": sell_price, "product_id": h["product"],
                "rate": h["rate"], "profit": sell_price,
                "xp": h["xp"], "xp_hr": round(h["xp"] * h["rate"]),
                "profit_hr": profit_hr, "afk_time": h["afk"]})
        results.sort(key=lambda x: x["profit_hr"], reverse=True)
        return jsonify({"items": results})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  BIRDHOUSE RUNS
# ─────────────────────────────────────────────
BIRDHOUSE_DATA = [
    {"log": 1521, "name": "Oak birdhouse",      "lvl": 15, "craft_lvl": 15, "seed_slots": 10, "nest_avg": 0.8},
    {"log": 1519, "name": "Teak birdhouse",     "lvl": 25, "craft_lvl": 25, "seed_slots": 10, "nest_avg": 0.9},
    {"log": 1517, "name": "Maple birdhouse",    "lvl": 35, "craft_lvl": 35, "seed_slots": 10, "nest_avg": 1.0},
    {"log": 6332, "name": "Mahogany birdhouse", "lvl": 45, "craft_lvl": 45, "seed_slots": 10, "nest_avg": 1.1},
    {"log": 1515, "name": "Yew birdhouse",      "lvl": 60, "craft_lvl": 50, "seed_slots": 10, "nest_avg": 1.2},
    {"log": 1513, "name": "Magic birdhouse",    "lvl": 75, "craft_lvl": 55, "seed_slots": 10, "nest_avg": 1.3},
    {"log": 19669, "name": "Redwood birdhouse", "lvl": 90, "craft_lvl": 60, "seed_slots": 10, "nest_avg": 1.5},
]
CLOCKWORK_ID = 8792
CHISEL_ID = 1755
HOP_SEEDS = [5305, 5307, 5309, 5311, 5313]  # cheap hop seeds to fill birdhouses
# Nests drop: bird nest (5070-5074) → seeds, rings, or empty. Avg value varies.
BIRD_NEST_AVG_VALUE = 5000  # gemiddelde waarde van een bird nest (seeds + ring drops)

@app.route("/api/money/birdhouse")
def api_money_birdhouse():
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        # Cheapest hop seed
        seed_prices = []
        for sid in HOP_SEEDS:
            p = round(_best_price(sid, prices, data_1h, data_5m, "low"))
            if p: seed_prices.append(p)
        seed_price = min(seed_prices) if seed_prices else 5
        results = []
        for b in BIRDHOUSE_DATA:
            log_price = round(_best_price(b["log"], prices, data_1h, data_5m, "low"))
            if not log_price: continue
            # 4 birdhouses per run, each needs: 1 log + 1 clockwork (reusable) + 10 seeds
            cost_per_house = log_price + (seed_price * b["seed_slots"])
            cost_per_run = cost_per_house * 4
            nests_per_run = round(b["nest_avg"] * 4, 1)
            revenue_per_run = round(BIRD_NEST_AVG_VALUE * nests_per_run)
            profit_per_run = revenue_per_run - cost_per_run
            # Run every 50 min, ~28 runs/day max but realistically 8-12
            runs_per_day = 12
            results.append({"name": b["name"], "lvl": b["lvl"], "craft_lvl": b["craft_lvl"],
                "log_price": log_price, "seed_price": seed_price * b["seed_slots"],
                "cost_run": cost_per_run, "nests_run": nests_per_run,
                "revenue_run": revenue_per_run, "profit_run": profit_per_run,
                "profit_day": profit_per_run * runs_per_day,
                "xp_run": round(b["nest_avg"] * 4 * 500),  # ~500 hunter xp per nest
                "afk_time": "2 min per run (elke 50 min)"})
        results.sort(key=lambda x: x["profit_run"], reverse=True)
        return jsonify({"items": results, "seed_price": seed_price, "nest_value": BIRD_NEST_AVG_VALUE})
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ═════════════════════════════════════════════
#  FARMING XP CALCULATOR
# ═════════════════════════════════════════════
# OSRS Level → Total XP table
LEVEL_XP = [0,0,83,174,276,388,512,650,801,969,1154,1358,1584,1833,2107,2411,2746,3115,3523,3973,4470,
5018,5624,6291,7028,7842,8740,9730,10824,12031,13363,14833,16456,18247,20224,22406,24815,27473,30408,
33648,37224,41171,45529,50339,55649,61512,67983,75127,83014,91721,101333,111945,123660,136594,150872,
166636,184040,203254,224466,247886,273742,302288,333804,368599,407015,449428,496254,547953,605032,
668051,737627,814445,899257,992895,1096278,1210421,1336443,1475581,1629200,1798808,1986068,2192818,
2421087,2673114,2951373,3258594,3597792,3972294,4385776,4842295,5346332,5902831,6517253,7195629,
7944614,8771558,9684577,10692629,11805606,13034431]

# ── TREE DATA ──
# seed = zaad item ID, sapling = sapling item ID (wat je daadwerkelijk plant)
FARM_TREES = [
    {"name": "Oak",    "seed": 5312, "sapling": 5370, "lvl": 15, "xp": 467.3+1356, "growth": "3h 20m", "grow_min": 200,
     "protect_item": 5968, "protect_name": "Basket of tomatoes", "protect_qty": 1},
    {"name": "Willow", "seed": 5313, "sapling": 5371, "lvl": 30, "xp": 1456.5, "growth": "4h 40m", "grow_min": 280,
     "protect_item": 5986, "protect_name": "Basket of apples", "protect_qty": 1},
    {"name": "Maple",  "seed": 5314, "sapling": 5372, "lvl": 45, "xp": 3403.4, "growth": "5h 20m", "grow_min": 320,
     "protect_item": 5396, "protect_name": "Basket of oranges", "protect_qty": 1},
    {"name": "Yew",    "seed": 5315, "sapling": 5373, "lvl": 60, "xp": 7069.9, "growth": "6h 40m", "grow_min": 400,
     "protect_item": 6016, "protect_name": "Cactus spine", "protect_qty": 10},
    {"name": "Magic",  "seed": 5316, "sapling": 5374, "lvl": 75, "xp": 13768.3, "growth": "8h", "grow_min": 480,
     "protect_item": 5974, "protect_name": "Coconut", "protect_qty": 25},
]

FARM_FRUIT_TREES = [
    {"name": "Apple tree",      "seed": 5283, "sapling": 5496, "lvl": 27, "xp": 1199.5, "growth": "16h", "grow_min": 960,
     "protect_item": 5986, "protect_name": "Sweetcorn", "protect_qty": 9},
    {"name": "Banana tree",     "seed": 5284, "sapling": 5497, "lvl": 33, "xp": 1750.5, "growth": "16h", "grow_min": 960,
     "protect_item": 5416, "protect_name": "Basket of apples", "protect_qty": 4},
    {"name": "Orange tree",     "seed": 5285, "sapling": 5498, "lvl": 39, "xp": 2470.2, "growth": "16h", "grow_min": 960,
     "protect_item": 5406, "protect_name": "Basket of strawberries", "protect_qty": 3},
    {"name": "Curry tree",      "seed": 5286, "sapling": 5499, "lvl": 42, "xp": 2906.9, "growth": "16h", "grow_min": 960,
     "protect_item": 5416, "protect_name": "Basket of bananas", "protect_qty": 5},
    {"name": "Pineapple tree",  "seed": 5287, "sapling": 5500, "lvl": 51, "xp": 4605.7, "growth": "16h", "grow_min": 960,
     "protect_item": 5982, "protect_name": "Watermelon", "protect_qty": 10},
    {"name": "Papaya tree",     "seed": 5288, "sapling": 5501, "lvl": 57, "xp": 6146.4, "growth": "16h", "grow_min": 960,
     "protect_item": 5972, "protect_name": "Pineapple", "protect_qty": 10},
    {"name": "Palm tree",       "seed": 5289, "sapling": 5502, "lvl": 68, "xp": 10150.1, "growth": "16h", "grow_min": 960,
     "protect_item": 5972, "protect_name": "Papaya fruit", "protect_qty": 15},
    {"name": "Dragonfruit tree","seed": 22877,"sapling": 22878,"lvl": 81, "xp": 17335, "growth": "16h", "grow_min": 960,
     "protect_item": 5974, "protect_name": "Coconut", "protect_qty": 15},
]

FARM_SPECIAL = [
    {"name": "Calquat tree",    "seed": 5290, "sapling": 5503, "lvl": 72, "xp": 12096, "growth": "21h 20m", "grow_min": 1280,
     "type": "calquat", "protect_item": 6018, "protect_name": "Poison ivy berries", "protect_qty": 8},
    {"name": "Celastrus tree",  "seed": 22869,"sapling": 22870,"lvl": 85, "xp": 14130, "growth": "13h 20m", "grow_min": 800,
     "type": "celastrus", "protect_item": 3138, "protect_name": "Potato cactus", "protect_qty": 8},
    {"name": "Redwood tree",    "seed": 22871,"sapling": 22872,"lvl": 90, "xp": 22450, "growth": "4d 6h 40m", "grow_min": 6400,
     "type": "redwood", "protect_item": 6693, "protect_name": "Dragonfruit", "protect_qty": 6},
    {"name": "Spirit tree",     "seed": 5317, "sapling": 5375, "lvl": 83, "xp": 19301.8, "growth": "2d 10h 40m", "grow_min": 3520,
     "type": "spirit", "protect_item": None, "protect_name": "Monkey nuts + ground teeth + monkey bar", "protect_qty": 1},
    {"name": "Teak tree",       "seed": 21486,"sapling": 21487,"lvl": 35, "xp": 7290, "growth": "3d 13h 20m", "grow_min": 5360,
     "type": "hardwood", "protect_item": 6059, "protect_name": "Limpwurt root", "protect_qty": 15},
    {"name": "Mahogany tree",   "seed": 21488,"sapling": 21489,"lvl": 55, "xp": 15720, "growth": "3d 13h 20m", "grow_min": 5360,
     "type": "hardwood", "protect_item": 3138, "protect_name": "Potato cactus", "protect_qty": 25},
]

# ── PATCH LOCATIONS ──
FARM_PATCHES = {
    "tree": [
        {"name": "Lumbridge",        "key": "lumb",   "quest": None, "lvl": 1},
        {"name": "Varrock",          "key": "varr",   "quest": None, "lvl": 1},
        {"name": "Falador",          "key": "fala",   "quest": None, "lvl": 1},
        {"name": "Taverly",          "key": "tav",    "quest": None, "lvl": 1},
        {"name": "Gnome Stronghold", "key": "gnome",  "quest": None, "lvl": 1},
        {"name": "Farming Guild",    "key": "guild",  "quest": "65 Farming", "lvl": 65},
    ],
    "fruit_tree": [
        {"name": "Gnome Stronghold", "key": "ft_gnome",   "quest": None, "lvl": 1},
        {"name": "Tree Gnome Village","key": "ft_village", "quest": None, "lvl": 1},
        {"name": "Brimhaven",        "key": "ft_brim",    "quest": None, "lvl": 1},
        {"name": "Catherby",         "key": "ft_cath",    "quest": None, "lvl": 1},
        {"name": "Lletya",           "key": "ft_lletya",  "quest": "Regicide", "lvl": 1},
        {"name": "Farming Guild",    "key": "ft_guild",   "quest": "85 Farming", "lvl": 85},
    ],
    "calquat":   [{"name": "Tai Bwo Wannai", "key": "calq", "quest": None, "lvl": 72}],
    "celastrus": [{"name": "Farming Guild",  "key": "cela", "quest": "85 Farming", "lvl": 85}],
    "redwood":   [{"name": "Farming Guild",  "key": "redw", "quest": "90 Farming", "lvl": 90}],
    "spirit":    [
        {"name": "Etceteria",       "key": "sp_etc",   "quest": "The Fremennik Trials", "lvl": 83},
        {"name": "Port Sarim",      "key": "sp_port",  "quest": None, "lvl": 83},
        {"name": "Brimhaven",       "key": "sp_brim",  "quest": None, "lvl": 91},
        {"name": "Farming Guild",   "key": "sp_guild", "quest": "85 Farming", "lvl": 83},
    ],
    "hardwood":  [
        {"name": "Fossil Island 1", "key": "hw1", "quest": "Bone Voyage", "lvl": 1},
        {"name": "Fossil Island 2", "key": "hw2", "quest": "Bone Voyage", "lvl": 1},
        {"name": "Fossil Island 3", "key": "hw3", "quest": "Bone Voyage", "lvl": 1},
    ],
}

@app.route("/api/farming/calc")
def api_farming_calc():
    """Farming XP calculator — 1 gewas per categorie, parallel groei, gecombineerde XP/dag."""
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}

        current_lvl = int(flask_request.args.get("current", "1"))
        target_lvl = int(flask_request.args.get("target", "99"))
        current_lvl = max(1, min(99, current_lvl))
        target_lvl = max(current_lvl + 1, min(99, target_lvl))

        current_xp = LEVEL_XP[current_lvl] if current_lvl < len(LEVEL_XP) else 0
        target_xp = LEVEL_XP[target_lvl] if target_lvl < len(LEVEL_XP) else 13034431
        xp_needed = target_xp - current_xp

        import json as _json
        patches_json = flask_request.args.get("patches", "{}")
        try: active_patches = _json.loads(patches_json)
        except: active_patches = {}

        selections_json = flask_request.args.get("selections", "{}")
        try: selections = _json.loads(selections_json)
        except: selections = {}

        # seed of sapling prijzen gebruiken
        buy_type = flask_request.args.get("buy_type", "sapling")  # default = sapling

        # Speeltijd venster en max runs
        play_start = int(flask_request.args.get("play_start", "8"))   # uur (0-23)
        play_end = int(flask_request.args.get("play_end", "23"))      # uur (0-23)
        max_runs_cap = int(flask_request.args.get("max_runs", "0"))   # 0 = geen cap
        play_start = max(0, min(23, play_start))
        play_end = max(1, min(24, play_end))
        if play_end <= play_start:
            play_end = min(play_start + 1, 24)
        available_hours = play_end - play_start

        # ── Bouw lijst van geselecteerde gewassen ──
        active_items = []

        # Trees — dropdown selectie (1 gewas)
        tree_sel = selections.get("tree", "")
        if tree_sel:
            tree_data = next((t for t in FARM_TREES if t["name"] == tree_sel), None)
            if tree_data:
                patches = FARM_PATCHES.get("tree", [])
                cnt = sum(1 for p in patches if active_patches.get(p["key"], True))
                if cnt > 0:
                    active_items.append({"tree": tree_data, "patches": cnt, "category": "Trees", "patch_type": "tree"})

        # Fruit trees — dropdown selectie (1 gewas)
        fruit_sel = selections.get("fruit_tree", "")
        if fruit_sel:
            tree_data = next((t for t in FARM_FRUIT_TREES if t["name"] == fruit_sel), None)
            if tree_data:
                patches = FARM_PATCHES.get("fruit_tree", [])
                cnt = sum(1 for p in patches if active_patches.get(p["key"], True))
                if cnt > 0:
                    active_items.append({"tree": tree_data, "patches": cnt, "category": "Fruit Trees", "patch_type": "fruit_tree"})

        # Hardwood — dropdown selectie (Teak of Mahogany)
        hw_sel = selections.get("hardwood", "")
        if hw_sel:
            tree_data = next((s for s in FARM_SPECIAL if s["type"] == "hardwood" and s["name"] == hw_sel), None)
            if tree_data:
                patches = FARM_PATCHES.get("hardwood", [])
                cnt = sum(1 for p in patches if active_patches.get(p["key"], True))
                if cnt > 0:
                    active_items.append({"tree": tree_data, "patches": cnt, "category": "Hardwood", "patch_type": "hardwood"})

        # Calquat, Celastrus, Redwood, Spirit — checkbox aan/uit
        for stype in ["calquat", "celastrus", "redwood", "spirit"]:
            if selections.get(stype, False):
                tree_data = next((s for s in FARM_SPECIAL if s["type"] == stype), None)
                if tree_data:
                    patches = FARM_PATCHES.get(stype, [])
                    cnt = sum(1 for p in patches if active_patches.get(p["key"], True))
                    if cnt > 0:
                        active_items.append({"tree": tree_data, "patches": cnt, "category": tree_data["name"], "patch_type": stype})

        # ── Metadata voor frontend dropdowns ──
        meta = {
            "patches": {k: list(v) for k, v in FARM_PATCHES.items()},
            "trees": [{"name": t["name"], "lvl": t["lvl"]} for t in FARM_TREES],
            "fruit_trees": [{"name": t["name"], "lvl": t["lvl"]} for t in FARM_FRUIT_TREES],
            "hardwoods": [{"name": s["name"], "lvl": s["lvl"]} for s in FARM_SPECIAL if s["type"] == "hardwood"],
            "specials": [{"name": s["name"], "type": s["type"], "lvl": s["lvl"]}
                         for s in FARM_SPECIAL if s["type"] not in ("hardwood",)],
        }

        if not active_items:
            return jsonify({
                "current_lvl": current_lvl, "target_lvl": target_lvl,
                "current_xp": current_xp, "target_xp": target_xp,
                "xp_needed": xp_needed, "items": [], "days_needed": 0,
                "total_xp_per_day": 0, "grand_seed": 0, "grand_protect": 0, "grand_total": 0,
                **meta,
            })

        # ── Bereken XP/dag per gewas (realistisch op basis van speeltijd) ──
        schedule_items = []
        for it in active_items:
            tree = it["tree"]; cnt = it["patches"]
            grow_min = tree.get("grow_min", 480)
            grow_hours = grow_min / 60.0
            xp_per_run = tree["xp"] * cnt

            # Realistische runs/dag:
            # 1e run = ochtend (overnight harvest), daarna elke grow_hours een nieuwe
            if grow_hours <= available_hours:
                realistic_runs = 1 + int(available_hours / grow_hours)
            elif grow_hours <= 24:
                realistic_runs = 1  # 1x per dag (groeit overnight)
            else:
                # Langzame bomen (redwood, spirit): 1 run per X dagen
                realistic_runs = round(24.0 / grow_hours, 3)  # bijv. 0.235

            # User cap toepassen
            if max_runs_cap > 0 and realistic_runs > max_runs_cap:
                realistic_runs = max_runs_cap

            runs_per_day = realistic_runs
            xp_per_day = xp_per_run * runs_per_day

            # Schema: wanneer te checken
            run_times = []
            if grow_hours <= available_hours and runs_per_day >= 1:
                t = play_start
                for r in range(int(runs_per_day)):
                    hh = int(t); mm = int((t - hh) * 60)
                    run_times.append(f"{hh:02d}:{mm:02d}")
                    t += grow_hours
                    if t >= play_end: break
            elif grow_hours <= 24:
                run_times.append(f"{play_start:02d}:00")
            else:
                run_times.append(f"elke {math.ceil(grow_hours/24)} dagen")

            # Prijs: seed of sapling (+ toon beide voor vergelijking)
            price_seed = round(_best_price(tree["seed"], prices, data_1h, data_5m, "avg"))
            price_sapling = round(_best_price(tree.get("sapling", tree["seed"]), prices, data_1h, data_5m, "avg"))
            plant_price = price_sapling if buy_type == "sapling" else price_seed

            protect_price = 0
            if tree.get("protect_item"):
                protect_price = round(_best_price(tree["protect_item"], prices, data_1h, data_5m, "avg"))

            it.update({
                "grow_min": grow_min, "growth": tree["growth"],
                "xp_per_run": round(xp_per_run), "runs_per_day": round(runs_per_day, 2),
                "xp_per_day": round(xp_per_day),
                "run_times": run_times,
                "seed_price": plant_price, "price_seed": price_seed, "price_sapling": price_sapling,
                "protect_price_each": protect_price,
                "protect_name": tree.get("protect_name", "-"),
                "protect_qty": tree.get("protect_qty", 0),
                "seed_cost_per_run": plant_price * cnt,
                "protect_cost_per_run": (protect_price * tree.get("protect_qty", 0)) * cnt,
                "name": tree["name"], "lvl": tree["lvl"], "xp_per_tree": tree["xp"],
            })
            it["total_cost_per_run"] = it["seed_cost_per_run"] + it["protect_cost_per_run"]

        total_xp_per_day = sum(i["xp_per_day"] for i in active_items)
        days_needed = math.ceil(xp_needed / total_xp_per_day) if total_xp_per_day > 0 else 0

        # ── Totalen per gewas op basis van de benodigde dagen ──
        results = []
        grand_seed = 0; grand_protect = 0; grand_total = 0
        for it in active_items:
            total_runs = math.ceil(days_needed * it["runs_per_day"])
            trees_needed = total_runs * it["patches"]
            seed_total = it["seed_price"] * trees_needed
            prot_total = (it["protect_price_each"] * it["protect_qty"]) * trees_needed
            cost_total = seed_total + prot_total
            grand_seed += seed_total; grand_protect += prot_total; grand_total += cost_total

            results.append({
                "category": it["category"], "name": it["name"], "lvl": it["lvl"],
                "xp_per_tree": it["xp_per_tree"], "xp_per_run": it["xp_per_run"],
                "xp_per_day": it["xp_per_day"], "growth": it["growth"],
                "grow_min": it["grow_min"], "patches": it["patches"],
                "runs_per_day": it["runs_per_day"], "run_times": it.get("run_times", []),
                "total_runs": total_runs,
                "trees_needed": trees_needed,
                "seed_price": it["seed_price"],
                "price_seed": it["price_seed"], "price_sapling": it["price_sapling"],
                "protect_name": it["protect_name"], "protect_qty": it["protect_qty"],
                "protect_price_each": it["protect_price_each"],
                "seed_cost_run": it["seed_cost_per_run"],
                "protect_cost_run": it["protect_cost_per_run"],
                "total_cost_run": it["total_cost_per_run"],
                "seed_cost_total": seed_total, "protect_cost_total": prot_total,
                "total_cost": cost_total,
                "total_xp": round(it["xp_per_tree"] * trees_needed),
            })

        return jsonify({
            "current_lvl": current_lvl, "target_lvl": target_lvl,
            "current_xp": current_xp, "target_xp": target_xp,
            "xp_needed": xp_needed,
            "total_xp_per_day": round(total_xp_per_day),
            "days_needed": days_needed,
            "items": results,
            "grand_seed": grand_seed, "grand_protect": grand_protect, "grand_total": grand_total,
            "buy_type": buy_type,
            "play_start": play_start, "play_end": play_end, "available_hours": available_hours,
            "max_runs_cap": max_runs_cap,
            **meta,
        })
    except Exception as e:
        return jsonify({"error": str(e), "items": []})

# ─────────────────────────────────────────────
#  HISCORES LOOKUP
# ─────────────────────────────────────────────
SKILL_ORDER = [
    "Overall", "Attack", "Defence", "Strength", "Hitpoints", "Ranged",
    "Prayer", "Magic", "Cooking", "Woodcutting", "Fletching", "Fishing",
    "Firemaking", "Crafting", "Smithing", "Mining", "Herblore", "Agility",
    "Thieving", "Slayer", "Farming", "Runecrafting", "Hunter", "Construction",
]

@app.route("/api/hiscores/<username>")
def api_hiscores(username):
    """Haal skill levels + XP op van de OSRS hiscores."""
    try:
        url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={username}"
        resp = requests.get(url, timeout=8, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 404:
            return jsonify({"error": "Speler niet gevonden", "skills": {}})
        if resp.status_code != 200:
            return jsonify({"error": f"Hiscores API fout ({resp.status_code})", "skills": {}})

        lines = resp.text.strip().split("\n")
        skills = {}
        for i, skill_name in enumerate(SKILL_ORDER):
            if i >= len(lines): break
            parts = lines[i].split(",")
            if len(parts) >= 3:
                rank = int(parts[0]) if parts[0] != "-1" else None
                level = int(parts[1]) if parts[1] != "-1" else 1
                xp = int(parts[2]) if parts[2] != "-1" else 0
                skills[skill_name.lower()] = {"rank": rank, "level": level, "xp": xp}

        return jsonify({"username": username, "skills": skills})
    except Exception as e:
        return jsonify({"error": str(e), "skills": {}})

# ─────────────────────────────────────────────
#  PRICE ALERTS
# ─────────────────────────────────────────────
_price_alerts = []  # [{id, item_id, item_name, direction: 'above'|'below', target_price, active}]

@app.route("/api/alerts", methods=["GET"])
def api_alerts_get():
    return jsonify({"alerts": _price_alerts})

@app.route("/api/alerts", methods=["POST"])
def api_alerts_set():
    data = flask_request.get_json()
    alert = {
        "id": len(_price_alerts) + 1,
        "item_id": data.get("item_id"),
        "item_name": data.get("item_name", ""),
        "direction": data.get("direction", "below"),  # 'above' or 'below'
        "target_price": data.get("target_price", 0),
        "active": True,
        "triggered": False,
    }
    _price_alerts.append(alert)
    return jsonify({"ok": True, "alert": alert})

@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
def api_alerts_delete(alert_id):
    global _price_alerts
    _price_alerts = [a for a in _price_alerts if a["id"] != alert_id]
    return jsonify({"ok": True})

@app.route("/api/alerts/check")
def api_alerts_check():
    """Check alle actieve alerts tegen huidige prijzen."""
    try:
        prices = fetch_prices(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
        triggered = []
        for a in _price_alerts:
            if not a["active"]: continue
            current = round(_best_price(a["item_id"], prices, data_1h, data_5m, "low")) or 0
            if a["direction"] == "below" and current > 0 and current <= a["target_price"]:
                a["triggered"] = True; a["current_price"] = current
                triggered.append(a)
            elif a["direction"] == "above" and current > 0 and current >= a["target_price"]:
                a["triggered"] = True; a["current_price"] = current
                triggered.append(a)
        return jsonify({"triggered": triggered, "total_active": sum(1 for a in _price_alerts if a["active"])})
    except Exception as e:
        return jsonify({"triggered": [], "error": str(e)})

# ─────────────────────────────────────────────
#  PROFIT TRACKER
# ─────────────────────────────────────────────
_profit_log = []  # [{timestamp, method, item, profit, quantity}]

@app.route("/api/profit/log", methods=["POST"])
def api_profit_log():
    data = flask_request.get_json()
    entry = {
        "timestamp": time.time(),
        "method": data.get("method", "manual"),
        "item": data.get("item", ""),
        "profit": data.get("profit", 0),
        "quantity": data.get("quantity", 1),
    }
    _profit_log.append(entry)
    return jsonify({"ok": True})

@app.route("/api/profit/summary")
def api_profit_summary():
    now = time.time()
    day_ago = now - 86400
    week_ago = now - 604800
    today_entries = [e for e in _profit_log if e["timestamp"] >= day_ago]
    week_entries = [e for e in _profit_log if e["timestamp"] >= week_ago]
    today_total = sum(e["profit"] * e["quantity"] for e in today_entries)
    week_total = sum(e["profit"] * e["quantity"] for e in week_entries)
    all_total = sum(e["profit"] * e["quantity"] for e in _profit_log)
    return jsonify({
        "today": today_total, "week": week_total, "all_time": all_total,
        "today_count": len(today_entries), "week_count": len(week_entries),
        "all_count": len(_profit_log), "entries": _profit_log[-50:]  # laatste 50
    })

@app.route("/api/money/alch")
def api_money_alch():
    staff = flask_request.args.get("staff", "fire")
    with market_lock:
        mapping = market.get("mapping", {})
    try:
        prices = fetch_prices(); volumes = fetch_volumes(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
    except:
        return jsonify({"error": "api_error", "bulk": [], "highvalue": [], "rune_prices": {}})

    rune_prices = {}
    for rname, rid in RUNE_IDS.items():
        rune_prices[rname] = round(_best_price(rid, prices, data_1h, data_5m, "low")) or 0

    nature_cost = rune_prices.get("nature", 0)
    fire_cost = rune_prices.get("fire", 0)

    saves_fire = staff in ("fire", "smoke", "steam", "lava")
    bryophyta = staff == "bryophyta"
    effective_nature = nature_cost * (14/15) if bryophyta else nature_cost
    effective_fire = 0 if saves_fire else fire_cost * 5
    cast_cost = effective_nature + effective_fire

    items = []
    for iid, info in mapping.items():
        alch_val = info.get("highalch")
        if not alch_val or alch_val <= 0: continue
        name = info.get("name", "")
        bl = info.get("limit")
        buy_price = _fast_price(iid, prices, data_1h, data_5m, "low")
        if not buy_price or buy_price <= 0: continue
        vol = volumes.get(str(iid), 0)
        if vol < 5: continue
        # Filter: volume < 10% van buy limit → niet weergeven
        if bl and isinstance(bl, int) and bl > 0 and vol < bl * 0.1:
            continue
        profit = alch_val - buy_price - cast_cost
        if profit <= -1000: continue
        items.append({
            "id": iid, "name": name, "buy_price": round(buy_price),
            "alch_value": alch_val, "profit": round(profit),
            "buy_limit": bl if isinstance(bl, int) else None,
            "volume": vol, "cast_cost": round(cast_cost)
        })
    items.sort(key=lambda x: -x["profit"])
    profitable = [i for i in items if i["profit"] > 0]
    # Bulk: buy limit 1000+ (runes, bolts, supplies etc)
    bulk = [i for i in profitable if i["buy_limit"] and i["buy_limit"] >= 1000][:15]
    # High Value: duurdere items, lager volume
    highvalue = [i for i in profitable if i["buy_price"] >= 20000 and i["volume"] >= 20][:15]
    return jsonify({"bulk": bulk, "highvalue": highvalue,
                    "rune_prices": rune_prices,
                    "nature_cost": round(effective_nature), "fire_cost": round(effective_fire),
                    "cast_cost": round(cast_cost), "staff": staff,
                    "rune_breakdown": {"nature": {"qty": 1, "cost": round(effective_nature)},
                                       "fire": {"qty": 5, "cost": round(effective_fire), "saved": saves_fire}}})

@app.route("/api/money/bolts")
def api_money_bolts():
    staff = flask_request.args.get("staff", "none")
    with market_lock:
        mapping = market.get("mapping", {})
    try:
        prices = fetch_prices(); volumes = fetch_volumes(); data_1h = fetch_1h()
        try: data_5m = fetch_5m()
        except: data_5m = {}
    except:
        return jsonify({"error": "api_error", "bolts": [], "rune_prices": {}})

    if not _name_to_id: build_name_map(mapping)
    rune_prices = {}
    for rname, rid in RUNE_IDS.items():
        rune_prices[rname] = round(_best_price(rid, prices, data_1h, data_5m, "low")) or 0

    saved_elements = STAFF_ELEMENTS.get(staff, [])
    results = []
    for be in BOLT_ENCHANTS:
        for variant in ["regular", "dragon"]:
            bolt_name = be["bolt"] if variant == "regular" else be.get("d_bolt", "")
            result_name = be["result"] if variant == "regular" else be.get("d_result", "")
            bolt_id = _name_to_id.get(bolt_name)
            result_id = _name_to_id.get(result_name)
            if not bolt_id or not result_id: continue
            bolt_price = _best_price(bolt_id, prices, data_1h, data_5m, "low")
            result_price = _best_price(result_id, prices, data_1h, data_5m, "high")
            if not bolt_price or not result_price: continue

            # Volumes & buy limit
            buy_vol = volumes.get(str(bolt_id), 0)
            sell_vol = volumes.get(str(result_id), 0)
            bolt_limit = mapping.get(str(bolt_id), {}).get("limit")
            if not isinstance(bolt_limit, int): bolt_limit = None

            rune_cost = 0; rune_detail = []
            for rune, qty in be["runes"].items():
                unit_price = rune_prices.get(rune, 0)
                if rune in saved_elements:
                    rune_detail.append({"rune": rune, "qty": qty, "saved": True, "cost": 0, "unit": round(unit_price)})
                else:
                    c = unit_price * qty
                    rune_cost += c
                    rune_detail.append({"rune": rune, "qty": qty, "saved": False, "cost": round(c), "unit": round(unit_price)})

            cost_10 = bolt_price * 10 + rune_cost
            revenue_10 = result_price * 10
            profit_10 = revenue_10 - cost_10

            # Aanbevolen staf
            best_staff = "none"; best_save = 0
            for sname, selems in STAFF_ELEMENTS.items():
                if sname == "none": continue
                save = sum(rune_prices.get(r, 0) * be["runes"].get(r, 0) for r in selems if r in be["runes"])
                if save > best_save: best_save = save; best_staff = sname

            # Advisory score: combinatie van winst, koop-volume en verkoop-volume
            profit_score = max(0, profit_10) / max(1, abs(profit_10) + 100) * 50
            buy_vol_score = min(buy_vol / 5000, 1) * 25
            sell_vol_score = min(sell_vol / 5000, 1) * 25
            advisory_score = round(profit_score + buy_vol_score + sell_vol_score, 1)
            # Advisory label
            if profit_10 <= 0:
                advisory = "vermijd"
            elif buy_vol < 100 or sell_vol < 100:
                advisory = "risico"
            elif advisory_score >= 60:
                advisory = "top"
            elif advisory_score >= 35:
                advisory = "goed"
            elif advisory_score >= 15:
                advisory = "matig"
            else:
                advisory = "laag"

            results.append({
                "name": result_name, "base_name": bolt_name, "variant": variant,
                "level": be["level"], "bolt_price": round(bolt_price), "result_price": round(result_price),
                "rune_cost": round(rune_cost), "rune_detail": rune_detail,
                "profit_10": round(profit_10), "profit_1": round(profit_10 / 10),
                "cost_10": round(cost_10), "recommended_staff": best_staff,
                "recommended_staff_name": STAFF_NAMES.get(best_staff, best_staff),
                "recommended_save": round(best_save),
                "buy_vol": buy_vol, "sell_vol": sell_vol,
                "buy_limit": bolt_limit,
                "max_profit": round(profit_10 / 10 * bolt_limit) if bolt_limit and profit_10 > 0 else None,
                "advisory": advisory, "advisory_score": advisory_score
            })
    results.sort(key=lambda x: -x["advisory_score"])
    return jsonify({"bolts": results, "rune_prices": rune_prices, "staff": staff})

# ─────────────────────────────────────────────
#  HTML
# ─────────────────────────────────────────────
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OSRS GE Scout</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0d1117; color:#c9d1d9; font-family:-apple-system,BlinkMacSystemFont,'SF Pro',system-ui,sans-serif; }
.app { max-width:1400px; margin:0 auto; padding:16px; }
.app.hidden-behind-splash { display:none; }

/* SPLASH SCREEN */
#splash {
    position:fixed; inset:0; z-index:9999; background:#0d1117;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    transition: opacity 0.4s ease;
}
#splash.fade-out { opacity:0; pointer-events:none; }
#splash .splash-icon {
    width:160px; height:160px; border-radius:28px;
    box-shadow: 0 8px 40px rgba(210,153,34,0.25), 0 0 80px rgba(210,153,34,0.08);
    animation: iconPulse 2.5s ease-in-out infinite;
    margin-bottom:28px;
}
@keyframes iconPulse {
    0%,100% { transform:scale(1); box-shadow: 0 8px 40px rgba(210,153,34,0.25); }
    50% { transform:scale(1.03); box-shadow: 0 12px 50px rgba(210,153,34,0.35); }
}
#splash .splash-title {
    font-size:28px; font-weight:700; color:#c9d1d9; letter-spacing:-0.5px; margin-bottom:6px;
}
#splash .splash-name {
    font-size:18px; font-weight:600; color:#d29922; margin-bottom:24px; min-height:22px;
}
#splash .splash-status {
    font-size:13px; color:#8b949e; margin-bottom:20px; min-height:18px;
    display:flex; align-items:center; gap:8px;
}
#splash .splash-spinner {
    width:14px; height:14px; border:2px solid #30363d; border-top-color:#d29922;
    border-radius:50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform:rotate(360deg); } }
#splash .splash-btn {
    padding:12px 40px; border:none; border-radius:10px;
    font-size:15px; font-weight:600; cursor:pointer; transition:all 0.2s;
    display:none;
}
#splash .splash-btn.btn-go {
    background:#1f6feb; color:#fff;
}
#splash .splash-btn.btn-go:hover { background:#388bfd; transform:scale(1.02); }
#splash .splash-btn.btn-setup {
    background:#238636; color:#fff;
}
#splash .splash-btn.btn-setup:hover { background:#2ea043; transform:scale(1.02); }
#splash .splash-rsn-input {
    padding:10px 16px; border:1px solid #30363d; border-radius:10px;
    background:#161b22; color:#d29922; font-size:16px; font-weight:600;
    text-align:center; width:260px; margin-bottom:16px; display:none;
    outline:none;
}
#splash .splash-rsn-input:focus { border-color:#d29922; box-shadow: 0 0 0 2px rgba(210,153,34,0.2); }
#splash .splash-version {
    position:absolute; bottom:20px; font-size:11px; color:#484f58;
}

/* NAV */
.nav { display:flex; gap:4px; background:#161b22; border:1px solid #30363d; border-radius:12px; padding:6px; margin-bottom:16px; }
.nav-btn { padding:10px 20px; border:none; background:transparent; color:#8b949e; font-size:14px; font-weight:600; cursor:pointer; border-radius:8px; transition:all .15s; }
.nav-btn:hover { color:#c9d1d9; background:rgba(255,255,255,.04); }
.nav-btn.active { background:#1f6feb; color:#fff; }
.page { display:none; }
.page.active { display:block; }

/* HEADER BAR */
.topbar { display:flex; justify-content:space-between; align-items:center; background:#161b22; border:1px solid #30363d; border-radius:12px; padding:14px 20px; margin-bottom:16px; flex-wrap:wrap; gap:12px; }
.topbar .stats { display:flex; gap:20px; font-size:13px; color:#8b949e; flex-wrap:wrap; }
.topbar .stats b { color:#c9d1d9; }
.status { display:flex; align-items:center; gap:6px; font-size:12px; color:#8b949e; }
.dot { width:8px; height:8px; border-radius:50%; background:#3fb950; }
.dot.err { background:#f85149; }
.dot.load { background:#d29922; animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

/* SECTIONS */
.section { background:#161b22; border:1px solid #30363d; border-radius:12px; margin-bottom:14px; overflow:hidden; }
.sh { padding:12px 18px; font-size:14px; font-weight:600; border-bottom:1px solid #30363d; display:flex; align-items:center; gap:8px; }
.sh .cnt { background:rgba(255,255,255,.08); padding:2px 8px; border-radius:10px; font-size:11px; }
.sh.t1 { color:#c9d1d9; } .sh.t2 { color:#bc8cff; } .sh.t3 { color:#d29922; } .sh.t4 { color:#58a6ff; }

table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; padding:8px 10px; color:#8b949e; font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:.5px; border-bottom:1px solid #21262d; }
td { padding:7px 10px; border-bottom:1px solid #21262d; }
tr:hover { background:rgba(255,255,255,.02); }
tr:last-child td { border-bottom:none; }
.gp { font-family:'SF Mono',Menlo,monospace; font-size:12px; }
.up { color:#3fb950; } .dn { color:#f85149; } .st { color:#8b949e; }
.mh { color:#3fb950; font-weight:600; } .mm { color:#d29922; } .ml { color:#f85149; }
.le { color:#d29922; font-style:italic; }
.dg { color:#3fb950; } .db { color:#f85149; } .dn2 { color:#8b949e; }
.dip { background:#0c2d1b; color:#3fb950; padding:1px 5px; border-radius:4px; font-size:10px; }
.empty { padding:20px; text-align:center; color:#484f58; font-size:13px; }
.profit-pos { color:#3fb950; font-weight:600; } .profit-neg { color:#f85149; font-weight:600; }

/* BUTTONS */
.btn { padding:5px 12px; border:none; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; transition:all .15s; }
.btn:hover { filter:brightness(1.15); }
.btn-blue { background:#1f6feb; color:#fff; }
.btn-green { background:#238636; color:#fff; }
.btn-red { background:#da3633; color:#fff; }
.btn-gold { background:#9e6a03; color:#fff; }
.btn-sm { padding:4px 10px; font-size:11px; }

/* MODAL */
.modal-bg { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,.6); z-index:100; justify-content:center; align-items:center; }
.modal-bg.show { display:flex; }
.modal { background:#161b22; border:1px solid #30363d; border-radius:14px; padding:24px; width:420px; max-width:90vw; }
.modal h3 { margin-bottom:16px; font-size:16px; color:#c9d1d9; }
.modal label { display:block; font-size:12px; color:#8b949e; margin-bottom:4px; margin-top:12px; }
.modal input { width:100%; padding:8px 12px; background:#0d1117; border:1px solid #30363d; border-radius:8px; color:#c9d1d9; font-size:14px; font-family:'SF Mono',Menlo,monospace; }
.modal input:focus { outline:none; border-color:#1f6feb; }
.modal .actions { display:flex; gap:8px; margin-top:18px; justify-content:flex-end; }
.modal .info { font-size:12px; color:#8b949e; margin-top:8px; background:#0d1117; padding:8px 12px; border-radius:8px; }

/* SETTINGS */
.settings-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:18px; }
.settings-grid label { font-size:12px; color:#8b949e; display:block; margin-bottom:4px; }
.settings-grid input { width:100%; padding:8px; background:#0d1117; border:1px solid #30363d; border-radius:6px; color:#c9d1d9; font-size:13px; }
.settings-grid input:focus { outline:none; border-color:#1f6feb; }

.footer { text-align:center; color:#484f58; font-size:11px; padding:12px; }
</style>
</head>
<body>

<!-- SPLASH SCREEN -->
<div id="splash">
    <img class="splash-icon" src="data:image/png;base64,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" alt="OSRS GE Scout">
    <div class="splash-title">OSRS GE Scout</div>
    <div class="splash-name" id="splash-name"></div>
    <div id="splash-setup" style="display:none;text-align:center">
        <input class="splash-rsn-input" id="splash-rsn" type="text" placeholder="Vul je RuneScape naam in" style="display:block" autofocus>
        <button class="splash-btn btn-setup" id="splash-setup-btn" style="display:inline-block" onclick="splashSaveRsn()">Start</button>
    </div>
    <div class="splash-status" id="splash-status">
        <div class="splash-spinner"></div>
        <span id="splash-status-text">Marktdata laden...</span>
    </div>
    <button class="splash-btn btn-go" id="splash-go" onclick="dismissSplash()">Doorgaan</button>
    <div class="splash-version" id="app-version-splash"></div>
</div>

<div class="app hidden-behind-splash">

<div class="nav">
    <button class="nav-btn active" onclick="showPage('dashboard')">📈 Dashboard</button>
    <button class="nav-btn" onclick="showPage('orders')">📋 Actieve Orders</button>
    <button class="nav-btn" onclick="showPage('history')">💰 Winst & Verlies</button>
    <button class="nav-btn" onclick="showPage('calc')">🧮 Calculator</button>
    <button class="nav-btn" onclick="showPage('herbs')">🌿 Herb Runs</button>
    <button class="nav-btn" onclick="showPage('money')">💸 Money Methods</button>
    <button class="nav-btn" onclick="showPage('farming')">🌳 Farming Calc</button>
    <button class="nav-btn" onclick="showPage('alerts')">🔔 Price Alerts</button>
    <button class="nav-btn" onclick="showPage('tracker')">📊 Profit Tracker</button>
    <button class="nav-btn" onclick="showPage('settings')">⚙️ Instellingen</button>
    <button class="nav-btn" onclick="showPage('guide')">📖 How To</button>
</div>

<div id="update-banner" style="display:none;background:linear-gradient(90deg,#1a3a2a,#0d2818);border:1px solid #238636;border-radius:8px;padding:10px 18px;margin-bottom:10px;display:none;align-items:center;justify-content:space-between;gap:12px">
    <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:18px">🔄</span>
        <div><b style="color:#3fb950" id="update-title">Update beschikbaar</b><br><span id="update-changelog" style="font-size:11px;color:#8b949e"></span></div>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
        <button onclick="doUpdate()" id="update-btn" style="background:#238636;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600">Update nu</button>
        <button onclick="document.getElementById('update-banner').style.display='none'" style="background:none;color:#484f58;border:none;cursor:pointer;font-size:16px">✕</button>
    </div>
</div>

<div class="topbar">
    <div class="stats">
        <div id="s-account" style="font-weight:600;color:#d29922;display:none"></div>
        <div>Kapitaal: <b id="s-cap">-</b></div>
        <div>In gebruik: <b id="s-used">-</b></div>
        <div>Beschikbaar: <b id="s-avail">-</b></div>
        <div>Actieve trades: <b id="s-active">-</b></div>
    </div>
    <div class="status"><div class="dot" id="s-dot"></div><span id="s-status">Laden...</span><span id="s-refresh" style="margin-left:8px;color:#484f58"></span></div>
</div>

<!-- DASHBOARD -->
<div class="page active" id="page-dashboard">
    <!-- Quick Lookup -->
    <div style="position:relative;margin-bottom:12px">
        <input id="quick-lookup" type="text" placeholder="🔍 Quick Lookup — zoek elk item..." autocomplete="off"
            style="width:100%;padding:10px 14px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:15px;outline:none;transition:border-color .2s"
            onfocus="this.style.borderColor='#58a6ff'" onblur="setTimeout(()=>{this.style.borderColor='#30363d';document.getElementById('ql-results').style.display='none'},200)"
            oninput="quickLookup(this.value)">
        <div id="ql-results" style="display:none;position:absolute;top:44px;left:0;right:0;background:#161b22;border:1px solid #30363d;border-radius:8px;max-height:320px;overflow-y:auto;z-index:999;box-shadow:0 8px 24px rgba(0,0,0,.4)"></div>
    </div>
    <div id="d-portfolio"></div>
    <div id="d-fav"></div><div id="d-bulk"></div><div id="d-tier0"></div><div id="d-tier1"></div><div id="d-tier2"></div><div id="d-tier3"></div><div id="d-tier4"></div><div id="d-tier5"></div>
</div>

<!-- ACTIEVE ORDERS -->
<div class="page" id="page-orders">
    <div id="orders-content"></div>
</div>

<!-- WINST & VERLIES -->
<div class="page" id="page-history">
    <div id="history-content"></div>
</div>

<!-- FLIP CALCULATOR -->
<div class="page" id="page-calc">
    <div class="section">
        <div class="sh t2">🧮 Flip Calculator</div>
        <div style="padding:18px">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:500px">
                <div><label style="font-size:12px;color:#8b949e;display:block;margin-bottom:4px">Koopprijs (GP)</label><input id="calc-buy" type="text" placeholder="bijv. 150k of 1.5m" oninput="updateCalc()" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px"></div>
                <div><label style="font-size:12px;color:#8b949e;display:block;margin-bottom:4px">Verkoopprijs (GP)</label><input id="calc-sell" type="text" placeholder="bijv. 160k of 1.6m" oninput="updateCalc()" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px"></div>
                <div><label style="font-size:12px;color:#8b949e;display:block;margin-bottom:4px">Aantal</label><input id="calc-qty" type="number" placeholder="bijv. 70" value="1" oninput="updateCalc()" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px"></div>
                <div><label style="font-size:12px;color:#8b949e;display:block;margin-bottom:4px">Buy Limit (optioneel)</label><input id="calc-limit" type="number" placeholder="bijv. 70" oninput="updateCalc()" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px"></div>
            </div>
            <div id="calc-result" style="margin-top:20px;padding:18px;background:#161b22;border:1px solid #30363d;border-radius:12px;font-size:14px;color:#c9d1d9;line-height:2"></div>
        </div>
    </div>
</div>

<!-- HERB RUN CALCULATOR -->
<div class="page" id="page-herbs">
    <div class="section">
        <div class="sh t2">🌿 Herb Run Calculator</div>
        <div style="padding:18px">
            <!-- Options -->
            <div style="display:flex;flex-wrap:wrap;gap:14px;align-items:end;margin-bottom:16px">
                <div>
                    <label style="font-size:12px;color:#8b949e;display:block;margin-bottom:4px">Compost</label>
                    <select id="herb-compost" onchange="loadHerbRun()" style="padding:6px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px;cursor:pointer">
                        <option value="ultracompost" selected>Ultracompost</option>
                        <option value="supercompost">Supercompost</option>
                        <option value="compost">Compost</option>
                        <option value="bottomless">Bottomless bucket</option>
                        <option value="none">Geen compost</option>
                    </select>
                </div>
                <div style="display:flex;gap:16px;align-items:center">
                    <label style="font-size:13px;color:#c9d1d9;cursor:pointer;display:flex;align-items:center;gap:6px">
                        <input type="checkbox" id="herb-secateurs" checked onchange="loadHerbRun()" style="accent-color:#3fb950"> Magic secateurs
                    </label>
                    <label style="font-size:13px;color:#c9d1d9;cursor:pointer;display:flex;align-items:center;gap:6px">
                        <input type="checkbox" id="herb-cape" onchange="loadHerbRun()" style="accent-color:#3fb950"> Farming cape
                    </label>
                </div>
            </div>

            <!-- Patches toggle -->
            <div style="margin-bottom:16px">
                <label style="font-size:12px;color:#8b949e;display:block;margin-bottom:8px">Patches (klik om aan/uit te zetten)</label>
                <div id="herb-patches" style="display:flex;flex-wrap:wrap;gap:6px"></div>
            </div>

            <!-- Summary -->
            <div id="herb-summary" style="padding:14px;background:#0d1117;border:1px solid #30363d;border-radius:10px;margin-bottom:16px;display:none"></div>

            <!-- Herb table -->
            <div id="herb-table"></div>

            <!-- Route -->
            <div id="herb-route" style="display:none;margin-top:16px"></div>
        </div>
    </div>
</div>

<!-- MONEY METHODS -->
<div class="page" id="page-money">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
        <div id="mm-magic-level" style="font-size:13px;color:#484f58"></div>
    </div>

    <!-- ═══ MAGIC ═══ -->
    <div style="margin-top:8px;margin-bottom:4px;font-size:11px;font-weight:700;color:#a371f7;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🧙 Magic</div>

    <div class="section"><div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:0 18px;cursor:pointer" onclick="toggleMmSection('alch')"><div class="sh t2" style="margin:0;padding:10px 0">🔥 High Alchemy <span id="alch-toggle" style="font-size:12px;color:#484f58">▼</span></div><div style="display:flex;gap:8px;align-items:center" onclick="event.stopPropagation()"><label style="font-size:11px;color:#8b949e">Staf:</label><select id="alch-staff" onchange="loadAlch()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer"><option value="fire" selected>Staff of fire</option><option value="none">Geen staf</option><option value="bryophyta">Bryophyta's staff</option></select></div></div><div id="alch-body"><div id="alch-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div style="padding:0 18px 6px"><b style="font-size:13px;color:#3fb950">📦 Bulk</b> <span style="font-size:11px;color:#484f58">(limit 1000+)</span></div><div id="alch-bulk" style="padding:0 18px 12px"></div><div style="padding:0 18px 6px"><b style="font-size:13px;color:#58a6ff">💎 High Value</b> <span style="font-size:11px;color:#484f58">(20K+)</span></div><div id="alch-highvalue" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('bolt')"><div class="sh t3" style="margin:0;padding:10px 0">🏹 Bolt Enchanting <span id="bolt-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="bolt-body"><div style="padding:0 18px"><div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><label style="font-size:11px;color:#8b949e">Staf:</label><select id="bolt-staff" onchange="loadBolts()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer"><option value="none">Geen staf</option><option value="fire">Staff of fire</option><option value="water">Staff of water</option><option value="earth">Staff of earth</option><option value="air">Staff of air</option><option value="smoke">Smoke battlestaff</option><option value="steam">Steam battlestaff</option><option value="dust">Dust battlestaff</option><option value="mud">Mud battlestaff</option><option value="lava">Lava battlestaff</option><option value="mist">Mist battlestaff</option></select></div></div><div id="bolt-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div id="bolt-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('planks')"><div class="sh t2" style="margin:0;padding:10px 0">🪵 Plank Make (Lunar) <span id="planks-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="planks-body"><div id="planks-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div id="planks-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('tan')"><div class="sh t3" style="margin:0;padding:10px 0">🐄 Tan Leather (Lunar) <span id="tan-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="tan-body"><div id="tan-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div id="tan-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ CRAFTING ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#d29922;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">✂️ Crafting</div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('staves')"><div class="sh t1" style="margin:0;padding:10px 0">🪄 Battlestaff Crafting <span id="staves-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="staves-body"><div id="staves-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div id="staves-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('dhide')"><div class="sh t2" style="margin:0;padding:10px 0">🐉 Dragonhide Bodies <span id="dhide-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="dhide-body"><div id="dhide-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('gems')"><div class="sh t3" style="margin:0;padding:10px 0">💎 Gem Cutting <span id="gems-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="gems-body"><div id="gems-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('jewelry')"><div class="sh t1" style="margin:0;padding:10px 0">💍 Gold Jewelry <span id="jewelry-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="jewelry-body"><div id="jewelry-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('glass')"><div class="sh t2" style="margin:0;padding:10px 0">🫧 Glass Blowing <span id="glass-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="glass-body"><div id="glass-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('stringing')"><div class="sh t3" style="margin:0;padding:10px 0">📿 Stringing Amulets <span id="stringing-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="stringing-body"><div id="stringing-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ SMITHING ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#58a6ff;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🔨 Smithing</div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('cballs')"><div class="sh t1" style="margin:0;padding:10px 0">💣 Cannonballs <span id="cballs-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="cballs-body"><div id="cballs-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('bf')"><div class="sh t2" style="margin:0;padding:10px 0">🏭 Blast Furnace <span id="bf-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="bf-body"><div id="bf-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div id="bf-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ COOKING ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#3fb950;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🍳 Cooking</div>

    <div class="section"><div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:0 18px;cursor:pointer" onclick="toggleMmSection('cook')"><div class="sh t1" style="margin:0;padding:10px 0">🦈 Cooking Profit <span id="cook-toggle" style="font-size:12px;color:#484f58">▼</span></div><div style="display:flex;gap:12px;align-items:center" onclick="event.stopPropagation()"><label style="font-size:12px;color:#c9d1d9;cursor:pointer;display:flex;align-items:center;gap:4px"><input type="checkbox" id="cook-gauntlets" checked onchange="loadCooking()" style="accent-color:#3fb950"> Cooking gauntlets</label><div><label style="font-size:11px;color:#8b949e">Level:</label> <input id="cook-level" type="number" value="99" min="1" max="99" onchange="loadCooking()" style="width:50px;padding:3px 6px;background:#0d1117;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;font-size:12px"></div></div></div><div id="cook-body"><div id="cook-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ FLETCHING ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#da3633;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🏹 Fletching</div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('bowcut')"><div class="sh t2" style="margin:0;padding:10px 0">🪓 Bow Cutting (logs) <span id="bowcut-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="bowcut-body"><div id="bowcut-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('fletch')"><div class="sh t1" style="margin:0;padding:10px 0">🏹 Stringing Bows <span id="fletch-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="fletch-body"><div id="fletch-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ HERBLORE ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#3fb950;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🧪 Herblore</div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('herblore')"><div class="sh t2" style="margin:0;padding:10px 0">🧪 Potion Making <span id="herblore-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="herblore-body"><div style="padding:8px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><label style="font-size:12px;color:#8b949e">Berekening voor:</label><input id="herb-qty" type="number" value="1000" min="1" style="width:80px;padding:4px 8px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:13px" onchange="loadHerblore()"><span style="font-size:12px;color:#8b949e">potions</span><span style="font-size:11px;color:#484f58">| Prijzen = GE marktprijs | Crafting = altijd 3-dose | Decanten = gratis bij Bob Barter</span></div><div id="herblore-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('herbclean')"><div class="sh t2" style="margin:0;padding:10px 0">🌿 Herb Cleaning <span id="herbclean-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="herbclean-body"><div id="herbclean-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('unfpot')"><div class="sh t2" style="margin:0;padding:10px 0">⚗️ Unfinished Potions <span id="unfpot-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="unfpot-body"><div id="unfpot-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ RUNECRAFTING ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#bc8cff;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🔮 Runecrafting</div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('runecraft')"><div class="sh t2" style="margin:0;padding:10px 0">🔮 Rune Crafting <span id="runecraft-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="runecraft-body"><div style="padding:4px 18px"><label style="font-size:12px;color:#8b949e">RC Level: </label><input id="rc-level" type="number" value="99" min="1" max="99" style="width:60px;padding:4px 8px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:13px" onchange="loadRunecraft()"></div><div id="runecraft-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div><div id="runecraft-table" style="padding:0 18px 18px"></div></div></div>

    <!-- ═══ HUNTER ═══ -->
    <div style="margin-top:16px;margin-bottom:4px;font-size:11px;font-weight:700;color:#d29922;text-transform:uppercase;letter-spacing:1.5px;padding-left:4px">🪤 Hunter</div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('hunter')"><div class="sh t2" style="margin:0;padding:10px 0">🐿️ Chinchompas <span id="hunter-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="hunter-body"><div id="hunter-table" style="padding:0 18px 18px"></div></div></div>

    <div class="section"><div style="padding:0 18px;cursor:pointer" onclick="toggleMmSection('birdhouse')"><div class="sh t2" style="margin:0;padding:10px 0">🏠 Birdhouse Runs <span id="birdhouse-toggle" style="font-size:12px;color:#484f58">▼</span></div></div><div id="birdhouse-body"><div id="birdhouse-table" style="padding:0 18px 18px"></div></div></div>
</div>

<!-- PRICE ALERTS -->
<div class="page" id="page-alerts">
    <div class="section">
        <div class="sh t2">🔔 Price Alerts</div>
        <div style="padding:14px 18px">
            <div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap;margin-bottom:14px">
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Item zoeken</label>
                <input id="alert-search" type="text" placeholder="Bijv. Dragon claws..." style="width:220px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px" oninput="searchAlertItem()"></div>
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Richting</label>
                <select id="alert-dir" style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px"><option value="below">Onder ≤</option><option value="above">Boven ≥</option></select></div>
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Prijs (GP)</label>
                <input id="alert-price" type="number" placeholder="10000" style="width:120px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px"></div>
                <button onclick="addAlert()" style="padding:8px 16px;background:#238636;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600">+ Alert</button>
            </div>
            <div id="alert-search-results" style="margin-bottom:10px"></div>
            <div id="alert-triggered" style="margin-bottom:14px"></div>
            <div id="alert-list"></div>
        </div>
    </div>
</div>

<!-- PROFIT TRACKER -->
<div class="page" id="page-tracker">
    <div class="section">
        <div class="sh t2">📊 Profit Tracker</div>
        <div id="tracker-summary" style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:14px 18px"></div>
    </div>
    <div class="section">
        <div class="sh t1" style="justify-content:space-between">📝 Winst Loggen
            <button onclick="document.getElementById('log-form').style.display=document.getElementById('log-form').style.display==='none'?'':'none'" style="padding:4px 12px;background:#238636;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600">+ Toevoegen</button>
        </div>
        <div id="log-form" style="padding:14px 18px;display:none;border-bottom:1px solid #30363d">
            <div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap">
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Methode</label>
                <input id="log-method" type="text" placeholder="Bijv. Herb Run, Flipping..." style="width:180px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px"></div>
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Item</label>
                <input id="log-item" type="text" placeholder="Optioneel" style="width:150px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px"></div>
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Winst (GP)</label>
                <input id="log-profit" type="number" placeholder="50000" style="width:120px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px"></div>
                <div><label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Aantal</label>
                <input id="log-qty" type="number" value="1" min="1" style="width:80px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:13px"></div>
                <button onclick="logProfit()" style="padding:8px 16px;background:#238636;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600">Opslaan</button>
            </div>
        </div>
        <div id="tracker-log" style="padding:14px 18px"></div>
    </div>
</div>

<!-- INSTELLINGEN -->
<div class="page" id="page-settings">
    <div class="section">
        <div class="sh t2">⭐ Favorieten Beheer</div>
        <div style="padding:14px 18px">
            <label style="font-size:12px;color:#8b949e;display:block;margin-bottom:6px">Zoek een item om toe te voegen</label>
            <input id="fav-search" type="text" placeholder="Bijv. Dragon claws, Bandos..." style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px" oninput="searchItems()">
            <div id="fav-results" style="margin-top:8px"></div>
            <div style="margin-top:14px"><b style="font-size:12px;color:#8b949e">Huidige favorieten:</b></div>
            <div id="fav-list" style="margin-top:6px"></div>
        </div>
    </div>
    <div class="section">
        <div class="sh t1">⚙️ Account & Filter Instellingen</div>
        <div style="padding:14px 18px 0"><label style="font-size:12px;color:#8b949e;display:block;margin-bottom:6px">Account naam (RSN)</label><input id="set-account" type="text" placeholder="Bijv. Zezima" style="width:100%;max-width:280px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#d29922;font-size:14px;font-weight:600"></div>
        <div class="settings-grid" id="settings-form">
            <div><label>Kapitaal (GP)</label><input id="set-capital" type="text" placeholder="bijv. 50m"></div>
            <div><label>Max GE Slots</label><input id="set-slots" type="number"></div>
            <div><label>Min ROI %</label><input id="set-roi" type="number" step="0.1"></div>
            <div><label>Max ROI %</label><input id="set-maxroi" type="number"></div>
            <div><label>Min Koopprijs</label><input id="set-minprice" type="text" placeholder="bijv. 100k"></div>
            <div><label>Min Winst per Trade</label><input id="set-minprofit" type="text" placeholder="bijv. 10k"></div>
            <div><label>Min Volume</label><input id="set-minvol" type="number"></div>
            <div><label>Min Score voor Trade</label><input id="set-minscore" type="number" step="0.1"></div>
            <div><label>Refresh (sec)</label><input id="set-refresh" type="number"></div>
        </div>
        <div style="padding:0 18px 18px;text-align:right">
            <button class="btn btn-blue" onclick="saveSettings()">Opslaan</button>
        </div>
    </div>
    <div class="section" style="border:1px solid #da3633;margin-top:16px">
        <div class="sh" style="background:#da363322;color:#da3633">⚠️ Danger Zone</div>
        <div style="padding:18px;display:flex;align-items:center;justify-content:space-between">
            <div>
                <div style="font-weight:600;color:#c9d1d9;font-size:14px">Account resetten</div>
                <div style="color:#8b949e;font-size:12px;margin-top:4px">Dit verwijdert <b>alle</b> gegevens: actieve orders, trade historie, favorieten en instellingen. Dit kan niet ongedaan worden gemaakt.</div>
            </div>
            <button class="btn btn-red" onclick="resetAccount()" style="white-space:nowrap;margin-left:18px">Reset alles</button>
        </div>
    </div>
</div>

<!-- FARMING CALCULATOR -->
<div class="page" id="page-farming">
    <div class="section">
        <div class="sh t2">🌳 Farming XP Calculator</div>
        <div style="padding:18px">
            <!-- Hiscores Lookup -->
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px;padding:10px 14px;background:#161b22;border:1px solid #30363d;border-radius:8px">
                <button onclick="lookupFarmingLevel()" style="padding:8px 16px;background:#1f6feb;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:12px">📊 Hiscores Lookup</button>
                <span id="farm-lookup-status" style="font-size:12px;color:#8b949e">Haalt je Farming level op via je RSN uit Instellingen</span>
            </div>

            <!-- Level inputs -->
            <div style="display:flex;gap:16px;align-items:end;flex-wrap:wrap;margin-bottom:20px">
                <div>
                    <label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Huidig Level</label>
                    <input id="farm-current" type="number" value="1" min="1" max="98" style="width:80px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px;font-weight:600">
                </div>
                <div>
                    <label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Doel Level</label>
                    <input id="farm-target" type="number" value="99" min="2" max="99" style="width:80px;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px;font-weight:600">
                </div>
                <div>
                    <label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Speeltijd van</label>
                    <input id="farm-play-start" type="number" value="8" min="0" max="23" style="width:60px;padding:8px 10px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px;font-weight:600;text-align:center">
                    <span style="color:#8b949e;font-size:12px">:00</span>
                </div>
                <div>
                    <label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Tot</label>
                    <input id="farm-play-end" type="number" value="23" min="1" max="24" style="width:60px;padding:8px 10px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px;font-weight:600;text-align:center">
                    <span style="color:#8b949e;font-size:12px">:00</span>
                </div>
                <div>
                    <label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Max runs/dag</label>
                    <input id="farm-max-runs" type="number" value="0" min="0" max="20" placeholder="0 = geen limiet" style="width:70px;padding:8px 10px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:14px;text-align:center">
                </div>
                <div>
                    <label style="font-size:11px;color:#8b949e;display:block;margin-bottom:4px">Prijzen</label>
                    <select id="farm-buy-type" style="padding:8px 10px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;font-size:12px">
                        <option value="sapling" selected>Saplings</option>
                        <option value="seed">Seeds</option>
                    </select>
                </div>
                <button onclick="calcFarming()" style="padding:8px 20px;background:#238636;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:13px">Bereken</button>
            </div>

            <!-- Gewas selectie -->
            <div style="font-size:12px;color:#8b949e;margin-bottom:8px;font-weight:600">Gewas Selectie <span style="font-weight:400">(1 gewas per categorie)</span></div>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-bottom:20px">
                <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px">
                    <label style="font-size:11px;color:#58a6ff;font-weight:600;display:block;margin-bottom:4px">🌲 Trees</label>
                    <select id="farm-sel-tree" style="width:100%;padding:6px 10px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:13px">
                        <option value="">— Geen —</option>
                    </select>
                </div>
                <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px">
                    <label style="font-size:11px;color:#58a6ff;font-weight:600;display:block;margin-bottom:4px">🍎 Fruit Trees</label>
                    <select id="farm-sel-fruit" style="width:100%;padding:6px 10px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:13px">
                        <option value="">— Geen —</option>
                    </select>
                </div>
                <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px">
                    <label style="font-size:11px;color:#58a6ff;font-weight:600;display:block;margin-bottom:4px">🪓 Hardwood</label>
                    <select id="farm-sel-hardwood" style="width:100%;padding:6px 10px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:13px">
                        <option value="">— Geen —</option>
                    </select>
                </div>
                <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px">
                    <label style="font-size:11px;color:#58a6ff;font-weight:600;display:block;margin-bottom:6px">Specials</label>
                    <div id="farm-sel-specials"></div>
                </div>
            </div>

            <!-- Patch selectie -->
            <div style="font-size:12px;color:#8b949e;margin-bottom:8px;font-weight:600">Patch Selectie</div>
            <div id="farm-patches" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin-bottom:10px"></div>
        </div>
    </div>

    <div id="farm-results" style="display:none">
        <div class="section">
            <div class="sh t1">📊 XP Overzicht</div>
            <div id="farm-xp-summary" style="padding:14px 18px"></div>
        </div>
        <div class="section">
            <div class="sh t1">🌲 Resultaten — Gecombineerde Farming Runs</div>
            <div id="farm-table" style="padding:14px 18px;overflow-x:auto"></div>
        </div>
    </div>
</div>

<!-- HOW TO / GUIDE -->
<div class="page" id="page-guide">
    <div class="section">
        <div class="sh t2">📖 Hoe werkt de OSRS GE Scout?</div>
        <div style="padding:18px;color:#c9d1d9;font-size:13px;line-height:1.8">
            <p>GE Scout scant automatisch de Grand Exchange API en zoekt items met winstgevende marges. Hij berekent voor elk item een <b>compound score</b> op basis van 7 factoren: ROI, item-leeftijd, fill-speed, trend, margestabiliteit, prijsmomentum en weekdagpatronen.</p>

            <h4 style="color:#58a6ff;margin:18px 0 8px;font-size:14px">🔄 Stap-voor-stap: een flip uitvoeren</h4>
            <p><b>1. Dashboard bekijken</b> — Kies een item uit een van de prijslijsten. Kijk naar de score, ROI, trend en max winst.</p>
            <p><b>2. Koop plaatsen</b> — Klik op <span style="background:#1f6feb;padding:2px 8px;border-radius:4px;font-size:11px">Koop</span> en vul de prijs en hoeveelheid in. Zet dit bod in de Grand Exchange in-game.</p>
            <p><b>3. Koop bevestigen</b> — Zodra je bod gevuld is in-game, ga naar <b>Actieve Orders</b> en klik <span style="background:#1f6feb;padding:2px 8px;border-radius:4px;font-size:11px">Koop Bevestigen</span>. Je kunt ook deels bevestigen als niet alles gevuld is.</p>
            <p><b>4. Verkopen</b> — Als status op <span style="color:#3fb950;font-weight:600">Klaar om te verkopen</span> staat, klik <span style="background:#238636;padding:2px 8px;border-radius:4px;font-size:11px">Verkoop</span>. Vul je verkoopprijs in en bevestig. De tool berekent automatisch de winst na GE tax.</p>
            <p><b>5. Deelverkoop</b> — Je hoeft niet alles tegelijk te verkopen. Verkoop een deel en de rest blijft als actieve order staan.</p>

            <h4 style="color:#58a6ff;margin:18px 0 8px;font-size:14px">💡 Merching Tips</h4>
            <p><b>Koop laag, verkoop hoog</b> — De "Koop" prijs is wat anderen willen verkopen, de "Verkoop" prijs is wat anderen willen kopen. Jij koopt op de lage prijs en verkoopt op de hoge.</p>
            <p><b>GE Tax</b> — Er gaat 2% af van elke verkoop, met een maximum van 5M GP per transactie. Dit is al verrekend in de ROI en winstberekeningen.</p>
            <p><b>Buy limits</b> — Elk item heeft een kooplimiet per 4 uur. Je kunt niet meer kopen dan dit limiet in die periode. Plan je flips hierop.</p>
            <p><b>Hoge score ≠ gegarandeerde winst</b> — De score is een indicatie, geen garantie. Check altijd in-game of de spread realistisch is voordat je koopt.</p>
            <p><b>Spreiding</b> — Zet niet al je geld in 1 item. Gebruik meerdere GE slots voor verschillende items om risico te spreiden.</p>
            <p><b>Tijdstippen</b> — Volumes zijn hoger overdag (UK tijd). Flips gaan sneller als er meer spelers online zijn.</p>
            <p><b>Dips</b> — Items met het <span class="dip" style="font-size:10px;padding:1px 5px">DIP</span> label zijn significant onder hun 7-daags gemiddelde. Dit kan een koopkans zijn.</p>
        </div>
    </div>

    <div class="section">
        <div class="sh t1">📊 Legenda — Dashboard kolommen</div>
        <div style="padding:18px;color:#c9d1d9;font-size:13px;line-height:1.8">
            <table style="width:100%;border-collapse:collapse">
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;font-weight:600;width:140px">Kolom</td><td style="padding:6px 12px">Betekenis</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Koop</td><td style="padding:6px 12px">Huidige laagste verkoopprijs in de GE (dit is wat jij betaalt)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Verkoop</td><td style="padding:6px 12px">Huidige hoogste koopprijs in de GE (dit is waarvoor jij verkoopt)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Limit</td><td style="padding:6px 12px">GE kooplimiet per 4 uur. <span style="color:#d29922">Geel met ~</span> = geschat (niet in API)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Vol/dag</td><td style="padding:6px 12px">Dagelijks handelsvolume — hoeveel stuks per dag verhandeld worden</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">ROI%</td><td style="padding:6px 12px">Return on Investment — winstmarge als percentage van je investering (na 2% tax)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Score</td><td style="padding:6px 12px">Compound score (7 factoren). Hoe hoger, hoe beter de flip-kans. Berekeningsfactoren: ROI, leeftijd, vulsnelheid, trend, margestabiliteit, momentum, weekdag</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Trend</td><td style="padding:6px 12px"><span class="up">↑</span> prijs stijgt, <span class="dn">↓</span> prijs daalt, <span class="st">→</span> stabiel (gebaseerd op 1-uurs data)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Marg.%</td><td style="padding:6px 12px">Margestabiliteit over 7 dagen — hoe vaak was er een positieve marge? <span class="mh">Groen</span> = vaak (70%+), <span class="mm">Geel</span> = matig (40-70%), <span class="ml">Rood</span> = zelden (&lt;40%)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">7d Mom.</td><td style="padding:6px 12px">Prijsmomentum over 7 dagen: <span class="up">⬆⬆</span> sterk stijgend, <span class="up">⬆</span> stijgend, <span class="st">──</span> stabiel, <span class="dn">⬇</span> dalend, <span class="dn">⬇⬇</span> sterk dalend</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Dag</td><td style="padding:6px 12px">Weekdag-effect: <span class="dg">☆ negatief%</span> = goede koopdag (prijs lager dan gemiddeld), <span class="db">✗ positief%</span> = slechte koopdag (prijs hoger)</td></tr>
                <tr><td style="padding:6px 12px;color:#58a6ff">Max winst</td><td style="padding:6px 12px">Maximale winst per flip = kooplimiet × winst per item (na tax)</td></tr>
            </table>
        </div>
    </div>

    <div class="section">
        <div class="sh t3">🏷️ Legenda — Prijslijsten (Tiers)</div>
        <div style="padding:18px;color:#c9d1d9;font-size:13px;line-height:1.8">
            <table style="width:100%;border-collapse:collapse">
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;font-weight:600;width:200px">Lijst</td><td style="padding:6px 12px">Budget range</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">⭐ Favorieten</td><td style="padding:6px 12px">Jouw opgeslagen items — altijd zichtbaar, ook bij negatieve marge</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">📦 Bulk Items</td><td style="padding:6px 12px">Buy limit 1000+ — runes, bolts, supplies. Groot volume, lage marge per stuk</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">💎 High Value Items</td><td style="padding:6px 12px">Duurdere items (20K+) — hogere marge per cast</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">💰 100K – 500K</td><td style="padding:6px 12px">Mid-range items</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">💎 500K – 5M</td><td style="padding:6px 12px">Hogere waarde items met goede marges</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">👑 5M – 10M</td><td style="padding:6px 12px">Premium items</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px">🏆 10M – 100M</td><td style="padding:6px 12px">High-end items</td></tr>
                <tr><td style="padding:6px 12px">🌟 100M+</td><td style="padding:6px 12px">Ultra-premium items — altijd zichtbaar, ook bij negatieve marge</td></tr>
            </table>
        </div>
    </div>

    <div class="section">
        <div class="sh t4">⚙️ Legenda — Instellingen</div>
        <div style="padding:18px;color:#c9d1d9;font-size:13px;line-height:1.8">
            <table style="width:100%;border-collapse:collapse">
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;font-weight:600;width:180px">Instelling</td><td style="padding:6px 12px">Wat doet het?</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Kapitaal</td><td style="padding:6px 12px">Je totale beschikbare GP. Wordt bijgewerkt bij kopen/verkopen.</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Max GE Slots</td><td style="padding:6px 12px">Hoeveel GE slots je gebruikt (standaard 8, members)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Min ROI %</td><td style="padding:6px 12px">Minimale return — filtert items met te lage marge</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Max ROI %</td><td style="padding:6px 12px">Maximale return — filtert verdacht hoge marges (manipulatie/inactief)</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Min Koopprijs</td><td style="padding:6px 12px">Minimale itemprijs — filtert goedkope junk items</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Min Winst per Trade</td><td style="padding:6px 12px">Minimale winst per flip in GP — filtert items die te weinig opleveren</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Min Volume</td><td style="padding:6px 12px">Minimaal dagelijks handelsvolume — filtert illiquide items</td></tr>
                <tr style="border-bottom:1px solid #21262d"><td style="padding:6px 12px;color:#58a6ff">Min Score</td><td style="padding:6px 12px">Minimale compound score om in de lijst te verschijnen</td></tr>
                <tr><td style="padding:6px 12px;color:#58a6ff">Refresh</td><td style="padding:6px 12px">Hoe vaak de pagina automatisch ververst (in seconden)</td></tr>
            </table>
        </div>
    </div>
</div>

<!-- BUY MODAL -->
<div class="modal-bg" id="buy-modal">
    <div class="modal">
        <h3>📦 Koop Order Plaatsen</h3>
        <div id="buy-item-name" style="font-weight:600;margin-bottom:4px"></div>
        <div class="info" id="buy-info"></div>
        <label>Koopprijs per stuk (GP)</label>
        <input id="buy-price" type="text" placeholder="bijv. 150k of 1.5m">
        <label>Aantal</label>
        <input id="buy-qty" type="number" placeholder="bijv. 70">
        <div style="font-size:12px;color:#8b949e;margin-top:8px">Totaal: <b id="buy-total">0</b> GP</div>
        <div class="actions">
            <button class="btn btn-red btn-sm" onclick="closeBuyModal()">Annuleer</button>
            <button class="btn btn-gold" onclick="submitBuy()">Koop Plaatsen</button>
        </div>
    </div>
</div>

<!-- SELL MODAL -->
<div class="modal-bg" id="sell-modal">
    <div class="modal">
        <h3>💰 Verkoop Order</h3>
        <div id="sell-item-name" style="font-weight:600;margin-bottom:4px"></div>
        <div class="info" id="sell-info"></div>
        <label>Verkoopprijs per stuk (GP)</label>
        <input id="sell-price" type="text" placeholder="bijv. 180k of 1.8m">
        <label>Aantal verkocht</label>
        <input id="sell-qty" type="number" placeholder="bijv. 70">
        <div style="font-size:12px;color:#8b949e;margin-top:8px" id="sell-calc"></div>
        <div class="actions">
            <button class="btn btn-red btn-sm" onclick="closeSellModal()">Annuleer</button>
            <button class="btn btn-green" onclick="submitSell()">Verkoop Bevestigen</button>
        </div>
    </div>
</div>

<!-- ITEM DETAIL MODAL -->
<div class="modal-bg" id="detail-modal">
    <div class="modal" style="max-width:1200px;width:95vw;max-height:90vh;overflow-y:auto">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div style="display:flex;align-items:center;gap:12px">
                <img id="detail-icon" src="" alt="" style="width:40px;height:40px;display:none;image-rendering:pixelated;border-radius:4px;background:#161b22;padding:2px">
                <h3 id="detail-title" style="margin:0">Item Details</h3>
            </div>
            <button onclick="document.getElementById('detail-modal').classList.remove('show')" style="background:none;border:none;color:#8b949e;font-size:22px;cursor:pointer">✕</button>
        </div>
        <div id="detail-stats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px"></div>
        <div id="detail-range-btns" style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap"></div>
        <canvas id="detail-chart" style="width:100%;height:450px;background:#0d1117;border-radius:8px"></canvas>
        <div id="detail-range-stats" style="margin-top:12px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px"></div>
    </div>
</div>

<!-- CONFIRM BUY MODAL -->
<div class="modal-bg" id="confirm-buy-modal">
    <div class="modal">
        <h3>✅ Koop Bevestigen</h3>
        <div id="cb-item-name" style="font-weight:600;margin-bottom:4px"></div>
        <div class="info" id="cb-info"></div>
        <label>Hoeveel items zijn er gekocht?</label>
        <input id="cb-qty" type="number" placeholder="bijv. 70">
        <div style="font-size:11px;color:#8b949e;margin-top:6px">Vul het werkelijke aantal in. Niet-gevulde items worden teruggestort naar je kapitaal.</div>
        <div class="actions">
            <button class="btn btn-red btn-sm" onclick="closeConfirmBuy()">Annuleer</button>
            <button class="btn btn-blue" onclick="submitConfirmBuy()">Bevestig Koop</button>
        </div>
    </div>
</div>

<div class="footer" id="app-version-footer"></div>
</div>

<script>
let currentBuyItem = null;
let currentSellTrade = null;
let favorites = [];

// FAVORITES
async function loadFavorites() {
    favorites = await (await fetch('/api/favorites')).json();
}

// NAV
function showPage(p) {
    document.querySelectorAll('.page').forEach(e => e.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(e => e.classList.remove('active'));
    document.getElementById('page-' + p).classList.add('active');
    event.target.classList.add('active');
    if (p === 'orders') loadOrders();
    if (p === 'history') loadHistory();
    if (p === 'settings') loadSettings();
    if (p === 'herbs') loadHerbRun();
    if (p === 'money') loadMoneyMethods();
    if (p === 'farming') initFarmingCalc();
    if (p === 'alerts') loadAlerts();
    if (p === 'tracker') loadTracker();
}

// FORMAT
function gp(n) {
    if (n == null) return '?'; n = Math.round(n);
    if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e5) return (n/1e3).toFixed(2) + 'K';
    return n.toLocaleString();
}
function gpExact(n) { return n != null ? Math.round(n).toLocaleString() : '?'; }
function parseGP(v) {
    if (typeof v === 'number') return v;
    if (!v || typeof v !== 'string') return 0;
    v = v.trim().replace(/,/g, '.').replace(/\s/g, '');
    let m = v.match(/^([0-9]*\.?[0-9]+)\s*(k|m|b)?$/i);
    if (!m) return parseFloat(v) || 0;
    let n = parseFloat(m[1]);
    let s = (m[2] || '').toLowerCase();
    if (s === 'k') n *= 1000;
    else if (s === 'm') n *= 1000000;
    else if (s === 'b') n *= 1000000000;
    return Math.round(n);
}
function trend(t) { return t==='up'?'<span class="up">↑</span>':t==='down'?'<span class="dn">↓</span>':'<span class="st">→</span>'; }
function mom(m) { return {strong_up:'<span class="up">⬆⬆</span>',up:'<span class="up">⬆</span>',stable:'<span class="st">──</span>',down:'<span class="dn">⬇</span>',strong_down:'<span class="dn">⬇⬇</span>'}[m]||'<span class="st">?</span>'; }
function marg(f) { if(f<=0)return'–'; let p=Math.round(f*100)+'%'; return f>=.7?`<span class="mh">${p}</span>`:f>=.4?`<span class="mm">${p}</span>`:`<span class="ml">${p}</span>`; }
function dayB(p) { return p<=-0.5?`<span class="dg">☆ ${p.toFixed(1)}%</span>`:p>=0.5?`<span class="db">✗ +${p.toFixed(1)}%</span>`:`<span class="dn2">${p>=0?'+':''}${p.toFixed(1)}%</span>`; }
function limitB(l,e) { return e?`<span class="le">~${l}</span>`:`${l}`; }

// TOPBAR
async function refreshTopbar() {
    let r = await fetch('/api/settings'); let s = await r.json();
    let accEl = document.getElementById('s-account');
    if (s.account_name) { accEl.textContent = s.account_name; accEl.style.display = ''; }
    else { accEl.style.display = 'none'; }
    document.getElementById('s-cap').textContent = gp(s.capital);
    document.getElementById('s-used').textContent = gp(s.used);
    document.getElementById('s-avail').textContent = gp(s.available);
    let trades = await (await fetch('/api/trades')).json();
    document.getElementById('s-active').textContent = trades.length + '/' + s.max_slots;
}

// DASHBOARD
const DEFAULT_TIER_LIMIT = 8;
let tierLimits = {};

function getTierLimit(tierKey) {
    if (!tierKey) return 9999;
    if (!tierLimits[tierKey]) tierLimits[tierKey] = DEFAULT_TIER_LIMIT;
    return tierLimits[tierKey];
}

function loadMoreTier(tierKey) {
    tierLimits[tierKey] = (tierLimits[tierKey] || DEFAULT_TIER_LIMIT) * 2;
    refreshDashboard();
}

function showLessTier(tierKey) {
    tierLimits[tierKey] = DEFAULT_TIER_LIMIT;
    refreshDashboard();
}

function renderTier(el, cls, icon, label, items, tierKey) {
    if (!items.length) { el.innerHTML = ''; return; }
    let limit = getTierLimit(tierKey);
    let shown = items.slice(0, limit);
    let hasMore = items.length > limit;
    let isExpanded = tierKey && tierLimits[tierKey] && tierLimits[tierKey] > DEFAULT_TIER_LIMIT;
    let h = `<div class="section"><div class="sh ${cls}">${icon} ${label} <span class="cnt">${shown.length}${hasMore ? '/' + items.length : ''}</span></div><table><tr>
        <th>#</th><th>Item</th><th>Koop</th><th>Verkoop</th><th>Limit</th><th>Vol/dag</th><th>ROI%</th><th>Score</th><th>Trend</th><th>Marg.%</th><th>7d Mom.</th><th>Dag</th><th>Max winst</th><th></th></tr>`;
    shown.forEach((o,i) => {
        let dip = o.in_dip ? ' <span class="dip">DIP</span>' : '';
        let isFav = favorites.includes(o.name);
        let starCls = isFav ? 'color:#d29922' : 'color:#484f58';
        let starBtn = `<span style="cursor:pointer;font-size:16px;${starCls}" onclick="toggleFav('${o.name.replace(/'/g, "\\'")}')">★</span> `;
        let roiCls = o.roi < 0 ? 'dn' : '';
        h += `<tr>
            <td>${i+1}</td><td>${starBtn}<span style="cursor:pointer;color:#58a6ff;text-decoration:none" onclick="openItemDetail(${o.id},'${o.name.replace(/'/g,"\\'")}')">${o.name}</span>${dip}</td><td class="gp">${gp(o.buy_price)}</td><td class="gp">${gp(o.sell_price)}</td>
            <td>${limitB(o.buy_limit,o.limit_estimated)}</td><td>${o.volume.toLocaleString()}</td><td class="${roiCls}">${o.roi}%</td><td>${o.score}</td><td>${trend(o.trend)}</td>
            <td>${marg(o.margin_freq)}</td><td>${mom(o.momentum)}</td><td>${dayB(o.today_pct)}</td><td class="gp">${gp(o.profit_flip)}/flip</td>
            <td><button class="btn btn-gold btn-sm" onclick='openBuyModal(${JSON.stringify(o).replace(/'/g,"&#39;")})'>Koop</button></td></tr>`;
    });
    h += '</table>';
    if (tierKey) {
        h += `<div style="text-align:center;padding:10px;display:flex;gap:8px;justify-content:center">`;
        if (hasMore) h += `<button class="btn btn-blue btn-sm" onclick="loadMoreTier('${tierKey}')">Meer laden</button>`;
        if (isExpanded) h += `<button class="btn btn-sm" style="background:#30363d;color:#8b949e" onclick="showLessTier('${tierKey}')">Minder tonen</button>`;
        h += `</div>`;
    }
    el.innerHTML = h + '</div>';
}

async function refreshDashboard() {
    await loadFavorites();
    let r = await fetch('/api/market'); let d = await r.json();
    document.getElementById('s-status').textContent = d.status;
    document.getElementById('s-refresh').textContent = d.last_refresh ? `#${d.iteration} @ ${d.last_refresh}` : '';
    let dot = document.getElementById('s-dot');
    dot.className = 'dot' + (d.error?' err':(d.status==='Scannen...'?' load':''));
    // Favorites — altijd tonen, uit all_items (geen filters)
    renderTier(document.getElementById('d-fav'), 't2', '⭐', 'FAVORIETEN', d.fav_items||[], null);
    // Tiers
    renderTier(document.getElementById('d-bulk'), 't1', '📦', 'BULK ITEMS — Limit 1000+ (runes, bolts, supplies)', d.bulk||[], 'bulk');
    renderTier(document.getElementById('d-tier0'), 't1', '🪙', 'LOW VALUE — Items < 100K', d.tier0||[], 'tier0');
    renderTier(document.getElementById('d-tier1'),'t1','⚔️','MID VALUE — Items 100K-500K',d.tier1||[],'tier1');
    renderTier(document.getElementById('d-tier2'),'t2','💎','HIGH VALUE — Items 500K-5M',d.tier2||[],'tier2');
    renderTier(document.getElementById('d-tier3'),'t3','🔥','ELITE — Items 5M-10M',d.tier3||[],'tier3');
    renderTier(document.getElementById('d-tier4'),'t4','👑','LEGENDARY — Items 10M-100M',d.tier4||[],'tier4');
    renderTier(document.getElementById('d-tier5'),'t4','💀','GOD TIER — Items 100M+',d.tier5||[],'tier5');
    refreshTopbar();
    renderPortfolio();
}

// FAVORITES
async function toggleFav(name) {
    await fetch('/api/favorites/toggle', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
    refreshDashboard();
}

// BUY MODAL
function openBuyModal(item) {
    currentBuyItem = item;
    document.getElementById('buy-item-name').textContent = item.name;
    document.getElementById('buy-info').innerHTML = `Marktprijs: <b>${gpExact(item.buy_price)}</b> GP (low) — <b>${gpExact(item.sell_price)}</b> GP (high)<br>Buy limit: ${item.buy_limit} | Volume: ${item.volume.toLocaleString()}/dag | ROI: ${item.roi}%`;
    document.getElementById('buy-price').value = item.buy_price;
    document.getElementById('buy-qty').value = item.buy_limit;
    updateBuyTotal();
    document.getElementById('buy-modal').classList.add('show');
}
function closeBuyModal() { document.getElementById('buy-modal').classList.remove('show'); }
function updateBuyTotal() {
    let p = parseGP(document.getElementById('buy-price').value);
    let q = parseInt(document.getElementById('buy-qty').value) || 0;
    document.getElementById('buy-total').textContent = (p * q).toLocaleString();
}
document.getElementById('buy-price').addEventListener('input', updateBuyTotal);
document.getElementById('buy-qty').addEventListener('input', updateBuyTotal);

async function submitBuy() {
    let price = parseGP(document.getElementById('buy-price').value);
    let qty = parseInt(document.getElementById('buy-qty').value);
    if (!price || !qty) return alert('Vul prijs en aantal in');
    await fetch('/api/buy', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({...currentBuyItem, buy_price: price, quantity: qty})});
    closeBuyModal();
    refreshDashboard();
}

// ORDERS PAGE
async function loadOrders() {
    let trades = await (await fetch('/api/trades_live')).json();
    let el = document.getElementById('orders-content');
    if (!trades.length) { el.innerHTML = '<div class="section"><div class="empty">Geen actieve orders</div></div>'; return; }
    let h = `<div class="section"><div class="sh t1">📋 Actieve Orders (${trades.length})</div><table><tr>
        <th>Item</th><th>Status</th><th>Koopprijs</th><th>Aantal</th><th>Totaal</th><th>Adv. Verkoop</th><th>Pot. Winst</th><th>ROI%</th><th>Trend</th><th>Marg.%</th><th>Gestart</th><th></th></tr>`;
    trades.forEach(t => {
        let age = Math.round((Date.now() - new Date(t.opened_at).getTime()) / 60000);
        let ageStr = age < 60 ? age + 'm' : Math.round(age/60) + 'u';
        let statusColor = t.status === 'KOPEN' ? '#d29922' : '#3fb950';
        let statusText = t.status === 'KOPEN' ? 'Wacht op koop' : 'Klaar om te verkopen';
        let liveSell = t.live_sell_price ? `<span class="up gp">${gpExact(t.live_sell_price)}</span>` : '–';
        let liveProfit = t.live_profit != null ? `<span class="${t.live_profit >= 0 ? 'profit-pos' : 'profit-neg'}">${gp(t.live_profit)}</span>` : '–';
        let liveRoi = t.live_profit_pct != null ? `${t.live_profit_pct}` : (t.live_roi ? t.live_roi.toFixed(1) : '–');
        let liveTrend = trend(t.live_trend || t.trend || 'stable');
        let liveMarg = marg(t.live_margin_freq != null ? t.live_margin_freq : (t.margin_freq || 0));
        let btns = '';
        if (t.status === 'KOPEN') {
            btns = `<button class="btn btn-blue btn-sm" onclick='openConfirmBuy(${JSON.stringify(t).replace(/'/g,"&#39;")})'>Koop Bevestigen</button> `;
        } else {
            btns = `<button class="btn btn-green btn-sm" onclick='openSellModal(${JSON.stringify(t).replace(/'/g,"&#39;")})'>Verkoop</button> `;
        }
        btns += `<button class="btn btn-red btn-sm" onclick="cancelTrade('${t.id}')">Annuleer</button>`;
        h += `<tr>
            <td>${t.name}</td><td style="color:${statusColor};font-weight:600;font-size:11px">${statusText}</td>
            <td class="gp">${gpExact(t.buy_price)}</td><td>${t.quantity.toLocaleString()}x</td>
            <td class="gp">${gp(t.total_cost)}</td><td>${liveSell}</td><td>${liveProfit}</td>
            <td>${liveRoi}</td><td>${liveTrend}</td>
            <td>${liveMarg}</td><td>${ageStr} geleden</td>
            <td>${btns}</td></tr>`;
    });
    el.innerHTML = h + '</table></div>';
}

// CONFIRM BUY MODAL
let currentConfirmTrade = null;
function openConfirmBuy(trade) {
    currentConfirmTrade = trade;
    document.getElementById('cb-item-name').textContent = trade.name;
    document.getElementById('cb-info').innerHTML = `Koop order: <b>${gpExact(trade.buy_price)}</b> GP × ${trade.quantity}x = <b>${gpExact(trade.total_cost)}</b> GP`;
    document.getElementById('cb-qty').value = trade.quantity;
    document.getElementById('confirm-buy-modal').classList.add('show');
}
function closeConfirmBuy() { document.getElementById('confirm-buy-modal').classList.remove('show'); }
async function submitConfirmBuy() {
    let qty = parseInt(document.getElementById('cb-qty').value);
    if (!qty || qty < 0) return alert('Vul een geldig aantal in');
    if (qty > currentConfirmTrade.quantity) return alert('Kan niet meer zijn dan besteld');
    await fetch('/api/confirm_buy', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({trade_id: currentConfirmTrade.id, filled_quantity: qty})});
    closeConfirmBuy();
    loadOrders(); refreshTopbar();
}

// SELL MODAL
function openSellModal(trade) {
    currentSellTrade = trade;
    document.getElementById('sell-item-name').textContent = trade.name;
    document.getElementById('sell-info').innerHTML = `Gekocht voor: <b>${gpExact(trade.buy_price)}</b> GP × ${trade.quantity}x = <b>${gpExact(trade.total_cost)}</b> GP`;
    document.getElementById('sell-price').value = trade.live_sell_price || trade.market_sell_price || '';
    document.getElementById('sell-qty').value = trade.quantity;
    updateSellCalc();
    document.getElementById('sell-modal').classList.add('show');
}
function closeSellModal() { document.getElementById('sell-modal').classList.remove('show'); }
function updateSellCalc() {
    let sp = parseGP(document.getElementById('sell-price').value);
    let sq = parseInt(document.getElementById('sell-qty').value) || 0;
    if (!sp || !sq || !currentSellTrade) { document.getElementById('sell-calc').innerHTML = ''; return; }
    let rev = sp * sq;
    let tax = Math.min(Math.round(sp * 0.02), 5000000) * sq;
    let cost = currentSellTrade.buy_price * sq;
    let profit = rev - tax - cost;
    let cls = profit >= 0 ? 'profit-pos' : 'profit-neg';
    document.getElementById('sell-calc').innerHTML = `Opbrengst: ${gpExact(rev)} GP — Tax: ${gpExact(tax)} GP<br><span class="${cls}">Winst: ${gpExact(profit)} GP</span>`;
}
document.getElementById('sell-price').addEventListener('input', updateSellCalc);
document.getElementById('sell-qty').addEventListener('input', updateSellCalc);

async function submitSell() {
    let sp = parseGP(document.getElementById('sell-price').value);
    let sq = parseInt(document.getElementById('sell-qty').value);
    if (!sp || !sq) return alert('Vul prijs en aantal in');
    if (sq > currentSellTrade.quantity) return alert('Je kunt niet meer verkopen dan je hebt');
    await fetch('/api/sell', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({trade_id: currentSellTrade.id, sell_price: sp, sell_quantity: sq})});
    closeSellModal();
    loadOrders(); refreshTopbar();
}

async function cancelTrade(id) {
    if (!confirm('Weet je zeker dat je deze trade wilt annuleren?')) return;
    await fetch('/api/cancel', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({trade_id: id})});
    loadOrders(); refreshTopbar();
}

// HISTORY PAGE
async function loadHistory() {
    let hist = await (await fetch('/api/history')).json();
    let el = document.getElementById('history-content');
    if (!hist.length) { el.innerHTML = '<div class="section"><div class="empty">Nog geen voltooide trades</div></div>'; return; }

    let totalProfit = hist.reduce((s,t) => s + (t.profit||0), 0);
    let totalRevenue = hist.reduce((s,t) => s + (t.revenue||0), 0);
    let totalTax = hist.reduce((s,t) => s + (t.tax||0), 0);
    let totalCost = hist.reduce((s,t) => s + ((t.buy_price||0) * (t.sell_quantity||t.quantity||0)), 0);
    let wins = hist.filter(t => (t.profit||0) > 0).length;
    let losses = hist.filter(t => (t.profit||0) < 0).length;
    let winRate = hist.length ? Math.round(wins / hist.length * 100) : 0;
    let avgProfit = hist.length ? Math.round(totalProfit / hist.length) : 0;
    let bestTrade = hist.reduce((best, t) => (t.profit||0) > (best.profit||0) ? t : best, hist[0]);
    let worstTrade = hist.reduce((worst, t) => (t.profit||0) < (worst.profit||0) ? t : worst, hist[0]);
    let cls = totalProfit >= 0 ? 'profit-pos' : 'profit-neg';

    // Flip-snelheid stats
    let flipsWithTime = hist.filter(t => t.flip_minutes != null && t.flip_minutes > 0);
    let avgFlipMins = flipsWithTime.length ? Math.round(flipsWithTime.reduce((s,t) => s + t.flip_minutes, 0) / flipsWithTime.length) : null;
    let fastestFlip = flipsWithTime.length ? flipsWithTime.reduce((f,t) => t.flip_minutes < f.flip_minutes ? t : f) : null;

    // ── Grafiek data opslaan voor renderChart ──
    window._chartHist = hist;

    // ── Stats cards ──
    let flipTimeStr = avgFlipMins != null ? (avgFlipMins < 60 ? avgFlipMins + ' min' : Math.round(avgFlipMins/60) + 'u ' + (avgFlipMins%60) + 'm') : '–';
    let h = `
    <div class="section"><div class="sh t1">📊 Portfolio Overzicht</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;padding:14px 18px">
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Totale Winst</div>
                <div style="font-size:20px;font-weight:700" class="${cls}">${gp(totalProfit)}</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Win Rate</div>
                <div style="font-size:20px;font-weight:700;color:${winRate>=50?'#3fb950':'#da3633'}">${winRate}%</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Trades</div>
                <div style="font-size:20px;font-weight:700;color:#c9d1d9">${hist.length}</div>
                <div style="font-size:10px;color:#484f58"><span class="up">${wins}W</span> / <span class="dn">${losses}L</span></div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Gem. Winst/Trade</div>
                <div style="font-size:20px;font-weight:700" class="${avgProfit>=0?'profit-pos':'profit-neg'}">${gp(avgProfit)}</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Gem. Flip Tijd</div>
                <div style="font-size:20px;font-weight:700;color:#d29922">${flipTimeStr}</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Totale Tax</div>
                <div style="font-size:20px;font-weight:700;color:#da3633">${gp(totalTax)}</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Beste Trade</div>
                <div style="font-size:14px;font-weight:600;color:#3fb950">${gp(bestTrade.profit||0)}</div>
                <div style="font-size:10px;color:#484f58">${bestTrade.name||'–'}</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Slechtste Trade</div>
                <div style="font-size:14px;font-weight:600;color:#da3633">${gp(worstTrade.profit||0)}</div>
                <div style="font-size:10px;color:#484f58">${worstTrade.name||'–'}</div>
            </div>
        </div>
    </div>
    <div class="section" id="chart-section">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:0 18px">
            <div class="sh t2" style="margin:0;padding:10px 0">📈 Winst Grafiek</div>
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                <select id="chart-mode" onchange="renderChart()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer">
                    <option value="trade">Per Trade</option>
                    <option value="day">Per Dag</option>
                </select>
                <select id="chart-range" onchange="renderChart()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer">
                    <option value="all">Alles</option>
                    <option value="7">7 dagen</option>
                    <option value="14">14 dagen</option>
                    <option value="30">30 dagen</option>
                </select>
                <select id="chart-type" onchange="renderChart()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer">
                    <option value="cumulative">Cumulatief</option>
                    <option value="individual">Per punt</option>
                </select>
            </div>
        </div>
        <div id="chart-container" style="padding:12px 18px 18px"></div>
    </div>
    <div class="section"><div class="sh t1">💰 Trade Historie</div>
        <table><tr><th>Datum</th><th>Item</th><th>Koop</th><th>Verkoop</th><th>Aantal</th><th>Winst</th><th>Flip Tijd</th><th></th></tr>`;
    let reversed = hist.map((t, i) => ({...t, _idx: i})).reverse();
    reversed.forEach(t => {
        let pcls = (t.profit||0) >= 0 ? 'profit-pos' : 'profit-neg';
        let date = t.closed_at ? new Date(t.closed_at).toLocaleDateString('nl-NL', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : '–';
        let fm = t.flip_minutes;
        let flipStr = fm != null ? (fm < 60 ? fm + 'm' : Math.floor(fm/60) + 'u ' + (fm%60) + 'm') : '–';
        h += `<tr>
            <td>${date}</td><td style="cursor:pointer;color:#58a6ff" onclick="showItemDetail('${t.name?.replace(/'/g,"\\'")}')">${t.name}</td>
            <td class="gp">${gpExact(t.buy_price)}</td>
            <td class="gp">${gpExact(t.sell_price)}</td><td>${(t.sell_quantity||t.quantity).toLocaleString()}x</td>
            <td class="${pcls}">${gpExact(t.profit)} GP</td>
            <td style="color:#d29922">${flipStr}</td>
            <td><button class="btn btn-red btn-sm" onclick="deleteHistory(${t._idx})">✕</button></td></tr>`;
    });
    el.innerHTML = h + '</table></div>';
    renderChart();
}

// ── WINST GRAFIEK ──
function renderChart() {
    let hist = window._chartHist || [];
    let container = document.getElementById('chart-container');
    if (!container) return;
    if (!hist.length) {
        container.innerHTML = '<div style="text-align:center;padding:30px;color:#484f58;font-size:13px">Nog geen trades — je grafiek verschijnt hier zodra je je eerste flip voltooit</div>';
        return;
    }

    let mode = document.getElementById('chart-mode').value;
    let range = document.getElementById('chart-range').value;
    let type = document.getElementById('chart-type').value;

    // Filter op tijdsperiode
    let filtered = hist;
    if (range !== 'all') {
        let cutoff = Date.now() - parseInt(range) * 86400000;
        filtered = hist.filter(t => t.closed_at && new Date(t.closed_at).getTime() >= cutoff);
    }
    if (!filtered.length) {
        container.innerHTML = '<div style="text-align:center;padding:30px;color:#484f58;font-size:13px">Geen trades in deze periode</div>';
        return;
    }

    // Sorteer op datum
    filtered.sort((a, b) => new Date(a.closed_at||0) - new Date(b.closed_at||0));

    let labels = [];
    let values = [];

    if (mode === 'day') {
        // Groepeer per dag
        let daily = {};
        filtered.forEach(t => {
            if (!t.closed_at) return;
            let day = new Date(t.closed_at).toLocaleDateString('nl-NL', {day:'numeric', month:'short'});
            daily[day] = (daily[day]||0) + (t.profit||0);
        });
        labels = Object.keys(daily);
        values = Object.values(daily);
    } else {
        // Per trade
        filtered.forEach(t => {
            let lbl = (t.name||'?').substring(0, 14);
            if (t.closed_at) {
                let d = new Date(t.closed_at);
                lbl += ' ' + d.toLocaleTimeString('nl-NL', {hour:'2-digit', minute:'2-digit'});
            }
            labels.push(lbl);
            values.push(t.profit||0);
        });
    }

    // Cumulatief of individueel
    let plotValues;
    if (type === 'cumulative') {
        plotValues = []; let cum = 0;
        values.forEach(v => { cum += v; plotValues.push(cum); });
    } else {
        plotValues = values;
    }

    if (!plotValues.length) {
        container.innerHTML = '<div style="text-align:center;padding:30px;color:#484f58;font-size:13px">Geen data beschikbaar</div>';
        return;
    }

    // Render bars
    let maxVal = Math.max(...plotValues.map(Math.abs), 1);
    let hasNeg = plotValues.some(v => v < 0);
    let chartHeight = 160;
    let zeroY = hasNeg ? 50 : 0; // percentage from bottom

    let barCount = plotValues.length;
    let gap = barCount > 20 ? 1 : 2;

    let barsH = '';
    plotValues.forEach((v, i) => {
        let pct = Math.abs(v) / maxVal * (hasNeg ? 48 : 92);
        let color = v >= 0 ? '#238636' : '#da3633';
        let hoverColor = v >= 0 ? '#2ea043' : '#f85149';
        let bottom, barStyle;
        if (hasNeg) {
            bottom = v >= 0 ? zeroY : zeroY - pct;
        } else {
            bottom = 0;
        }
        let leftPct = (i / barCount * 100).toFixed(2);
        let widthPct = Math.max((90 / barCount).toFixed(2), 0.5);
        let sign = v >= 0 ? '+' : '';
        let tt = `${labels[i]}: ${sign}${gpExact(v)} GP`;
        barsH += `<div title="${tt}" style="position:absolute;bottom:${bottom}%;left:${leftPct}%;width:${widthPct}%;height:${Math.max(pct, 1)}%;background:${color};border-radius:3px 3px 0 0;cursor:pointer;transition:background 0.15s" onmouseenter="this.style.background='${hoverColor}'" onmouseleave="this.style.background='${color}'"></div>`;
    });

    // Zero line
    let zeroLine = hasNeg ? `<div style="position:absolute;bottom:${zeroY}%;left:0;right:0;height:1px;background:#30363d"></div>` : '';

    // Value labels
    let topLabel = type === 'cumulative' ? gpExact(plotValues[plotValues.length-1]) + ' GP' : '';
    let summaryH = '';
    if (type === 'cumulative') {
        let final = plotValues[plotValues.length-1];
        let cls = final >= 0 ? 'profit-pos' : 'profit-neg';
        summaryH = `<div style="text-align:right;font-size:12px;margin-top:6px"><span class="${cls}" style="font-weight:600">${final >= 0 ? '+' : ''}${gpExact(final)} GP totaal</span> over ${barCount} ${mode === 'day' ? 'dagen' : 'trades'}</div>`;
    } else {
        let total = values.reduce((s,v) => s + v, 0);
        let cls = total >= 0 ? 'profit-pos' : 'profit-neg';
        summaryH = `<div style="text-align:right;font-size:12px;margin-top:6px"><span class="${cls}" style="font-weight:600">${total >= 0 ? '+' : ''}${gpExact(total)} GP totaal</span> over ${barCount} ${mode === 'day' ? 'dagen' : 'trades'}</div>`;
    }

    container.innerHTML = `
        <div style="position:relative;height:${chartHeight}px;margin-bottom:4px">
            ${zeroLine}
            ${barsH}
        </div>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#484f58;padding:0 2px">
            <span>${labels[0]}</span>
            ${labels.length > 2 ? '<span>' + labels[Math.floor(labels.length/2)] + '</span>' : ''}
            <span>${labels[labels.length-1]}</span>
        </div>
        ${summaryH}`;
}

async function deleteHistory(idx) {
    if (!confirm('Weet je zeker dat je deze trade wilt verwijderen?')) return;
    await fetch('/api/history/delete', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({index: idx})});
    loadHistory();
}

// QUICK LOOKUP (dashboard)
let qlTimer = null;
async function quickLookup(q) {
    clearTimeout(qlTimer);
    let box = document.getElementById('ql-results');
    if (q.length < 2) { box.style.display = 'none'; return; }
    qlTimer = setTimeout(async () => {
        try {
            let res = await (await fetch('/api/search?q=' + encodeURIComponent(q))).json();
            if (!res.length) { box.innerHTML = '<div style="padding:12px;color:#8b949e">Geen resultaten</div>'; box.style.display = 'block'; return; }
            let h = '';
            res.forEach(r => {
                let isFav = favorites.includes(r.name);
                let star = isFav ? 'color:#d29922' : 'color:#484f58';
                h += `<div style="display:flex;align-items:center;gap:10px;padding:8px 14px;cursor:pointer;border-bottom:1px solid #21262d;transition:background .15s"
                    onmouseenter="this.style.background='#1c2333'" onmouseleave="this.style.background='none'"
                    onclick="document.getElementById('quick-lookup').value='';document.getElementById('ql-results').style.display='none';openItemDetail(${r.id},'${r.name.replace(/'/g,"\\'")}')">
                    <span style="font-size:16px;${star}">★</span>
                    <span style="color:#c9d1d9;flex:1">${r.name}</span>
                    <span style="color:#484f58;font-size:12px">Limit: ${r.limit || '?'}</span>
                    <span style="color:#58a6ff;font-size:12px">→ Details</span>
                </div>`;
            });
            box.innerHTML = h;
            box.style.display = 'block';
        } catch(e) { console.log('Quick lookup error:', e); }
    }, 200);
}

// SETTINGS - SEARCH & FAVORITES
async function searchItems() {
    let q = document.getElementById('fav-search').value;
    if (q.length < 2) { document.getElementById('fav-results').innerHTML = ''; return; }
    let res = await (await fetch('/api/search?q=' + encodeURIComponent(q))).json();
    let h = '';
    res.forEach(r => {
        let isFav = favorites.includes(r.name);
        let starStyle = isFav ? 'color:#d29922' : 'color:#484f58';
        h += `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #21262d">
            <span style="cursor:pointer;font-size:18px;${starStyle}" onclick="toggleFavSearch('${r.name.replace(/'/g, "\\'")}')">★</span>
            <span>${r.name}</span>
            <span style="color:#484f58;font-size:11px">Limit: ${r.limit || '?'}</span>
        </div>`;
    });
    document.getElementById('fav-results').innerHTML = h;
}

async function toggleFavSearch(name) {
    await fetch('/api/favorites/toggle', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
    await loadFavorites();
    searchItems();
    loadFavList();
}

async function loadFavList() {
    let favs = await (await fetch('/api/favorites')).json();
    let h = '';
    if (!favs.length) { h = '<span style="color:#484f58;font-size:12px">Nog geen favorieten</span>'; }
    favs.forEach(name => {
        h += `<div style="display:flex;align-items:center;gap:8px;padding:4px 0">
            <span style="cursor:pointer;font-size:16px;color:#d29922" onclick="toggleFavSearch('${name.replace(/'/g, "\\'")}')">★</span>
            <span style="font-size:13px">${name}</span>
        </div>`;
    });
    document.getElementById('fav-list').innerHTML = h;
}

// SETTINGS PAGE
async function loadSettings() {
    let s = await (await fetch('/api/settings')).json();
    document.getElementById('set-account').value = s.account_name || '';
    document.getElementById('set-capital').value = s.capital;
    document.getElementById('set-slots').value = s.max_slots;
    document.getElementById('set-roi').value = s.min_roi;
    document.getElementById('set-maxroi').value = s.max_roi;
    document.getElementById('set-minprice').value = s.min_buy_price;
    document.getElementById('set-minprofit').value = s.min_profit_per_trade;
    document.getElementById('set-minvol').value = s.min_volume;
    document.getElementById('set-minscore').value = s.min_score_for_trade;
    document.getElementById('set-refresh').value = s.refresh_seconds;
    loadFavList();
}
async function saveSettings() {
    await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
            account_name: document.getElementById('set-account').value.trim(),
            capital: parseGP(document.getElementById('set-capital').value),
            max_slots: parseInt(document.getElementById('set-slots').value),
            min_roi: parseFloat(document.getElementById('set-roi').value),
            max_roi: parseInt(document.getElementById('set-maxroi').value),
            min_buy_price: parseGP(document.getElementById('set-minprice').value),
            min_profit_per_trade: parseGP(document.getElementById('set-minprofit').value),
            min_volume: parseInt(document.getElementById('set-minvol').value),
            min_score_for_trade: parseFloat(document.getElementById('set-minscore').value),
            refresh_seconds: parseInt(document.getElementById('set-refresh').value),
        })});
    refreshTopbar();
    alert('Instellingen opgeslagen!');
}

async function resetAccount() {
    if (!confirm('⚠️ WAARSCHUWING\\n\\nDit verwijdert ALLE gegevens:\\n• Actieve orders\\n• Trade historie\\n• Favorieten\\n• Instellingen\\n\\nDit kan NIET ongedaan worden gemaakt.\\n\\nWeet je het zeker?')) return;
    if (!confirm('Laatste kans — echt alles wissen?')) return;
    await fetch('/api/reset', {method:'POST'});
    alert('Account is gereset. Pagina wordt herladen.');
    location.reload();
}

// MONEY METHODS
// ── HERB RUN CALCULATOR ──
let herbData = null;
let herbPatches = {};

function initHerbPatches(patches) {
    let el = document.getElementById('herb-patches');
    if (!el) return;
    let h = '';
    patches.forEach(p => {
        if (herbPatches[p.key] === undefined) herbPatches[p.key] = true;
        let on = herbPatches[p.key];
        let quest = p.quest ? ` (${p.quest})` : '';
        h += `<button id="patch-${p.key}" onclick="togglePatch('${p.key}')" style="padding:6px 12px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid ${on?'#238636':'#30363d'};background:${on?'#0d2818':'#161b22'};color:${on?'#3fb950':'#484f58'};transition:all .2s">${p.name}<span style="font-size:10px;color:#484f58">${quest}</span></button>`;
    });
    el.innerHTML = h;
}

function togglePatch(key) {
    herbPatches[key] = !herbPatches[key];
    renderHerbRun();
    let btn = document.getElementById('patch-' + key);
    if (btn) {
        let on = herbPatches[key];
        btn.style.border = `1px solid ${on?'#238636':'#30363d'}`;
        btn.style.background = on?'#0d2818':'#161b22';
        btn.style.color = on?'#3fb950':'#484f58';
    }
}

async function loadHerbRun() {
    let compost = document.getElementById('herb-compost').value;
    let secateurs = document.getElementById('herb-secateurs').checked;
    let cape = document.getElementById('herb-cape').checked;
    try {
        let r = await fetch(`/api/money/herbrun?compost=${compost}&secateurs=${secateurs}&cape=${cape}`);
        herbData = await r.json();
        if (herbData.patches) initHerbPatches(herbData.patches);
        renderHerbRun();
    } catch(e) { console.log('Herb run error:', e); }
}

function renderHerbRun() {
    if (!herbData || !herbData.herbs) return;
    let numPatches = Object.values(herbPatches).filter(v => v).length;
    let tableEl = document.getElementById('herb-table');
    let summaryEl = document.getElementById('herb-summary');
    let routeEl = document.getElementById('herb-route');

    let h = '<table><tr><th>Lvl</th><th>Herb</th><th>Seed</th><th>Herb prijs</th><th>Opbrengst/patch</th><th>Kosten/patch</th><th>Winst/patch</th><th>Winst/run</th></tr>';
    let bestProfit = 0;
    let bestHerb = '';
    herbData.herbs.forEach(herb => {
        let runProfit = herb.profit_patch * numPatches;
        let cls = herb.profit_patch > 0 ? 'color:#3fb950' : 'color:#da3633';
        if (runProfit > bestProfit) { bestProfit = runProfit; bestHerb = herb.name; }
        h += `<tr>
            <td style="color:#484f58">${herb.lvl}</td>
            <td><span style="cursor:pointer;color:#58a6ff" onclick="openItemDetail(${herb.herb_id},'${herb.name.replace(/'/g,"\\'")}')">${herb.name}</span></td>
            <td class="gp">${gp(herb.seed_price)}</td>
            <td class="gp">${gp(herb.herb_price)}</td>
            <td class="gp">${gp(herb.revenue_patch)}</td>
            <td class="gp">${gp(herb.cost_patch)}</td>
            <td style="${cls};font-weight:600">${gp(herb.profit_patch)}</td>
            <td style="${cls};font-weight:700">${gp(runProfit)}</td>
        </tr>`;
    });
    h += '</table>';
    tableEl.innerHTML = h;

    // Summary
    if (herbData.herbs.length > 0) {
        summaryEl.style.display = 'block';
        summaryEl.innerHTML = `
            <div style="display:flex;flex-wrap:wrap;gap:20px;font-size:14px;color:#c9d1d9">
                <div>🌿 <b>${numPatches}</b> patches actief</div>
                <div>📊 Gem. opbrengst: <b>${herbData.avg_yield}</b> herbs/patch</div>
                <div>🧪 Compost: <b>${gp(herbData.compost_price)}</b> GP/patch</div>
                <div style="color:#3fb950;font-weight:700">💰 Beste herb: <b>${bestHerb}</b> — ${gp(bestProfit)} GP/run</div>
            </div>`;
    }

    // Route
    if (!herbData.patches) { routeEl.style.display = 'none'; return; }
    let activePatches = herbData.patches
        .filter(p => herbPatches[p.key])
        .sort((a, b) => a.order - b.order);

    if (activePatches.length === 0) { routeEl.style.display = 'none'; return; }
    routeEl.style.display = 'block';

    // Collect all unique items needed
    let allItems = [];
    activePatches.forEach(p => { if (p.items) p.items.forEach(it => { if (!allItems.includes(it)) allItems.push(it); }); });

    let compostType = document.getElementById('herb-compost').value;
    let compostName = {none:'Geen', compost:'Compost', supercompost:'Supercompost', ultracompost:'Ultracompost', bottomless:'Bottomless compost bucket'}[compostType] || compostType;
    let secateurs = document.getElementById('herb-secateurs').checked;

    let rh = `<div class="section" style="margin:0"><div class="sh t3">🗺️ Route & Inventory</div><div style="padding:14px">`;

    // Inventory checklist
    rh += `<div style="margin-bottom:16px;padding:12px;background:#0d1117;border:1px solid #30363d;border-radius:8px">`;
    rh += `<div style="font-size:13px;font-weight:600;color:#d29922;margin-bottom:8px">🎒 Inventory Checklist</div>`;
    rh += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;font-size:13px;color:#c9d1d9">`;
    rh += `<div>🌱 ${activePatches.length}x Herb seed (keuze)</div>`;
    rh += `<div>🧰 Seed dibber</div>`;
    rh += `<div>🔧 Spade</div>`;
    if (secateurs) rh += `<div>✂️ Magic secateurs (equipped)</div>`;
    if (compostType !== 'none') rh += `<div>🧪 ${compostType === 'bottomless' ? 'Bottomless compost bucket' : activePatches.length + 'x ' + compostName}</div>`;
    rh += `<div>💰 GP voor teleports</div>`;
    allItems.forEach(it => { rh += `<div>🔮 ${it}</div>`; });
    rh += `</div></div>`;

    // Route steps
    rh += `<div style="font-size:13px;font-weight:600;color:#58a6ff;margin-bottom:10px">📍 Optimale Route (${activePatches.length} stops)</div>`;
    activePatches.forEach((p, i) => {
        let isLast = i === activePatches.length - 1;
        let diseaseFree = (p.key === 'troll' || p.key === 'weiss');
        rh += `<div style="display:flex;gap:12px;margin-bottom:${isLast?'0':'4'}px">`;
        // Timeline
        rh += `<div style="display:flex;flex-direction:column;align-items:center;min-width:28px">`;
        rh += `<div style="width:28px;height:28px;border-radius:50%;background:${i===0?'#238636':'#30363d'};color:${i===0?'#fff':'#8b949e'};display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700">${i+1}</div>`;
        if (!isLast) rh += `<div style="width:2px;flex:1;background:#21262d;margin:4px 0"></div>`;
        rh += `</div>`;
        // Content
        rh += `<div style="flex:1;padding-bottom:${isLast?'0':'14'}px">`;
        rh += `<div style="font-size:14px;font-weight:600;color:#c9d1d9">${p.name}</div>`;
        rh += `<div style="font-size:12px;color:#8b949e;margin-top:2px">🔮 ${p.teleport}</div>`;
        if (p.tip) rh += `<div style="font-size:12px;color:#6e7681;margin-top:2px;font-style:italic">${p.tip}</div>`;
        if (diseaseFree) rh += `<div style="font-size:11px;color:#3fb950;margin-top:2px">✅ Disease-free — geen compost nodig</div>`;
        if (p.quest) rh += `<div style="font-size:11px;color:#d29922;margin-top:2px">⚠️ Vereist: ${p.quest}</div>`;
        rh += `</div></div>`;
    });

    rh += `</div></div>`;
    routeEl.innerHTML = rh;
}

let mmMagicLevel = null;
let mmCollapsed = {};

function toggleMmSection(key) {
    mmCollapsed[key] = !mmCollapsed[key];
    let body = document.getElementById(key + '-body');
    let toggle = document.getElementById(key + '-toggle');
    if (mmCollapsed[key]) {
        body.style.display = 'none';
        toggle.textContent = '▶';
    } else {
        body.style.display = '';
        toggle.textContent = '▼';
    }
}

async function loadMoneyMethods() {
    // Haal hiscores op voor magic level check
    try {
        let hs = await (await fetch('/api/hiscores')).json();
        if (!hs.error && hs.skills && hs.skills.Magic) {
            mmMagicLevel = hs.skills.Magic.level;
            document.getElementById('mm-magic-level').innerHTML = `🧙 <b style="color:#a371f7">${hs.rsn}</b> — Magic level: <b style="color:${mmMagicLevel >= 55 ? '#3fb950' : '#d29922'}">${mmMagicLevel}</b>`;
        } else if (hs.error === 'no_rsn') {
            document.getElementById('mm-magic-level').innerHTML = '<span style="color:#d29922">Vul je RSN in bij Instellingen voor magic level check</span>';
        } else {
            document.getElementById('mm-magic-level').innerHTML = '<span style="color:#484f58">Hiscores niet beschikbaar</span>';
        }
    } catch(e) {
        document.getElementById('mm-magic-level').innerHTML = '';
    }
    loadAlch(); loadBolts(); loadStaves();
    loadDhide(); loadGems(); loadJewelry(); loadGlass(); loadStringing();
    loadPlanks(); loadTan();
    loadCballs(); loadBf();
    loadCooking(); loadFletching(); loadBowCut();
    loadHerblore(); loadHerbClean(); loadUnfPotions();
    loadRunecraft(); loadHunter(); loadBirdhouse();
}

async function loadStaves() {
    let infoEl = document.getElementById('staves-info');
    let tableEl = document.getElementById('staves-table');
    tableEl.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch('/api/money/staves?diary=elite')).json();
        if (d.error) { tableEl.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        if (!d.staves || !d.staves.length) { tableEl.innerHTML = '<span style="color:#484f58">Geen data</span>'; return; }

        infoEl.innerHTML = `Battlestaff GE: <b>${gp(d.bstaff_price)}</b> GP | Zaff prijs: <b>7,000</b> GP | Zaff dagelijks: <b>${d.zaff_qty}</b> (Elite Varrock Diary)`;

        let h = '<table><tr><th>Lvl</th><th>Staff</th><th>Orb</th><th>Verkoop</th><th>Winst (GE staff)</th><th>Winst (Zaff staff)</th><th>Dagelijks (Zaff)</th></tr>';
        d.staves.forEach(s => {
            let clsGe = s.profit_ge > 0 ? 'color:#3fb950' : 'color:#da3633';
            let clsZaff = s.profit_zaff > 0 ? 'color:#3fb950' : 'color:#da3633';
            let clsDaily = s.daily_profit_zaff > 0 ? 'color:#3fb950' : 'color:#da3633';
            h += `<tr>
                <td style="color:#484f58">${s.lvl}</td>
                <td><span style="cursor:pointer;color:#58a6ff" onclick="openItemDetail(${s.product_id},'${s.name.replace(/'/g,"\\'")}')">${s.name}</span></td>
                <td class="gp">${gp(s.orb_price)}</td>
                <td class="gp">${gp(s.sell_price)}</td>
                <td style="${clsGe};font-weight:600">${gp(s.profit_ge)}</td>
                <td style="${clsZaff};font-weight:700">${gp(s.profit_zaff)}</td>
                <td style="${clsDaily};font-weight:700">${gp(s.daily_profit_zaff)}</td>
            </tr>`;
        });
        h += '</table>';
        h += `<div style="margin-top:10px;font-size:12px;color:#8b949e">⏱️ 30 sec per inv | 💡 Koop battlestaves dagelijks van Zaff in Varrock voor 7,000 GP (Elite Diary = 120/dag). Combineer met orbs (Crafting) en verkoop voor winst.</div>`;
        tableEl.innerHTML = h;
    } catch(e) {
        tableEl.innerHTML = '<span style="color:#da3633">Fout bij laden</span>';
    }
}

// Generic table builder for simple crafting methods
function buildSimpleTable(items, cols) {
    if (!items || !items.length) return '<span style="color:#484f58">Geen data</span>';
    let h = '<table><tr>';
    cols.forEach(c => h += `<th>${c.label}</th>`);
    h += '</tr>';
    items.forEach(it => {
        h += '<tr>';
        cols.forEach(c => {
            let v = c.fn(it);
            let style = c.style ? c.style(it) : '';
            h += `<td style="${style}">${v}</td>`;
        });
        h += '</tr>';
    });
    return h + '</table>';
}
function profitStyle(it, key) { return (it[key||'profit'] > 0 ? 'color:#3fb950;font-weight:600' : 'color:#da3633;font-weight:600'); }
function nameLink(it, key) { return `<span style="cursor:pointer;color:#58a6ff" onclick="openItemDetail(${it.product_id},'${(it.name||'').replace(/'/g,"\\'")}')">${it.name}</span>`; }

async function loadSimpleSection(url, tableId, columns) {
    let el = document.getElementById(tableId);
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch(url)).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return d; }
        el.innerHTML = buildSimpleTable(d.items, columns);
        return d;
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; return null; }
}

function xpCol(i) { return `<span style="color:#a371f7">${i.xp_hr ? (i.xp_hr/1000).toFixed(1)+'K' : '-'}</span>`; }
function afkCol(i) { return `<span style="color:#8b949e;font-size:12px">⏱️ ${i.afk_time || '-'}</span>`; }

async function loadDhide() {
    await loadSimpleSection('/api/money/dhide', 'dhide-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Body', fn:nameLink},
        {label:'Hide/st', fn:i=>`<span style="color:#d29922">${gp(i.hide_price)}</span>`},
        {label:'3x Kosten', fn:i=>gp(i.cost)},
        {label:'Verkoop', fn:i=>gp(i.body_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadGems() {
    await loadSimpleSection('/api/money/gems', 'gems-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Gem', fn:nameLink},
        {label:'Uncut', fn:i=>gp(i.uncut_price)},
        {label:'Cut', fn:i=>gp(i.cut_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadJewelry() {
    await loadSimpleSection('/api/money/jewelry', 'jewelry-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Item', fn:nameLink},
        {label:'Gem', fn:i=>`<span style="color:#8b949e">${i.gem}</span>`},
        {label:'Kosten', fn:i=>gp(i.cost)},
        {label:'Verkoop', fn:i=>gp(i.sell_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadGlass() {
    await loadSimpleSection('/api/money/glass', 'glass-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Item', fn:nameLink},
        {label:'Glas', fn:i=>`<span style="color:#d29922">${gp(i.glass_price)}</span>`},
        {label:'Verkoop', fn:i=>gp(i.sell_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadStringing() {
    let d = await loadSimpleSection('/api/money/stringing', 'stringing-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Amulet', fn:nameLink},
        {label:'Unstrung', fn:i=>gp(i.unstrung_price)},
        {label:'Wool', fn:i=>`<span style="color:#d29922">${gp(i.wool_price)}</span>`},
        {label:'Strung', fn:i=>gp(i.strung_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadPlanks() {
    let el = document.getElementById('planks-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch('/api/money/planks')).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        let rn = d.runes || {};
        document.getElementById('planks-info').innerHTML = `Spell: <b>${gp(d.spell_cost)}</b> GP/cast | Runes: Astral <b>${gp(rn.astral)}</b> · Nature <b>${gp(rn.nature)}</b> · Earth <b>${gp(rn.earth)}</b> | 90 Magic XP/cast | ~1860/hr`;
        el.innerHTML = buildSimpleTable(d.items, [
            {label:'Plank', fn:nameLink},
            {label:'Log', fn:i=>gp(i.log_price)},
            {label:'Spell', fn:i=>`<span style="color:#d29922">${gp(i.spell_cost)}</span>`},
            {label:'Verkoop', fn:i=>gp(i.plank_price)},
            {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
            {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
            {label:'XP/hr', fn:xpCol},
            {label:'AFK', fn:afkCol},
        ]);
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

async function loadTan() {
    let el = document.getElementById('tan-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch('/api/money/tan')).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        let rn2 = d.runes || {};
        document.getElementById('tan-info').innerHTML = `Spell: <b>${gp(d.spell_per_hide)}</b> GP/hide (2 astral + 1 nature per 5 hides) | Runes: Astral <b>${gp(rn2.astral)}</b> · Nature <b>${gp(rn2.nature)}</b> | 81 Magic XP/cast | ~5000 hides/hr`;
        el.innerHTML = buildSimpleTable(d.items, [
            {label:'Leather', fn:nameLink},
            {label:'Hide', fn:i=>gp(i.hide_price)},
            {label:'Spell/hide', fn:i=>`<span style="color:#d29922">${gp(i.spell_cost)}</span>`},
            {label:'Verkoop', fn:i=>gp(i.leather_price)},
            {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
            {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
            {label:'XP/hr', fn:xpCol},
            {label:'AFK', fn:afkCol},
        ]);
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

async function loadCballs() {
    let el = document.getElementById('cballs-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch('/api/money/cballs')).json();
        if (d.error || !d.items.length) { el.innerHTML = '<span style="color:#484f58">Geen data</span>'; return; }
        let c = d.items[0];
        let cls = c.profit_bar > 0 ? 'color:#3fb950' : 'color:#da3633';
        el.innerHTML = `<div style="padding:8px 0;font-size:14px;color:#c9d1d9;line-height:2">
            <div>Steel bar: <b>${gp(c.steel_price)}</b> GP → 4 cannonballs: <b>${gp(c.cball_price * 4)}</b> GP</div>
            <div>Winst per bar: <b style="${cls}">${gp(c.profit_bar)}</b> GP | XP per bar: <span style="color:#a371f7">${c.xp}</span></div>
            <div>~${c.bars_per_hr} bars/uur → <b style="${cls}">${gp(c.profit_hr)}</b> GP/uur | <span style="color:#a371f7">${(c.xp_hr/1000).toFixed(1)}K</span> XP/uur</div>
            <div style="font-size:12px;color:#8b949e;margin-top:4px">⏱️ ${c.afk_time} | 💡 Dwarf Cannon quest + 35 Smithing. Super AFK.</div>
        </div>`;
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

async function loadBf() {
    let el = document.getElementById('bf-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch('/api/money/blastfurnace')).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        document.getElementById('bf-info').innerHTML = `Coal: <b>${gp(d.coal_price)}</b> GP/st | Coffer: <b>${gp(d.coffer_cost)}</b> GP/hr (72K bij 60+ Smithing) | ${d.goldsmith ? '⭐ Goldsmith gauntlets actief' : 'Geen gauntlets'}`;
        el.innerHTML = buildSimpleTable(d.items, [
            {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
            {label:'Bar', fn:nameLink},
            {label:'Ore', fn:i=>gp(i.ore_price)},
            {label:'Coal', fn:i=>i.coal_needed ? `<span style="color:#d29922">${i.coal_needed}x ${gp(i.coal_price)}</span>` : '-'},
            {label:'Verkoop', fn:i=>gp(i.bar_price)},
            {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
            {label:'Bars/hr', fn:i=>`<span style="color:#8b949e">${i.bars_hr}</span>`},
            {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
            {label:'XP/hr', fn:i=>{let s=i.goldsmith?'⭐ ':''; return `<span style="color:#a371f7">${s}${(i.xp_hr/1000).toFixed(1)}K</span>`;}},
            {label:'AFK', fn:afkCol},
        ]);
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

async function loadCooking() {
    let gauntlets = document.getElementById('cook-gauntlets').checked;
    let level = document.getElementById('cook-level').value || 99;
    await loadSimpleSection(`/api/money/cooking?gauntlets=${gauntlets}&level=${level}`, 'cook-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Vis', fn:nameLink},
        {label:'Raw', fn:i=>gp(i.raw_price)},
        {label:'Cooked', fn:i=>gp(i.cooked_price)},
        {label:'Burn%', fn:i=>`<span style="color:${i.burn_rate > 0 ? '#d29922' : '#3fb950'}">${i.burn_rate}%</span>`},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadBowCut() {
    await loadSimpleSection('/api/money/bowcut', 'bowcut-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Bow', fn:nameLink},
        {label:'Log', fn:i=>gp(i.log_price)},
        {label:'Bow (u)', fn:i=>gp(i.bow_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadFletching() {
    await loadSimpleSection('/api/money/fletching', 'fletch-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Bow', fn:nameLink},
        {label:'Unstrung', fn:i=>gp(i.unstrung_price)},
        {label:'String', fn:i=>`<span style="color:#d29922">${gp(i.string_price)}</span>`},
        {label:'Strung', fn:i=>gp(i.strung_price)},
        {label:'Winst', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadHerblore() {
    let qty = document.getElementById('herb-qty').value || 1000;
    let el = document.getElementById('herblore-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch(`/api/money/herblore?qty=${qty}`)).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        if (!d.items || !d.items.length) { el.innerHTML = '<span style="color:#484f58">Geen data</span>'; return; }
        let q = d.qty;
        let h = '<table style="font-size:12px"><tr><th>Lvl</th><th>Potion</th><th>Herb (grimy)</th><th>Secondary</th><th>Unf potion</th><th>3-dose</th><th>4-dose</th><th>Winst/st (herb)</th><th>Winst/st (unf)</th><th>${q}x herb → 3d</th><th>${q}x herb → ${Math.round(q*0.75)}x 4d</th><th>XP/hr</th></tr>';
        h = h.replace(/\$\{q\}/g, q).replace('${Math.round(q*0.75)}', Math.round(q*0.75));
        d.items.forEach(i => {
            let cls3h = i.profit_3_herb >= 0 ? 'color:#3fb950' : 'color:#da3633';
            let cls3u = i.profit_3_unf >= 0 ? 'color:#3fb950' : 'color:#da3633';
            let clsB3 = i.profit_3_herb_batch >= 0 ? 'color:#3fb950' : 'color:#da3633';
            let clsB4 = i.profit_4_herb_batch >= 0 ? 'color:#3fb950' : 'color:#da3633';
            h += `<tr>
                <td style="color:#484f58">${i.lvl}</td>
                <td><span style="cursor:pointer;color:#58a6ff" onclick="openItemDetail(${i.product_id},'${i.name.replace(/'/g,"\\'")}')">${i.name}</span></td>
                <td><span style="color:#d29922">${gp(i.herb_price)}</span> <span style="color:#484f58;font-size:10px">${i.herb_name}</span></td>
                <td><span style="color:#d29922">${gp(i.sec_price)}</span> <span style="color:#484f58;font-size:10px">${i.sec_name}</span></td>
                <td style="color:#8b949e">${i.unf_price ? gp(i.unf_price) : '-'}</td>
                <td>${gp(i.price_3)}</td>
                <td>${i.price_4 ? gp(i.price_4) : '-'}</td>
                <td style="${cls3h};font-weight:600">${gp(i.profit_3_herb)}</td>
                <td style="${cls3u};font-weight:600">${i.unf_price ? gp(i.profit_3_unf) : '-'}</td>
                <td style="${clsB3};font-weight:700">${gp(i.profit_3_herb_batch)}</td>
                <td style="${clsB4};font-weight:700">${gp(i.profit_4_herb_batch)}</td>
                <td><span style="color:#a371f7">${i.xp_hr ? (i.xp_hr/1000).toFixed(1)+'K' : '-'}</span></td>
            </tr>`;
        });
        h += '</table>';
        h += `<div style="margin-top:8px;font-size:12px;color:#8b949e">⏱️ 50 sec per inv | 💡 Decanten: ${q} x 3-dose = ${Math.round(q*0.75)} x 4-dose (gratis bij Bob Barter, GE). Prijzen = GE marktprijs (1h gemiddelde).</div>`;
        el.innerHTML = h;
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

async function loadHerbClean() {
    await loadSimpleSection('/api/money/herbclean', 'herbclean-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Herb', fn:nameLink},
        {label:'Grimy', fn:i=>`<span style="color:#d29922">${gp(i.grimy_price)}</span>`},
        {label:'Clean', fn:i=>gp(i.clean_price)},
        {label:'Winst/st', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadUnfPotions() {
    await loadSimpleSection('/api/money/unfpotions', 'unfpot-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Unf Potion', fn:nameLink},
        {label:'Clean herb', fn:i=>`<span style="color:#d29922">${gp(i.clean_price)}</span> <span style="color:#484f58;font-size:10px">${i.herb_name}</span>`},
        {label:'Vial of water', fn:i=>`<span style="color:#d29922">${gp(i.vial_price)}</span>`},
        {label:'Verkoop', fn:i=>gp(i.sell_price)},
        {label:'Winst/st', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadRunecraft() {
    let lvl = document.getElementById('rc-level').value || 99;
    let el = document.getElementById('runecraft-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch(`/api/money/runecraft?level=${lvl}`)).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        document.getElementById('runecraft-info').innerHTML = `Pure essence: <b>${gp(d.ess_price)}</b> GP | RC Level: <b>${d.rc_level}</b>`;
        el.innerHTML = buildSimpleTable(d.items, [
            {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
            {label:'Rune', fn:nameLink},
            {label:'Essence', fn:i=>`<span style="color:#d29922">${gp(i.ess_price)}</span>`},
            {label:'Multi', fn:i=>`<span style="color:${i.multiplier>1?'#3fb950':'#484f58'}">${i.multiplier}x</span> <span style="color:#484f58;font-size:10px">(${i.multi_lvl}+)</span>`},
            {label:'Rune prijs', fn:i=>gp(i.rune_price)},
            {label:'Winst/rune', fn:i=>gp(i.profit), style:i=>profitStyle(i)},
            {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
            {label:'XP/hr', fn:xpCol},
            {label:'AFK', fn:afkCol},
        ]);
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

async function loadHunter() {
    await loadSimpleSection('/api/money/hunter', 'hunter-table', [
        {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}</span>`},
        {label:'Chin', fn:nameLink},
        {label:'Prijs/st', fn:i=>gp(i.sell_price)},
        {label:'Catch/hr', fn:i=>`<span style="color:#8b949e">${i.rate}</span>`},
        {label:'GP/hr', fn:i=>gp(i.profit_hr), style:i=>profitStyle(i,'profit_hr')},
        {label:'XP/hr', fn:xpCol},
        {label:'AFK', fn:afkCol},
    ]);
}

async function loadBirdhouse() {
    let el = document.getElementById('birdhouse-table');
    el.innerHTML = '<span style="color:#484f58">Laden...</span>';
    try {
        let d = await (await fetch('/api/money/birdhouse')).json();
        if (d.error) { el.innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }
        el.innerHTML = buildSimpleTable(d.items, [
            {label:'Lvl', fn:i=>`<span style="color:#484f58">${i.lvl}/${i.craft_lvl}</span>`},
            {label:'Birdhouse', fn:i=>`<span style="color:#58a6ff">${i.name}</span>`},
            {label:'Log', fn:i=>`<span style="color:#d29922">${gp(i.log_price)}</span>`},
            {label:'Seeds', fn:i=>`<span style="color:#d29922">${gp(i.seed_price)}</span>`},
            {label:'Kosten/run', fn:i=>gp(i.cost_run)},
            {label:'Nests/run', fn:i=>`<span style="color:#8b949e">${i.nests_run}</span>`},
            {label:'Winst/run', fn:i=>gp(i.profit_run), style:i=>profitStyle(i,'profit_run')},
            {label:'Winst/dag', fn:i=>gp(i.profit_day), style:i=>profitStyle(i,'profit_day')},
            {label:'AFK', fn:afkCol},
        ]);
    } catch(e) { el.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; }
}

// ═══ PRICE ALERTS ═══
let alertSelectedItem = null;
function searchAlertItem() {
    let q = document.getElementById('alert-search').value;
    let box = document.getElementById('alert-search-results');
    if (q.length < 2) { box.innerHTML = ''; return; }
    clearTimeout(qlTimer);
    qlTimer = setTimeout(async () => {
        let res = await (await fetch('/api/search?q=' + encodeURIComponent(q))).json();
        if (!res.results || !res.results.length) { box.innerHTML = '<span style="color:#484f58;font-size:12px">Geen resultaten</span>'; return; }
        box.innerHTML = res.results.slice(0,5).map(r =>
            `<div style="padding:6px 10px;cursor:pointer;border-radius:6px;font-size:13px;color:#c9d1d9" onmouseenter="this.style.background='#1c2333'" onmouseleave="this.style.background='none'" onclick="alertSelectedItem={id:${r.id},name:'${r.name.replace(/'/g,"\\'")}'};document.getElementById('alert-search').value='${r.name.replace(/'/g,"\\'")}';document.getElementById('alert-search-results').innerHTML='<span style=\\'color:#3fb950;font-size:12px\\'>✓ ${r.name.replace(/'/g,"\\'")}</span>'">${r.name} <span style="color:#484f58;font-size:11px">Limit: ${r.limit||'?'}</span></div>`
        ).join('');
    }, 200);
}

async function addAlert() {
    if (!alertSelectedItem) { alert('Selecteer eerst een item'); return; }
    let dir = document.getElementById('alert-dir').value;
    let price = parseInt(document.getElementById('alert-price').value);
    if (!price || price <= 0) { alert('Vul een geldige prijs in'); return; }
    await fetch('/api/alerts', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({item_id: alertSelectedItem.id, item_name: alertSelectedItem.name, direction: dir, target_price: price})});
    alertSelectedItem = null;
    document.getElementById('alert-search').value = '';
    document.getElementById('alert-price').value = '';
    document.getElementById('alert-search-results').innerHTML = '';
    loadAlerts();
}

async function deleteAlert(id) {
    await fetch(`/api/alerts/${id}`, {method:'DELETE'});
    loadAlerts();
}

async function loadAlerts() {
    // Check triggered
    let check = await (await fetch('/api/alerts/check')).json();
    let trigEl = document.getElementById('alert-triggered');
    if (check.triggered && check.triggered.length) {
        trigEl.innerHTML = '<div style="font-weight:600;color:#3fb950;margin-bottom:6px">🔔 Getriggerde alerts!</div>' +
            check.triggered.map(a => `<div style="background:#1a3a2a;border:1px solid #238636;border-radius:8px;padding:10px 14px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
                <div><b style="color:#c9d1d9">${a.item_name}</b> — prijs is nu <b style="color:#3fb950">${gp(a.current_price)}</b> GP (target: ${a.direction === 'below' ? '≤' : '≥'} ${gp(a.target_price)})</div>
                <button onclick="deleteAlert(${a.id})" style="padding:4px 10px;background:#da3633;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px">Verwijder</button>
            </div>`).join('');
    } else { trigEl.innerHTML = ''; }
    // List all
    let d = await (await fetch('/api/alerts')).json();
    let el = document.getElementById('alert-list');
    if (!d.alerts || !d.alerts.length) { el.innerHTML = '<span style="color:#484f58;font-size:13px">Geen alerts ingesteld. Voeg er een toe hierboven.</span>'; return; }
    el.innerHTML = '<div style="font-size:12px;font-weight:600;color:#8b949e;margin-bottom:8px">Actieve alerts (' + d.alerts.length + ')</div>' +
        d.alerts.map(a => `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:8px;margin-bottom:6px">
            <div><span style="cursor:pointer;color:#58a6ff" onclick="openItemDetail(${a.item_id},'${(a.item_name||'').replace(/'/g,"\\'")}')">${a.item_name}</span>
            <span style="color:#8b949e;font-size:12px;margin-left:8px">${a.direction === 'below' ? '≤' : '≥'} <b>${gp(a.target_price)}</b> GP</span>
            ${a.triggered ? '<span style="color:#3fb950;font-size:11px;margin-left:6px">✓ TRIGGERED</span>' : ''}</div>
            <button onclick="deleteAlert(${a.id})" style="padding:4px 10px;background:#21262d;color:#8b949e;border:1px solid #30363d;border-radius:6px;cursor:pointer;font-size:11px">✕</button>
        </div>`).join('');
}

// Auto-check alerts elke 60 sec
setInterval(async () => {
    let check = await (await fetch('/api/alerts/check')).json();
    if (check.triggered && check.triggered.length) {
        let badge = document.querySelector('[onclick*="alerts"]');
        if (badge && !badge.textContent.includes('●')) badge.innerHTML = '🔔 Price Alerts <span style="color:#3fb950">●</span>';
    }
}, 60000);

// ═══ PROFIT TRACKER ═══
async function logProfit() {
    let method = document.getElementById('log-method').value;
    let item = document.getElementById('log-item').value;
    let profit = parseInt(document.getElementById('log-profit').value);
    let qty = parseInt(document.getElementById('log-qty').value) || 1;
    if (!method || !profit) { alert('Vul methode en winst in'); return; }
    await fetch('/api/profit/log', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({method, item, profit, quantity: qty})});
    document.getElementById('log-method').value = '';
    document.getElementById('log-item').value = '';
    document.getElementById('log-profit').value = '';
    document.getElementById('log-qty').value = '1';
    loadTracker();
}

async function loadTracker() {
    let d = await (await fetch('/api/profit/summary')).json();
    let sumEl = document.getElementById('tracker-summary');
    let todayCls = d.today >= 0 ? 'color:#3fb950' : 'color:#da3633';
    let weekCls = d.week >= 0 ? 'color:#3fb950' : 'color:#da3633';
    let allCls = d.all_time >= 0 ? 'color:#3fb950' : 'color:#da3633';
    sumEl.innerHTML = `
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Vandaag</div>
            <div style="${todayCls};font-size:20px;font-weight:700">${gp(d.today)} GP</div>
            <div style="color:#484f58;font-size:11px">${d.today_count} entries</div>
        </div>
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Deze week</div>
            <div style="${weekCls};font-size:20px;font-weight:700">${gp(d.week)} GP</div>
            <div style="color:#484f58;font-size:11px">${d.week_count} entries</div>
        </div>
        <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Totaal</div>
            <div style="${allCls};font-size:20px;font-weight:700">${gp(d.all_time)} GP</div>
            <div style="color:#484f58;font-size:11px">${d.all_count} entries</div>
        </div>`;
    // Log entries
    let logEl = document.getElementById('tracker-log');
    if (!d.entries || !d.entries.length) { logEl.innerHTML = '<span style="color:#484f58;font-size:13px">Nog geen winst gelogd. Gebruik de knop hierboven om te beginnen.</span>'; return; }
    let h = '<table><tr><th>Tijd</th><th>Methode</th><th>Item</th><th>Winst</th><th>Aantal</th><th>Totaal</th></tr>';
    d.entries.reverse().forEach(e => {
        let dt = new Date(e.timestamp * 1000);
        let time = dt.toLocaleTimeString('nl-NL', {hour:'2-digit',minute:'2-digit'});
        let date = dt.toLocaleDateString('nl-NL', {day:'numeric',month:'short'});
        let cls = e.profit >= 0 ? 'color:#3fb950' : 'color:#da3633';
        h += `<tr><td style="color:#484f58;font-size:12px">${date} ${time}</td><td>${e.method}</td><td style="color:#8b949e">${e.item||'-'}</td><td style="${cls};font-weight:600">${gp(e.profit)}</td><td>${e.quantity}</td><td style="${cls};font-weight:700">${gp(e.profit * e.quantity)}</td></tr>`;
    });
    logEl.innerHTML = h + '</table>';
}

// ── FARMING CALCULATOR ──
let farmMeta = null;  // tree/fruit/special lists + patch data
let farmPatchState = {};
let farmSpecialState = {};

function initFarmingCalc() {
    if (farmMeta) return;
    // Haal metadata op via lege calc call
    fetch('/api/farming/calc?current=1&target=2&selections={}&patches={}')
        .then(r => r.json())
        .then(d => {
            farmMeta = d;
            populateFarmDropdowns();
            renderFarmPatches();
        });
    // Auto-lookup als RSN al is ingesteld
    lookupFarmingLevel(true);
}

async function lookupFarmingLevel(silent) {
    let statusEl = document.getElementById('farm-lookup-status');
    // Haal RSN uit instellingen
    let settings;
    try { settings = await (await fetch('/api/settings')).json(); } catch(e) { return; }
    let rsn = settings.account_name;
    if (!rsn || !rsn.trim()) {
        if (!silent) statusEl.innerHTML = '<span style="color:#d29922">Vul eerst je RSN in bij Instellingen</span>';
        return;
    }
    statusEl.innerHTML = `<span style="color:#58a6ff">Zoeken naar ${rsn}...</span>`;
    try {
        let d = await (await fetch('/api/hiscores/' + encodeURIComponent(rsn))).json();
        if (d.error) {
            statusEl.innerHTML = `<span style="color:#da3633">${d.error}</span>`;
            return;
        }
        let farming = d.skills?.farming;
        if (farming) {
            document.getElementById('farm-current').value = farming.level;
            statusEl.innerHTML = `<span style="color:#3fb950">✓ ${rsn} — Farming level ${farming.level} (${gp(farming.xp)} XP)</span>`;
        } else {
            statusEl.innerHTML = '<span style="color:#da3633">Farming data niet gevonden</span>';
        }
    } catch(e) {
        statusEl.innerHTML = '<span style="color:#da3633">Hiscores lookup mislukt</span>';
    }
}

function populateFarmDropdowns() {
    if (!farmMeta) return;
    // Trees dropdown
    let tSel = document.getElementById('farm-sel-tree');
    (farmMeta.trees || []).forEach(t => {
        tSel.innerHTML += `<option value="${t.name}">${t.name} (lvl ${t.lvl})</option>`;
    });
    // Fruit trees dropdown
    let fSel = document.getElementById('farm-sel-fruit');
    (farmMeta.fruit_trees || []).forEach(t => {
        fSel.innerHTML += `<option value="${t.name}">${t.name} (lvl ${t.lvl})</option>`;
    });
    // Hardwood dropdown
    let hSel = document.getElementById('farm-sel-hardwood');
    (farmMeta.hardwoods || []).forEach(t => {
        hSel.innerHTML += `<option value="${t.name}">${t.name} (lvl ${t.lvl})</option>`;
    });
    // Specials checkboxes
    let spEl = document.getElementById('farm-sel-specials');
    let spH = '';
    (farmMeta.specials || []).forEach(s => {
        farmSpecialState[s.type] = false;
        spH += `<label style="display:flex;align-items:center;gap:6px;font-size:12px;color:#c9d1d9;margin:3px 0;cursor:pointer">
            <input type="checkbox" onchange="farmSpecialState['${s.type}']=this.checked" style="accent-color:#238636">
            ${s.name} <span style="color:#8b949e;font-size:10px">(lvl ${s.lvl})</span>
        </label>`;
    });
    spEl.innerHTML = spH;
}

function renderFarmPatches() {
    let el = document.getElementById('farm-patches');
    if (!farmMeta || !farmMeta.patches) { el.innerHTML = ''; return; }
    const labels = {
        tree: '🌲 Tree Patches', fruit_tree: '🍎 Fruit Tree Patches',
        calquat: '🌴 Calquat', celastrus: '🌿 Celastrus',
        redwood: '🪵 Redwood', spirit: '👻 Spirit Tree', hardwood: '🪓 Hardwood'
    };
    let h = '';
    for (let [type, patches] of Object.entries(farmMeta.patches)) {
        h += `<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px">`;
        h += `<div style="font-size:11px;font-weight:600;color:#58a6ff;margin-bottom:4px">${labels[type] || type}</div>`;
        patches.forEach(p => {
            if (!(p.key in farmPatchState)) farmPatchState[p.key] = true;
            let checked = farmPatchState[p.key] ? 'checked' : '';
            let quest = p.quest ? ` <span style="color:#d29922;font-size:10px">(${p.quest})</span>` : '';
            h += `<label style="display:flex;align-items:center;gap:6px;font-size:11px;color:#c9d1d9;margin:2px 0;cursor:pointer">
                <input type="checkbox" ${checked} onchange="farmPatchState['${p.key}']=this.checked" style="accent-color:#238636">
                ${p.name}${quest}
            </label>`;
        });
        h += `</div>`;
    }
    el.innerHTML = h;
}

async function calcFarming() {
    let current = parseInt(document.getElementById('farm-current').value) || 1;
    let target = parseInt(document.getElementById('farm-target').value) || 99;
    if (target <= current) { alert('Doel level moet hoger zijn dan huidig level'); return; }

    // Bouw selections object
    let selections = {};
    let treeSel = document.getElementById('farm-sel-tree').value;
    if (treeSel) selections.tree = treeSel;
    let fruitSel = document.getElementById('farm-sel-fruit').value;
    if (fruitSel) selections.fruit_tree = fruitSel;
    let hwSel = document.getElementById('farm-sel-hardwood').value;
    if (hwSel) selections.hardwood = hwSel;
    for (let [k, v] of Object.entries(farmSpecialState)) {
        if (v) selections[k] = true;
    }

    if (Object.keys(selections).length === 0) {
        alert('Selecteer minstens 1 gewas'); return;
    }

    let buyType = document.getElementById('farm-buy-type').value;
    let playStart = parseInt(document.getElementById('farm-play-start').value) || 8;
    let playEnd = parseInt(document.getElementById('farm-play-end').value) || 23;
    let maxRuns = parseInt(document.getElementById('farm-max-runs').value) || 0;

    let resultsDiv = document.getElementById('farm-results');
    resultsDiv.style.display = '';
    document.getElementById('farm-table').innerHTML = '<span style="color:#484f58">Berekenen...</span>';

    let patchesParam = encodeURIComponent(JSON.stringify(farmPatchState));
    let selectionsParam = encodeURIComponent(JSON.stringify(selections));
    let d;
    try {
        d = await (await fetch(`/api/farming/calc?current=${current}&target=${target}&patches=${patchesParam}&selections=${selectionsParam}&buy_type=${buyType}&play_start=${playStart}&play_end=${playEnd}&max_runs=${maxRuns}`)).json();
    } catch(e) { document.getElementById('farm-table').innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; return; }
    if (d.error) { document.getElementById('farm-table').innerHTML = `<span style="color:#da3633">${d.error}</span>`; return; }

    let buyLabel = buyType === 'sapling' ? 'Sapling' : 'Seed';

    // XP samenvatting met dagen
    let ps = d.play_start || 8, pe = d.play_end || 23;
    document.getElementById('farm-xp-summary').innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px">
            <div style="background:#161b22;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Huidig XP</div>
                <div style="font-size:18px;font-weight:700;color:#58a6ff">${gp(d.current_xp)}</div>
                <div style="font-size:12px;color:#8b949e">Level ${d.current_lvl}</div>
            </div>
            <div style="background:#161b22;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Doel XP</div>
                <div style="font-size:18px;font-weight:700;color:#3fb950">${gp(d.target_xp)}</div>
                <div style="font-size:12px;color:#8b949e">Level ${d.target_lvl}</div>
            </div>
            <div style="background:#161b22;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:11px;color:#8b949e">XP Nodig</div>
                <div style="font-size:18px;font-weight:700;color:#d29922">${gp(d.xp_needed)}</div>
            </div>
            <div style="background:#161b22;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:11px;color:#8b949e">XP / Dag</div>
                <div style="font-size:18px;font-weight:700;color:#a371f7">${gp(d.total_xp_per_day)}</div>
            </div>
            <div style="background:#161b22;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:11px;color:#8b949e">Speeltijd</div>
                <div style="font-size:16px;font-weight:700;color:#c9d1d9">${ps}:00 — ${pe}:00</div>
                <div style="font-size:12px;color:#8b949e">${d.available_hours}h beschikbaar</div>
            </div>
            <div style="background:#238636;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:11px;color:#ffffffcc">Geschatte Tijd</div>
                <div style="font-size:22px;font-weight:700;color:#fff">${d.days_needed} dagen</div>
            </div>
        </div>`;

    if (!d.items || !d.items.length) {
        document.getElementById('farm-table').innerHTML = '<span style="color:#484f58">Geen resultaten. Controleer of je patches hebt aangevinkt.</span>';
        return;
    }

    // ── Dagelijks schema ──
    let sched = '<div style="margin-bottom:14px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px">';
    sched += '<div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:8px">Dagelijks Schema</div>';
    sched += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px">';
    d.items.forEach(i => {
        let times = (i.run_times || []).join(', ') || '-';
        sched += `<div style="background:#0d1117;border-radius:6px;padding:8px 12px">
            <div style="font-size:12px;font-weight:600;color:#c9d1d9">${i.name}</div>
            <div style="font-size:11px;color:#8b949e;margin-top:2px">${i.runs_per_day}x/dag — groei: ${i.growth}</div>
            <div style="font-size:12px;color:#3fb950;margin-top:4px;font-weight:600">${times}</div>
        </div>`;
    });
    sched += '</div></div>';

    // ── Prijsvergelijking seed vs sapling ──
    let priceComp = '<div style="margin-bottom:14px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px">';
    priceComp += '<div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:6px">Prijsvergelijking Seed vs Sapling</div>';
    priceComp += '<table style="font-size:11px;width:auto"><tr><th>Gewas</th><th>Seed prijs</th><th>Sapling prijs</th><th>Verschil</th></tr>';
    d.items.forEach(i => {
        let diff = i.price_sapling - i.price_seed;
        let diffCls = diff > 0 ? 'color:#da3633' : diff < 0 ? 'color:#3fb950' : 'color:#8b949e';
        let diffSign = diff > 0 ? '+' : '';
        priceComp += `<tr>
            <td>${i.name}</td>
            <td ${buyType==='seed'?'style="font-weight:700;color:#3fb950"':'style="color:#8b949e"'}>${gp(i.price_seed)}</td>
            <td ${buyType==='sapling'?'style="font-weight:700;color:#3fb950"':'style="color:#8b949e"'}>${gp(i.price_sapling)}</td>
            <td style="${diffCls}">${diffSign}${gp(diff)}</td>
        </tr>`;
    });
    priceComp += '</table></div>';

    // ── Resultaten tabel ──
    let h = sched + priceComp;
    h += `<table style="font-size:12px;width:100%"><tr>
        <th>Gewas</th><th>Lvl</th><th>XP/tree</th><th>Patches</th>
        <th>Groeitijd</th><th>Runs/dag</th><th style="color:#a371f7">XP/dag</th>
        <th>Totale runs</th><th>Trees totaal</th>
        <th style="color:#3fb950">${buyLabel}/run</th><th style="color:#d29922">Protect/run</th><th>Totaal/run</th>
        <th style="color:#3fb950">${buyLabel}s totaal</th><th style="color:#d29922">Protect totaal</th><th style="font-weight:700">Kosten</th>
    </tr>`;
    d.items.forEach(i => {
        h += `<tr>
            <td><span style="color:#58a6ff;font-weight:600">${i.category}</span><br><span style="font-size:11px;color:#c9d1d9">${i.name}</span></td>
            <td>${i.lvl}</td>
            <td style="color:#a371f7">${gp(Math.round(i.xp_per_tree))}</td>
            <td>${i.patches}</td>
            <td style="color:#8b949e">${i.growth}</td>
            <td>${i.runs_per_day}</td>
            <td style="color:#a371f7;font-weight:600">${gp(i.xp_per_day)}</td>
            <td style="font-weight:700">${i.total_runs}</td>
            <td>${i.trees_needed}</td>
            <td style="color:#3fb950">${gp(i.seed_cost_run)}</td>
            <td style="color:#d29922">${gp(i.protect_cost_run)}</td>
            <td>${gp(i.total_cost_run)}</td>
            <td style="color:#3fb950">${gp(i.seed_cost_total)}</td>
            <td style="color:#d29922">${gp(i.protect_cost_total)}</td>
            <td style="font-weight:700">${gp(i.total_cost)}</td>
        </tr>`;
    });
    h += `<tr style="border-top:2px solid #30363d;font-weight:700">
        <td colspan="12" style="text-align:right;padding-right:12px">TOTAAL →</td>
        <td style="color:#3fb950">${gp(d.grand_seed)}</td>
        <td style="color:#d29922">${gp(d.grand_protect)}</td>
        <td>${gp(d.grand_total)}</td>
    </tr>`;
    h += '</table>';
    h += `<div style="margin-top:14px;font-size:11px;color:#484f58;line-height:1.6">
        💡 Runs zijn berekend op basis van je speeltijd (${ps}:00-${pe}:00). Snellere bomen passen vaker in je venster.<br>
        Protection is optioneel maar voorkomt dat je tree doodgaat.
        ${d.items.map(i => '<b>' + i.name + '</b>: ' + i.protect_name + ' x' + i.protect_qty).join(' | ')}
    </div>`;
    document.getElementById('farm-table').innerHTML = h;
}

async function loadAlch() {
    let staff = document.getElementById('alch-staff').value;
    let bulkEl = document.getElementById('alch-bulk');
    let hvEl = document.getElementById('alch-highvalue');
    let infoEl = document.getElementById('alch-info');
    bulkEl.innerHTML = '<span style="color:#484f58">Laden...</span>';
    hvEl.innerHTML = '';

    let d;
    try { d = await (await fetch('/api/money/alch?staff=' + staff)).json(); }
    catch(e) { bulkEl.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; return; }
    if (d.error) { bulkEl.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; return; }

    let rb = d.rune_breakdown || {};
    let runeH = '<b>Runes per cast:</b> ';
    runeH += `1× Nature (${gpExact(rb.nature?.cost || 0)} GP)`;
    if (rb.fire?.saved) {
        runeH += ' | <span style="color:#3fb950">5× Fire — bespaard door staf ✓</span>';
    } else {
        runeH += ` | 5× Fire (${gpExact(rb.fire?.cost || 0)} GP)`;
    }
    runeH += ` | <b>Totaal: ${gpExact(d.cast_cost)} GP/cast</b>`;
    infoEl.innerHTML = runeH;

    function alchTable(items, showMaxWinst) {
        if (!items || !items.length) return '<span style="color:#484f58;font-size:12px">Geen winstgevende items gevonden met voldoende volume</span>';
        let cols = '<tr><th>#</th><th>Item</th><th>Advies Koop</th><th>Alch Waarde</th><th>Rune Cost</th><th>Winst/cast</th><th>Buy Limit</th><th>Vol/dag</th>';
        if (showMaxWinst) cols += '<th>Max Winst</th>';
        cols += '</tr>';
        let h = `<table style="font-size:12px">${cols}`;
        items.forEach((it, i) => {
            let mw = showMaxWinst && it.buy_limit ? gpExact(it.profit * it.buy_limit) + ' GP' : '';
            h += `<tr><td>${i+1}</td><td>${it.name}</td>
                <td class="gp"><b>${gpExact(it.buy_price)}</b></td>
                <td style="color:#d29922">${gpExact(it.alch_value)}</td>
                <td style="color:#8b949e">${gpExact(it.cast_cost)}</td>
                <td class="profit-pos"><b>${gpExact(it.profit)} GP</b></td>
                <td>${it.buy_limit || '?'}</td><td>${it.volume.toLocaleString()}</td>`;
            if (showMaxWinst) h += `<td style="color:#3fb950">${mw}</td>`;
            h += '</tr>';
        });
        return h + '</table>';
    }
    bulkEl.innerHTML = alchTable(d.bulk, true);
    hvEl.innerHTML = alchTable(d.highvalue, false);
}

async function loadBolts() {
    let staff = document.getElementById('bolt-staff').value;
    let tableEl = document.getElementById('bolt-table');
    let infoEl = document.getElementById('bolt-info');
    tableEl.innerHTML = '<span style="color:#484f58">Laden...</span>';

    let d = await (await fetch('/api/money/bolts?staff=' + staff)).json();
    if (d.error) { tableEl.innerHTML = '<span style="color:#da3633">Fout bij laden</span>'; return; }

    let rp = d.rune_prices || {};
    infoEl.innerHTML = `Rune prijzen — Cosmic: <b>${gpExact(rp.cosmic||0)}</b> | Nature: <b>${gpExact(rp.nature||0)}</b> | Blood: <b>${gpExact(rp.blood||0)}</b> | Soul: <b>${gpExact(rp.soul||0)}</b> | Death: <b>${gpExact(rp.death||0)}</b> | Law: <b>${gpExact(rp.law||0)}</b>`;

    if (!d.bolts.length) {
        tableEl.innerHTML = '<span style="color:#484f58;font-size:12px">Geen bolt enchants beschikbaar</span>';
        return;
    }

    let advColors = {top:'#3fb950', goed:'#58a6ff', matig:'#d29922', laag:'#484f58', risico:'#da3633', vermijd:'#da3633'};
    let advLabels = {top:'★ Top', goed:'● Goed', matig:'◐ Matig', laag:'○ Laag', risico:'⚠ Risico', vermijd:'✗ Vermijd'};

    let h = `<table style="font-size:11px"><tr><th>Advies</th><th>Bolt (koop)</th><th>Lvl</th><th>Type</th><th>Runes (per cast)</th><th>Koop/st</th><th>Verkoop (e)/st</th><th>Rune Cost</th><th>Winst/10</th><th>Buy Limit</th><th>Max Winst</th><th>Koop Vol</th><th>Verkoop Vol</th><th>Advies Staf</th></tr>`;
    d.bolts.forEach(b => {
        let tooLow = mmMagicLevel !== null && b.level > mmMagicLevel;
        let rowStyle = tooLow ? 'color:#da3633;opacity:0.55' : '';
        let profitCls = b.profit_10 >= 0 ? 'profit-pos' : 'profit-neg';
        let typeLabel = b.variant === 'dragon' ? '<span style="color:#d29922;font-size:10px">DRAGON</span>' : '<span style="color:#484f58;font-size:10px">Regular</span>';
        let levelStyle = tooLow ? 'color:#da3633;font-weight:700' : (b.level <= 30 ? 'color:#3fb950' : 'color:#c9d1d9');

        // Rune detail inline
        let runeStr = b.rune_detail.map(r => {
            if (r.saved) return `<span style="color:#3fb950">${r.qty}× ${r.rune} ✓</span>`;
            return `${r.qty}× ${r.rune} <span style="color:#484f58">(${gpExact(r.unit)}/st = ${gpExact(r.cost)})</span>`;
        }).join('<br>');

        let recStaff = b.recommended_save > 0 ? `<span style="color:#d29922" title="Bespaart ${gpExact(b.recommended_save)} GP/cast">${b.recommended_staff_name}</span>` : '<span style="color:#484f58">–</span>';

        // Volume kleuring
        let buyVolStyle = b.buy_vol >= 1000 ? 'color:#3fb950' : (b.buy_vol >= 200 ? 'color:#d29922' : 'color:#da3633');
        let sellVolStyle = b.sell_vol >= 1000 ? 'color:#3fb950' : (b.sell_vol >= 200 ? 'color:#d29922' : 'color:#da3633');

        // Advisory badge
        let advColor = advColors[b.advisory] || '#484f58';
        let advLabel = advLabels[b.advisory] || b.advisory;
        if (tooLow) { advColor = '#da3633'; advLabel = '🔒 Lvl ' + b.level; }

        let priceWarn = '';

        h += `<tr style="${rowStyle}">
            <td><span style="color:${advColor};font-weight:700;font-size:11px">${advLabel}</span></td>
            <td>${b.base_name} <span style="color:#484f58;font-size:9px">→ (e)</span></td>
            <td style="${levelStyle}">${b.level}</td>
            <td>${typeLabel}</td>
            <td style="font-size:10px;line-height:1.5">${runeStr}</td>
            <td class="gp">${gpExact(b.bolt_price)}${priceWarn}</td>
            <td class="gp">${gpExact(b.result_price)}${priceWarn}</td>
            <td style="color:#8b949e">${gpExact(b.rune_cost)}</td>
            <td class="${profitCls}"><b>${gpExact(b.profit_10)} GP</b>${priceWarn}</td>
            <td>${b.buy_limit || '?'}</td>
            <td style="color:#3fb950">${b.max_profit ? gpExact(b.max_profit) + ' GP' : '–'}</td>
            <td style="${buyVolStyle}">${b.buy_vol.toLocaleString()}</td>
            <td style="${sellVolStyle}">${b.sell_vol.toLocaleString()}</td>
            <td style="font-size:10px">${recStaff}</td></tr>`;
    });
    h += '</table>';
    h += `<div style="margin-top:8px;font-size:12px;color:#8b949e">⏱️ 1-tick: Click-intensive | 10x10: ~30 sec per set</div>`;
    tableEl.innerHTML = h;
}

// FLIP CALCULATOR
function updateCalc() {
    let buy = parseGP(document.getElementById('calc-buy').value);
    let sell = parseGP(document.getElementById('calc-sell').value);
    let qty = parseInt(document.getElementById('calc-qty').value) || 1;
    let limit = parseInt(document.getElementById('calc-limit').value) || 0;
    let el = document.getElementById('calc-result');
    if (!buy || !sell) { el.innerHTML = '<span style="color:#484f58">Vul koop- en verkoopprijs in om te berekenen</span>'; return; }

    let taxRate = 0.02;
    let taxMax = 5000000;
    let taxPerItem = Math.min(sell * taxRate, taxMax);
    let profitPerItem = sell - buy - taxPerItem;
    let totalCost = buy * qty;
    let totalRevenue = sell * qty;
    let totalTax = taxPerItem * qty;
    let totalProfit = profitPerItem * qty;
    let roi = buy > 0 ? (profitPerItem / buy * 100) : 0;

    let limitProfit = limit > 0 ? profitPerItem * limit : null;
    let limitCost = limit > 0 ? buy * limit : null;

    let cls = totalProfit >= 0 ? 'profit-pos' : 'profit-neg';
    let h = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 20px">
            <div>💰 <b>Winst per item:</b></div><div class="${cls}"><b>${gpExact(profitPerItem)} GP</b></div>
            <div>📦 <b>Totale investering:</b></div><div>${gpExact(totalCost)} GP</div>
            <div>🏷️ <b>Totale opbrengst:</b></div><div>${gpExact(totalRevenue)} GP</div>
            <div>🏛️ <b>Totale GE Tax:</b></div><div style="color:#da3633">${gpExact(totalTax)} GP</div>
            <div>📊 <b>Totale winst (${qty}x):</b></div><div class="${cls}" style="font-size:16px"><b>${gpExact(totalProfit)} GP</b></div>
            <div>📈 <b>ROI:</b></div><div style="color:${roi >= 0 ? '#3fb950' : '#da3633'}">${roi.toFixed(2)}%</div>`;
    if (limitProfit !== null) {
        h += `<div style="border-top:1px solid #30363d;padding-top:8px;grid-column:1/-1;margin-top:4px"></div>
            <div>🔒 <b>Max winst (buy limit ${limit}x):</b></div><div class="${limitProfit>=0?'profit-pos':'profit-neg'}"><b>${gpExact(limitProfit)} GP</b></div>
            <div>🔒 <b>Benodigde GP (${limit}x):</b></div><div>${gpExact(limitCost)} GP</div>`;
    }
    h += '</div>';
    el.innerHTML = h;
}

// ITEM DETAIL POPUP
async function showItemDetail(itemName) {
    if (!itemName) return;
    let modal = document.getElementById('detail-modal');
    let titleEl = document.getElementById('detail-title');
    let contentEl = document.getElementById('detail-content');

    titleEl.textContent = '📋 ' + itemName;
    contentEl.innerHTML = '<div style="text-align:center;padding:20px;color:#484f58">Laden...</div>';
    modal.classList.add('show');

    let hist = await (await fetch('/api/history')).json();
    let itemTrades = hist.filter(t => t.name === itemName);

    if (!itemTrades.length) {
        contentEl.innerHTML = '<div style="text-align:center;padding:20px;color:#484f58">Geen voltooide trades voor dit item</div>';
        return;
    }

    let totalProfit = itemTrades.reduce((s,t) => s + (t.profit||0), 0);
    let totalQty = itemTrades.reduce((s,t) => s + (t.sell_quantity||t.quantity||0), 0);
    let totalTax = itemTrades.reduce((s,t) => s + (t.tax||0), 0);
    let avgProfit = Math.round(totalProfit / itemTrades.length);
    let wins = itemTrades.filter(t => (t.profit||0) > 0).length;
    let winRate = Math.round(wins / itemTrades.length * 100);
    let flipsWithTime = itemTrades.filter(t => t.flip_minutes != null && t.flip_minutes > 0);
    let avgFlipMins = flipsWithTime.length ? Math.round(flipsWithTime.reduce((s,t) => s + t.flip_minutes, 0) / flipsWithTime.length) : null;
    let flipTimeStr = avgFlipMins != null ? (avgFlipMins < 60 ? avgFlipMins + ' min' : Math.floor(avgFlipMins/60) + 'u ' + (avgFlipMins%60) + 'm') : '–';
    let bestTrade = itemTrades.reduce((b,t) => (t.profit||0) > (b.profit||0) ? t : b);
    let worstTrade = itemTrades.reduce((w,t) => (t.profit||0) < (w.profit||0) ? t : w);
    let cls = totalProfit >= 0 ? 'profit-pos' : 'profit-neg';

    let h = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:16px">
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="font-size:10px;color:#8b949e">Totale Winst</div>
            <div style="font-size:16px;font-weight:700" class="${cls}">${gp(totalProfit)}</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="font-size:10px;color:#8b949e">Trades</div>
            <div style="font-size:16px;font-weight:700;color:#c9d1d9">${itemTrades.length}x</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="font-size:10px;color:#8b949e">Win Rate</div>
            <div style="font-size:16px;font-weight:700;color:${winRate>=50?'#3fb950':'#da3633'}">${winRate}%</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="font-size:10px;color:#8b949e">Gem. Flip Tijd</div>
            <div style="font-size:16px;font-weight:700;color:#d29922">${flipTimeStr}</div>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;font-size:13px;margin-bottom:16px">
        <div>📦 <b>Totaal verhandeld:</b></div><div>${totalQty.toLocaleString()} stuks</div>
        <div>📊 <b>Gem. winst/trade:</b></div><div class="${avgProfit>=0?'profit-pos':'profit-neg'}">${gpExact(avgProfit)} GP</div>
        <div>🏛️ <b>Totale tax betaald:</b></div><div style="color:#da3633">${gpExact(totalTax)} GP</div>
        <div>🏆 <b>Beste trade:</b></div><div class="profit-pos">${gpExact(bestTrade.profit||0)} GP</div>
        <div>💀 <b>Slechtste trade:</b></div><div class="profit-neg">${gpExact(worstTrade.profit||0)} GP</div>
    </div>
    <div style="font-size:12px;font-weight:600;color:#8b949e;margin-bottom:8px">Recente trades</div>
    <table style="font-size:12px"><tr><th>Datum</th><th>Koop</th><th>Verkoop</th><th>Aantal</th><th>Winst</th><th>Flip</th></tr>`;

    itemTrades.slice(-10).reverse().forEach(t => {
        let pcls = (t.profit||0) >= 0 ? 'profit-pos' : 'profit-neg';
        let date = t.closed_at ? new Date(t.closed_at).toLocaleDateString('nl-NL', {day:'numeric',month:'short'}) : '–';
        let fm = t.flip_minutes;
        let fStr = fm != null ? (fm < 60 ? fm + 'm' : Math.floor(fm/60) + 'u') : '–';
        h += `<tr><td>${date}</td><td class="gp">${gpExact(t.buy_price)}</td><td class="gp">${gpExact(t.sell_price)}</td>
            <td>${(t.sell_quantity||t.quantity||0).toLocaleString()}x</td><td class="${pcls}">${gpExact(t.profit)} GP</td><td style="color:#d29922">${fStr}</td></tr>`;
    });
    h += '</table>';
    contentEl.innerHTML = h;
}

// PORTFOLIO DASHBOARD WIDGET (main dashboard)
async function renderPortfolio() {
    let el = document.getElementById('d-portfolio');
    if (!el) return;
    let hist = await (await fetch('/api/history')).json();
    if (!hist.length) { el.innerHTML = ''; return; }

    let totalProfit = hist.reduce((s,t) => s + (t.profit||0), 0);
    let wins = hist.filter(t => (t.profit||0) > 0).length;
    let winRate = hist.length ? Math.round(wins / hist.length * 100) : 0;
    let todayStr = new Date().toISOString().slice(0,10);
    let todayTrades = hist.filter(t => t.closed_at && t.closed_at.slice(0,10) === todayStr);
    let todayProfit = todayTrades.reduce((s,t) => s + (t.profit||0), 0);

    // Top 3 items by profit
    let itemProfits = {};
    hist.forEach(t => { if(t.name) itemProfits[t.name] = (itemProfits[t.name]||0) + (t.profit||0); });
    let topItems = Object.entries(itemProfits).sort((a,b) => b[1] - a[1]).slice(0, 3);

    let cls = totalProfit >= 0 ? 'profit-pos' : 'profit-neg';
    let tCls = todayProfit >= 0 ? 'profit-pos' : 'profit-neg';

    let h = `<div class="section"><div class="sh t2">📊 Portfolio Samenvatting</div>
        <div style="display:flex;flex-wrap:wrap;gap:12px;padding:14px 18px;align-items:stretch">
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 18px;flex:1;min-width:120px;text-align:center">
                <div style="font-size:10px;color:#8b949e">Totale Winst</div>
                <div style="font-size:18px;font-weight:700" class="${cls}">${gp(totalProfit)}</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 18px;flex:1;min-width:120px;text-align:center">
                <div style="font-size:10px;color:#8b949e">Vandaag</div>
                <div style="font-size:18px;font-weight:700" class="${tCls}">${todayTrades.length ? gp(todayProfit) : '–'}</div>
                <div style="font-size:10px;color:#484f58">${todayTrades.length} trades</div>
            </div>
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 18px;flex:1;min-width:120px;text-align:center">
                <div style="font-size:10px;color:#8b949e">Win Rate</div>
                <div style="font-size:18px;font-weight:700;color:${winRate>=50?'#3fb950':'#da3633'}">${winRate}%</div>
                <div style="font-size:10px;color:#484f58">${hist.length} trades</div>
            </div>`;
    if (topItems.length) {
        h += `<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 18px;flex:1.5;min-width:180px">
            <div style="font-size:10px;color:#8b949e;margin-bottom:6px">Top Items</div>`;
        topItems.forEach(([name, profit]) => {
            h += `<div style="display:flex;justify-content:space-between;font-size:12px;padding:2px 0">
                <span style="color:#58a6ff;cursor:pointer" onclick="showPage('history')">${name}</span>
                <span class="${profit>=0?'profit-pos':'profit-neg'}">${gp(profit)}</span></div>`;
        });
        h += '</div>';
    }
    h += '</div></div>';
    el.innerHTML = h;
}

// SPLASH SCREEN
let splashDismissed = false;

async function initSplash() {
    // Haal settings op om te checken of RSN al is ingevuld
    let s = await (await fetch('/api/settings')).json();
    let name = s.account_name || '';

    if (!name) {
        // Eerste keer: toon RSN input
        document.getElementById('splash-name').textContent = 'Welkom!';
        document.getElementById('splash-setup').style.display = 'block';
        document.getElementById('splash-status').style.display = 'none';
        document.getElementById('splash-rsn').focus();
    } else {
        // Terugkerend: toon naam + loading
        document.getElementById('splash-name').textContent = 'Welkom terug, ' + name;
        document.getElementById('splash-setup').style.display = 'none';
        document.getElementById('splash-status').style.display = 'flex';
        // Wacht op eerste marktdata
        pollSplashReady();
    }
}

async function splashSaveRsn() {
    let rsn = document.getElementById('splash-rsn').value.trim();
    if (!rsn) { document.getElementById('splash-rsn').focus(); return; }
    // Sla RSN op
    let s = await (await fetch('/api/settings')).json();
    s.account_name = rsn;
    await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(s)});
    // Switch naar loading state
    document.getElementById('splash-name').textContent = 'Welkom, ' + rsn;
    document.getElementById('splash-setup').style.display = 'none';
    document.getElementById('splash-status').style.display = 'flex';
    pollSplashReady();
}

// Enter toets op RSN input
document.getElementById('splash-rsn').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') splashSaveRsn();
});

async function pollSplashReady() {
    let statusEl = document.getElementById('splash-status-text');
    let goBtn = document.getElementById('splash-go');
    let spinnerParent = document.getElementById('splash-status');

    statusEl.textContent = 'Marktdata laden...';

    // Poll tot data beschikbaar is
    let attempts = 0;
    let interval = setInterval(async () => {
        attempts++;
        try {
            let r = await fetch('/api/market');
            let d = await r.json();
            let hasData = (d.bulk && d.bulk.length > 0) || (d.tier0 && d.tier0.length > 0) || (d.tier1 && d.tier1.length > 0) || (d.tier2 && d.tier2.length > 0);

            if (attempts <= 3) statusEl.textContent = 'Verbinden met GE API...';
            else if (attempts <= 8) statusEl.textContent = 'Items analyseren...';
            else statusEl.textContent = 'Voorspellingen berekenen...';

            if (hasData) {
                clearInterval(interval);
                spinnerParent.style.display = 'none';
                goBtn.style.display = 'inline-block';
                // Start alvast de dashboard data
                refreshDashboard();
            }
        } catch(e) {
            statusEl.textContent = 'Verbinden...';
        }
    }, 2000);
}

function dismissSplash() {
    splashDismissed = true;
    let splash = document.getElementById('splash');
    splash.classList.add('fade-out');
    document.querySelector('.app').classList.remove('hidden-behind-splash');
    setTimeout(() => { splash.style.display = 'none'; }, 500);
    refreshDashboard();
    refreshTopbar();
}

// ── AUTO-UPDATE ──
async function checkForUpdate() {
    try {
        let r = await fetch('/api/update/check');
        let d = await r.json();
        console.log('Update check:', JSON.stringify(d));
        if (d.has_update) {
            let banner = document.getElementById('update-banner');
            document.getElementById('update-title').textContent = `Update beschikbaar: v${d.remote} (je hebt v${d.current})`;
            document.getElementById('update-changelog').textContent = d.changelog || '';
            banner.style.cssText = 'display:flex;background:linear-gradient(90deg,#1a3a2a,#0d2818);border:1px solid #238636;border-radius:8px;padding:10px 18px;margin-bottom:10px;align-items:center;justify-content:space-between;gap:12px';
        }
    } catch(e) { console.log('Update check failed:', e); }
}

async function doUpdate() {
    let btn = document.getElementById('update-btn');
    btn.disabled = true;
    btn.textContent = 'Downloaden...';
    try {
        let r = await fetch('/api/update/install', {method: 'POST'});
        let d = await r.json();
        if (d.ok) {
            btn.textContent = 'Herstarten...';
            btn.style.background = '#3fb950';
            document.getElementById('update-title').innerHTML = `v${d.new_version} geinstalleerd — app herstart...`;
            document.getElementById('update-changelog').textContent = 'Bestanden bijgewerkt: ' + d.updated.join(', ');
            setTimeout(() => {
                fetch('/api/update/restart', {method:'POST'}).catch(()=>{});
                document.getElementById('update-title').innerHTML = 'App herstart... <span style="color:#8b949e">(sluit automatisch)</span>';
                btn.textContent = 'Herstarten...';
                // Als de app niet automatisch herstart na 8s, toon handmatige instructie
                setTimeout(() => {
                    document.getElementById('update-title').innerHTML = 'Update geinstalleerd! Sluit de app handmatig en open opnieuw.';
                    btn.textContent = 'Klaar';
                    btn.style.background = '#30363d';
                }, 8000);
            }, 1500);
        } else {
            btn.textContent = 'Mislukt';
            btn.style.background = '#da3633';
            setTimeout(() => { btn.disabled = false; btn.textContent = 'Opnieuw proberen'; btn.style.background = '#238636'; }, 3000);
        }
    } catch(e) {
        btn.textContent = 'Fout';
        btn.style.background = '#da3633';
        setTimeout(() => { btn.disabled = false; btn.textContent = 'Opnieuw proberen'; btn.style.background = '#238636'; }, 3000);
    }
}

// ── ITEM DETAIL ──
let detailData = null;
let detailRange = '1m';
const RANGES = [
    {key:'1d', label:'1 Dag', seconds:86400},
    {key:'1w', label:'1 Week', seconds:604800},
    {key:'14d', label:'14 Dagen', seconds:1209600},
    {key:'1m', label:'1 Maand', seconds:2592000},
    {key:'3m', label:'3 Maanden', seconds:7776000},
    {key:'6m', label:'6 Maanden', seconds:15552000},
    {key:'1y', label:'1 Jaar', seconds:31536000},
    {key:'all', label:'Alles', seconds:0}
];

async function openItemDetail(id, name) {
    document.getElementById('detail-title').textContent = name;
    document.getElementById('detail-stats').innerHTML = '<div style="color:#8b949e">Laden...</div>';
    document.getElementById('detail-range-stats').innerHTML = '';
    let iconEl = document.getElementById('detail-icon');
    iconEl.style.display = 'none'; iconEl.src = '';
    document.getElementById('detail-modal').classList.add('show');
    // Load icon from OSRS Wiki
    fetch(`/api/item/${id}/icon`).then(r=>r.json()).then(d=>{
        if(d.icon_url){iconEl.src=d.icon_url;iconEl.style.display='block';iconEl.onerror=()=>{iconEl.style.display='none'};}
    }).catch(()=>{});
    try {
        let r = await fetch(`/api/item/${id}/history`);
        detailData = await r.json();
        renderDetailRangeButtons();
        renderItemDetail();
    } catch(e) {
        document.getElementById('detail-stats').innerHTML = '<div style="color:#da3633">Fout bij laden</div>';
    }
}

function renderDetailRangeButtons() {
    let h = '';
    RANGES.forEach(r => {
        let active = r.key === detailRange ? 'background:#238636;color:#fff' : 'background:#21262d;color:#8b949e';
        h += `<button onclick="detailRange='${r.key}';renderDetailRangeButtons();renderItemDetail()" style="${active};border:1px solid #30363d;padding:5px 12px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600">${r.label}</button>`;
    });
    document.getElementById('detail-range-btns').innerHTML = h;
}

function getDetailPoints() {
    if (!detailData) return [];
    let rangeObj = RANGES.find(r => r.key === detailRange);
    let cutoff = rangeObj.seconds > 0 ? (Date.now()/1000 - rangeObj.seconds) : 0;
    let pts;
    if (detailRange === '1d') {
        pts = (detailData.ts_5m||[]).filter(p => p.timestamp >= cutoff);
    } else if (detailRange === '1w' || detailRange === '14d') {
        pts = (detailData.ts_1h||[]).filter(p => p.timestamp >= cutoff);
    } else if (detailRange === '1m' || detailRange === '3m') {
        pts = (detailData.ts_6h||[]).filter(p => p.timestamp >= cutoff);
    } else {
        // 6m, 1y, all → 24h data
        pts = (detailData.ts_24h||[]).filter(p => p.timestamp >= cutoff);
        // Fallback naar 6h als 24h leeg is
        if (!pts.length) pts = (detailData.ts_6h||[]).filter(p => p.timestamp >= cutoff);
    }
    pts.sort((a,b) => a.timestamp - b.timestamp);
    return pts;
}

function renderItemDetail() {
    if (!detailData) return;
    let d = detailData;
    // Stats bovenaan
    let avgHigh = d.current_high, avgLow = d.current_low;
    let spread = avgHigh && avgLow ? avgHigh - avgLow : 0;
    let spreadPct = avgLow > 0 ? ((spread / avgLow) * 100).toFixed(1) : '0';
    document.getElementById('detail-stats').innerHTML = `
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Huidige Low</div>
            <div style="color:#3fb950;font-size:18px;font-weight:700">${avgLow ? gp(avgLow) : '?'}</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Huidige High</div>
            <div style="color:#da3633;font-size:18px;font-weight:700">${avgHigh ? gp(avgHigh) : '?'}</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Spread</div>
            <div style="color:#d29922;font-size:18px;font-weight:700">${gp(spread)} <span style="font-size:12px">(${spreadPct}%)</span></div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Buy Limit</div>
            <div style="color:#58a6ff;font-size:18px;font-weight:700">${d.limit || '?'}</div>
        </div>`;
    // Chart tekenen
    let pts = getDetailPoints();
    drawChart(pts);
    // Range stats
    renderRangeStats(pts);
}

function renderRangeStats(pts) {
    if (!pts.length) { document.getElementById('detail-range-stats').innerHTML = ''; return; }
    let highs = pts.map(p => p.avgHighPrice || p.highPrice || 0).filter(v => v > 0);
    let lows = pts.map(p => p.avgLowPrice || p.lowPrice || 0).filter(v => v > 0);
    let allPrices = [...highs, ...lows].filter(v => v > 0);
    let avgAll = allPrices.length ? Math.round(allPrices.reduce((a,b)=>a+b,0) / allPrices.length) : 0;
    let maxP = allPrices.length ? Math.max(...allPrices) : 0;
    let minP = allPrices.length ? Math.min(...allPrices) : 0;
    let rangeLabel = RANGES.find(r => r.key === detailRange)?.label || '';
    document.getElementById('detail-range-stats').innerHTML = `
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Gem. Prijs (${rangeLabel})</div>
            <div style="color:#58a6ff;font-size:16px;font-weight:700">${gpExact(avgAll)} GP</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Hoogste (${rangeLabel})</div>
            <div style="color:#da3633;font-size:16px;font-weight:700">${gpExact(maxP)} GP</div>
        </div>
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
            <div style="color:#8b949e;font-size:11px">Laagste (${rangeLabel})</div>
            <div style="color:#3fb950;font-size:16px;font-weight:700">${gpExact(minP)} GP</div>
        </div>`;
}

let chartState = {};
let hoverIdx = -1;

function drawChart(pts, hoverT) {
    let canvas = document.getElementById('detail-chart');
    let ctx = canvas.getContext('2d');
    let dpr = window.devicePixelRatio || 1;
    let rect = canvas.getBoundingClientRect();
    let H = 450;
    canvas.width = rect.width * dpr;
    canvas.height = H * dpr;
    canvas.style.height = H + 'px';
    ctx.scale(dpr, dpr);
    let W = rect.width;
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle = '#0d1117'; ctx.fillRect(0,0,W,H);
    if (!pts || !pts.length) {
        ctx.fillStyle = '#8b949e'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('Geen data beschikbaar voor deze periode', W/2, H/2);
        chartState = {}; return;
    }
    let pad = {t:20, r:20, b:40, l:80};
    let cW = W - pad.l - pad.r, cH = H - pad.t - pad.b;
    let highSeries = pts.map(p => ({t: p.timestamp, v: p.avgHighPrice || 0})).filter(p => p.v > 0);
    let lowSeries = pts.map(p => ({t: p.timestamp, v: p.avgLowPrice || 0})).filter(p => p.v > 0);
    let allV = [...highSeries.map(p=>p.v), ...lowSeries.map(p=>p.v)];
    if (!allV.length) {
        ctx.fillStyle = '#8b949e'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('Geen prijsdata', W/2, H/2); chartState = {}; return;
    }
    let minV = Math.min(...allV), maxV = Math.max(...allV);
    let range = maxV - minV || 1;
    minV -= range * 0.05; maxV += range * 0.05; range = maxV - minV;
    let minT = pts[0].timestamp, maxT = pts[pts.length-1].timestamp;
    let tRange = maxT - minT || 1;
    let txF = (t) => pad.l + ((t - minT) / tRange) * cW;
    let tyF = (v) => pad.t + cH - ((v - minV) / range) * cH;
    chartState = {pts, pad, cW, cH, W, H, minT, tRange, txF, tyF};
    // Grid
    ctx.strokeStyle = '#21262d'; ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
        let y = pad.t + (cH / 5) * i;
        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
        let val = maxV - (range / 5) * i;
        ctx.fillStyle = '#8b949e'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
        ctx.fillText(gpExact(val), pad.l - 8, y + 4);
    }
    // Tijdlabels
    ctx.textAlign = 'center'; ctx.fillStyle = '#8b949e'; ctx.font = '10px sans-serif';
    let nLabels = Math.min(8, pts.length);
    for (let i = 0; i < nLabels; i++) {
        let idx = Math.floor(i * (pts.length - 1) / Math.max(nLabels - 1, 1));
        let p = pts[idx]; let d = new Date(p.timestamp * 1000);
        let label = detailRange === '1d' ? d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}) :
                    ['6m','1y','all'].includes(detailRange) ? d.toLocaleDateString('nl-NL',{month:'short',year:'2-digit'}) :
                    d.toLocaleDateString('nl-NL',{day:'numeric',month:'short'});
        ctx.fillText(label, txF(p.timestamp), H - pad.b + 18);
    }
    // High lijn
    if (highSeries.length > 1) {
        ctx.beginPath(); ctx.strokeStyle = '#da3633'; ctx.lineWidth = 2;
        highSeries.forEach((p,i) => { i===0 ? ctx.moveTo(txF(p.t),tyF(p.v)) : ctx.lineTo(txF(p.t),tyF(p.v)); });
        ctx.stroke();
        ctx.lineTo(txF(highSeries[highSeries.length-1].t), pad.t+cH);
        ctx.lineTo(txF(highSeries[0].t), pad.t+cH);
        ctx.closePath(); ctx.fillStyle='rgba(218,54,51,0.08)'; ctx.fill();
    }
    // Low lijn
    if (lowSeries.length > 1) {
        ctx.beginPath(); ctx.strokeStyle = '#3fb950'; ctx.lineWidth = 2;
        lowSeries.forEach((p,i) => { i===0 ? ctx.moveTo(txF(p.t),tyF(p.v)) : ctx.lineTo(txF(p.t),tyF(p.v)); });
        ctx.stroke();
        ctx.lineTo(txF(lowSeries[lowSeries.length-1].t), pad.t+cH);
        ctx.lineTo(txF(lowSeries[0].t), pad.t+cH);
        ctx.closePath(); ctx.fillStyle='rgba(63,185,80,0.08)'; ctx.fill();
    }
    // Legenda
    ctx.font='12px sans-serif';
    ctx.fillStyle='#da3633'; ctx.fillRect(W-pad.r-140,pad.t,12,12);
    ctx.fillStyle='#c9d1d9'; ctx.textAlign='left'; ctx.fillText('High (verkoop)',W-pad.r-124,pad.t+11);
    ctx.fillStyle='#3fb950'; ctx.fillRect(W-pad.r-140,pad.t+20,12,12);
    ctx.fillStyle='#c9d1d9'; ctx.fillText('Low (koop)',W-pad.r-124,pad.t+31);
    // Hover crosshair
    if (hoverT !== undefined && hoverT >= 0) {
        let closest = pts.reduce((prev,curr) => Math.abs(curr.timestamp-hoverT)<Math.abs(prev.timestamp-hoverT)?curr:prev);
        let cx = txF(closest.timestamp);
        ctx.strokeStyle='rgba(139,148,158,0.5)'; ctx.lineWidth=1; ctx.setLineDash([4,4]);
        ctx.beginPath(); ctx.moveTo(cx,pad.t); ctx.lineTo(cx,pad.t+cH); ctx.stroke(); ctx.setLineDash([]);
        let hi = closest.avgHighPrice||0, lo = closest.avgLowPrice||0;
        if(hi>0){ctx.beginPath();ctx.arc(cx,tyF(hi),5,0,Math.PI*2);ctx.fillStyle='#da3633';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.stroke();}
        if(lo>0){ctx.beginPath();ctx.arc(cx,tyF(lo),5,0,Math.PI*2);ctx.fillStyle='#3fb950';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.stroke();}
    }
}

// Tooltip setup
(function(){
    let tip = document.createElement('div');
    tip.id='chart-tooltip';
    tip.style.cssText='display:none;position:fixed;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;color:#c9d1d9;font-size:12px;pointer-events:none;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.5)';
    document.body.appendChild(tip);
    document.addEventListener('mousemove', function(e){
        let canvas = document.getElementById('detail-chart');
        if(!canvas || !chartState.pts) return;
        let rect = canvas.getBoundingClientRect();
        let mx = e.clientX - rect.left, my = e.clientY - rect.top;
        if(mx<0||mx>rect.width||my<0||my>rect.height||!chartState.pad){tip.style.display='none';return;}
        let {pad,cW,minT,tRange,pts} = chartState;
        if(mx < pad.l || mx > pad.l+cW){tip.style.display='none';return;}
        let mouseT = minT + ((mx-pad.l)/cW)*tRange;
        let closest = pts.reduce((prev,curr) => Math.abs(curr.timestamp-mouseT)<Math.abs(prev.timestamp-mouseT)?curr:prev);
        let hi=closest.avgHighPrice||0, lo=closest.avgLowPrice||0;
        let vol=(closest.highPriceVolume||0)+(closest.lowPriceVolume||0);
        let d=new Date(closest.timestamp*1000);
        let timeStr=d.toLocaleDateString('nl-NL',{day:'numeric',month:'short',year:'numeric'})+' '+d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});
        tip.innerHTML=`<div style="color:#8b949e;margin-bottom:4px">${timeStr}</div>`+
            (hi?`<div><span style="color:#da3633">High:</span> <b>${gpExact(hi)} GP</b></div>`:'')+
            (lo?`<div><span style="color:#3fb950">Low:</span> <b>${gpExact(lo)} GP</b></div>`:'')+
            (hi&&lo?`<div><span style="color:#d29922">Spread:</span> <b>${gpExact(hi-lo)} GP</b></div>`:'')+
            (vol?`<div style="color:#8b949e">Volume: ${vol.toLocaleString()}</div>`:'');
        tip.style.display='block';
        tip.style.left=(e.clientX+15)+'px'; tip.style.top=(e.clientY-10)+'px';
        drawChart(pts, mouseT);
    });
    document.addEventListener('mouseleave', function(){
        document.getElementById('chart-tooltip').style.display='none';
    });
    let canvas = document.getElementById('detail-chart');
    if(canvas) canvas.addEventListener('mouseleave', function(){
        document.getElementById('chart-tooltip').style.display='none';
        if(chartState.pts) drawChart(chartState.pts);
    });
})();

// INIT
async function loadVersion() {
    try {
        let r = await fetch('/api/update/check');
        let d = await r.json();
        let v = d.current || '?';
        document.getElementById('app-version-splash').textContent = 'v' + v;
        document.getElementById('app-version-footer').textContent = 'OSRS GE Scout v' + v + ' — Auto-refresh elke 10s — Data opgeslagen in ~/.osrs_agent/';
    } catch(e) {}
}
loadVersion();
initSplash();
checkForUpdate();
setInterval(() => { if (splashDismissed) refreshDashboard(); }, 10000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────
#  SCANNER START (altijd, ook bij import)
# ─────────────────────────────────────────────
_scanner = threading.Thread(target=market_scanner, daemon=True)
_scanner.start()

#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  OSRS GE Scout — Web UI v3")
    print(f"  Data folder: {DATA_DIR}")
    print("  http://localhost:5050")
    print("  Druk Ctrl+C om te stoppen\n")
    if not os.environ.get("OSRS_NO_BROWSER"):
        import webbrowser
        webbrowser.open("http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)

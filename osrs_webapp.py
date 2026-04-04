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
APP_VERSION = "4.9"
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
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OSRS_GE_SCOUT.png")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "osrs_icon.png")
    if os.path.exists(icon_path):
        from flask import send_file
        return send_file(icon_path, mimetype="image/png")
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

def _get_resources_dir():
    """Vind de juiste map om bestanden te schrijven — werkt met PyInstaller en gewone Python."""
    # PyInstaller: __file__ zit in _MEIPASS (read-only temp dir)
    # De echte Resources map is via de .app bundle
    src = Path(__file__).resolve().parent
    # Check of we in een .app bundle zitten (Resources/ → Contents/ → .app)
    if src.name == "Resources" and src.parent.name == "Contents":
        return src  # Al in Resources
    # Check of we in een PyInstaller _MEIPASS zitten
    if hasattr(sys, '_MEIPASS'):
        # Zoek de .app bundle via de executable
        exe = Path(sys.executable).resolve()
        # exe = .app/Contents/MacOS/OSRS GE Scout
        resources = exe.parent.parent / "Resources"
        if resources.exists():
            return resources
    return src  # Fallback: zelfde map als het script

@app.route("/api/update/install", methods=["POST"])
def api_update_install():
    """Download en installeer de nieuwe versie. Vervangt .py bestanden."""
    try:
        r = requests.get(UPDATE_CHECK_URL, timeout=5, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        remote = r.json()
        files = remote.get("files", {})
        if not files:
            return jsonify({"ok": False, "error": "no_files"})
        app_dir = _get_resources_dir()
        updated = []
        for fname, url in files.items():
            if not fname.endswith(".py"):
                continue
            target = app_dir / fname
            dl = requests.get(url, timeout=15)
            dl.raise_for_status()
            # Backup maken
            if target.exists():
                backup = app_dir / f"{fname}.bak"
                try: backup.write_bytes(target.read_bytes())
                except: pass
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

@app.route("/api/update/restart", methods=["POST"])
def api_update_restart():
    """Herstart de app na een update via de .app bundle."""
    import subprocess
    try:
        app_dir = _get_resources_dir()
        # Zoek de .app bundle
        app_bundle = None
        # Resources → Contents → .app
        check = app_dir.parent.parent
        if check.suffix == ".app" and check.exists():
            app_bundle = str(check)
        # PyInstaller: executable zit in .app/Contents/MacOS/
        if not app_bundle and hasattr(sys, '_MEIPASS'):
            exe = Path(sys.executable).resolve()
            check2 = exe.parent.parent.parent
            if check2.suffix == ".app" and check2.exists():
                app_bundle = str(check2)
        if app_bundle:
            # Herstart via 'open' zodat het icoon en menubalk correct blijven
            subprocess.Popen(
                ["bash", "-c", f'sleep 2 && open -n "{app_bundle}"'],
                start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            # Fallback: direct python starten
            subprocess.Popen(
                ["bash", "-c", f'sleep 2 && cd "{app_dir}" && exec python3 osrs_app.py'],
                start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        threading.Timer(1.0, lambda: os._exit(0)).start()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

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
    <img class="splash-icon" src="/app-icon.png" alt="OSRS GE Scout">
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
    <button class="nav-btn" onclick="showPage('money')">💸 Money Methods</button>
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

<!-- MONEY METHODS -->
<div class="page" id="page-money">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
        <div id="mm-magic-level" style="font-size:13px;color:#484f58"></div>
    </div>

    <!-- HIGH ALCH SECTION -->
    <div class="section">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:0 18px">
            <div class="sh t2" style="margin:0;padding:10px 0">🔥 High Alchemy</div>
            <div style="display:flex;gap:8px;align-items:center">
                <label style="font-size:11px;color:#8b949e">Staf:</label>
                <select id="alch-staff" onchange="loadAlch()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer">
                    <option value="fire" selected>Staff of fire (aanbevolen)</option>
                    <option value="none">Geen staf</option>
                    <option value="bryophyta">Bryophyta's staff</option>
                </select>
            </div>
        </div>
        <div id="alch-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div>
        <div style="padding:0 18px 6px"><b style="font-size:13px;color:#3fb950">📦 Bulk Items</b> <span style="font-size:11px;color:#484f58">(buy limit 1000+ — runes, bolts, supplies)</span></div>
        <div id="alch-bulk" style="padding:0 18px 12px"></div>
        <div style="padding:0 18px 6px"><b style="font-size:13px;color:#58a6ff">💎 High Value Items</b> <span style="font-size:11px;color:#484f58">(20K+ koopprijs)</span></div>
        <div id="alch-highvalue" style="padding:0 18px 18px"></div>
    </div>

    <!-- BOLT ENCHANT SECTION -->
    <div class="section">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:0 18px">
            <div class="sh t3" style="margin:0;padding:10px 0">🏹 Bolt Enchanting</div>
            <div style="display:flex;gap:8px;align-items:center">
                <label style="font-size:11px;color:#8b949e">Staf:</label>
                <select id="bolt-staff" onchange="loadBolts()" style="padding:4px 10px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:12px;cursor:pointer">
                    <option value="none">Geen staf</option>
                    <option value="fire">Staff of fire</option>
                    <option value="water">Staff of water</option>
                    <option value="earth">Staff of earth</option>
                    <option value="air">Staff of air</option>
                    <option value="smoke">Smoke battlestaff</option>
                    <option value="steam">Steam battlestaff</option>
                    <option value="dust">Dust battlestaff</option>
                    <option value="mud">Mud battlestaff</option>
                    <option value="lava">Lava battlestaff</option>
                    <option value="mist">Mist battlestaff</option>
                </select>
            </div>
        </div>
        <div id="bolt-info" style="padding:4px 18px;font-size:12px;color:#8b949e"></div>
        <div id="bolt-table" style="padding:0 18px 18px"></div>
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
            <h3 id="detail-title" style="margin:0">Item Details</h3>
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
    if (p === 'money') loadMoneyMethods();
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
let mmMagicLevel = null;

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
    loadAlch();
    loadBolts();
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
    tableEl.innerHTML = h + '</table>';
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
            setTimeout(async () => { await fetch('/api/update/restart', {method:'POST'}); }, 1500);
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
    document.getElementById('detail-modal').classList.add('show');
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

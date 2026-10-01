# =============================================================================
# gamification.py — ZamFarm Climate Gamification Engine
# FR5: 10 pts/login, 50 pts/simulation
# FR6: Auto-advance 5 levels with level-up notification
# UR4/FR4: Crop Investment Simulator
# UR5: Immediate risk feedback
# UR6: Points, badges, levels
# =============================================================================

from datetime import date, timedelta
import json

# =============================================================================
# LEVEL DEFINITIONS  (FR6 — exactly 5 levels matching design document §4.5.2)
# =============================================================================
LEVELS = [
    {"level": 1, "name": "Climate Novice",       "min_pts": 0,    "icon": "🌱", "color": "#888"},
    {"level": 2, "name": "Climate Learner",      "min_pts": 100,  "icon": "🌿", "color": "#198A00"},
    {"level": 3, "name": "Climate Practitioner", "min_pts": 300,  "icon": "🌳", "color": "#EF7D00"},
    {"level": 4, "name": "Climate Champion",     "min_pts": 600,  "icon": "🏆", "color": "#F5C518"},
    {"level": 5, "name": "Climate Master",       "min_pts": 1000, "icon": "👑", "color": "#8B2FC9"},
]

# =============================================================================
# BADGE DEFINITIONS
# =============================================================================
BADGES = {
    "first_login":      {"name": "First Steps",        "icon": "👣", "desc": "Logged in for the first time"},
    "first_simulation": {"name": "First Harvest",      "icon": "🌱", "desc": "Ran your first simulation"},
    "weather_watcher":  {"name": "Weather Watcher",    "icon": "🌤️", "desc": "7 consecutive daily logins"},
    "iron_farmer":      {"name": "Iron Farmer",        "icon": "⚡", "desc": "30 consecutive daily logins"},
    "simulation_star":  {"name": "Simulation Star",    "icon": "⭐", "desc": "Completed 10 simulations"},
    "risk_manager":     {"name": "Risk Manager",       "icon": "🧪", "desc": "Simulated 5 different crops"},
    "drought_survivor": {"name": "Drought Survivor",   "icon": "🏜️", "desc": "Simulated a drought scenario"},
    "rain_master":      {"name": "Rain Master",        "icon": "🌧️", "desc": "Above-normal rainfall scenario"},
    "high_yield":       {"name": "Bumper Harvest",     "icon": "🌟", "desc": "Predicted yield above 5 T/ha"},
    "level_3":          {"name": "Practitioner",       "icon": "🔬", "desc": "Reached Level 3"},
    "level_4":          {"name": "Champion Farmer",    "icon": "🏆", "desc": "Reached Level 4"},
    "level_5":          {"name": "ZamFarm Master",     "icon": "👑", "desc": "Reached Level 5"},
    "data_hero":        {"name": "Data Hero",          "icon": "📡", "desc": "Contributed climate data"},
}

# =============================================================================
# CROP INVESTMENT SIMULATOR DATA  (FR4 / UR4)
# Hardcoded values are FALLBACKS ONLY.
# Live values come from get_crop_params() in app.py via the db_params argument.
# =============================================================================
SIMULATOR_CROPS = {
    "Maize": {
        "emoji": "🌽", "base_yield": 2.5, "input_cost": 1200, "market_price": 850,
        "scenarios": {
            "normal":      {"rain_mm": 750,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 280,  "yield_mod": 0.42, "risk": "high",   "risk_color": "#EF0000"},
            "abovenormal": {"rain_mm": 1100, "yield_mod": 1.18, "risk": "medium", "risk_color": "#EF7D00"},
        },
    },
    "Soyabeans": {
        "emoji": "🫘", "base_yield": 1.4, "input_cost": 950, "market_price": 1100,
        "scenarios": {
            "normal":      {"rain_mm": 600,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 280,  "yield_mod": 0.38, "risk": "high",   "risk_color": "#EF0000"},
            "abovenormal": {"rain_mm": 1050, "yield_mod": 1.10, "risk": "low",    "risk_color": "#198A00"},
        },
    },
    "Groundnuts": {
        "emoji": "🥜", "base_yield": 1.1, "input_cost": 800, "market_price": 1400,
        "scenarios": {
            "normal":      {"rain_mm": 550,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 250,  "yield_mod": 0.55, "risk": "medium", "risk_color": "#EF7D00"},
            "abovenormal": {"rain_mm": 950,  "yield_mod": 0.88, "risk": "medium", "risk_color": "#EF7D00"},
        },
    },
    "Cassava": {
        "emoji": "🍠", "base_yield": 8.2, "input_cost": 600, "market_price": 280,
        "scenarios": {
            "normal":      {"rain_mm": 800,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 280,  "yield_mod": 0.72, "risk": "medium", "risk_color": "#EF7D00"},
            "abovenormal": {"rain_mm": 1200, "yield_mod": 1.05, "risk": "low",    "risk_color": "#198A00"},
        },
    },
    "Sorghum": {
        "emoji": "🌾", "base_yield": 1.8, "input_cost": 700, "market_price": 950,
        "scenarios": {
            "normal":      {"rain_mm": 500,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 200,  "yield_mod": 0.75, "risk": "medium", "risk_color": "#EF7D00"},
            "abovenormal": {"rain_mm": 900,  "yield_mod": 1.08, "risk": "low",    "risk_color": "#198A00"},
        },
    },
    "Millet": {
        "emoji": "🌿", "base_yield": 1.2, "input_cost": 550, "market_price": 880,
        "scenarios": {
            "normal":      {"rain_mm": 400,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 180,  "yield_mod": 0.80, "risk": "low",    "risk_color": "#198A00"},
            "abovenormal": {"rain_mm": 750,  "yield_mod": 0.92, "risk": "medium", "risk_color": "#EF7D00"},
        },
    },
    "Sunflower": {
        "emoji": "🌻", "base_yield": 1.6, "input_cost": 900, "market_price": 1250,
        "scenarios": {
            "normal":      {"rain_mm": 500,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 220,  "yield_mod": 0.65, "risk": "medium", "risk_color": "#EF7D00"},
            "abovenormal": {"rain_mm": 950,  "yield_mod": 1.10, "risk": "low",    "risk_color": "#198A00"},
        },
    },
    "Potatoes": {
        "emoji": "🥔", "base_yield": 12.0, "input_cost": 1500, "market_price": 600,
        "scenarios": {
            "normal":      {"rain_mm": 600,  "yield_mod": 1.00, "risk": "low",    "risk_color": "#198A00"},
            "drought":     {"rain_mm": 280,  "yield_mod": 0.50, "risk": "high",   "risk_color": "#EF0000"},
            "abovenormal": {"rain_mm": 1100, "yield_mod": 0.90, "risk": "medium", "risk_color": "#EF7D00"},
        },
    },
}

POINTS_LOGIN      = 10   # FR5
POINTS_SIMULATION = 50   # FR5


# =============================================================================
# GAMIFICATION ENGINE CLASS
# =============================================================================
class GamificationEngine:

    def __init__(self, mysql):
        self.mysql = mysql

    def _cur(self):
        return self.mysql.connection.cursor()

    # ── Ensure a gamification row exists for this farmer ─────────────────────
    def _ensure_row(self, farmer_id):
        cur = self._cur()
        cur.execute(
            "SELECT id FROM gamification WHERE farmer_id = %s",
            (farmer_id,)
        )
        if not cur.fetchone():
            cur.execute("""
                INSERT IGNORE INTO gamification
                    (farmer_id, points, level, badges, streak_days,
                     total_simulations, total_logins, last_login_date)
                VALUES (%s, 0, 1, '[]', 0, 0, 0, NULL)
            """, (farmer_id,))
            self.mysql.connection.commit()

    # ── Compute level number from total points ────────────────────────────────
    def _compute_level(self, points):
        level = 1
        for lv in LEVELS:
            if points >= lv["min_pts"]:
                level = lv["level"]
        return level

    # ── Get level info dict ───────────────────────────────────────────────────
    def _level_info(self, level_num):
        idx = max(0, min(level_num - 1, len(LEVELS) - 1))
        return LEVELS[idx]

    # =========================================================================
    # AWARD LOGIN POINTS  (FR5: 10 pts per day)
    # =========================================================================
    def award_login(self, farmer_id):
        self._ensure_row(farmer_id)
        cur = self._cur()

        cur.execute("""
            SELECT points, level, streak_days, last_login_date,
                   total_logins, badges
            FROM gamification WHERE farmer_id = %s
        """, (farmer_id,))
        row = cur.fetchone()
        if not row:
            return {}

        pts, lvl, streak, last_login, total_logins, badges_json = row
        today         = date.today()
        points_earned = 0
        new_badges    = []

        if last_login != today:
            points_earned  = POINTS_LOGIN
            pts           += points_earned
            total_logins  += 1

            if last_login and (today - last_login).days == 1:
                streak += 1
            else:
                streak = 1

            badges = json.loads(badges_json or '[]')

            if streak >= 7  and "weather_watcher" not in badges:
                badges.append("weather_watcher"); new_badges.append("weather_watcher")
            if streak >= 30 and "iron_farmer"     not in badges:
                badges.append("iron_farmer");     new_badges.append("iron_farmer")
            if total_logins == 1 and "first_login" not in badges:
                badges.append("first_login"); new_badges.append("first_login")

            old_lvl = lvl
            lvl     = self._compute_level(pts)

            if lvl >= 3 and "level_3" not in badges:
                badges.append("level_3"); new_badges.append("level_3")
            if lvl >= 4 and "level_4" not in badges:
                badges.append("level_4"); new_badges.append("level_4")
            if lvl >= 5 and "level_5" not in badges:
                badges.append("level_5"); new_badges.append("level_5")

            cur.execute("""
                UPDATE gamification
                SET points = %s,
                    level = %s,
                    streak_days = %s,
                    last_login_date = %s,
                    total_logins = %s,
                    badges = %s
                WHERE farmer_id = %s
            """, (pts, lvl, streak, today,
                  total_logins, json.dumps(badges), farmer_id))
            self.mysql.connection.commit()

            return {
                "points_earned": points_earned,
                "new_total":     pts,
                "level":         lvl,
                "level_up":      lvl > old_lvl,
                "level_info":    self._level_info(lvl),
                "streak":        streak,
                "new_badges":    new_badges,
                "badge_details": [BADGES[b] for b in new_badges if b in BADGES],
            }

        return {
            "points_earned": 0,
            "new_total":     pts,
            "level":         lvl,
            "streak":        streak,
        }

    # =========================================================================
    # AWARD SIMULATION POINTS  (FR5: 50 pts per simulation)
    # =========================================================================
    def award_simulation(self, farmer_id, scenario, crop, yield_per_ha):
        self._ensure_row(farmer_id)
        cur = self._cur()

        cur.execute("""
            SELECT points, level, total_simulations, badges
            FROM gamification WHERE farmer_id = %s
        """, (farmer_id,))
        row = cur.fetchone()
        if not row:
            return {}

        pts, lvl, total_sims, badges_json = row
        badges        = json.loads(badges_json or '[]')
        points_earned = POINTS_SIMULATION
        pts          += points_earned
        total_sims   += 1
        new_badges    = []

        if total_sims == 1  and "first_simulation" not in badges:
            badges.append("first_simulation"); new_badges.append("first_simulation")
        if total_sims >= 10 and "simulation_star"  not in badges:
            badges.append("simulation_star");  new_badges.append("simulation_star")

        if scenario == "drought"     and "drought_survivor" not in badges:
            badges.append("drought_survivor"); new_badges.append("drought_survivor")
        if scenario == "abovenormal" and "rain_master"      not in badges:
            badges.append("rain_master");      new_badges.append("rain_master")

        if yield_per_ha and float(yield_per_ha) > 5.0 and "high_yield" not in badges:
            badges.append("high_yield"); new_badges.append("high_yield")

        old_lvl = lvl
        lvl     = self._compute_level(pts)

        if lvl >= 3 and "level_3" not in badges:
            badges.append("level_3"); new_badges.append("level_3")
        if lvl >= 4 and "level_4" not in badges:
            badges.append("level_4"); new_badges.append("level_4")
        if lvl >= 5 and "level_5" not in badges:
            badges.append("level_5"); new_badges.append("level_5")

        cur.execute("""
            UPDATE gamification
            SET points = %s,
                level = %s,
                total_simulations = %s,
                badges = %s
            WHERE farmer_id = %s
        """, (pts, lvl, total_sims, json.dumps(badges), farmer_id))
        self.mysql.connection.commit()

        return {
            "points_earned": points_earned,
            "new_total":     pts,
            "level":         lvl,
            "level_up":      lvl > old_lvl,
            "level_info":    self._level_info(lvl),
            "new_badges":    new_badges,
            "badge_details": [BADGES[b] for b in new_badges if b in BADGES],
        }

    # =========================================================================
    # GET FULL PROFILE
    # =========================================================================
    def get_profile(self, farmer_id):
        self._ensure_row(farmer_id)
        cur = self._cur()
        cur.execute("""
            SELECT points, level, badges, streak_days,
                   total_simulations, total_logins, last_login_date
            FROM gamification WHERE farmer_id = %s
        """, (farmer_id,))
        row = cur.fetchone()
        if not row:
            return None

        pts, lvl, badges_json, streak, total_sims, total_logins, last_login = row
        badges     = json.loads(badges_json or '[]')
        level_info = self._level_info(lvl)

        next_idx   = min(lvl, len(LEVELS) - 1)
        next_level = LEVELS[next_idx]

        pts_this   = level_info["min_pts"]
        pts_next   = next_level["min_pts"]
        if pts_next > pts_this:
            progress = min(int((pts - pts_this) / (pts_next - pts_this) * 100), 100)
        else:
            progress = 100

        return {
            "points":            pts,
            "level":             lvl,
            "level_info":        level_info,
            "next_level":        next_level,
            "progress_pct":      progress,
            "pts_to_next":       max(pts_next - pts, 0),
            "streak_days":       streak,
            "total_simulations": total_sims,
            "total_logins":      total_logins,
            "last_login":        str(last_login) if last_login else "Never",
            "badges":            badges,
            "badge_details":     [{"key": b, **BADGES[b]} for b in badges if b in BADGES],
            "all_badges":        BADGES,
            "all_levels":        LEVELS,
        }

    # =========================================================================
    # LEADERBOARD
    # =========================================================================
    def get_leaderboard(self, district=None, limit=20):
        cur = self._cur()
        if district:
            cur.execute("""
                SELECT f.fullname, f.district, f.profile_pic,
                       g.points, g.level, g.streak_days, g.badges
                FROM gamification g
                JOIN farmers f ON f.id = g.farmer_id
                WHERE f.district = %s
                ORDER BY g.points DESC LIMIT %s
            """, (district, limit))
        else:
            cur.execute("""
                SELECT f.fullname, f.district, f.profile_pic,
                       g.points, g.level, g.streak_days, g.badges
                FROM gamification g
                JOIN farmers f ON f.id = g.farmer_id
                ORDER BY g.points DESC LIMIT %s
            """, (limit,))

        rows = cur.fetchall()
        return [
            {
                "fullname":    r[0],
                "district":    r[1],
                "profile_pic": r[2] or "default.png",
                "points":      r[3],
                "level":       r[4],
                "streak_days": r[5],
                "badges":      json.loads(r[6] or '[]'),
                "level_info":  self._level_info(r[4]),
                "is_me":       False,
            }
            for r in rows
        ]


# =============================================================================
# CROP INVESTMENT SIMULATOR  (FR4 / UR4 / UR5)
# =============================================================================
def run_simulation(crop, scenario, hectares, soil_type=1, investment=0, db_params=None):
    """
    Run the Crop Investment Simulator.
    Returns: yield, ROI, risk level (low/medium/high), advice.
    FR4: suitability score, yield forecast, risk classification.
    UR5: immediate feedback after each simulation.

    db_params: optional dict passed from app.py via get_crop_params(crop).
               Keys used: 'base_yield', 'market_price', 'input_cost'.
               When provided, live DB/admin-edited values override the
               hardcoded SIMULATOR_CROPS fallbacks, so the simulator stays
               in sync with yield prediction and the admin market price editor.
    """
    if crop not in SIMULATOR_CROPS:
        return {"error": f"Unknown crop: {crop}"}
    if scenario not in ("normal", "drought", "abovenormal"):
        return {"error": f"Invalid scenario: {scenario}"}

    c      = SIMULATOR_CROPS[crop]
    sc     = c["scenarios"][scenario]
    soil_m = {1: 1.00, 2: 0.80, 3: 0.88}.get(int(soil_type), 1.0)

    # ── Use live DB values if available, fall back to hardcoded ──────────────
    if db_params:
        live_base_yield   = db_params.get('base_yield',   c["base_yield"])
        live_market_price = db_params.get('market_price', c["market_price"])
        live_input_cost   = db_params.get('input_cost',   c["input_cost"])
        price_source      = "live_db"
    else:
        live_base_yield   = c["base_yield"]
        live_market_price = c["market_price"]
        live_input_cost   = c["input_cost"]
        price_source      = "simulator_default"

    # ── Yield ─────────────────────────────────────────────────────────────────
    yield_per_ha = round(live_base_yield * sc["yield_mod"] * soil_m, 2)
    total_yield  = round(yield_per_ha * float(hectares), 2)

    # ── Financials (ZMW) — all from live DB prices ────────────────────────────
    total_cost    = round(live_input_cost   * float(hectares) + float(investment or 0), 2)
    gross_revenue = round(total_yield       * live_market_price, 2)
    net_profit    = round(gross_revenue - total_cost, 2)
    roi_pct       = round((net_profit / total_cost) * 100, 1) if total_cost else 0

    # ── Risk labels  (UR5) ───────────────────────────────────────────────────
    risk       = sc["risk"]
    risk_map   = {"low": "Low Risk 🟢", "medium": "Medium Risk 🟡", "high": "High Risk 🔴"}
    risk_label = risk_map.get(risk, "Unknown")
    risk_icon  = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")

    # ── Suitability score  (FR3/FR4: 0–100%) ────────────────────────────────
    suitability = {"low": 85, "medium": 60, "high": 30}[risk]
    if net_profit < 0:
        suitability = max(suitability - 15, 5)

    scenario_labels = {
        "normal":      "Normal Rainfall",
        "drought":     "Drought",
        "abovenormal": "Above-Normal Rainfall",
    }

    advice = _generate_advice(crop, scenario, risk, roi_pct, yield_per_ha)

    return {
        "crop":           crop,
        "emoji":          c["emoji"],
        "scenario":       scenario,
        "scenario_label": scenario_labels[scenario],
        "hectares":       float(hectares),
        "rainfall_mm":    sc["rain_mm"],
        "yield_per_ha":   yield_per_ha,
        "total_yield":    total_yield,
        "total_cost":     total_cost,
        "gross_revenue":  gross_revenue,
        "net_profit":     net_profit,
        "roi_pct":        roi_pct,
        "risk":           risk,
        "risk_label":     risk_label,
        "risk_icon":      risk_icon,
        "risk_color":     sc["risk_color"],
        "suitability":    suitability,
        "advice":         advice,
        "profitable":     net_profit >= 0,
        # ── Price provenance — shown in simulator UI ──────────────────────
        "market_price":   live_market_price,
        "input_cost":     live_input_cost,
        "base_yield_tha": live_base_yield,
        "price_source":   price_source,
    }


def _generate_advice(crop, scenario, risk, roi, yld):
    """Generate tailored agronomic advice per crop × scenario (UR5)."""
    advice_map = {
        ("Maize",      "normal"):      "✅ Optimal conditions. Plant on schedule with full fertiliser.",
        ("Maize",      "drought"):     "⚠️ High drought risk. Use drought-tolerant varieties (e.g. SC403). Reduce area and mulch.",
        ("Maize",      "abovenormal"): "🌧️ Watch for fungal disease. Ensure drainage and apply fungicides.",
        ("Soyabeans",  "normal"):      "✅ Ideal for soybeans. Inoculate seeds with Rhizobium for nitrogen fixation.",
        ("Soyabeans",  "drought"):     "⚠️ Soybeans are drought-sensitive. Delay planting or switch to groundnuts.",
        ("Soyabeans",  "abovenormal"): "✅ Soybeans tolerate wet conditions well. Monitor for root rot.",
        ("Groundnuts", "normal"):      "✅ Good conditions. Plant after first rains for optimal germination.",
        ("Groundnuts", "drought"):     "🌡️ Moderate risk. Groundnuts handle mild drought — apply gypsum at pegging.",
        ("Groundnuts", "abovenormal"): "🌧️ Risk of aflatoxin in wet conditions. Harvest promptly and dry thoroughly.",
        ("Cassava",    "normal"):      "✅ Cassava is highly adaptable. Ideal for food security.",
        ("Cassava",    "drought"):     "✅ Cassava is highly drought-tolerant. Good fallback crop in dry years.",
        ("Cassava",    "abovenormal"): "✅ Cassava handles heavy rain well. Space widely for air circulation.",
        ("Sorghum",    "normal"):      "✅ Sorghum performs well in Zambia's conditions. Good food security crop.",
        ("Sorghum",    "drought"):     "✅ Sorghum is drought-tolerant. A smart choice in low-rainfall seasons.",
        ("Sorghum",    "abovenormal"): "🌧️ Monitor for grain mould in wet conditions. Harvest as soon as mature.",
        ("Millet",     "normal"):      "✅ Millet thrives in Zambia. Low input costs make it profitable.",
        ("Millet",     "drought"):     "✅ Millet is among the most drought-tolerant cereals. Proceed with confidence.",
        ("Millet",     "abovenormal"): "⚠️ Millet prefers drier conditions. Excess rain may flatten stems.",
        ("Sunflower",  "normal"):      "✅ Good conditions for sunflower. Ensure well-drained soil.",
        ("Sunflower",  "drought"):     "⚠️ Moderate drought risk. Sunflower handles mild dry spells — monitor closely.",
        ("Sunflower",  "abovenormal"): "🌧️ Excess moisture can cause fungal issues. Ensure wide row spacing.",
        ("Potatoes",   "normal"):      "✅ Good conditions for potatoes. Ensure consistent moisture and mounding.",
        ("Potatoes",   "drought"):     "🔴 Potatoes are highly water-dependent. Irrigation strongly recommended.",
        ("Potatoes",   "abovenormal"): "⚠️ Risk of blight in wet conditions. Apply preventive fungicides weekly.",
    }
    advice = advice_map.get(
        (crop, scenario),
        "Consult your local extension officer for tailored advice."
    )
    if roi < 0:
        advice += " ⚠️ Negative ROI expected — consider cost-reduction or alternative crops."
    elif roi > 80:
        advice += " 💰 Excellent ROI projected — consider scaling up production."
    return advice
# =============================================================================
# app.py — ZamFarm Climate Connect
# Copperbelt University | IS 400 | Sibenza Munkombwe
# Roles: Farmer | Extension Officer | Admin
# FR1-FR8 implemented
# =============================================================================

import os
import joblib
import json
import numpy as np
import requests
from functools import wraps
from datetime import datetime


from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify
)
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


# =============================================================================
# APP SETUP
# =============================================================================
app = Flask(__name__)
app.secret_key = "zamfarm_climate_2025_secret"


# =============================================================================
# DATABASE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
# XAMPP (original):
#   HOST=localhost, USER=root, PASSWORD='', PORT=3307
#
# MySQL Community Server (standalone — recommended after XAMPP corruption):
#   HOST=localhost, USER=root, PASSWORD='root' (or whatever you set), PORT=3307
#   Set MYSQL_PORT to whichever port your MySQL server runs on.
# =============================================================================
app.config['MYSQL_HOST']          = '127.0.0.1'
app.config['MYSQL_USER']          = 'sibenza'
app.config['MYSQL_PASSWORD']      = 'S1@mudaLa'          # change to 'root' or your password
app.config['MYSQL_DB']            = 'ai_farming_db'
app.config['MYSQL_PORT']          = 3307        # change to 3307 for standalone MySQL
app.config['MYSQL_CONNECT_TIMEOUT'] = 10

# Force utf8mb4 on every connection — prevents collation mismatch errors
app.config['MYSQL_CHARSET']       = 'utf8mb4'
app.config['MYSQL_CUSTOM_OPTIONS'] = {
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
}

mysql = MySQL(app)


@app.before_request
def _set_utf8mb4():
    """Set utf8mb4 collation on every DB connection to prevent collation mix errors."""
    try:
        cur = mysql.connection.cursor()
        cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute("SET CHARACTER SET utf8mb4")
        cur.execute("SET character_set_connection=utf8mb4")
    except Exception:
        pass


# =============================================================================
# UPLOAD FOLDER
# =============================================================================
UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =============================================================================
# AI MODELS — graceful fallback if not yet trained
# =============================================================================
try:
    model      = joblib.load("ai_model/model.pkl")
    crop_model = joblib.load("ai_model/crop_model.pkl")
    print("[AI] Yield + Crop models loaded.")
except Exception as e:
    model = crop_model = None
    print(f"[AI WARNING] Models not loaded: {e}")


# =============================================================================
# ROLE CONSTANTS
# =============================================================================
ROLE_FARMER  = 'farmer'
ROLE_OFFICER = 'extension_officer'
ROLE_ADMIN   = 'admin'


# =============================================================================
# DECORATORS
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Restrict a route to one or more roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in.", "error")
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash("Access denied.", "error")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# =============================================================================
# HELPERS
# =============================================================================

def get_db():
    return mysql.connection.cursor()


# Zambia-specific fallback values (used when DB has no entry for a crop)
_ZAMBIA_CROP_DEFAULTS = {
    'Maize':      {'base_yield': 3.50, 'temp_min': 18, 'temp_max': 30, 'rain_min': 500, 'rain_max': 900},
    'Soyabeans':  {'base_yield': 1.80, 'temp_min': 20, 'temp_max': 30, 'rain_min': 450, 'rain_max': 700},
    'Groundnuts': {'base_yield': 1.20, 'temp_min': 22, 'temp_max': 35, 'rain_min': 400, 'rain_max': 650},
    'Cassava':    {'base_yield':10.00, 'temp_min': 20, 'temp_max': 35, 'rain_min': 500, 'rain_max':1500},
    'Sorghum':    {'base_yield': 2.00, 'temp_min': 18, 'temp_max': 38, 'rain_min': 300, 'rain_max': 700},
    'Millet':     {'base_yield': 1.50, 'temp_min': 16, 'temp_max': 38, 'rain_min': 250, 'rain_max': 600},
    'Sunflower':  {'base_yield': 1.80, 'temp_min': 18, 'temp_max': 32, 'rain_min': 400, 'rain_max': 700},
    'Potatoes':   {'base_yield':15.00, 'temp_min': 10, 'temp_max': 22, 'rain_min': 500, 'rain_max': 800},
}

def get_crop_params(crop_name=None):
    """Load crop parameters from DB including market prices and input costs.
    Falls back to hardcoded Zambia defaults for any missing values.
    If crop_name given, returns that crop's dict only."""
    params = {}
    try:
        cur = get_db()
        cur.execute("""
            SELECT crop_name,
                   COALESCE(base_yield_tha, 0),
                   COALESCE(opt_temp_min,   0),
                   COALESCE(opt_temp_max,   0),
                   COALESCE(opt_rain_min,   0),
                   COALESCE(opt_rain_max,   0),
                   COALESCE(market_price,   0),
                   COALESCE(input_cost_ha,  0)
            FROM crops ORDER BY crop_name
        """)
        for row in cur.fetchall():
            name = row[0]
            fallback = _ZAMBIA_CROP_DEFAULTS.get(name, {})
            fb_price = CROP_MARKET_PRICES.get(name, 900)
            fb_cost  = CROP_INPUT_COSTS.get(name, 800)
            params[name] = {
                'base_yield':   float(row[1]) if float(row[1]) > 0 else fallback.get('base_yield', 2.5),
                'temp_min':     float(row[2]) if float(row[2]) > 0 else fallback.get('temp_min',   18.0),
                'temp_max':     float(row[3]) if float(row[3]) > 0 else fallback.get('temp_max',   32.0),
                'rain_min':     float(row[4]) if float(row[4]) > 0 else fallback.get('rain_min',  400.0),
                'rain_max':     float(row[5]) if float(row[5]) > 0 else fallback.get('rain_max',  800.0),
                'market_price': float(row[6]) if float(row[6]) > 0 else fb_price,
                'input_cost':   float(row[7]) if float(row[7]) > 0 else fb_cost,
            }
    except Exception as e:
        print(f"[get_crop_params] DB error: {e} — using hardcoded defaults")
        params = {
            name: dict(v,
                       market_price=CROP_MARKET_PRICES.get(name, 900),
                       input_cost=CROP_INPUT_COSTS.get(name, 800))
            for name, v in _ZAMBIA_CROP_DEFAULTS.items()
        }

    # Fill in any crops missing from DB
    for name, defaults in _ZAMBIA_CROP_DEFAULTS.items():
        if name not in params:
            params[name] = dict(defaults,
                                market_price=CROP_MARKET_PRICES.get(name, 900),
                                input_cost=CROP_INPUT_COSTS.get(name, 800))

    if crop_name:
        return params.get(crop_name,
                          dict(_ZAMBIA_CROP_DEFAULTS.get(crop_name, {'base_yield': 2.5}),
                               market_price=CROP_MARKET_PRICES.get(crop_name, 900),
                               input_cost=CROP_INPUT_COSTS.get(crop_name, 800)))
    return params


def _build_advisory(crop, hectares, yield_tha, yield_per_ha, soil_type,
                    net_profit, roi_pct, gross_rev, total_cost,
                    temperature, rainfall, fertilizer, market_price, investment):
    """Generate a rich, plain-language advisory dict for the prediction results page."""

    # ── Benchmark yields for Zambia (t/ha) ───────────────────────────────────
    BENCHMARKS = {
        'Maize': 3.5, 'Soyabeans': 1.8, 'Groundnuts': 1.2, 'Cassava': 10.0,
        'Sorghum': 2.0, 'Millet': 1.5, 'Sunflower': 1.8, 'Potatoes': 15.0,
    }
    CROP_EMOJI = {
        'Maize': '🌽', 'Soyabeans': '🌱', 'Groundnuts': '🥜', 'Cassava': '🍠',
        'Sorghum': '🌾', 'Millet': '🌿', 'Sunflower': '🌻', 'Potatoes': '🥔',
    }
    SOIL_NAMES = {1: 'Loamy', 2: 'Sandy', 3: 'Clay'}
    benchmark    = BENCHMARKS.get(crop, 2.5)
    emoji        = CROP_EMOJI.get(crop, '🌾')
    soil_name    = SOIL_NAMES.get(int(soil_type), 'Loamy')
    pct_of_bench = round((yield_per_ha / benchmark * 100), 1) if benchmark > 0 else 100

    # ── Yield performance verdict ─────────────────────────────────────────────
    if pct_of_bench >= 110:
        yield_verdict    = 'exceptional'
        yield_colour     = 'success'
        yield_headline   = f"Outstanding! Your {crop} yield is {pct_of_bench}% of the Zambia national average."
        yield_msg = (
            f"At {yield_per_ha} T/ha, this is well above the {benchmark} T/ha benchmark for Zambian {crop}. "
            f"Your combination of soil management, fertilizer use, and growing conditions is delivering "
            f"excellent results. This is the kind of output commercial operations aim for."
        )
    elif pct_of_bench >= 90:
        yield_verdict    = 'good'
        yield_colour     = 'success'
        yield_headline   = f"Solid performance — your {crop} is tracking at {pct_of_bench}% of the national benchmark."
        yield_msg = (
            f"A yield of {yield_per_ha} T/ha is within the healthy range for Zambia. "
            f"The {benchmark} T/ha national average is well within reach. Small improvements "
            f"in fertilizer timing or row spacing could push you above benchmark next season."
        )
    elif pct_of_bench >= 65:
        yield_verdict    = 'moderate'
        yield_colour     = 'warning'
        yield_headline   = f"Moderate yield — {crop} is at {pct_of_bench}% of what Zambian farms typically achieve."
        yield_msg = (
            f"Your {yield_per_ha} T/ha is below the {benchmark} T/ha Zambia benchmark. "
            f"Common causes include low soil fertility, inadequate rainfall, or delayed planting. "
            f"Consider soil testing, increasing fertilizer to 200+ kg/ha basal, and planting "
            f"at the onset of reliable rains (November–December in most provinces)."
        )
    else:
        yield_verdict    = 'low'
        yield_colour     = 'danger'
        yield_headline   = f"Low yield alert — {crop} at only {pct_of_bench}% of the Zambian benchmark."
        yield_msg = (
            f"At {yield_per_ha} T/ha, this is significantly below the {benchmark} T/ha average. "
            f"Immediate action is recommended: soil test for pH and nutrient deficiencies, "
            f"switch to improved/drought-tolerant seed varieties (ZARI-approved), and consider "
            f"supplemental irrigation if rainfall is below 500mm this season."
        )

    # ── Financial verdict ─────────────────────────────────────────────────────
    if roi_pct >= 40:
        fin_verdict  = 'profitable'
        fin_colour   = 'success'
        fin_headline = f"Excellent investment! ROI of {roi_pct}% — your {crop} farm is paying off well."
        fin_msg = (
            f"You stand to earn ZMW {net_profit:,.0f} net profit on this {hectares} ha of {crop}. "
            f"With ZMW {market_price:,.0f}/T market price factored in, this is a strong return. "
            f"Consider reinvesting a portion of profits into certified seed for next season to "
            f"maintain yield momentum."
        )
    elif roi_pct >= 10:
        fin_verdict  = 'breakeven'
        fin_colour   = 'warning'
        fin_headline = f"Slim margins — {roi_pct}% ROI. Profitable but optimisation is needed."
        fin_msg = (
            f"Net profit of ZMW {net_profit:,.0f} covers your costs with a small return. "
            f"To improve margins: negotiate bulk pricing on inputs, join a farmer cooperative "
            f"to access better {crop} prices, or reduce input costs by 15-20% through "
            f"precision fertilizer application."
        )
    elif roi_pct >= 0:
        fin_verdict  = 'marginal'
        fin_colour   = 'warning'
        fin_headline = f"Breaking even — you'll recover costs but profit is minimal at {roi_pct}% ROI."
        fin_msg = (
            f"Revenue of ZMW {gross_rev:,.0f} barely covers total costs of ZMW {total_cost:,.0f}. "
            f"This is a risky position. Try to reduce hectarage on lower-potential land, focus "
            f"inputs on your best fields, and explore value-adding (e.g. selling processed "
            f"groundnut paste, or dried cassava chips) to increase revenue per tonne."
        )
    else:
        fin_verdict  = 'loss'
        fin_colour   = 'danger'
        fin_headline = f"Warning: projected loss of ZMW {abs(net_profit):,.0f} at current conditions."
        _high_cost   = total_cost > (gross_rev * 1.3)
        fin_msg = (
            f"Costs of ZMW {total_cost:,.0f} exceed revenue of ZMW {gross_rev:,.0f}. "
            f"This is largely driven by {'the high input cost per hectare' if _high_cost else 'low yield'} "
            f"and the current market price of ZMW {market_price:,.0f}/T. "
            f"Before the season: revise your input plan, apply for FISP subsidised inputs if eligible, "
            f"and explore contract farming agreements that guarantee a higher off-take price."
        )

    # ── Weather / climate notes ───────────────────────────────────────────────
    weather_tips = []
    if rainfall < 400:
        weather_tips.append(
            f"⚠️ Low rainfall ({rainfall:.0f}mm) — consider drought-tolerant varieties or "
            f"short-season cultivars. Mulching can conserve up to 30% soil moisture."
        )
    elif rainfall > 1200:
        weather_tips.append(
            f"🌧️ High rainfall ({rainfall:.0f}mm) — risk of waterlogging and fungal diseases. "
            f"Ensure good field drainage and apply fungicide at early vegetative stage."
        )
    else:
        weather_tips.append(
            f"🌤️ Rainfall of {rainfall:.0f}mm is within the optimal range for {crop}. "
            f"Maintain rain gauge records to track seasonal patterns."
        )

    if temperature > 35:
        weather_tips.append(
            f"🌡️ High temperature ({temperature:.1f}°C) may cause heat stress at flowering — "
            f"plant earlier in the season to shift critical stages to cooler months."
        )
    elif temperature < 14:
        weather_tips.append(
            f"❄️ Cool temperature ({temperature:.1f}°C) slows germination — use plastic mulch "
            f"to warm the soil and delay planting until temperatures exceed 16°C."
        )

    # ── Fertilizer recommendation ─────────────────────────────────────────────
    if fertilizer < 50:
        fert_tip = (
            f"🌿 Fertilizer rate of {fertilizer:.0f} kg/ha is very low. ZARI recommends "
            f"200 kg/ha basal (D-Compound) + 200 kg/ha top-dress (Urea) for {crop}. "
            f"Increasing to recommended rates could boost your yield by 30-50%."
        )
    elif fertilizer < 150:
        fert_tip = (
            f"🌿 At {fertilizer:.0f} kg/ha, fertilizer use is moderate. Consider "
            f"supplementing with a top-dress of 100 kg/ha Urea at knee-high stage "
            f"to maximize grain fill."
        )
    else:
        fert_tip = (
            f"✅ Good fertilizer application at {fertilizer:.0f} kg/ha. Split applications "
            f"(basal + top-dress) work better than single applications for nutrient efficiency."
        )

    # ── Soil-specific tip ─────────────────────────────────────────────────────
    soil_tips = {
        1: (f"🟤 Loamy soil is your biggest asset — it holds both moisture and nutrients well. "
            f"Maintain organic matter by incorporating crop residues after harvest."),
        2: (f"🟡 Sandy soil drains quickly, so split your fertilizer into 3 applications rather "
            f"than 2. Water-retention polymers or compost (5T/ha) significantly improve yields."),
        3: (f"🔵 Clay soil can waterlog easily. Raise your beds or create furrows for drainage. "
            f"Till when soil is moist (not wet) to avoid compaction damaging root development."),
    }
    soil_tip = soil_tips.get(int(soil_type), soil_tips[1])

    # ── Next steps ────────────────────────────────────────────────────────────
    next_steps = [
        f"📋 Record this prediction in your farm register — compare actual harvest against {yield_tha:.2f}T.",
        f"🌱 Source certified {crop} seed early — ZARI-approved varieties yield 25-40% more than recycled seed.",
        f"📅 Mark your planting window: aim for the first reliable 20mm rain in your district.",
        f"🤝 Contact your Extension Officer to review this plan and access FISP or LASF support.",
    ]
    if net_profit < 0:
        next_steps.insert(1, "💡 Explore contract farming — ZAMACE and FRA both offer guaranteed {crop} prices.")
    if yield_per_ha < benchmark * 0.7:
        next_steps.insert(2, f"🧪 Get a soil test (ZMW ~150 at ZARI) — low pH or micronutrient deficiency is a common hidden cause of low {crop} yields.")

    return {
        'emoji':          emoji,
        'crop':           crop,
        'soil_name':      soil_name,
        'yield_verdict':  yield_verdict,
        'yield_colour':   yield_colour,
        'yield_headline': yield_headline,
        'yield_msg':      yield_msg,
        'fin_verdict':    fin_verdict,
        'fin_colour':     fin_colour,
        'fin_headline':   fin_headline,
        'fin_msg':        fin_msg,
        'weather_tips':   weather_tips,
        'fert_tip':       fert_tip,
        'soil_tip':       soil_tip,
        'next_steps':     next_steps,
        'pct_of_bench':   pct_of_bench,
        'benchmark':      benchmark,
    }


def get_current_farmer():
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return None
    cur = get_db()
    # Explicit columns in guaranteed order:
    # [0]id [1]fullname [2]email [3]phone [4]password [5]farm_size
    # [6]village [7]district [8]profile_pic
    cur.execute("""
        SELECT id, fullname, email, phone, password,
               farm_size, village, district, profile_pic
        FROM farmers WHERE id = %s
    """, (session['user_id'],))
    return cur.fetchone()


def get_weather(district):
    """Fetch live weather; fall back to Zambian averages on error."""
    API_KEY = "9a15cce295222fccf0e5cb17f852cfbd"
    url = (
        f"http://api.openweathermap.org/data/2.5/weather"
        f"?q={district},ZM&appid={API_KEY}&units=metric"
    )
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json()
            return d["main"]["temp"], d.get("rain", {}).get("1h", 0)
    except Exception:
        pass
    return 25.0, 0.0


def allowed_image(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_audio(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'webm', 'ogg', 'mp3', 'm4a', 'wav', 'mp4'}


def check_password_compat(stored, provided):
    """
    Verify password against stored hash.
    Supports: werkzeug scrypt (new default), pbkdf2, sha256, bcrypt, plain-text legacy.
    """
    if not stored or not provided:
        return False
    stored   = stored.strip()
    provided = provided.strip()
    # Any werkzeug hash format
    if ':' in stored or '$' in stored:
        try:
            return check_password_hash(stored, provided)
        except Exception as e:
            print(f"[Auth] check_password_hash error: {e}")
            # Last resort: plain-text comparison
            return stored == provided
    # Legacy plain-text password (accounts created before hashing)
    return stored == provided


def redirect_by_role(role):
    """Route each role to its home dashboard."""
    if role == ROLE_FARMER:  return redirect(url_for('dashboard'))
    if role == ROLE_OFFICER: return redirect(url_for('officer_dashboard'))
    if role == ROLE_ADMIN:   return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


def get_gamif_engine():
    from gamification import GamificationEngine
    return GamificationEngine(mysql)


def maybe_award_login(farmer_id):
    """Award daily login points silently — never crash the page."""
    try:
        return get_gamif_engine().award_login(farmer_id)
    except Exception as e:
        print(f"[Gamification] Login award skipped: {e}")
        return {}


# =============================================================================
# HOME
# =============================================================================
@app.route("/")
def home():
    return redirect(url_for('login'))


# =============================================================================
# LOGIN  (FR1 — multi-role)
# =============================================================================

@app.route('/about')
def about():
    """Public about/system info page — accessible to all roles and guests."""
    farmer = get_current_farmer() if session.get('role') == ROLE_FARMER else None
    return render_template('about.html', farmer=farmer)



def favicon():
    """Serve favicon from static/img/ directory."""
    from flask import send_from_directory
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon.svg', mimetype='image/svg+xml')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Already logged in — go straight to the right dashboard
    if 'user_id' in session:
        return redirect_by_role(session.get('role'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '').strip()
        cur        = get_db()
        
        ident_lower = identifier.lower()

        # ── 1. TRY ADMIN TIERS FIRST (Matches by exact username) ──
        cur.execute("SELECT * FROM admins WHERE LOWER(username)=%s LIMIT 1", (ident_lower,))
        admin = cur.fetchone()
        if admin:
            if check_password_compat(admin[2], password):
                session['user_id'] = admin[0]
                session['role']    = ROLE_ADMIN
                session['name']    = admin[1]
                flash(f"Admin access granted. Welcome, {admin[1]}. ✨", "success")
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Incorrect password. Please try again.", "error")
                return render_template('login.html')

        # ── 2. TRY EXTENSION OFFICERS (Matches by email or phone) ──
        cur.execute(
            "SELECT * FROM extension_officers WHERE LOWER(email)=%s OR phone=%s LIMIT 1",
            (ident_lower, identifier)
        )
        officer = cur.fetchone()
        if officer:
            if check_password_compat(officer[3], password):
                session['user_id'] = officer[0]
                session['role']    = ROLE_OFFICER
                session['name']    = officer[1]
                session['zone']    = officer[4]
                flash(f"Welcome, Officer {officer[1]}! 🚜", "success")
                return redirect(url_for('officer_dashboard'))
            else:
                flash("Incorrect password. Please try again.", "error")
                return render_template('login.html')

        # ── 3. TRY FARMERS (Matches by case-insensitive email or robust phone formatting) ──
        user = None

        # Try by email
        cur.execute(
            "SELECT id, fullname, email, phone, password FROM farmers WHERE LOWER(email)=%s LIMIT 1",
            (ident_lower,)
        )
        user = cur.fetchone()

        # Try by phone directly if email didn't hit
        if not user:
            cur.execute(
                "SELECT id, fullname, email, phone, password FROM farmers WHERE phone=%s LIMIT 1",
                (identifier,)
            )
            user = cur.fetchone()

        # Try by cleaned phone (handles space/dash formatting issues seamlessly)
        if not user:
            clean_phone = ''.join(filter(str.isdigit, identifier))
            if clean_phone:
                cur.execute(
                    "SELECT id, fullname, email, phone, password FROM farmers WHERE REPLACE(REPLACE(phone,' ',''),'-','')=%s LIMIT 1",
                    (clean_phone,)
                )
                user = cur.fetchone()

        # If a farmer profile was matched
        if user:
            if check_password_compat(user[4], password):
                session['user_id'] = user[0]
                session['role']    = ROLE_FARMER
                session['name']    = user[1]
                flash(f"Welcome back, {user[1]}! 🌿", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Incorrect password. Please try again.", "error")
                return render_template('login.html')

        # ── 4. ABSOLUTELY NO MATCH FOUND ANYWHERE ──
        flash("No account found with that username, email, or phone number.", "error")

    return render_template('login.html')


# =============================================================================
# REGISTER  (FR1 — farmer self-registration only)
# =============================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname  = request.form['fullname']
        email     = request.form['email']
        phone     = request.form['phone']
        password  = generate_password_hash(request.form['password'])
        farm_size = request.form['farm_size']
        village   = request.form['village']
        district  = request.form['district']

        file = request.files.get('profile_pic')
        if file and file.filename and allowed_image(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = "default.png"

        cur = get_db()
        try:
            cur.execute("""
                INSERT INTO farmers
                    (fullname, email, phone, password,
                     farm_size, village, district, profile_pic)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (fullname, email, phone, password,
                  farm_size, village, district, filename))
            mysql.connection.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            err_str = str(e)
            if 'Duplicate entry' in err_str and 'phone' in err_str:
                flash("A farmer with that phone number already exists. Please log in instead.", "error")
            elif 'Duplicate entry' in err_str and 'email' in err_str:
                flash("A farmer with that email already exists. Please log in instead.", "error")
            else:
                flash(f"Registration error: {e}", "error")

    return render_template('register.html')


# =============================================================================
# LOGOUT
# =============================================================================
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))


# =============================================================================
# ── FARMER ROUTES
# =============================================================================

@app.route('/dashboard')
@role_required(ROLE_FARMER)
def dashboard():
    farmer = get_current_farmer()
    if not farmer:
        return redirect(url_for('login'))

    temperature, rainfall = get_weather(farmer[7])

    # FR5: Award 10 points for daily login
    login_reward = maybe_award_login(session['user_id'])

    # Fetch gamification profile for dashboard widgets
    profile = None
    try:
        profile = get_gamif_engine().get_profile(session['user_id'])
    except Exception:
        pass

    return render_template(
        "dashboard.html",
        farmer=farmer,
        temperature=temperature,
        rainfall=rainfall,
        login_reward=login_reward,
        gamif=profile,
        CROP_MARKET_PRICES=CROP_MARKET_PRICES,
        CROP_INPUT_COSTS=CROP_INPUT_COSTS,
    )


# Soil type modifiers for yield (agronomic basis)
SOIL_MODIFIERS = {
    1: {"name": "Loamy",  "modifier": 1.00,
        "note": "Loamy soil has excellent moisture retention and nutrient availability — optimal baseline yield."},
    2: {"name": "Sandy",  "modifier": 0.80,
        "note": "Sandy soil drains rapidly and holds fewer nutrients — estimated 20% yield reduction vs loamy baseline."},
    3: {"name": "Clay",   "modifier": 0.88,
        "note": "Clay soil retains moisture well but risks waterlogging and compaction — estimated 12% yield reduction vs loamy baseline."},
}

# Market prices per crop (ZMW/tonne) for financial calculations
CROP_MARKET_PRICES = {
    "Maize":      850,
    "Soyabeans": 1100,
    "Groundnuts":1400,
    "Cassava":    280,
    "Sorghum":    950,
    "Millet":     880,
    "Sunflower": 1250,
    "Potatoes":   600,
}

# Input costs per hectare (ZMW) per crop
CROP_INPUT_COSTS = {
    "Maize":     1200,
    "Soyabeans":  950,
    "Groundnuts": 800,
    "Cassava":    600,
    "Sorghum":    700,
    "Millet":     550,
    "Sunflower":  900,
    "Potatoes": 1500,
}


@app.route('/predict', methods=['POST'])
@role_required(ROLE_FARMER)
def predict():
    farmer = get_current_farmer()
    if not farmer:
        return redirect(url_for('login'))

    try:
        # ── Parse form inputs ─────────────────────────────────────────────
        hectares   = float(request.form.get('hectares')   or 1.0)
        crop       = request.form.get('crop', 'Maize')
        soil_type  = int(request.form.get('soil_type')    or 1)
        fertilizer = float(request.form.get('fertilizer') or 60.0)
        # Farmer now enters their total input cost manually (fertiliser, seed, labour…)
        manual_cost = float(request.form.get('input_cost') or 0)

        # Clamp to safe ranges
        hectares    = max(0.1, min(500, hectares))
        soil_type   = max(1,   min(3,   soil_type))
        fertilizer  = max(0,   min(500, fertilizer))
        manual_cost = max(0,   manual_cost)

        # ── Get weather for farmer's district ────────────────────────────
        temperature, rainfall = get_weather(farmer[7])

        # ── Soil modifier ─────────────────────────────────────────────────
        soil_info = SOIL_MODIFIERS.get(soil_type, SOIL_MODIFIERS[1])
        soil_mod  = soil_info["modifier"]

        # ── Crop ID mapping (matches training order in train_crop_model.py) ─
        crop_map = {
            "Maize": 0, "Soyabeans": 1, "Soybeans": 1,
            "Groundnuts": 2, "Cassava": 3, "Sorghum": 4,
            "Millet": 5, "Sunflower": 6, "Potatoes": 7
        }
        crop_id = crop_map.get(crop, 0)

        # ── AI model prediction with fallback ─────────────────────────────
        predicted_yield   = None
        prediction_engine = 'unknown'   # 'ai_model' | 'agronomic_estimate'
        model_error_msg   = None

        # `model` is the variable name used throughout this app for the yield model
        if model is not None:
            try:
                features = [[hectares, rainfall, temperature, fertilizer,
                             soil_type, crop_id]]
                raw = model.predict(features)[0]
                predicted_yield   = round(float(raw) * soil_mod, 2)
                prediction_engine = 'ai_model'
            except Exception as model_err:
                model_error_msg = str(model_err)
                print(f"[Predict] Model error: {model_err} — using agronomic fallback")
        else:
            model_error_msg = "AI model file not loaded"

        if predicted_yield is None or predicted_yield <= 0:
            # Agronomic baseline — use DB params first, then gamification fallback
            prediction_engine = 'agronomic_estimate'
            try:
                cp = get_crop_params(crop)
                base_tha = cp.get('base_yield', 2.5)
            except Exception:
                try:
                    from gamification import SIMULATOR_CROPS
                    base_tha = SIMULATOR_CROPS.get(crop, {}).get("base_yield", 2.5)
                except Exception:
                    base_tha = 2.5
            predicted_yield = round(base_tha * soil_mod * hectares, 2)

        yield_per_ha = round(predicted_yield / hectares, 3) if hectares > 0 else 0

        # ── Financial calculations — prices from DB (fallback to hardcoded) ─
        cp           = get_crop_params(crop)
        market_price = cp.get('market_price', CROP_MARKET_PRICES.get(crop, 900))
        # Farmer-entered total input cost is used directly. If they leave it
        # blank, fall back to a per-hectare estimate so the page still works.
        est_per_ha   = cp.get('input_cost', CROP_INPUT_COSTS.get(crop, 800))
        est_total    = round(est_per_ha * hectares, 2)
        if manual_cost > 0:
            total_cost   = round(manual_cost, 2)
            cost_is_manual = True
        else:
            total_cost   = est_total
            cost_is_manual = False
        gross_rev    = round(predicted_yield * market_price, 2)
        net_profit   = round(gross_rev - total_cost, 2)
        roi_pct      = round((net_profit / total_cost * 100), 1) if total_cost > 0 else 0

        # ── Generate smart advisory ───────────────────────────────────────
        advisory = _build_advisory(
            crop=crop, hectares=hectares, yield_tha=predicted_yield,
            yield_per_ha=yield_per_ha, soil_type=soil_type,
            net_profit=net_profit, roi_pct=roi_pct,
            gross_rev=gross_rev, total_cost=total_cost,
            temperature=temperature, rainfall=rainfall,
            fertilizer=fertilizer, market_price=market_price,
            investment=total_cost
        )

        # ── Save to database ──────────────────────────────────────────────
        try:
            cur = get_db()
            cur.execute("""
                INSERT INTO predictions
                    (farmer_id, crop, hectares, predicted_yield,
                     soil_type, prediction_date)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (session['user_id'], crop, hectares, predicted_yield, soil_type))
            mysql.connection.commit()
            print(f"[Predict] Saved: farmer={session['user_id']} "
                  f"crop={crop} soil={soil_type} yield={predicted_yield}T")
        except Exception as db_err:
            print(f"[Predict] DB save error: {db_err}")
            try: mysql.connection.rollback()
            except Exception: pass
            flash(f"Prediction made but could not be saved: {db_err}", "warning")

        # ── Render ────────────────────────────────────────────────────────
        return render_template(
            "predict_yield.html",
            farmer=farmer,
            result=predicted_yield,
            yield_per_ha=yield_per_ha,
            crop=crop,
            hectares=hectares,
            soil_info=soil_info,
            soil_type=soil_type,
            market_price=market_price,
            total_cost=total_cost,
            gross_revenue=gross_rev,
            net_profit=net_profit,
            roi_pct=roi_pct,
            investment=total_cost,
            cost_is_manual=cost_is_manual,
            est_total=est_total,
            advisory=advisory,
            temperature=temperature,
            rainfall=rainfall,
            fertilizer=fertilizer,
            prediction_engine=prediction_engine,
            model_error_msg=model_error_msg,
            gamif=None,
        )

    except Exception as e:
        import traceback
        print(f"[Predict] Unhandled error: {e}")
        traceback.print_exc()
        flash(f"Prediction error: {e}", "error")
        return redirect(url_for('predict_yield'))


def _build_crop_explanation(crop, rainfall, temperature, soil_type, confidence):
    """Return a dict of specific, quantified reasons why this crop was recommended."""
    params = _ZAMBIA_CROP_DEFAULTS.get(crop, {
        'temp_min': 16, 'temp_max': 35,
        'rain_min': 300, 'rain_max': 900
    })
    SOIL_NAMES = {1: 'Loamy', 2: 'Sandy', 3: 'Clay'}
    SOIL_SUITABILITY = {
        'Maize':      {1: 'Excellent', 2: 'Fair',      3: 'Good'},
        'Soyabeans':  {1: 'Excellent', 2: 'Fair',      3: 'Good'},
        'Groundnuts': {1: 'Good',      2: 'Excellent', 3: 'Poor'},
        'Cassava':    {1: 'Good',      2: 'Good',      3: 'Fair'},
        'Sorghum':    {1: 'Good',      2: 'Excellent', 3: 'Fair'},
        'Millet':     {1: 'Good',      2: 'Excellent', 3: 'Fair'},
        'Sunflower':  {1: 'Excellent', 2: 'Good',      3: 'Fair'},
        'Potatoes':   {1: 'Excellent', 2: 'Fair',      3: 'Good'},
    }

    t_min = params.get('temp_min', 16)
    t_max = params.get('temp_max', 35)
    r_min = params.get('rain_min', 300)
    r_max = params.get('rain_max', 900)
    soil_name = SOIL_NAMES.get(soil_type, 'Loamy')

    # Temperature assessment
    t_mid = (t_min + t_max) / 2
    t_margin = round(min(temperature - t_min, t_max - temperature), 1)
    if t_min <= temperature <= t_max:
        if t_margin >= 5:
            t_status = 'optimal'
            t_icon   = '✅'
            t_msg    = (f"Your temperature of {temperature}°C sits comfortably within "
                        f"the {t_min}–{t_max}°C ideal range for {crop} "
                        f"({t_margin}°C margin to stress threshold).")
        else:
            t_status = 'acceptable'
            t_icon   = '⚠️'
            t_msg    = (f"Temperature {temperature}°C is within range ({t_min}–{t_max}°C) "
                        f"but only {t_margin}°C from the stress threshold. "
                        f"Plant early in the season to avoid peak heat.")
    elif temperature < t_min:
        gap = round(t_min - temperature, 1)
        t_status = 'marginal'
        t_icon   = '⚠️'
        t_msg    = (f"At {temperature}°C, it's {gap}°C below the minimum {t_min}°C "
                    f"for {crop}. {crop} can still grow but germination may be slow. "
                    f"Use dark plastic mulch to warm the soil.")
    else:
        gap = round(temperature - t_max, 1)
        t_status = 'stress'
        t_icon   = '❌'
        t_msg    = (f"Temperature {temperature}°C exceeds the {t_max}°C maximum for {crop} "
                    f"by {gap}°C. Heat stress at flowering may reduce yields. "
                    f"Consider a shorter-season variety or cooler planting window.")

    # Rainfall assessment
    r_margin = round(min(rainfall - r_min, r_max - rainfall), 0)
    if r_min <= rainfall <= r_max:
        if r_margin >= 100:
            r_status = 'optimal'
            r_icon   = '✅'
            r_msg    = (f"Rainfall of {rainfall:.0f}mm is well within {crop}'s "
                        f"{r_min}–{r_max}mm seasonal requirement "
                        f"({r_margin:.0f}mm margin to stress threshold).")
        else:
            r_status = 'acceptable'
            r_icon   = '⚠️'
            r_msg    = (f"Rainfall {rainfall:.0f}mm is within range ({r_min}–{r_max}mm) "
                        f"but only {r_margin:.0f}mm from the boundary. "
                        f"Conserve moisture with mulching if rains become erratic.")
    elif rainfall < r_min:
        deficit = round(r_min - rainfall, 0)
        r_status = 'low'
        r_icon   = '⚠️'
        r_msg    = (f"Rainfall {rainfall:.0f}mm is {deficit:.0f}mm below {crop}'s "
                    f"minimum {r_min}mm requirement. "
                    f"{crop} is still the best available option — mulch heavily "
                    f"and consider early planting to capture early-season rains.")
    else:
        excess = round(rainfall - r_max, 0)
        r_status = 'high'
        r_icon   = '⚠️'
        r_msg    = (f"Rainfall {rainfall:.0f}mm exceeds {crop}'s maximum "
                    f"{r_max}mm by {excess:.0f}mm. Ensure good field drainage "
                    f"to prevent waterlogging and fungal disease.")

    # Soil assessment
    soil_suit = SOIL_SUITABILITY.get(crop, {}).get(soil_type, 'Good')
    soil_icons = {'Excellent': '✅', 'Good': '🟡', 'Fair': '⚠️', 'Poor': '❌'}
    soil_icon  = soil_icons.get(soil_suit, '🟡')
    soil_tips  = {
        (1, 'Excellent'): f"Loamy soil is ideal for {crop} — excellent moisture retention and nutrient availability.",
        (1, 'Good'):      f"Loamy soil supports {crop} well. Incorporate crop residues to maintain organic matter.",
        (2, 'Excellent'): f"Sandy soil is well-suited for {crop} — its deep root system thrives in free-draining conditions.",
        (2, 'Good'):      f"Sandy soil works for {crop} with 3-split fertilizer applications to prevent nutrient leaching.",
        (2, 'Fair'):      f"Sandy soil is marginal for {crop}. Add compost (5T/ha) to improve water and nutrient retention.",
        (3, 'Good'):      f"Clay soil retains moisture well — a benefit for {crop} during dry spells. Ensure drainage furrows.",
        (3, 'Fair'):      f"Clay can waterlog. Build raised beds for {crop} and avoid tilling when soil is wet.",
    }
    soil_msg = soil_tips.get((soil_type, soil_suit),
                              f"{soil_name} soil has {soil_suit.lower()} suitability for {crop}.")

    # Overall verdict
    statuses = [t_status, r_status]
    if all(s == 'optimal' for s in statuses) and soil_suit == 'Excellent':
        overall = 'perfect'
        verdict = f"All three factors — temperature, rainfall, and soil — are optimal for {crop}. Excellent growing conditions."
    elif 'stress' in statuses or soil_suit == 'Poor':
        overall = 'challenging'
        verdict = f"Conditions are challenging but {crop} is still the best fit available. Follow the mitigation tips below."
    elif all(s in ('optimal', 'acceptable') for s in statuses):
        overall = 'good'
        verdict = f"Conditions are good for {crop}. Minor adjustments noted — see details below."
    else:
        overall = 'moderate'
        verdict = f"{crop} can grow under your conditions. It outscores all alternatives despite the constraints listed below."

    return {
        'overall':    overall,
        'verdict':    verdict,
        'temperature': {'status': t_status, 'icon': t_icon, 'msg': t_msg,
                        'actual': temperature, 'min': t_min, 'max': t_max},
        'rainfall':    {'status': r_status,  'icon': r_icon,  'msg': r_msg,
                        'actual': round(rainfall, 0), 'min': r_min, 'max': r_max},
        'soil':        {'status': soil_suit.lower(), 'icon': soil_icon, 'msg': soil_msg,
                        'name': soil_name, 'suitability': soil_suit},
    }


def _build_crop_comparison(ranked_proba, rainfall, temperature, soil_type):
    """Build a comparison table showing how each crop scores against the farmer's conditions."""
    CROP_EMOJI = {
        'Maize':'🌽','Soyabeans':'🌱','Groundnuts':'🥜','Cassava':'🍠',
        'Sorghum':'🌾','Millet':'🌿','Sunflower':'🌻','Potatoes':'🥔'
    }
    rows = []
    for name, prob in ranked_proba:
        p = _ZAMBIA_CROP_DEFAULTS.get(str(name), {})
        if not p:
            continue
        t_ok = p.get('temp_min',16) <= temperature <= p.get('temp_max',35)
        r_ok = p.get('rain_min',300) <= rainfall   <= p.get('rain_max',900)
        score = round(float(prob) * 100, 1)
        rows.append({
            'name':    str(name),
            'emoji':   CROP_EMOJI.get(str(name), '🌾'),
            'score':   score,
            'temp_ok': t_ok,
            'rain_ok': r_ok,
            'temp_range': f"{p.get('temp_min',16)}–{p.get('temp_max',35)}°C",
            'rain_range': f"{p.get('rain_min',300)}–{p.get('rain_max',900)}mm",
        })
    return rows[:8]


@app.route('/crop', methods=['GET', 'POST'])
@role_required(ROLE_FARMER)
def crop():
    farmer = get_current_farmer()

    if request.method == 'GET':
        return render_template("crop.html", farmer=farmer)

    if not crop_model:
        flash("Crop model not available.", "error")
        return render_template("crop.html", farmer=farmer)

    # Safely parse form values — fall back to live weather if missing
    try:
        rainfall    = float(request.form.get('rainfall') or 0)
        temperature = float(request.form.get('temperature') or 0)
        soil_type   = int(request.form.get('soil') or 1)
    except (ValueError, TypeError):
        flash("Invalid input. Please use the auto-filled weather values.", "error")
        return render_template("crop.html", farmer=farmer)

    # If weather values missing (JS didn't fill), use district averages
    if rainfall == 0 and temperature == 0:
        temperature, rainfall = get_weather(farmer[7])

    # Clamp to reasonable ranges
    rainfall    = max(50, min(2000, rainfall))
    temperature = max(8,  min(45,   temperature))
    soil_type   = max(1,  min(3,    soil_type))

    try:
        prediction       = crop_model.predict([[rainfall, temperature, soil_type]])
        recommended_crop = str(prediction[0])
    except Exception as e:
        print(f"[CropRec] Model predict error: {e}")
        flash("Crop recommendation failed. Please try again.", "error")
        return render_template("crop.html", farmer=farmer)

    confidence, also_suitable = None, []

    try:
        proba      = crop_model.predict_proba([[rainfall, temperature, soil_type]])
        confidence = round(float(np.max(proba)) * 100, 1)
        ranked     = sorted(zip(crop_model.classes_, proba[0]),
                            key=lambda x: x[1], reverse=True)
        also_suitable = [
            {"name": str(n), "score": round(float(p) * 100, 1)}
            for n, p in ranked[1:5] if p > 0.05
        ]
    except Exception:
        pass

    # ── Build explanation: why this crop was recommended ─────────────────
    explanation = _build_crop_explanation(
        recommended_crop, rainfall, temperature, soil_type, confidence
    )

    # ── Full comparison table: all crops vs farmer's conditions ──────────
    comparison = _build_crop_comparison(
        ranked if 'ranked' in dir() else [], rainfall, temperature, soil_type
    )

    SOIL_NAMES = {1: 'Loamy', 2: 'Sandy', 3: 'Clay'}

    return render_template(
        "crop.html",
        farmer=farmer,
        recommended_crop=recommended_crop,
        confidence=confidence,
        also_suitable=also_suitable,
        explanation=explanation,
        comparison=comparison,
        input_rainfall=round(rainfall, 1),
        input_temperature=round(temperature, 1),
        input_soil=SOIL_NAMES.get(soil_type, 'Loamy'),
    )


@app.route('/history')
@role_required(ROLE_FARMER)
def history():
    farmer  = get_current_farmer()
    records = []
    try:
        cur = get_db()
        cur.execute("""
            SELECT crop, hectares, predicted_yield, prediction_date,
                   COALESCE(soil_type, 1) as soil_type
            FROM predictions
            WHERE farmer_id = %s
            ORDER BY prediction_date DESC
            LIMIT 200
        """, (session['user_id'],))
        rows = cur.fetchall()
        SOIL_NAMES = {1: 'Loamy', 2: 'Sandy', 3: 'Clay'}
        records = [
            [str(r[0]), float(r[1]), float(r[2]), str(r[3]),
             SOIL_NAMES.get(int(r[4]) if r[4] else 1, 'Loamy')]
            for r in rows
        ]
    except Exception as e:
        print(f"[History] DB error: {e}")
        flash("Could not load prediction history.", "error")
    return render_template("history.html", farmer=farmer, records=records)


# =============================================================================
# ── GAMIFICATION ROUTES  (FR4 / FR5 / FR6 / UR4 / UR5 / UR6)
# =============================================================================

@app.route('/simulator', methods=['GET', 'POST'])
@role_required(ROLE_FARMER)
def simulator():
    farmer  = get_current_farmer()
    profile = None
    result  = None
    reward  = None

    try:
        eng     = get_gamif_engine()
        profile = eng.get_profile(session['user_id'])
    except Exception as e:
        print(f"[Gamification] Profile load: {e}")

    if request.method == 'POST':
        from gamification import run_simulation
        crop       = request.form.get('crop', 'Maize')
        scenario   = request.form.get('scenario', 'normal')
        hectares   = float(request.form.get('hectares', 1.0))
        soil_type  = int(request.form.get('soil_type', 1))
        investment = float(request.form.get('investment', 0) or 0)

        # Fetch live prices from DB so simulator matches yield prediction
        try:
            db_params = get_crop_params(crop)
        except Exception:
            db_params = None
        result = run_simulation(crop, scenario, hectares, soil_type, investment,
                                db_params=db_params)

        if 'error' not in result:
            # Persist the simulation so it appears in Recent Simulations
            try:
                cur = get_db()
                cur.execute("""
                    INSERT INTO simulation_sessions
                        (farmer_id, crop_name, scenario, hectares, soil_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session['user_id'], crop, scenario, hectares, soil_type))
                session_id = cur.lastrowid
                cur.execute("""
                    INSERT INTO simulation_results
                        (sessionID, yield_per_ha, total_yield, suitability_pct,
                         risk_level, net_profit, roi_pct)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (session_id,
                      result.get('yield_per_ha'),
                      result.get('total_yield'),
                      result.get('suitability'),
                      result.get('risk'),
                      result.get('net_profit'),
                      result.get('roi_pct')))
                mysql.connection.commit()
            except Exception as e:
                print(f"[Simulator] persist error: {e}")

            try:
                eng    = get_gamif_engine()
                reward = eng.award_simulation(
                    session['user_id'], scenario, crop,
                    result.get('yield_per_ha', 0)
                )
                profile = eng.get_profile(session['user_id'])
            except Exception as e:
                print(f"[Gamification] Award simulation: {e}")

    # ── Recent simulations (last 8) for the table ─────────────────────────
    recent_sims = []
    try:
        cur = get_db()
        cur.execute("""
            SELECT ss.crop_name, ss.scenario, ss.hectares, ss.soil_type,
                   sr.yield_per_ha, sr.total_yield, sr.suitability_pct,
                   sr.risk_level, sr.net_profit, sr.roi_pct, ss.simulated_at
            FROM simulation_sessions ss
            LEFT JOIN simulation_results sr ON sr.sessionID = ss.sessionID
            WHERE ss.farmer_id = %s
            ORDER BY ss.simulated_at DESC
            LIMIT 8
        """, (session['user_id'],))
        recent_sims = cur.fetchall()
    except Exception as e:
        print(f"[Simulator] recent_sims load: {e}")

    return render_template(
        'simulator.html',
        farmer=farmer,
        profile=profile,
        result=result,
        reward=reward,
        gamif=profile,
        recent_sims=recent_sims,
    )


@app.route('/gamification')
@role_required(ROLE_FARMER)
def gamification_page():
    farmer = get_current_farmer()
    profile     = None
    leaderboard = []
    try:
        eng         = get_gamif_engine()
        profile     = eng.get_profile(session['user_id'])
        leaderboard = eng.get_leaderboard(
            district=farmer[7] if farmer else None, limit=8
        )
        for entry in leaderboard:
            entry['is_me'] = (entry['fullname'] == (farmer[1] if farmer else ''))
    except Exception as e:
        flash(f"Gamification data error: {e}", "error")
        print(f"[Gamification] gamification_page error: {e}")

    return render_template(
        'gamification.html',
        farmer=farmer,
        profile=profile,
        leaderboard=leaderboard,
        enumerate=enumerate,
    )


@app.route('/leaderboard')
@role_required(ROLE_FARMER)
def leaderboard():
    farmer = get_current_farmer()
    eng    = get_gamif_engine()

    global_board   = eng.get_leaderboard(limit=50)
    district_board = eng.get_leaderboard(
        district=farmer[7] if farmer else None, limit=20
    )

    farmer_name = farmer[1] if farmer else ''
    for entry in global_board + district_board:
        entry['is_me'] = (entry['fullname'] == farmer_name)

    return render_template(
        'leaderboard.html',
        farmer=farmer,
        global_board=global_board,
        district_board=district_board,
        enumerate=enumerate,
    )



@app.route('/predict_yield')
@role_required(ROLE_FARMER)
def predict_yield():
    """Show the standalone yield prediction form page."""
    farmer = get_current_farmer()
    if not farmer:
        return redirect(url_for('login'))
    profile = None
    try:
        profile = get_gamif_engine().get_profile(session['user_id'])
    except Exception:
        pass
    return render_template(
        'predict_yield.html',
        farmer=farmer,
        gamif=profile,
    )

# =============================================================================
# ── EXTENSION OFFICER ROUTES  (FR7)
# =============================================================================

@app.route('/officer')
@role_required(ROLE_OFFICER)
def officer_dashboard():
    zone = session.get('zone', '')
    cur  = get_db()

    # ── Farmers with last_login for at-risk detection ─────────────────────────
    cur.execute("""
        SELECT
            f.id, f.fullname, f.phone, f.district, f.village,
            f.farm_size, f.profile_pic,
            COALESCE(g.points, 0)  AS points,
            COALESCE(g.level,  1)  AS level,
            COALESCE(g.badges, '') AS badges,
            (SELECT MAX(p.prediction_date)
             FROM predictions p WHERE p.farmer_id = f.id) AS last_simulation,
            COALESCE(g.last_login_date, NULL)              AS last_login,
            COALESCE(g.streak_days, 0)                     AS streak
        FROM farmers f
        LEFT JOIN gamification g ON g.farmer_id = f.id
        WHERE f.district = %s
        ORDER BY g.points DESC
    """, (zone,))
    farmers = cur.fetchall()

    # ── Zone aggregate stats ──────────────────────────────────────────────────
    cur.execute("""
        SELECT
            COUNT(DISTINCT f.id)          AS total_farmers,
            COUNT(p.id)                   AS total_simulations,
            COALESCE(AVG(g.points), 0)    AS avg_points,
            COALESCE(SUM(f.farm_size), 0) AS total_hectares
        FROM farmers f
        LEFT JOIN predictions  p ON p.farmer_id = f.id
        LEFT JOIN gamification g ON g.farmer_id = f.id
        WHERE f.district = %s
    """, (zone,))
    zone_stats = cur.fetchone()

    # ── Zone yield analytics — aggregated predictions ─────────────────────────
    cur.execute("""
        SELECT p.crop,
               COUNT(*)                        AS pred_count,
               ROUND(AVG(p.predicted_yield),2) AS avg_yield,
               ROUND(MAX(p.predicted_yield),2) AS max_yield,
               ROUND(SUM(p.hectares),1)        AS total_ha
        FROM predictions p
        JOIN farmers f ON f.id = p.farmer_id
        WHERE f.district = %s
        GROUP BY p.crop
        ORDER BY pred_count DESC
    """, (zone,))
    yield_by_crop = cur.fetchall()

    # ── At-risk farmers: no login in 14+ days ─────────────────────────────────
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=14)
    at_risk = []
    for f in farmers:
        last_login = f[11]   # last_login_date from gamification
        if last_login is None or (hasattr(last_login, 'date') and last_login.date() < cutoff) \
           or (isinstance(last_login, date) and last_login < cutoff):
            at_risk.append(f)

    # ── Recent activity ───────────────────────────────────────────────────────
    cur.execute("""
        SELECT f.fullname, p.crop, p.hectares, p.predicted_yield, p.prediction_date
        FROM predictions p
        JOIN farmers f ON f.id = p.farmer_id
        WHERE f.district = %s
        ORDER BY p.prediction_date DESC LIMIT 20
    """, (zone,))
    recent_activity = cur.fetchall()

    return render_template(
        'officer_dashboard.html',
        officer_name=session.get('name'),
        zone=zone,
        farmers=farmers,
        zone_stats=zone_stats,
        recent_activity=recent_activity,
        yield_by_crop=yield_by_crop,
        at_risk=at_risk,
    )


@app.route('/officer/farmer/<int:farmer_id>')
@role_required(ROLE_OFFICER)
def officer_farmer_detail(farmer_id):
    cur = get_db()
    cur.execute("SELECT * FROM farmers WHERE id=%s", (farmer_id,))
    farmer = cur.fetchone()

    cur.execute("""
        SELECT crop, hectares, predicted_yield, prediction_date
        FROM predictions WHERE farmer_id=%s ORDER BY prediction_date DESC
    """, (farmer_id,))
    predictions = cur.fetchall()

    cur.execute(
        "SELECT points, level, badges FROM gamification WHERE farmer_id=%s",
        (farmer_id,)
    )
    gamif = cur.fetchone()

    return render_template(
        'officer_farmer_detail.html',
        farmer=farmer,
        predictions=predictions,
        gamif=gamif,
    )


@app.route('/officer/send_message', methods=['POST'])
@role_required(ROLE_OFFICER)
def officer_send_message():
    zone         = request.form.get('zone', session.get('zone', ''))
    subject      = request.form.get('subject', '')
    message_body = request.form.get('message_body', '')

    cur = get_db()
    cur.execute("""
        INSERT INTO officer_messages (officer_id, zone, subject, message_body)
        VALUES (%s,%s,%s,%s)
    """, (session['user_id'], zone, subject, message_body))
    mysql.connection.commit()

    flash(f"Message sent to all farmers in {zone}.", "success")
    return redirect(url_for('officer_dashboard'))


@app.route('/officer/message_farmer/<int:farmer_id>', methods=['POST'])
@role_required(ROLE_OFFICER)
def officer_message_farmer(farmer_id):
    """Send a direct, individual message to a single farmer in the officer's zone."""
    subject      = (request.form.get('subject') or 'Message from your Officer').strip()
    message_body = (request.form.get('message_body') or '').strip()
    if not message_body:
        flash("Please type a message.", "error")
        return redirect(url_for('officer_farmer_detail', farmer_id=farmer_id))

    cur = get_db()
    # Verify the farmer is in this officer's zone
    cur.execute("SELECT fullname, district FROM farmers WHERE id=%s", (farmer_id,))
    row = cur.fetchone()
    zone = session.get('zone', '')
    if not row or (row[1] or '') != zone:
        flash("You can only message farmers in your zone.", "error")
        return redirect(url_for('officer_dashboard'))

    try:
        # Log it (farmer_id set => individual message, not a zone broadcast)
        try:
            cur.execute("""
                INSERT INTO officer_messages (officer_id, zone, subject, message_body, farmer_id)
                VALUES (%s,%s,%s,%s,%s)
            """, (session['user_id'], zone, subject, message_body, farmer_id))
            mysql.connection.commit()
        except Exception as _e:
            # Falls back gracefully if the farmer_id column has not been added yet
            print(f"[Officer msg] log skipped: {_e}")

        # Deliver straight to the farmer's notification bell
        _create_notification(
            farmer_id, 'officer_message',
            f'📢 {subject}',
            message_body,
            ''
        )
        flash(f"Message sent to {row[0]}.", "success")
    except Exception as e:
        flash(f"Could not send message: {e}", "error")
    return redirect(url_for('officer_farmer_detail', farmer_id=farmer_id))


# =============================================================================
# ── HELP & SUPPORT  (farmer help center + admin support inbox)
# =============================================================================

SUPPORT_PHONE = "0976501017"
SUPPORT_EMAIL = "zamfarm@gmail.com"


@app.route('/help')
@role_required(ROLE_FARMER)
def help_center():
    """Farmer help center: guided tour, FAQs, contact, and support tickets."""
    farmer = get_current_farmer()
    tickets = []
    try:
        cur = get_db()
        cur.execute("""
            SELECT id, subject, message, COALESCE(reply,''), replied_at, created_at
            FROM help_messages WHERE farmer_id=%s
            ORDER BY created_at DESC LIMIT 20
        """, (farmer[0],))
        tickets = cur.fetchall()
        # mark replies as seen by the farmer
        cur.execute("""UPDATE help_messages SET farmer_read_reply=1
                       WHERE farmer_id=%s AND reply IS NOT NULL""", (farmer[0],))
        mysql.connection.commit()
    except Exception as e:
        print(f"[Help] tickets error: {e}")
    return render_template('help.html', farmer=farmer, tickets=tickets,
                           support_phone=SUPPORT_PHONE, support_email=SUPPORT_EMAIL)


@app.route('/help/send', methods=['POST'])
@role_required(ROLE_FARMER)
def help_send():
    """Farmer sends a help/support message to the technical team."""
    farmer  = get_current_farmer()
    subject = (request.form.get('subject') or 'Help request').strip()[:200]
    message = (request.form.get('message') or '').strip()
    if not message:
        flash("Please describe your problem or question.", "error")
        return redirect(url_for('help_center'))
    try:
        cur = get_db()
        cur.execute("""
            INSERT INTO help_messages (farmer_id, subject, message)
            VALUES (%s,%s,%s)
        """, (farmer[0], subject, message))
        mysql.connection.commit()
        flash("Your message has been sent to the technical team. We'll reply here soon.", "success")
    except Exception as e:
        flash(f"Could not send your message: {e}", "error")
    return redirect(url_for('help_center'))


@app.route('/admin/support')
@role_required(ROLE_ADMIN)
def admin_support():
    """Admin inbox: view and reply to farmer help messages."""
    cur = get_db()
    messages, unread = [], 0
    try:
        cur.execute("""
            SELECT hm.id, hm.subject, hm.message, COALESCE(hm.reply,''),
                   hm.replied_at, hm.created_at, hm.is_read,
                   f.fullname, f.phone, f.district
            FROM help_messages hm
            JOIN farmers f ON f.id = hm.farmer_id
            ORDER BY (hm.reply IS NULL) DESC, hm.created_at DESC
        """)
        messages = cur.fetchall()
        unread = sum(1 for m in messages if not m[6])
        cur.execute("UPDATE help_messages SET is_read=1 WHERE is_read=0")
        mysql.connection.commit()
    except Exception as e:
        print(f"[Admin support] error: {e}")
    return render_template('admin_support.html', messages=messages, unread=unread)


@app.route('/admin/support/reply/<int:msg_id>', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_support_reply(msg_id):
    """Admin replies to a help message; farmer is notified in-app."""
    reply = (request.form.get('reply') or '').strip()
    if not reply:
        flash("Please type a reply.", "error")
        return redirect(url_for('admin_support'))
    try:
        cur = get_db()
        cur.execute("SELECT farmer_id, subject FROM help_messages WHERE id=%s", (msg_id,))
        row = cur.fetchone()
        if not row:
            flash("Message not found.", "error")
            return redirect(url_for('admin_support'))
        cur.execute("""
            UPDATE help_messages
            SET reply=%s, replied_at=NOW(), admin_name=%s, farmer_read_reply=0
            WHERE id=%s
        """, (reply, session.get('name', 'Support Team'), msg_id))
        mysql.connection.commit()
        _create_notification(
            row[0], 'general',
            f'🛟 Support replied: {row[1][:60]}',
            reply[:200],
            '/help'
        )
        flash("Reply sent. The farmer has been notified.", "success")
    except Exception as e:
        flash(f"Could not send reply: {e}", "error")
    return redirect(url_for('admin_support'))


# =============================================================================
# ── ADMIN ROUTES  (FR8)
# =============================================================================

@app.route('/admin')
@role_required(ROLE_ADMIN)
def admin_dashboard():
    cur = get_db()

    cur.execute("SELECT COUNT(*) FROM farmers")
    total_farmers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM extension_officers")
    total_officers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM predictions")
    total_simulations = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(AVG(points),0) FROM gamification")
    avg_points = round(float(cur.fetchone()[0]), 1)

    cur.execute("SELECT COUNT(*) FROM climate_data")
    climate_records = cur.fetchone()[0]

    cur.execute("""
        SELECT DATE(prediction_date), COUNT(*)
        FROM predictions
        GROUP BY DATE(prediction_date)
        ORDER BY DATE(prediction_date) DESC LIMIT 30
    """)
    sim_trend = [(str(r[0]), r[1]) for r in cur.fetchall()]

    cur.execute("""
        SELECT f.fullname, f.district, g.points, g.level
        FROM farmers f
        JOIN gamification g ON g.farmer_id = f.id
        ORDER BY g.points DESC LIMIT 10
    """)
    top_farmers = cur.fetchall()

    cur.execute("""
        SELECT id, fullname, email, district, created_at
        FROM farmers ORDER BY created_at DESC LIMIT 10
    """)
    recent_farmers = cur.fetchall()

    cur.execute("""
        SELECT cropID, crop_name,
               COALESCE(base_yield_tha,
                 CASE crop_name
                   WHEN 'Maize'      THEN 3.50
                   WHEN 'Soyabeans'  THEN 1.80
                   WHEN 'Groundnuts' THEN 1.20
                   WHEN 'Cassava'    THEN 10.00
                   WHEN 'Sorghum'    THEN 2.00
                   WHEN 'Millet'     THEN 1.50
                   WHEN 'Sunflower'  THEN 1.80
                   WHEN 'Potatoes'   THEN 15.00
                   ELSE 2.50 END) AS base_yield_tha,
               COALESCE(opt_temp_min,
                 CASE crop_name WHEN 'Maize' THEN 18 WHEN 'Soyabeans' THEN 20
                   WHEN 'Groundnuts' THEN 22 WHEN 'Cassava' THEN 20
                   WHEN 'Sorghum' THEN 18 WHEN 'Millet' THEN 16
                   WHEN 'Sunflower' THEN 18 WHEN 'Potatoes' THEN 10 ELSE 16 END),
               COALESCE(opt_temp_max,
                 CASE crop_name WHEN 'Maize' THEN 30 WHEN 'Soyabeans' THEN 30
                   WHEN 'Groundnuts' THEN 35 WHEN 'Cassava' THEN 35
                   WHEN 'Sorghum' THEN 38 WHEN 'Millet' THEN 38
                   WHEN 'Sunflower' THEN 32 WHEN 'Potatoes' THEN 22 ELSE 32 END),
               COALESCE(opt_rain_min,
                 CASE crop_name WHEN 'Maize' THEN 500 WHEN 'Soyabeans' THEN 450
                   WHEN 'Groundnuts' THEN 400 WHEN 'Cassava' THEN 500
                   WHEN 'Sorghum' THEN 300 WHEN 'Millet' THEN 250
                   WHEN 'Sunflower' THEN 400 WHEN 'Potatoes' THEN 500 ELSE 350 END),
               COALESCE(opt_rain_max,
                 CASE crop_name WHEN 'Maize' THEN 900 WHEN 'Soyabeans' THEN 700
                   WHEN 'Groundnuts' THEN 650 WHEN 'Cassava' THEN 1500
                   WHEN 'Sorghum' THEN 700 WHEN 'Millet' THEN 600
                   WHEN 'Sunflower' THEN 700 WHEN 'Potatoes' THEN 800 ELSE 700 END)
        FROM crops ORDER BY crop_name
    """)
    crop_params = cur.fetchall()

    cur.execute(
        "SELECT id, fullname, email, zone, phone FROM extension_officers"
    )
    officers = cur.fetchall()

    analytics = {
        'total_farmers':     total_farmers,
        'total_officers':    total_officers,
        'total_simulations': total_simulations,
        'avg_points':        avg_points,
        'climate_records':   climate_records,
        'sim_trend':         sim_trend,
        'top_farmers':       top_farmers,
    }

    return render_template(
        'admin_dashboard.html',
        admin_name=session.get('name'),
        analytics=analytics,
        recent_farmers=recent_farmers,
        crop_params=crop_params,
        officers=officers,
        enumerate=enumerate,
    )


@app.route('/admin/users')
@role_required(ROLE_ADMIN)
def admin_users():
    cur = get_db()
    cur.execute("""
        SELECT f.id, f.fullname, f.email, f.phone, f.district,
               f.farm_size, 1 AS is_active, f.created_at,
               COALESCE(g.points, 0), COALESCE(g.level, 1)
        FROM farmers f
        LEFT JOIN gamification g ON g.farmer_id = f.id
        ORDER BY f.created_at DESC
    """)
    return render_template('admin_users.html', farmers=cur.fetchall())


@app.route('/admin/user/delete/<int:farmer_id>', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_delete_user(farmer_id):
    cur = get_db()
    for tbl, col in [
        ('simulation_results', None),
        ('simulation_sessions', 'farmer_id'),
        ('point_transactions',  'farmer_id'),
        ('farmer_badges',       'farmer_id'),
        ('gamification',        'farmer_id'),
        ('predictions',         'farmer_id'),
        ('farms',               'farmer_id'),
        ('farmers',             'id'),
    ]:
        if tbl == 'simulation_results':
            # cascade via FK, skip direct delete
            continue
        cur.execute(f"DELETE FROM {tbl} WHERE {col} = %s", (farmer_id,))
    mysql.connection.commit()
    flash("Farmer account deleted.", "success")
    return redirect(url_for('admin_users'))


@app.route('/admin/user/toggle/<int:farmer_id>', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_toggle_user(farmer_id):
    cur = get_db()
    # is_active column may not exist yet — add it first via migrate.sql
    try:
        cur.execute("SELECT is_active FROM farmers WHERE id=%s", (farmer_id,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE farmers SET is_active=%s WHERE id=%s",
                (0 if row[0] else 1, farmer_id)
            )
            mysql.connection.commit()
            flash("Account status updated.", "success")
    except Exception:
        flash("Run migrate.sql first to add the is_active column.", "error")
    return redirect(url_for('admin_users'))


@app.route('/admin/crop_params', methods=['GET', 'POST'])
@role_required(ROLE_ADMIN)
def admin_crop_params():
    cur = get_db()
    if request.method == 'POST':
        try:
            crop_name     = request.form.get('crop_name', '').strip()
            base_yield    = float(request.form.get('base_yield') or 0)
            opt_temp_min  = float(request.form.get('opt_temp_min') or 0)
            opt_temp_max  = float(request.form.get('opt_temp_max') or 0)
            opt_rain_min  = float(request.form.get('opt_rain_min') or 0)
            opt_rain_max  = float(request.form.get('opt_rain_max') or 0)

            if not crop_name:
                flash("Crop name is required.", "error")
                return redirect(url_for('admin_dashboard') + '#crop-params')

            cur.execute("""
                INSERT INTO crops
                    (crop_name, base_yield_tha, opt_temp_min, opt_temp_max,
                     opt_rain_min, opt_rain_max)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    base_yield_tha = VALUES(base_yield_tha),
                    opt_temp_min   = VALUES(opt_temp_min),
                    opt_temp_max   = VALUES(opt_temp_max),
                    opt_rain_min   = VALUES(opt_rain_min),
                    opt_rain_max   = VALUES(opt_rain_max),
                    updated_at     = NOW()
            """, (crop_name, base_yield, opt_temp_min, opt_temp_max,
                  opt_rain_min, opt_rain_max))
            mysql.connection.commit()
            flash(f"✅ Crop parameters for {crop_name} saved successfully!", "success")
        except Exception as e:
            print(f"[CropParams] Error: {e}")
            import traceback; traceback.print_exc()
            flash(f"Could not save parameters: {e}", "error")
        return redirect(url_for('admin_dashboard') + '#crop-params')

    cur.execute("SELECT cropID, crop_name, base_yield_tha, opt_temp_min, opt_temp_max, opt_rain_min, opt_rain_max FROM crops ORDER BY crop_name")
    return render_template('admin_crop_params.html', crop_params=cur.fetchall())


@app.route('/admin/officer/create', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_create_officer():
    cur = get_db()
    try:
        cur.execute("""
            INSERT INTO extension_officers
                (fullname, email, password, zone, phone)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            request.form['fullname'],
            request.form['email'],
            generate_password_hash(request.form['password']),
            request.form['zone'],
            request.form.get('phone', ''),
        ))
        mysql.connection.commit()
        flash(f"Officer '{request.form['fullname']}' created for zone: {request.form['zone']}.", "success")
    except Exception as e:
        flash(f"Error creating officer: {e}", "error")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/officer/delete/<int:officer_id>', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_delete_officer(officer_id):
    cur = get_db()
    cur.execute("DELETE FROM extension_officers WHERE id=%s", (officer_id,))
    mysql.connection.commit()
    flash("Officer account removed.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/api/analytics')
@role_required(ROLE_ADMIN)
def admin_api_analytics():
    cur = get_db()
    cur.execute("SELECT crop, COUNT(*) FROM predictions GROUP BY crop")
    crop_dist = dict(cur.fetchall())
    cur.execute("""
        SELECT district, COUNT(*) AS c FROM farmers
        GROUP BY district ORDER BY c DESC LIMIT 10
    """)
    district_dist = dict(cur.fetchall())
    return jsonify({
        'crop_distribution':     crop_dist,
        'district_distribution': district_dist,
    })



# =============================================================================
# ── DASHBOARD API ENDPOINTS
# =============================================================================

@app.route('/api/my_predictions')
def api_my_predictions():
    """Return the farmer's prediction history as JSON for dashboard charts."""
    # Return empty data gracefully if not logged in (fetch() gets JSON not a redirect)
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'records': [], 'count': 0})
    try:
        cur = get_db()
        SOIL_NAMES = {1: 'Loamy', 2: 'Sandy', 3: 'Clay'}
        cur.execute("""
            SELECT crop, hectares, predicted_yield, prediction_date,
                   COALESCE(soil_type, 1) as soil_type
            FROM predictions
            WHERE farmer_id = %s
            ORDER BY prediction_date DESC
            LIMIT 200
        """, (session['user_id'],))
        rows = cur.fetchall()
        records = [
            [r[0], float(r[1]), float(r[2]), str(r[3]),
             SOIL_NAMES.get(int(r[4]) if r[4] else 1, 'Loamy')]
            for r in rows
        ]
        return jsonify({'records': records, 'count': len(records)})
    except Exception as e:
        return jsonify({'records': [], 'count': 0, 'error': str(e)})


@app.route('/api/messages')
def api_messages():
    """Return officer messages for this farmer's district + system notifications."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'messages': [], 'count': 0})
    try:
        farmer = get_current_farmer()
        district = farmer[7] if farmer else ''
        cur = get_db()
        # Officer messages sent to this farmer's district/zone
        cur.execute("""
            SELECT om.subject, om.message_body, om.sent_at,
                   eo.fullname AS officer_name, eo.zone
            FROM officer_messages om
            JOIN extension_officers eo ON eo.id = om.officer_id
            WHERE om.zone = %s
            ORDER BY om.sent_at DESC LIMIT 20
        """, (district,))
        rows = cur.fetchall()
        messages = [
            {
                'subject':      r[0] or 'Message from Officer',
                'body':         r[1],
                'sent_at':      str(r[2]),
                'officer_name': r[3],
                'zone':         r[4],
                'type':         'officer',
            }
            for r in rows
        ]
        return jsonify({'messages': messages, 'count': len(messages)})
    except Exception as e:
        return jsonify({'messages': [], 'count': 0, 'error': str(e)})


@app.route('/api/farmer_profile')
def api_farmer_profile():
    """Return full farmer profile data for the profile popup."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        farmer = get_current_farmer()
        if not farmer:
            return jsonify({'error': 'Farmer not found'}), 404

        # Gamification
        profile = None
        try:
            profile = get_gamif_engine().get_profile(session['user_id'])
        except Exception:
            pass

        # Prediction count
        cur = get_db()
        cur.execute("SELECT COUNT(*) FROM predictions WHERE farmer_id=%s", (session['user_id'],))
        pred_count = cur.fetchone()[0]

        return jsonify({
            'id':            farmer[0],
            'fullname':      farmer[1],
            'email':         farmer[2] or '—',
            'phone':         farmer[3],
            'farm_size':     float(farmer[5]),
            'village':       farmer[6] or '—',
            'district':      farmer[7],
            'profile_pic':   farmer[8] or 'default.png',
            'points':        profile['points']        if profile else 0,
            'level':         profile['level']         if profile else 1,
            'level_name':    profile['level_info']['name'] if profile else 'Climate Novice',
            'level_icon':    profile['level_info']['icon'] if profile else '🌱',
            'streak':        profile['streak_days']   if profile else 0,
            'total_sims':    profile['total_simulations'] if profile else 0,
            'pred_count':    pred_count,
            'badges':        profile['badges']        if profile else [],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/profile/update', methods=['POST'])
def update_profile():
    """Update the logged-in farmer's profile (name, phone, village, district,
    farm size, and optional profile picture)."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return redirect(url_for('login'))

    farmer = get_current_farmer()
    if not farmer:
        return redirect(url_for('login'))

    try:
        fullname  = (request.form.get('fullname')  or farmer[1]).strip()
        phone     = (request.form.get('phone')     or farmer[3]).strip()
        village   = (request.form.get('village')   or farmer[6] or '').strip()
        district  = (request.form.get('district')  or farmer[7] or '').strip()
        try:
            farm_size = float(request.form.get('farm_size') or farmer[5])
        except (TypeError, ValueError):
            farm_size = farmer[5]
        farm_size = max(0.1, min(10000, farm_size))

        # ── Optional profile picture ─────────────────────────────────────
        filename = farmer[8] or 'default.png'
        file = request.files.get('profile_pic')
        if file and file.filename and allowed_image(file.filename):
            # Prefix with farmer id + timestamp to avoid collisions/overwrites
            safe = secure_filename(file.filename)
            filename = f"farmer{farmer[0]}_{int(datetime.now().timestamp())}_{safe}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur = get_db()
        cur.execute("""
            UPDATE farmers
            SET fullname=%s, phone=%s, village=%s, district=%s,
                farm_size=%s, profile_pic=%s
            WHERE id=%s
        """, (fullname, phone, village, district, farm_size, filename, farmer[0]))
        mysql.connection.commit()

        # Keep session display name in sync
        session['name'] = fullname
        flash("Profile updated successfully.", "success")
    except Exception as e:
        try: mysql.connection.rollback()
        except Exception: pass
        if 'Duplicate entry' in str(e) and 'phone' in str(e):
            flash("That phone number is already in use by another account.", "error")
        else:
            flash(f"Could not update profile: {e}", "error")

    return redirect(url_for('dashboard'))


@app.route('/api/history_stats')
def api_history_stats():
    """Return prediction history stats for the history page charts."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'records': [], 'stats': {}})
    try:
        cur = get_db()
        cur.execute("""
            SELECT crop, hectares, predicted_yield, prediction_date
            FROM predictions WHERE farmer_id=%s
            ORDER BY prediction_date DESC
        """, (session['user_id'],))
        rows = cur.fetchall()
        records = [[r[0], float(r[1]), float(r[2]), str(r[3])] for r in rows]
        if records:
            yields  = [r[2] for r in records]
            crops   = [r[0] for r in records]
            stats   = {
                'total':       len(records),
                'best_yield':  max(yields),
                'avg_yield':   round(sum(yields)/len(yields), 2),
                'unique_crops':len(set(crops)),
            }
        else:
            stats = {'total': 0, 'best_yield': 0, 'avg_yield': 0, 'unique_crops': 0}
        return jsonify({'records': records, 'stats': stats})
    except Exception as e:
        return jsonify({'records': [], 'stats': {}, 'error': str(e)})


# =============================================================================
# ── FARMER API ENDPOINTS (for dashboard panels)
# =============================================================================

@app.route('/api/officer_messages')
def api_officer_messages():
    """Return officer messages sent to this farmer's district — for notifications."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'messages': []})
    try:
        farmer = get_current_farmer()
        if not farmer:
            return jsonify({'messages': []})
        district = farmer[7]
        cur = get_db()
        cur.execute("""
            SELECT om.subject, om.message_body, om.sent_at,
                   eo.fullname AS officer_name, om.zone
            FROM officer_messages om
            JOIN extension_officers eo ON eo.id = om.officer_id
            WHERE om.zone = %s
            ORDER BY om.sent_at DESC
            LIMIT 20
        """, (district,))
        rows = cur.fetchall()
        messages = [
            {
                'subject':      r[0] or 'Message from Officer',
                'body':         r[1],
                'sent_at':      str(r[2])[:16],
                'officer_name': r[3],
                'zone':         r[4],
            }
            for r in rows
        ]
        return jsonify({'messages': messages, 'count': len(messages)})
    except Exception as e:
        return jsonify({'messages': [], 'error': str(e)})


# =============================================================================
# ── NOTIFICATIONS  (in-app bell system)
# =============================================================================

def _create_notification(farmer_id, notif_type, title, body='', link=''):
    """Insert a notification row — called whenever a notable event occurs."""
    try:
        cur = get_db()
        cur.execute("""
            INSERT INTO notifications (farmer_id, type, title, body, link)
            VALUES (%s, %s, %s, %s, %s)
        """, (farmer_id, notif_type, title, body, link))
        mysql.connection.commit()
    except Exception as e:
        print(f"[Notif] Could not create notification: {e}")


def _unread_notification_count(farmer_id):
    """Return the number of unread notifications for a farmer."""
    try:
        cur = get_db()
        cur.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE farmer_id = %s AND is_read = 0
        """, (farmer_id,))
        return cur.fetchone()[0] or 0
    except Exception:
        return 0


@app.route('/api/notifications')
def api_notifications():
    """Return all notifications for the logged-in farmer, newest first.
    Also merges live marketplace inquiry count and officer messages."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'notifications': [], 'unread': 0})

    farmer_id = session['user_id']
    farmer    = get_current_farmer()
    notifs    = []

    try:
        cur = get_db()

        # ── 1. Stored notifications (DB table) ───────────────────────────
        cur.execute("""
            SELECT id, type, title, body, link, is_read, created_at
            FROM notifications
            WHERE farmer_id = %s
            ORDER BY created_at DESC
            LIMIT 30
        """, (farmer_id,))
        for r in cur.fetchall():
            notifs.append({
                'id':         r[0],
                'type':       r[1],
                'title':      r[2],
                'body':       r[3] or '',
                'link':       r[4] or '',
                'is_read':    bool(r[5]),
                'created_at': str(r[6])[:16],
                'source':     'db',
            })

        # ── 2. Live marketplace inquiries (unread buyer messages) ─────────
        try:
            cur.execute("""
                SELECT COUNT(*) FROM marketplace_inquiries mq
                JOIN marketplace_listings ml ON ml.id = mq.listing_id
                WHERE ml.farmer_id = %s AND mq.is_read = 0
            """, (farmer_id,))
            mkt_unread = cur.fetchone()[0] or 0
            if mkt_unread > 0:
                notifs.insert(0, {
                    'id':         None,
                    'type':       'marketplace_inquiry',
                    'title':      f'🛒 {mkt_unread} New Marketplace Inquir{"y" if mkt_unread==1 else "ies"}',
                    'body':       'Buyers are interested in your listings. Check your messages.',
                    'link':       '/marketplace/messages',
                    'is_read':    False,
                    'created_at': 'Now',
                    'source':     'live',
                })
        except Exception:
            mkt_unread = 0

        # ── 3. Live officer messages (zone broadcasts only) ───────────────
        try:
            district = farmer[7] if farmer else ''
            # Try the schema with farmer_id (individual messages excluded);
            # fall back to the old schema if the column isn't there yet.
            try:
                cur.execute("""
                    SELECT om.subject, om.message_body, om.sent_at, eo.fullname
                    FROM officer_messages om
                    JOIN extension_officers eo ON eo.id = om.officer_id
                    WHERE om.zone = %s AND om.farmer_id IS NULL
                    ORDER BY om.sent_at DESC LIMIT 5
                """, (district,))
            except Exception:
                cur.execute("""
                    SELECT om.subject, om.message_body, om.sent_at, eo.fullname
                    FROM officer_messages om
                    JOIN extension_officers eo ON eo.id = om.officer_id
                    WHERE om.zone = %s
                    ORDER BY om.sent_at DESC LIMIT 5
                """, (district,))
            for r in cur.fetchall():
                notifs.append({
                    'id':         None,
                    'type':       'officer_message',
                    'title':      f'📢 {r[0] or "Officer Advisory"}',
                    'body':       (r[1] or '')[:120] + ('…' if r[1] and len(r[1]) > 120 else ''),
                    'link':       '',
                    'is_read':    True,
                    'created_at': str(r[2])[:16],
                    'source':     'live',
                })
        except Exception:
            pass

        # ── 4. Yield alert — compare last two predictions ─────────────────
        try:
            cur.execute("""
                SELECT crop, predicted_yield, hectares
                FROM predictions
                WHERE farmer_id = %s
                ORDER BY prediction_date DESC LIMIT 2
            """, (farmer_id,))
            preds = cur.fetchall()
            if len(preds) == 2:
                latest_tha = float(preds[0][2]) and round(float(preds[0][1]) / float(preds[0][2]), 2)
                prev_tha   = float(preds[1][2]) and round(float(preds[1][1]) / float(preds[1][2]), 2)
                if prev_tha and latest_tha:
                    pct_change = round(((latest_tha - prev_tha) / prev_tha) * 100, 1)
                    if abs(pct_change) >= 25:
                        direction = 'dropped' if pct_change < 0 else 'jumped'
                        notifs.append({
                            'id':         None,
                            'type':       'yield_alert',
                            'title':      f'⚠️ Yield Alert — {preds[0][0]}',
                            'body':       f'Your latest {preds[0][0]} yield {direction} {abs(pct_change):.0f}% '
                                          f'({prev_tha} → {latest_tha} T/ha) vs your previous prediction.',
                            'link':       '/history',
                            'is_read':    False,
                            'created_at': 'Latest prediction',
                            'source':     'live',
                        })
        except Exception:
            pass

        unread = sum(1 for n in notifs if not n['is_read'])
        return jsonify({'notifications': notifs, 'unread': unread})

    except Exception as e:
        return jsonify({'notifications': [], 'unread': 0, 'error': str(e)})


@app.route('/api/notifications/mark_read', methods=['POST'])
def api_notifications_mark_read():
    """Mark all DB notifications as read for this farmer."""
    if 'user_id' not in session or session.get('role') != ROLE_FARMER:
        return jsonify({'ok': False})
    try:
        cur = get_db()
        cur.execute("""
            UPDATE notifications SET is_read = 1
            WHERE farmer_id = %s AND is_read = 0
        """, (session['user_id'],))
        mysql.connection.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})



# =============================================================================
# ── CLIMATE ROUTES (FR2) — Data Ingestion, Seasonal Forecast, Crop Recommendation
# =============================================================================
try:
    from climate_routes import register_climate_routes
    register_climate_routes(app, mysql)
    print("[Climate] Routes registered: /climate_data, /climate_forecast, /climate_scenarios")
except ImportError as e:
    print(f"[Climate WARNING] climate_routes.py not found: {e}")
except Exception as e:
    print(f"[Climate WARNING] Could not register climate routes: {e}")


# ── RECOMMEND CROP alias (/recommend_crop → /crop handler) ───────────────────
@app.route('/recommend_crop', methods=['GET', 'POST'])
@role_required(ROLE_FARMER)
def recommend_crop():
    """Alias for /crop — some templates reference /recommend_crop."""
    return crop()






@app.route('/admin/gamification', methods=['GET', 'POST'])
@role_required(ROLE_ADMIN)
def admin_gamification():
    cur = get_db()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_level':
            cur.execute("""
                UPDATE levels
                SET level_name=%s, min_points=%s, icon=%s, color_hex=%s
                WHERE levelID=%s
            """, (
                request.form['level_name'],
                int(request.form['min_points']),
                request.form.get('icon', '🌱'),
                request.form.get('color_hex', '#888888'),
                int(request.form['level_id']),
            ))
            mysql.connection.commit()
            flash("Level updated.", "success")

        elif action == 'add_level':
            try:
                cur.execute("""
                    INSERT INTO levels (level_number, level_name, min_points, icon, color_hex)
                    VALUES (%s,%s,%s,%s,%s)
                """, (
                    int(request.form['level_number']),
                    request.form['level_name'],
                    int(request.form['min_points']),
                    request.form.get('icon', '🌱'),
                    request.form.get('color_hex', '#888888'),
                ))
                mysql.connection.commit()
                flash("Level added.", "success")
            except Exception as e:
                flash(f"Could not add level: {e}", "error")

        elif action == 'delete_level':
            cur.execute("DELETE FROM levels WHERE levelID=%s",
                        (int(request.form['level_id']),))
            mysql.connection.commit()
            flash("Level deleted.", "success")

        elif action == 'reset_points':
            farmer_id = int(request.form['farmer_id'])
            cur.execute(
                "UPDATE gamification SET points=0, level=1 WHERE farmer_id=%s",
                (farmer_id,)
            )
            cur.execute(
                "UPDATE farmers SET total_points=0 WHERE id=%s", (farmer_id,)
            )
            mysql.connection.commit()
            flash("Farmer points reset to 0.", "success")

        return redirect(url_for('admin_gamification'))

    # GET — load all data
    cur.execute("SELECT * FROM levels ORDER BY level_number")
    levels = cur.fetchall()

    cur.execute("""
        SELECT f.id, f.fullname, f.district,
               COALESCE(g.points,0)  AS points,
               COALESCE(g.level,1)   AS level,
               COALESCE(g.streak_days,0)  AS streak,
               COALESCE(g.total_simulations,0) AS sims,
               COALESCE(g.total_logins,0) AS logins
        FROM farmers f
        LEFT JOIN gamification g ON g.farmer_id = f.id
        ORDER BY points DESC
    """)
    farmer_gamif = cur.fetchall()

    cur.execute("SELECT COALESCE(AVG(points),0) FROM gamification")
    avg_pts = round(float(cur.fetchone()[0]), 1)

    cur.execute("SELECT COALESCE(MAX(points),0) FROM gamification")
    max_pts = int(cur.fetchone()[0])

    cur.execute("SELECT COUNT(*) FROM gamification WHERE level >= 3")
    high_level = int(cur.fetchone()[0])

    cur.execute("SELECT * FROM badges ORDER BY badgeID")
    badges = cur.fetchall()

    return render_template(
        'admin_gamification.html',
        levels=levels,
        farmer_gamif=farmer_gamif,
        avg_pts=avg_pts,
        max_pts=max_pts,
        high_level=high_level,
        badges=badges,
        admin_name=session.get('name'),
    )

# =============================================================================
# ── FARMER ↔ OFFICER COMMUNICATION (FR7 extension)
# =============================================================================

@app.route('/api/my_officer')
@role_required(ROLE_FARMER)
def api_my_officer():
    """Return the extension officer assigned to this farmer's district."""
    farmer = get_current_farmer()
    if not farmer:
        return jsonify({'officer': None})
    district = farmer[7]
    try:
        cur = get_db()
        cur.execute("""
            SELECT id, fullname, email, zone, phone
            FROM extension_officers
            WHERE zone = %s
            LIMIT 1
        """, (district,))
        row = cur.fetchone()
        if row:
            return jsonify({'officer': {
                'id':      row[0],
                'name':    row[1],
                'email':   row[2] or '',
                'zone':    row[3],
                'phone':   row[4] or '',
            }})
        # No officer assigned to this zone — return first officer as fallback
        cur.execute("SELECT id, fullname, email, zone, phone FROM extension_officers LIMIT 1")
        row = cur.fetchone()
        if row:
            return jsonify({'officer': {
                'id': row[0], 'name': row[1],
                'email': row[2] or '', 'zone': row[3], 'phone': row[4] or '',
            }})
        return jsonify({'officer': None})
    except Exception as e:
        return jsonify({'officer': None, 'error': str(e)})


@app.route('/api/farmer_messages')
@role_required(ROLE_FARMER)
def api_farmer_messages():
    """Return all officer messages for this farmer's district, newest first."""
    farmer = get_current_farmer()
    if not farmer:
        return jsonify({'messages': []})
    district = farmer[7]
    try:
        cur = get_db()
        cur.execute("""
            SELECT om.id, om.subject, om.message_body, om.sent_at,
                   eo.fullname, eo.phone, eo.email, om.zone
            FROM officer_messages om
            JOIN extension_officers eo ON eo.id = om.officer_id
            WHERE om.zone = %s
            ORDER BY om.sent_at DESC
            LIMIT 50
        """, (district,))
        rows = cur.fetchall()
        return jsonify({'messages': [
            {
                'id':           r[0],
                'subject':      r[1] or 'Advisory from Officer',
                'body':         r[2],
                'sent_at':      str(r[3])[:16],
                'officer_name': r[4],
                'officer_phone': r[5] or '',
                'officer_email': r[6] or '',
                'zone':         r[7],
            } for r in rows
        ], 'count': len(rows), 'district': district})
    except Exception as e:
        return jsonify({'messages': [], 'error': str(e)})



# =============================================================================
# ── FORGOT PASSWORD / OTP RESET  (FR1 extension)
# =============================================================================
import random, hashlib
from datetime import datetime, timedelta

def generate_otp():
    return str(random.randint(100000, 999999))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    identifier = request.form.get('identifier', '').strip()
    if not identifier:
        flash("Please enter your email or phone number.", "error")
        return render_template('forgot_password.html')

    try:
        cur = get_db()
        # Search farmers by email or phone
        cur.execute("""
            SELECT id, fullname, email, phone
            FROM farmers
            WHERE (LOWER(email) = LOWER(%s) OR phone = %s OR phone = %s)
            LIMIT 1
        """, (identifier, identifier, identifier.replace(' ', '')))
        farmer = cur.fetchone()

        if not farmer:
            flash("No account found with that email or phone.", "error")
            return render_template('forgot_password.html')

        # Generate OTP and store with expiry (10 minutes)
        otp      = generate_otp()
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        expiry   = datetime.now() + timedelta(minutes=10)

        # Store in DB
        cur.execute("""
            INSERT INTO password_resets (farmer_id, otp_hash, expires_at)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE otp_hash=%s, expires_at=%s, used=0
        """, (farmer[0], otp_hash, expiry, otp_hash, expiry))
        mysql.connection.commit()

        # In production: send SMS/email. For demo: show OTP on screen.
        print(f"[OTP] Farmer {farmer[1]} OTP: {otp}")  # Remove in production!

        session['otp_farmer_id'] = farmer[0]
        session['otp_identifier'] = identifier
        flash(f"OTP sent! For demo purposes your OTP is: {otp}", "info")
        return redirect(url_for('verify_otp'))

    except Exception as e:
        print(f"[ForgotPassword] Error: {e}")
        flash("Could not process request. Try again.", "error")
        return render_template('forgot_password.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'otp_farmer_id' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'GET':
        return render_template('verify_otp.html',
                               identifier=session.get('otp_identifier', ''))

    otp_entered = request.form.get('otp', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not otp_entered or not new_password:
        flash("Please enter the OTP and new password.", "error")
        return render_template('verify_otp.html',
                               identifier=session.get('otp_identifier', ''))

    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template('verify_otp.html',
                               identifier=session.get('otp_identifier', ''))

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return render_template('verify_otp.html',
                               identifier=session.get('otp_identifier', ''))

    try:
        farmer_id = session['otp_farmer_id']
        otp_hash  = hashlib.sha256(otp_entered.encode()).hexdigest()
        cur = get_db()
        cur.execute("""
            SELECT id FROM password_resets
            WHERE farmer_id = %s
              AND otp_hash  = %s
              AND expires_at > NOW()
              AND used = 0
        """, (farmer_id, otp_hash))
        reset_row = cur.fetchone()

        if not reset_row:
            flash("Invalid or expired OTP. Please request a new one.", "error")
            return render_template('verify_otp.html',
                                   identifier=session.get('otp_identifier', ''))

        # Update password
        from werkzeug.security import generate_password_hash
        new_hash = generate_password_hash(new_password)
        cur.execute("UPDATE farmers SET password=%s WHERE id=%s",
                    (new_hash, farmer_id))
        cur.execute("UPDATE password_resets SET used=1 WHERE farmer_id=%s",
                    (farmer_id,))
        mysql.connection.commit()

        session.pop('otp_farmer_id', None)
        session.pop('otp_identifier', None)
        flash("Password reset successfully! Please log in.", "success")
        return redirect(url_for('login'))

    except Exception as e:
        print(f"[VerifyOTP] Error: {e}")
        flash("Could not reset password. Try again.", "error")
        return render_template('verify_otp.html',
                               identifier=session.get('otp_identifier', ''))


# =============================================================================
# ── MARKETPLACE  (FR_NEW — farmer product listings)
# =============================================================================

# =============================================================================
# ── MARKETPLACE  (Full feature — multi-image, inquiries, edit, sold tracking)
# =============================================================================

import uuid as _uuid

def _save_market_images(files, listing_id):
    """Save uploaded images for a listing and return list of saved filenames."""
    saved = []
    upload_dir = os.path.join('static', 'uploads', 'market')
    os.makedirs(upload_dir, exist_ok=True)
    for f in files:
        if f and f.filename:
            ext  = os.path.splitext(f.filename)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                continue
            name = f"market_{listing_id}_{_uuid.uuid4().hex[:8]}{ext}"
            path = os.path.join(upload_dir, name)
            f.save(path)
            saved.append(name)
    return saved


@app.route('/marketplace')
def marketplace():
    # Detect farmer BEFORE the DB try block so exceptions can't hide logged-in state
    farmer = get_current_farmer() if session.get('role') == ROLE_FARMER else None

    try:
        cur      = get_db()
        category = request.args.get('category', '')
        district = request.args.get('district', '')
        search   = request.args.get('q', '')
        sort     = request.args.get('sort', 'newest')

        sort_clause = {
            'newest':   'ml.created_at DESC',
            'oldest':   'ml.created_at ASC',
            'price_asc':  'ml.price_per_kg ASC',
            'price_desc': 'ml.price_per_kg DESC',
            'qty_desc':   'ml.quantity_kg DESC',
        }.get(sort, 'ml.created_at DESC')

        base = """
            SELECT ml.id, ml.title, ml.description, ml.crop_name,
                   ml.quantity_kg, ml.price_per_kg, ml.district,
                   ml.contact_phone, ml.contact_whatsapp,
                   ml.created_at, f.fullname, f.village,
                   COALESCE(ml.status,'available') AS status,
                   COALESCE(ml.unit_label,'kg') AS unit_label,
                   ml.farmer_id,
                   ml.latitude, ml.longitude,
                   (SELECT GROUP_CONCAT(mi.filename ORDER BY mi.sort_order SEPARATOR ',')
                    FROM marketplace_images mi WHERE mi.listing_id = ml.id) AS images,
                   (SELECT COUNT(*) FROM marketplace_inquiries mq
                    WHERE mq.listing_id = ml.id) AS inquiry_count,
                   COALESCE(f.profile_pic, 'default.png') AS seller_pic
            FROM marketplace_listings ml
            JOIN farmers f ON f.id = ml.farmer_id
            WHERE ml.is_active = 1
        """
        params = []
        if category: base += " AND ml.crop_name = %s";        params.append(category)
        if district: base += " AND ml.district  = %s";        params.append(district)
        if search:
            base += " AND (ml.title LIKE %s OR ml.description LIKE %s OR ml.crop_name LIKE %s OR f.fullname LIKE %s)"
            params += [f'%{search}%']*4
        base += f" ORDER BY {sort_clause} LIMIT 80"

        cur.execute(base, params)
        listings = cur.fetchall()

        cur.execute("SELECT DISTINCT crop_name FROM marketplace_listings WHERE is_active=1 ORDER BY crop_name")
        categories = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT district FROM marketplace_listings WHERE is_active=1 ORDER BY district")
        districts = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM marketplace_listings WHERE is_active=1")
        total_listings = cur.fetchone()[0]

        # Farmer's own listings
        my_listings = []
        unread_msgs = 0
        if farmer:
            cur.execute("""
                SELECT ml.id, ml.title, ml.crop_name, ml.quantity_kg,
                       ml.price_per_kg, ml.status, ml.created_at,
                       (SELECT mi.filename FROM marketplace_images mi
                        WHERE mi.listing_id = ml.id ORDER BY mi.sort_order LIMIT 1) AS thumb,
                       (SELECT COUNT(*) FROM marketplace_inquiries mq WHERE mq.listing_id = ml.id) AS inquiries
                FROM marketplace_listings ml
                WHERE ml.farmer_id = %s AND ml.is_active = 1
                ORDER BY ml.created_at DESC
            """, (farmer[0],))
            my_listings = cur.fetchall()
            unread_msgs = _unread_message_count(farmer[0])

        return render_template('marketplace.html',
            listings=listings, categories=categories,
            districts=districts, selected_cat=category,
            selected_dist=district, search_q=search,
            sort=sort, farmer=farmer, my_listings=my_listings,
            total_listings=total_listings, unread_msgs=unread_msgs)
    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template('marketplace.html',
            listings=[], categories=[], districts=[],
            selected_cat='', selected_dist='', search_q='',
            sort='newest', farmer=farmer, my_listings=[], total_listings=0,
            unread_msgs=0)


@app.route('/marketplace/listing/<int:listing_id>')
def marketplace_detail(listing_id):
    """Public listing detail — any visitor can view; owner sees inquiries."""
    farmer = get_current_farmer() if session.get('role') == ROLE_FARMER else None
    cur = get_db()

    # 1. View counter (best-effort, never fatal)
    try:
        cur.execute("UPDATE marketplace_listings SET views=COALESCE(views,0)+1 WHERE id=%s",
                    (listing_id,))
        mysql.connection.commit()
    except Exception:
        try: mysql.connection.rollback()
        except Exception: pass

    # 2. Core listing fetch — try rich query, fall back to minimal
    listing = None
    try:
        cur.execute("""
            SELECT ml.id, ml.title, ml.description, ml.crop_name,
                   ml.quantity_kg, ml.price_per_kg, ml.district,
                   ml.contact_phone, ml.contact_whatsapp,
                   ml.created_at, f.fullname, f.village,
                   COALESCE(ml.status,'available'), COALESCE(ml.unit_label,'kg'),
                   ml.farmer_id, ml.latitude, ml.longitude,
                   (SELECT GROUP_CONCAT(mi.filename ORDER BY mi.sort_order SEPARATOR ',')
                    FROM marketplace_images mi WHERE mi.listing_id = ml.id) AS images,
                   COALESCE(ml.views,0),
                   (SELECT COUNT(*) FROM marketplace_inquiries mq WHERE mq.listing_id = ml.id),
                   COALESCE(f.profile_pic, 'default.png')
            FROM marketplace_listings ml
            JOIN farmers f ON f.id = ml.farmer_id
            WHERE ml.id = %s AND ml.is_active = 1
        """, (listing_id,))
        listing = cur.fetchone()
    except Exception as eq:
        print(f"[MarketDetail] Rich query failed ({eq}); using fallback")
        try:
            cur.execute("""
                SELECT ml.id, ml.title, ml.description, ml.crop_name,
                       ml.quantity_kg, ml.price_per_kg, ml.district,
                       ml.contact_phone, ml.contact_whatsapp,
                       ml.created_at, f.fullname, f.village,
                       COALESCE(ml.status,'available'), COALESCE(ml.unit_label,'kg'),
                       ml.farmer_id, ml.latitude, ml.longitude,
                       NULL, 0, 0, COALESCE(f.profile_pic, 'default.png')
                FROM marketplace_listings ml
                JOIN farmers f ON f.id = ml.farmer_id
                WHERE ml.id = %s
            """, (listing_id,))
            listing = cur.fetchone()
        except Exception as eq2:
            print(f"[MarketDetail] Fallback query also failed: {eq2}")
            flash(f"Could not load listing: {eq2}", "error")
            return redirect(url_for('marketplace'))

    if not listing:
        flash("That listing is no longer available.", "error")
        return redirect(url_for('marketplace'))

    is_own = bool(farmer and farmer[0] == listing[14])

    # 3. Inquiries — only the owner sees buyer messages
    inquiries = []
    if is_own:
        try:
            cur.execute("""
                SELECT mq.id, mq.listing_id, mq.message, f.phone,
                       f.fullname, f.district, mq.created_at, mq.is_read
                FROM marketplace_inquiries mq
                JOIN farmers f ON f.id = mq.farmer_id
                WHERE mq.listing_id = %s
                ORDER BY mq.created_at DESC
            """, (listing_id,))
            inquiries = cur.fetchall()
            cur.execute("UPDATE marketplace_inquiries SET is_read=1 WHERE listing_id=%s",
                        (listing_id,))
            mysql.connection.commit()
        except Exception as ie:
            print(f"[MarketDetail] Inquiries failed: {ie}")
            inquiries = []

    # 4. Related listings (same crop, other listings)
    related = []
    try:
        cur.execute("""
            SELECT ml.id, ml.crop_name, ml.title, ml.price_per_kg,
                   ml.district, f.fullname,
                   (SELECT mi2.filename FROM marketplace_images mi2
                    WHERE mi2.listing_id = ml.id ORDER BY mi2.sort_order LIMIT 1),
                   COALESCE(ml.unit_label,'kg')
            FROM marketplace_listings ml
            JOIN farmers f ON f.id = ml.farmer_id
            WHERE ml.crop_name = %s AND ml.id != %s AND ml.is_active = 1
            ORDER BY ml.created_at DESC LIMIT 4
        """, (listing[3], listing_id))
        related = cur.fetchall()
    except Exception as re_err:
        print(f"[MarketDetail] Related failed: {re_err}")
        related = []

    return render_template('marketplace_detail.html',
                           listing=listing, farmer=farmer,
                           inquiries=inquiries, related=related)


@app.route('/marketplace/post', methods=['GET', 'POST'])
@role_required(ROLE_FARMER)
def marketplace_post():
    farmer = get_current_farmer()
    if request.method == 'POST':
        title         = request.form.get('title', '').strip()
        description   = request.form.get('description', '').strip()
        crop_name     = request.form.get('crop_name', '')
        quantity_kg   = float(request.form.get('quantity_kg')   or 0)
        price_per_kg  = float(request.form.get('price_per_kg')  or 0)
        unit_label    = request.form.get('unit_label', 'kg')
        contact_phone    = request.form.get('contact_phone', farmer[3] or '').strip()
        contact_whatsapp = request.form.get('contact_whatsapp', '').strip()
        latitude      = request.form.get('latitude', None) or None
        longitude     = request.form.get('longitude', None) or None
        district      = farmer[7] or ''

        if not title or not crop_name or quantity_kg <= 0 or price_per_kg <= 0:
            flash("Please fill in all required fields.", "error")
            return render_template('marketplace_post.html', farmer=farmer, edit=None)
        try:
            cur = get_db()
            cur.execute("""
                INSERT INTO marketplace_listings
                    (farmer_id, title, description, crop_name,
                     quantity_kg, price_per_kg, unit_label, district,
                     contact_phone, contact_whatsapp, latitude, longitude, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'available')
            """, (farmer[0], title, description, crop_name,
                  quantity_kg, price_per_kg, unit_label, district,
                  contact_phone, contact_whatsapp, latitude, longitude))
            mysql.connection.commit()
            listing_id = cur.lastrowid

            # Save uploaded images
            files = request.files.getlist('photos') or request.files.getlist('images')
            captions = request.form.getlist('captions')
            saved = _save_market_images(files, listing_id)
            # Handle deletion of existing images (edit mode)
            del_ids_raw = request.form.get('delete_images', '')
            if del_ids_raw:
                for did in del_ids_raw.split(','):
                    did = did.strip()
                    if did.isdigit():
                        cur.execute("SELECT filename FROM marketplace_images WHERE id=%s", (int(did),))
                        row = cur.fetchone()
                        if row:
                            fpath = os.path.join('static', 'uploads', 'market', row[0])
                            try: os.remove(fpath)
                            except: pass
                        cur.execute("DELETE FROM marketplace_images WHERE id=%s", (int(did),))
            for i, fname in enumerate(saved):
                cap = captions[i] if i < len(captions) else ''
                cur.execute("""
                    INSERT INTO marketplace_images (listing_id, filename, caption, sort_order)
                    VALUES (%s,%s,%s,%s)
                """, (listing_id, fname, cap, i))
            mysql.connection.commit()

            flash("Your listing is live! Other farmers can now see your produce.", "success")
            return redirect(url_for('marketplace_detail', listing_id=listing_id))
        except Exception as e:
            import traceback; traceback.print_exc()
            flash(f"Could not post listing: {e}", "error")

    return render_template('marketplace_post.html', farmer=farmer, edit=None)


@app.route('/marketplace/edit/<int:listing_id>', methods=['GET', 'POST'])
@role_required(ROLE_FARMER)
def marketplace_edit(listing_id):
    farmer = get_current_farmer()
    cur = get_db()
    # SELECT in the exact column order the template expects:
    # 0=id 1=title 2=description 3=crop_name 4=quantity 5=price 6=district
    # 7=phone 8=whatsapp 9=created 10=fullname 11=village 12=status
    # 13=unit_label 14=farmer_id 15=latitude 16=longitude
    cur.execute("""
        SELECT ml.id, ml.title, ml.description, ml.crop_name,
               ml.quantity_kg, ml.price_per_kg, ml.district,
               ml.contact_phone, ml.contact_whatsapp, ml.created_at,
               f.fullname, f.village,
               COALESCE(ml.status,'available'), COALESCE(ml.unit_label,'kg'),
               ml.farmer_id, ml.latitude, ml.longitude
        FROM marketplace_listings ml
        JOIN farmers f ON f.id = ml.farmer_id
        WHERE ml.id=%s AND ml.farmer_id=%s
    """, (listing_id, farmer[0]))
    listing = cur.fetchone()
    if not listing:
        flash("Listing not found or you don't own it.", "error")
        return redirect(url_for('marketplace'))

    if request.method == 'POST':
        title         = request.form.get('title', '').strip()
        description   = request.form.get('description', '').strip()
        crop_name     = request.form.get('crop_name', '')
        quantity_kg   = float(request.form.get('quantity_kg')  or 0)
        price_per_kg  = float(request.form.get('price_per_kg') or 0)
        unit_label    = request.form.get('unit_label', 'kg')
        status        = request.form.get('status', 'available')
        contact_phone    = request.form.get('contact_phone', '').strip()
        contact_whatsapp = request.form.get('contact_whatsapp', '').strip()
        latitude      = request.form.get('latitude', None) or None
        longitude     = request.form.get('longitude', None) or None
        try:
            cur.execute("""
                UPDATE marketplace_listings
                SET title=%s, description=%s, crop_name=%s,
                    quantity_kg=%s, price_per_kg=%s, unit_label=%s,
                    status=%s, contact_phone=%s, contact_whatsapp=%s,
                    latitude=%s, longitude=%s
                WHERE id=%s AND farmer_id=%s
            """, (title, description, crop_name, quantity_kg, price_per_kg,
                  unit_label, status, contact_phone, contact_whatsapp,
                  latitude, longitude, listing_id, farmer[0]))
            mysql.connection.commit()

            # Handle new images
            files = request.files.getlist('photos') or request.files.getlist('images')
            if files and files[0].filename:
                saved = _save_market_images(files, listing_id)
                cur.execute("SELECT MAX(sort_order) FROM marketplace_images WHERE listing_id=%s",
                            (listing_id,))
                max_ord = (cur.fetchone()[0] or -1) + 1
                captions = request.form.getlist('captions')
                for i, fname in enumerate(saved):
                    cap = captions[i] if i < len(captions) else ''
                    cur.execute("""
                        INSERT INTO marketplace_images (listing_id, filename, caption, sort_order)
                        VALUES (%s,%s,%s,%s)
                    """, (listing_id, fname, cap, max_ord + i))
                mysql.connection.commit()

            # Handle image deletions
            del_ids = request.form.getlist('delete_image')
            for img_id in del_ids:
                cur.execute("DELETE FROM marketplace_images WHERE id=%s AND listing_id=%s",
                            (img_id, listing_id))
            mysql.connection.commit()

            flash("Listing updated successfully!", "success")
            return redirect(url_for('marketplace_detail', listing_id=listing_id))
        except Exception as e:
            flash(f"Could not update listing: {e}", "error")

    cur.execute("""
        SELECT id, filename, caption FROM marketplace_images
        WHERE listing_id=%s ORDER BY sort_order
    """, (listing_id,))
    images = cur.fetchall()
    return render_template('marketplace_post.html',
                           farmer=farmer, edit=True, listing=listing, images=images)


@app.route('/marketplace/delete/<int:listing_id>', methods=['POST'])
@role_required(ROLE_FARMER)
def marketplace_delete(listing_id):
    farmer = get_current_farmer()
    try:
        cur = get_db()
        cur.execute("UPDATE marketplace_listings SET is_active=0 WHERE id=%s AND farmer_id=%s",
                    (listing_id, farmer[0]))
        mysql.connection.commit()
        flash("Listing removed.", "success")
    except Exception as e:
        flash(f"Could not remove listing: {e}", "error")
    return redirect(url_for('marketplace'))


@app.route('/marketplace/inquire/<int:listing_id>', methods=['POST'])
@role_required(ROLE_FARMER)
def marketplace_inquire(listing_id):
    """Buyer sends a message/inquiry to the seller."""
    farmer = get_current_farmer()
    message = request.form.get('message', '').strip()
    if not message:
        flash("Please enter a message.", "error")
        return redirect(url_for('marketplace_detail', listing_id=listing_id))
    try:
        cur = get_db()
        # Prevent sellers from inquiring on their own listing
        cur.execute("SELECT farmer_id FROM marketplace_listings WHERE id=%s", (listing_id,))
        row = cur.fetchone()
        if row and row[0] == farmer[0]:
            flash("You cannot send an inquiry on your own listing.", "error")
            return redirect(url_for('marketplace_detail', listing_id=listing_id))
        cur.execute("""
            INSERT INTO marketplace_inquiries (listing_id, farmer_id, message)
            VALUES (%s, %s, %s)
        """, (listing_id, farmer[0], message))
        mysql.connection.commit()
        inquiry_id = cur.lastrowid
        # Seed the conversation with the buyer's first message
        try:
            cur.execute("""
                INSERT INTO marketplace_chat_messages (inquiry_id, sender_id, msg_type, body)
                VALUES (%s, %s, 'text', %s)
            """, (inquiry_id, farmer[0], message))
            mysql.connection.commit()
        except Exception as _e:
            print(f"[Chat] seed message skipped: {_e}")
        # Notify the seller
        cur.execute("SELECT farmer_id, title FROM marketplace_listings WHERE id=%s", (listing_id,))
        listing_row = cur.fetchone()
        if listing_row:
            _create_notification(
                listing_row[0], 'marketplace_inquiry',
                f'🛒 New inquiry on "{listing_row[1]}"',
                f'{farmer[1]} is interested in buying your produce.',
                f'/marketplace/chat/{inquiry_id}'
            )
        flash("Message sent! You can continue the conversation in your messages.", "success")
    except Exception as e:
        flash(f"Could not send message: {e}", "error")
    return redirect(url_for('marketplace_detail', listing_id=listing_id))


@app.route('/marketplace/messages')
@role_required(ROLE_FARMER)
def marketplace_messages():
    """Seller inbox — all buyer inquiries across the farmer's listings."""
    farmer = get_current_farmer()
    cur = get_db()
    threads = []
    try:
        cur.execute("""
            SELECT mq.id, mq.listing_id, ml.title, mq.message,
                   buyer.fullname, buyer.phone, buyer.district,
                   mq.created_at, mq.is_read,
                   COALESCE(mq.reply, ''), mq.replied_at,
                   buyer.id
            FROM marketplace_inquiries mq
            JOIN marketplace_listings ml ON ml.id = mq.listing_id
            JOIN farmers buyer ON buyer.id = mq.farmer_id
            WHERE ml.farmer_id = %s
            ORDER BY mq.created_at DESC
        """, (farmer[0],))
        threads = cur.fetchall()
        # Mark all as read once the seller opens the inbox
        cur.execute("""
            UPDATE marketplace_inquiries mq
            JOIN marketplace_listings ml ON ml.id = mq.listing_id
            SET mq.is_read = 1
            WHERE ml.farmer_id = %s
        """, (farmer[0],))
        mysql.connection.commit()
    except Exception as e:
        print(f"[Messages] inbox error: {e}")
        threads = []
    return render_template('marketplace_messages.html',
                           farmer=farmer, threads=threads, mode='seller')


@app.route('/marketplace/my-inquiries')
@role_required(ROLE_FARMER)
def marketplace_my_inquiries():
    """Buyer view — messages the farmer has sent and seller replies."""
    farmer = get_current_farmer()
    cur = get_db()
    threads = []
    try:
        cur.execute("""
            SELECT mq.id, mq.listing_id, ml.title, mq.message,
                   seller.fullname, seller.phone, ml.district,
                   mq.created_at, mq.is_read,
                   COALESCE(mq.reply, ''), mq.replied_at,
                   seller.id
            FROM marketplace_inquiries mq
            JOIN marketplace_listings ml ON ml.id = mq.listing_id
            JOIN farmers seller ON seller.id = ml.farmer_id
            WHERE mq.farmer_id = %s
            ORDER BY mq.created_at DESC
        """, (farmer[0],))
        threads = cur.fetchall()
        # Mark seller replies as read by the buyer
        cur.execute("""
            UPDATE marketplace_inquiries
            SET buyer_read_reply = 1
            WHERE farmer_id = %s AND reply IS NOT NULL
        """, (farmer[0],))
        mysql.connection.commit()
    except Exception as e:
        print(f"[Messages] my-inquiries error: {e}")
        threads = []
    return render_template('marketplace_messages.html',
                           farmer=farmer, threads=threads, mode='buyer')


@app.route('/marketplace/reply/<int:inquiry_id>', methods=['POST'])
@role_required(ROLE_FARMER)
def marketplace_reply(inquiry_id):
    """Seller replies to a buyer inquiry, in-system."""
    farmer = get_current_farmer()
    reply  = request.form.get('reply', '').strip()
    if not reply:
        flash("Please type a reply.", "error")
        return redirect(url_for('marketplace_messages'))
    try:
        cur = get_db()
        # Verify the inquiry belongs to one of the seller's listings
        cur.execute("""
            SELECT mq.id FROM marketplace_inquiries mq
            JOIN marketplace_listings ml ON ml.id = mq.listing_id
            WHERE mq.id = %s AND ml.farmer_id = %s
        """, (inquiry_id, farmer[0]))
        if not cur.fetchone():
            flash("You can only reply to inquiries on your own listings.", "error")
            return redirect(url_for('marketplace_messages'))
        cur.execute("""
            UPDATE marketplace_inquiries
            SET reply = %s, replied_at = NOW(), buyer_read_reply = 0
            WHERE id = %s
        """, (reply, inquiry_id))
        mysql.connection.commit()
        # Notify the buyer
        cur.execute("""
            SELECT mq.farmer_id, ml.title
            FROM marketplace_inquiries mq
            JOIN marketplace_listings ml ON ml.id = mq.listing_id
            WHERE mq.id = %s
        """, (inquiry_id,))
        inq_row = cur.fetchone()
        if inq_row:
            _create_notification(
                inq_row[0], 'marketplace_reply',
                f'💬 Reply received on "{inq_row[1]}"',
                f'{farmer[1]} replied to your inquiry. Check your messages.',
                '/marketplace/my-inquiries'
            )
        flash("Reply sent! The buyer can see it in their inquiries.", "success")
    except Exception as e:
        flash(f"Could not send reply: {e}", "error")
    return redirect(url_for('marketplace_messages'))



# =============================================================================
# ── INTERACTIVE MARKETPLACE CHAT  (WhatsApp-style threads + voice notes)
# =============================================================================
 
def _chat_participants(inquiry_id):
    """Return (ok, buyer_id, seller_id, listing_title) for an inquiry thread."""
    cur = get_db()
    cur.execute("""
        SELECT mq.farmer_id, ml.farmer_id, ml.title, ml.id
        FROM marketplace_inquiries mq
        JOIN marketplace_listings ml ON ml.id = mq.listing_id
        WHERE mq.id = %s
    """, (inquiry_id,))
    row = cur.fetchone()
    if not row:
        return False, None, None, None
    return True, row[0], row[1], row[2]
 
 
def _seed_chat_from_legacy(inquiry_id):
    """If a thread has no chat rows yet, seed it from the old message/reply fields
    so older conversations still display in the new chat view."""
    cur = get_db()
    cur.execute("SELECT COUNT(*) FROM marketplace_chat_messages WHERE inquiry_id=%s", (inquiry_id,))
    if (cur.fetchone()[0] or 0) > 0:
        return
    cur.execute("""
        SELECT mq.farmer_id, ml.farmer_id, mq.message, mq.created_at,
               COALESCE(mq.reply,''), mq.replied_at
        FROM marketplace_inquiries mq
        JOIN marketplace_listings ml ON ml.id = mq.listing_id
        WHERE mq.id = %s
    """, (inquiry_id,))
    r = cur.fetchone()
    if not r:
        return
    buyer_id, seller_id, message, created_at, reply, replied_at = r
    try:
        if message:
            cur.execute("""INSERT INTO marketplace_chat_messages
                (inquiry_id, sender_id, msg_type, body, created_at)
                VALUES (%s,%s,'text',%s,%s)""",
                (inquiry_id, buyer_id, message, created_at))
        if reply:
            cur.execute("""INSERT INTO marketplace_chat_messages
                (inquiry_id, sender_id, msg_type, body, created_at)
                VALUES (%s,%s,'text',%s,%s)""",
                (inquiry_id, seller_id, reply, replied_at or created_at))
        mysql.connection.commit()
    except Exception as e:
        print(f"[Chat] legacy seed error: {e}")
 
 
@app.route('/marketplace/chat/<int:inquiry_id>')
@role_required(ROLE_FARMER)
def marketplace_chat(inquiry_id):
    """Open an interactive chat thread for a marketplace inquiry."""
    farmer = get_current_farmer()
    ok, buyer_id, seller_id, title = _chat_participants(inquiry_id)
    if not ok or farmer[0] not in (buyer_id, seller_id):
        flash("Conversation not found.", "error")
        return redirect(url_for('marketplace_messages'))
 
    _seed_chat_from_legacy(inquiry_id)
 
    # Identify the other participant
    other_id = seller_id if farmer[0] == buyer_id else buyer_id
    cur = get_db()
    cur.execute("SELECT fullname, profile_pic FROM farmers WHERE id=%s", (other_id,))
    o = cur.fetchone()
    other_name = o[0] if o else 'User'
    other_pic  = (o[1] if o and o[1] else 'default.png')
    my_role    = 'buyer' if farmer[0] == buyer_id else 'seller'
 
    # Mark messages from the other person as read
    try:
        cur.execute("""UPDATE marketplace_chat_messages SET is_read=1
                       WHERE inquiry_id=%s AND sender_id<>%s""", (inquiry_id, farmer[0]))
        mysql.connection.commit()
    except Exception:
        pass
 
    return render_template('marketplace_chat.html',
                           farmer=farmer, inquiry_id=inquiry_id,
                           listing_title=title, other_name=other_name,
                           other_pic=other_pic, my_role=my_role)
 
 
@app.route('/api/marketplace/chat/<int:inquiry_id>')
@role_required(ROLE_FARMER)
def api_marketplace_chat(inquiry_id):
    """JSON list of messages in a thread (for live polling)."""
    farmer = get_current_farmer()
    ok, buyer_id, seller_id, _ = _chat_participants(inquiry_id)
    if not ok or farmer[0] not in (buyer_id, seller_id):
        return jsonify({'error': 'not found'}), 404
    cur = get_db()
    cur.execute("""
        SELECT id, sender_id, msg_type, COALESCE(body,''),
               COALESCE(audio_file,''), COALESCE(duration_sec,0), created_at,
               reply_to_id
        FROM marketplace_chat_messages
        WHERE inquiry_id=%s ORDER BY id ASC
    """, (inquiry_id,))
    msgs = []
    for r in cur.fetchall():
        # created_at is a datetime object from MySQL
        dt = r[6]
        msgs.append({
            'id':         r[0],
            'mine':       r[1] == farmer[0],
            'type':       r[2],
            'body':       r[3],
            'audio':      ('/static/uploads/' + r[4]) if r[4] else '',
            'duration':   r[5],
            'time':       str(dt)[11:16] if dt else '',
            'date':       str(dt)[:10]   if dt else '',   # "YYYY-MM-DD" for day separators
            'replyToId':  r[7],                            # None or int
        })
    # mark incoming as read
    try:
        cur.execute("""UPDATE marketplace_chat_messages SET is_read=1
                       WHERE inquiry_id=%s AND sender_id<>%s""", (inquiry_id, farmer[0]))
        mysql.connection.commit()
    except Exception:
        pass
    return jsonify({'messages': msgs})
 
 
@app.route('/marketplace/chat/<int:inquiry_id>/send', methods=['POST'])
@role_required(ROLE_FARMER)
def marketplace_chat_send(inquiry_id):
    """Send a text or voice message into a thread."""
    farmer = get_current_farmer()
    ok, buyer_id, seller_id, title = _chat_participants(inquiry_id)
    if not ok or farmer[0] not in (buyer_id, seller_id):
        return jsonify({'ok': False, 'error': 'not found'}), 404
 
    body  = (request.form.get('body') or '').strip()
    audio = request.files.get('audio')
    reply_to_id  = request.form.get('reply_to_id') or None
    if reply_to_id:
        try: reply_to_id = int(reply_to_id)
        except (ValueError, TypeError): reply_to_id = None
    msg_type, audio_name, duration = 'text', None, 0
 
    try:
        cur = get_db()
        if audio and audio.filename and allowed_audio(audio.filename):
            msg_type = 'voice'
            ext = audio.filename.rsplit('.', 1)[1].lower()
            audio_name = f"voice_{inquiry_id}_{farmer[0]}_{int(datetime.now().timestamp())}.{ext}"
            audio.save(os.path.join(app.config['UPLOAD_FOLDER'], audio_name))
            try:
                duration = int(float(request.form.get('duration') or 0))
            except (TypeError, ValueError):
                duration = 0
        elif not body:
            return jsonify({'ok': False, 'error': 'empty'})
 
        cur.execute("""
            INSERT INTO marketplace_chat_messages
                (inquiry_id, sender_id, msg_type, body, audio_file, duration_sec, reply_to_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (inquiry_id, farmer[0], msg_type, body or None, audio_name, duration, reply_to_id))
        mysql.connection.commit()
 
        # Notify the other participant
        other_id = seller_id if farmer[0] == buyer_id else buyer_id
        preview  = '🎤 Voice note' if msg_type == 'voice' else (body[:60] if body else 'New message')
        _create_notification(
            other_id, 'marketplace_reply',
            f'💬 New message on "{title}"',
            f'{farmer[1]}: {preview}',
            f'/marketplace/chat/{inquiry_id}'
        )
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[Chat] send error: {e}")
        return jsonify({'ok': False, 'error': str(e)})
 
 
def _unread_message_count(farmer_id):
    """Count unread buyer inquiries for a seller (for the inbox badge)."""
    try:
        cur = get_db()
        cur.execute("""
            SELECT COUNT(*) FROM marketplace_inquiries mq
            JOIN marketplace_listings ml ON ml.id = mq.listing_id
            WHERE ml.farmer_id = %s AND mq.is_read = 0
        """, (farmer_id,))
        return cur.fetchone()[0] or 0
    except Exception:
        return 0
 
 
@app.route('/marketplace/my-listings')
@role_required(ROLE_FARMER)
def my_listings():
    farmer = get_current_farmer()
    cur = get_db()
    cur.execute("""
        SELECT ml.id, ml.title, ml.crop_name, ml.quantity_kg, ml.price_per_kg,
               COALESCE(ml.status,'available'), ml.created_at, ml.district,
               (SELECT mi.filename FROM marketplace_images mi
                WHERE mi.listing_id = ml.id ORDER BY mi.sort_order LIMIT 1) AS thumb,
               (SELECT COUNT(*) FROM marketplace_inquiries mq WHERE mq.listing_id=ml.id) AS inqs
        FROM marketplace_listings ml
        WHERE ml.farmer_id=%s AND ml.is_active=1
        ORDER BY ml.created_at DESC
    """, (farmer[0],))
    my = cur.fetchall()
    return render_template('my_listings.html', farmer=farmer, listings=my)
 

# =============================================================================
# ── SMART SEARCH  (Google Custom Search API integration)
# =============================================================================

@app.route('/search')
def smart_search():
    """Smart search using Google Custom Search API."""
    query    = request.args.get('q', '').strip()
    category = request.args.get('cat', 'all')  # weather, disease, market, general
    results  = []
    error    = None

    # Google Custom Search API key + CX (Search Engine ID)
    # Replace with your actual keys from https://programmablesearch.google.com/
    GOOGLE_API_KEY = 'YOUR_GOOGLE_API_KEY_HERE'
    GOOGLE_CX      = 'YOUR_SEARCH_ENGINE_ID_HERE'

    # Topic-specific query augmentations for agricultural relevance
    TOPIC_HINTS = {
        'weather':  'Zambia weather forecast climate rainfall',
        'disease':  'crop disease treatment pesticide Zambia agriculture',
        'market':   'Zambia agricultural commodity market price',
        'seeds':    'certified seed Zambia where to buy agro dealer',
        'all':      'Zambia farming agriculture',
    }

    if query:
        hint = TOPIC_HINTS.get(category, TOPIC_HINTS['all'])
        full_query = f"{query} {hint}"

        if GOOGLE_API_KEY != 'YOUR_GOOGLE_API_KEY_HERE':
            # Live search via Google Custom Search JSON API
            import urllib.request, json as json_module
            url = (f"https://www.googleapis.com/customsearch/v1"
                   f"?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}"
                   f"&q={urllib.parse.quote(full_query)}&num=10")
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json_module.loads(resp.read())
                    items = data.get('items', [])
                    results = [
                        {
                            'title':   item.get('title', ''),
                            'link':    item.get('link', '#'),
                            'snippet': item.get('snippet', ''),
                            'source':  item.get('displayLink', ''),
                        }
                        for item in items
                    ]
            except Exception as e:
                error = "Search temporarily unavailable. Check your API key."
                print(f"[Search] Error: {e}")
        else:
            # Demo mode — return curated static results
            results = _demo_search_results(query, category)

    farmer = get_current_farmer() if session.get('role') == ROLE_FARMER else None
    return render_template('smart_search.html',
                           query=query, category=category,
                           results=results, error=error,
                           farmer=farmer)


def _demo_search_results(query, category):
    """Returns static demo results when no API key is configured."""
    demo = [
        {'title': 'Zambia Meteorological Department — Weather Forecasts',
         'link': 'https://www.zmd.gov.zm',
         'snippet': 'Official weather forecasts, rainfall data, and climate advisories for all provinces of Zambia.',
         'source': 'zmd.gov.zm'},
        {'title': 'FAO Crop Disease Management in Sub-Saharan Africa',
         'link': 'https://www.fao.org/africa/en/',
         'snippet': 'Identification, prevention and treatment of major crop diseases affecting maize, cassava, groundnuts and other staple crops.',
         'source': 'fao.org'},
        {'title': 'Zambia Agriculture Research Institute (ZARI)',
         'link': 'https://www.zari.gov.zm',
         'snippet': 'Research-backed farming recommendations, improved seed varieties, and crop management guides for Zambian farmers.',
         'source': 'zari.gov.zm'},
        {'title': 'Agro Dealer Network Zambia — Find Input Suppliers',
         'link': 'https://www.znfu.org.zm',
         'snippet': 'Locate certified agro dealers near you for seeds, fertilisers, pesticides, and crop protection chemicals.',
         'source': 'znfu.org.zm'},
        {'title': 'ZNFU Market Prices — Weekly Commodity Prices',
         'link': 'https://www.znfu.org.zm/content/category/market-information',
         'snippet': 'Weekly maize, soya, groundnut and cassava prices from markets across Zambia provinces.',
         'source': 'znfu.org.zm'},
    ]
    return [r for r in demo if query.lower() in r['title'].lower()
            or query.lower() in r['snippet'].lower()] or demo[:3]


# =============================================================================
# ── FARM ASSISTANT CHATBOT  (knowledge-based, works without external APIs)
# =============================================================================

# Curated, Zambia-specific knowledge base. Each topic returns an answer plus
# optional helpful links. The bot also pulls live data (weather, prices) where
# relevant so answers are personalised to the farmer.

_CHATBOT_LINKS = {
    'zmd':  {'label': 'Zambia Meteorological Department', 'url': 'https://www.zmd.gov.zm'},
    'zari': {'label': 'Zambia Agriculture Research Institute (ZARI)', 'url': 'https://www.zari.gov.zm'},
    'fao':  {'label': 'FAO – Crop Disease Management', 'url': 'https://www.fao.org/africa/en/'},
    'znfu': {'label': 'ZNFU – Market Prices & Agro Dealers', 'url': 'https://www.znfu.org.zm'},
}

# Common crop disease guidance (kept brief and practical)
_CROP_DISEASES = {
    'maize': "Common maize problems in Zambia include Fall Armyworm, Maize Streak Virus, and Grey Leaf Spot. "
             "Scout fields weekly, plant early, use certified/treated seed, and rotate with legumes. "
             "For Fall Armyworm, apply recommended insecticides early in the morning into the funnel.",
    'cassava': "Cassava Mosaic Disease and Cassava Brown Streak are the main threats. "
               "Use clean, disease-free cuttings from certified sources, remove and destroy infected plants, "
               "and choose tolerant varieties recommended by ZARI.",
    'groundnuts': "Watch for Groundnut Rosette Virus and leaf spots. Plant early, use certified seed, "
                  "maintain good spacing for airflow, and rotate crops. Harvest and dry promptly to avoid aflatoxin.",
    'soyabeans': "Soybean rust and bacterial blight can reduce yields. Use rust-tolerant varieties, "
                 "inoculate seed with Rhizobium, and avoid overhead irrigation late in the day.",
    'potatoes': "Late blight is the major potato disease, especially in wet conditions. Use certified seed potatoes, "
                "ensure good drainage, and apply preventive fungicides on a weekly schedule during humid weather.",
    'sorghum': "Sorghum is hardy but watch for grain mould in wet conditions and stem borers. "
               "Harvest promptly once mature and use clean seed.",
    'millet': "Millet is among the most resilient cereals. Main issues are downy mildew and birds; "
              "use treated seed and consider bird-scaring near maturity.",
    'sunflower': "Sunflower can suffer from rust and downy mildew in wet conditions. Ensure wide spacing for airflow "
                 "and rotate fields between seasons.",
}


def _detect_crop(text):
    """Return a canonical crop name mentioned in the text, or None."""
    t = text.lower()
    crop_keys = {
        'maize': 'Maize', 'corn': 'Maize',
        'soya': 'Soyabeans', 'soybean': 'Soyabeans', 'soyabean': 'Soyabeans',
        'groundnut': 'Groundnuts', 'peanut': 'Groundnuts',
        'cassava': 'Cassava', 'sorghum': 'Sorghum', 'millet': 'Millet',
        'sunflower': 'Sunflower', 'potato': 'Potatoes',
    }
    for key, name in crop_keys.items():
        if key in t:
            return name
    return None


def _chatbot_response(message, farmer):
    """Generate a helpful response to a farmer's question.
    Returns {'reply': str, 'links': [ {label,url}, ... ]}."""
    msg = (message or '').strip()
    low = msg.lower()
    links = []

    if not msg:
        return {'reply': "Please type a question and I'll do my best to help.", 'links': []}

    # ── Greetings ─────────────────────────────────────────────────────────
    if any(w in low for w in ['hello', 'hi ', 'hie', 'hey', 'muli', 'mulibwanji', 'good morning',
                              'good afternoon', 'good evening']) and len(low) < 25:
        name = farmer[1].split()[0] if farmer else 'there'
        return {'reply': f"Hello {name}! 👋 I'm your ZamFarm assistant. Ask me about the weather, "
                         f"crop prices, planting advice, pests and diseases, or how to use the app.",
                'links': []}

    if any(w in low for w in ['thank', 'thanks', 'zikomo', 'natotela']):
        return {'reply': "You're welcome! Feel free to ask me anything else about your farming. 🌱",
                'links': []}

    crop = _detect_crop(low)

    # ── Weather ───────────────────────────────────────────────────────────
    if any(w in low for w in ['weather', 'rain', 'temperature', 'forecast', 'climate today', 'hot', 'cold', 'mvula']):
        district = farmer[7] if farmer else 'your district'
        try:
            temp, rain = get_weather(farmer[7]) if farmer else (25, 0)
            reply = (f"The current conditions for {district} are about {temp:.1f}°C with "
                     f"recent rainfall around {rain:.0f} mm. ")
            if rain < 10:
                reply += "It's quite dry — consider moisture-conserving practices like mulching, and prioritise drought-tolerant crops if dry weather continues."
            elif rain > 50:
                reply += "There's significant moisture — ensure good field drainage and watch for fungal diseases."
            else:
                reply += "Conditions are moderate — a good window for most field operations."
        except Exception:
            reply = (f"I couldn't fetch live weather right now, but you can always check the official "
                     f"forecast for {district} from the Zambia Meteorological Department.")
        links = [_CHATBOT_LINKS['zmd']]
        return {'reply': reply, 'links': links}

    # ── Market prices ─────────────────────────────────────────────────────
    if any(w in low for w in ['price', 'market', 'sell', 'selling', 'buy', 'cost of', 'how much', 'mtengo']):
        if crop:
            price = CROP_MARKET_PRICES.get(crop)
            if price:
                reply = (f"The current reference price for {crop} in the system is about "
                         f"ZMW {price:,.0f} per tonne. Prices vary by market and season, so check "
                         f"ZNFU's weekly prices before selling, and compare offers on the ZamFarm Marketplace.")
            else:
                reply = f"I don't have a stored price for {crop} right now. ZNFU publishes weekly commodity prices you can check."
        else:
            reply = ("Crop prices change weekly and by market. You can see the system's reference prices "
                     "in the Investment Simulator, list or browse produce on the ZamFarm Marketplace, "
                     "and check ZNFU for the latest weekly commodity prices.")
        links = [_CHATBOT_LINKS['znfu']]
        return {'reply': reply, 'links': links}

    # ── Pests & diseases ──────────────────────────────────────────────────
    if any(w in low for w in ['disease', 'pest', 'insect', 'worm', 'armyworm', 'fungus', 'rot',
                              'blight', 'mould', 'mold', 'rust', 'virus', 'sick', 'dying', 'spots', 'yellow']):
        if crop and crop.lower() in _CROP_DISEASES:
            reply = _CROP_DISEASES[crop.lower()]
        else:
            reply = ("Tell me which crop is affected (for example maize, cassava, or groundnuts) and I can give "
                     "specific guidance. In general: scout your fields weekly, use certified/treated seed, "
                     "remove and destroy badly infected plants, rotate crops between seasons, and consult your "
                     "extension officer or ZARI for the correct chemical and dose.")
        links = [_CHATBOT_LINKS['fao'], _CHATBOT_LINKS['zari']]
        return {'reply': reply, 'links': links}

    # ── What to plant / crop recommendation ───────────────────────────────
    if any(w in low for w in ['what should i plant', 'what to plant', 'which crop', 'recommend',
                              'best crop', 'suitable crop', 'what can i grow', 'grow']):
        reply = ("The best crop depends on your rainfall, temperature, and soil. Use the app's "
                 "Crop Recommendation tool — it compares all eight crops against your conditions and explains why. "
                 "As a rule of thumb: in drier or drought-prone seasons, hardy crops like sorghum, millet, and cassava "
                 "are safer; in good-rainfall seasons, maize, soyabeans, and groundnuts perform well.")
        links = [_CHATBOT_LINKS['zari']]
        return {'reply': reply, 'links': links}

    # ── Planting / timing ─────────────────────────────────────────────────
    if any(w in low for w in ['when to plant', 'planting', 'plant time', 'sow', 'season', 'when should i']):
        reply = ("In most of Zambia, planting is timed with the onset of reliable rains (typically late November to "
                 "December for the main season). Plant after the first well-established rains rather than the very first "
                 "shower, use certified seed, and check the ZMD seasonal forecast before committing. You can also run the "
                 "Investment Simulator to compare normal, drought, and above-normal rainfall scenarios.")
        links = [_CHATBOT_LINKS['zmd']]
        return {'reply': reply, 'links': links}

    # ── Fertiliser ────────────────────────────────────────────────────────
    if any(w in low for w in ['fertiliz', 'fertilis', 'manure', 'compost', 'nutrient', 'lime', 'soil fertility']):
        reply = ("Apply fertiliser based on a soil test where possible. For maize, a common approach is a basal "
                 "compound (e.g. D-compound) at planting followed by a top-dressing (e.g. Urea) about 3–4 weeks later. "
                 "Legumes like soyabeans and groundnuts fix their own nitrogen, so they need less — inoculate the seed instead. "
                 "Organic manure and crop rotation improve long-term soil fertility. Confirm exact rates with your extension officer.")
        links = [_CHATBOT_LINKS['zari']]
        return {'reply': reply, 'links': links}

    # ── Drought / climate-smart ───────────────────────────────────────────
    if any(w in low for w in ['drought', 'dry spell', 'climate change', 'climate smart', 'conservation', 'mulch', 'erosion']):
        reply = ("To cope with drought and a changing climate: choose drought-tolerant varieties (sorghum, millet, cassava), "
                 "practise conservation farming (minimum tillage, mulching, and crop residue retention), harvest rainwater, "
                 "and stagger planting to spread risk. The app's risk indicators and simulator help you plan for drought scenarios.")
        links = [_CHATBOT_LINKS['zari'], _CHATBOT_LINKS['fao']]
        return {'reply': reply, 'links': links}

    # ── App help ──────────────────────────────────────────────────────────
    if any(w in low for w in ['how do i', 'how to use', 'points', 'level', 'badge', 'simulator',
                              'predict', 'app', 'marketplace', 'login', 'profile', 'password']):
        reply = ("Here's how the app helps you: use **Predict Yield** to forecast a crop's output and profit; "
                 "**Crop Recommendation** to find the best crop for your conditions; the **Investment Simulator** to test "
                 "drought/normal/above-normal scenarios (and earn 50 points each time); and the **Marketplace** to buy and "
                 "sell produce. You earn 10 points for logging in daily and advance through five levels as you engage. "
                 "You can edit your profile by tapping your photo, then 'Edit Profile'.")
        return {'reply': reply, 'links': []}

    # ── Fallback ──────────────────────────────────────────────────────────
    reply = ("I'm not certain about that one, but I can help with weather, crop prices, planting advice, "
             "pests and diseases, fertiliser, drought, and using the app. Try rephrasing, or check these trusted "
             "Zambian resources below.")
    links = [_CHATBOT_LINKS['zari'], _CHATBOT_LINKS['zmd'], _CHATBOT_LINKS['znfu']]
    return {'reply': reply, 'links': links}


# =============================================================================
# ── LLM-POWERED CHATBOT  (Anthropic Claude API, with rule-based fallback)
# =============================================================================
# To enable smart AI answers, set your Anthropic API key. The easiest way is an
# environment variable:  set ANTHROPIC_API_KEY=sk-ant-...   (Windows)
#                        export ANTHROPIC_API_KEY=sk-ant-... (Linux/Mac)
# Or paste it directly below (less secure). When no key is set, the assistant
# automatically falls back to the built-in rule-based answers, so the app always
# works either way.
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '') or 'YOUR_ANTHROPIC_API_KEY_HERE'
ANTHROPIC_MODEL   = 'claude-3-5-sonnet-20241022'   # change to any model your key supports
ANTHROPIC_URL     = 'https://api.anthropic.com/v1/messages'


def _chat_system_prompt(farmer):
    """Build a context-rich system prompt so the AI answers are tailored
    to this farmer and to Zambian conditions."""
    district = farmer[7] if farmer else 'Zambia'
    temp = rain = None
    if farmer:
        try:
            temp, rain = get_weather(farmer[7])
        except Exception:
            temp = rain = None
    weather_line = (f"{temp:.1f}\u00b0C, recent rainfall about {rain:.0f} mm"
                    if temp is not None else "not available right now")
    try:
        prices = ", ".join(f"{c}: ZMW {p:,.0f}/tonne" for c, p in CROP_MARKET_PRICES.items())
    except Exception:
        prices = "not available"

    return (
        "You are the ZamFarm Farm Assistant, a knowledgeable and friendly agricultural advisor for "
        "smallholder farmers in Zambia. You give practical, accurate, and concise advice tailored to "
        "Zambian conditions.\n\n"
        "Context about the farmer you are helping:\n"
        f"- District: {district}\n"
        f"- Current weather: {weather_line}\n"
        "- Crops supported in the app: Maize, Soyabeans, Groundnuts, Cassava, Sorghum, Millet, "
        "Sunflower, Potatoes\n"
        f"- Reference market prices (per tonne): {prices}\n\n"
        "How to answer:\n"
        "- Answer the farmer's actual question directly and specifically.\n"
        "- When comparing crops or giving agronomic advice, give clear, reasoned, specific guidance.\n"
        "- Keep answers concise (2-4 short paragraphs), in simple language suited to low-literacy users.\n"
        "- All money is in Zambian Kwacha (ZMW). If asked about prices, note these are per-tonne "
        "reference figures and that real market prices vary by location and season.\n"
        "- Do not invent precise statistics you are unsure of; be honest about uncertainty.\n"
        "- When helpful, mention the app's tools: Predict Yield, Crop Recommendation, Investment "
        "Simulator, and the Marketplace.\n"
        "- If a question is unrelated to farming, weather, or the app, gently steer back to those topics."
    )


def _llm_chat(message, farmer, history):
    """Call the Anthropic Claude API. Returns the reply text, or raises on failure."""
    msgs = []
    for h in (history or [])[-10:]:        # keep the last 10 turns for context
        role    = h.get('role')
        content = (h.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            msgs.append({'role': role, 'content': content})
    msgs.append({'role': 'user', 'content': message})

    resp = requests.post(
        ANTHROPIC_URL,
        headers={
            'x-api-key':         ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type':      'application/json',
        },
        json={
            'model':      ANTHROPIC_MODEL,
            'max_tokens': 700,
            'system':     _chat_system_prompt(farmer),
            'messages':   msgs,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic API {resp.status_code}: {resp.text[:200]}")
    data  = resp.json()
    parts = [b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text']
    text  = "".join(parts).strip()
    if not text:
        raise RuntimeError("Empty response from API")
    return text


def _chatbot_resources(message, farmer):
    """Build a richer set of suggested sources for any question:
    a tailored YouTube video search, a relevant authoritative site, and a web search."""
    from urllib.parse import quote_plus
    low  = (message or '').lower()
    crop = _detect_crop(low)
    res  = []

    # Tailored YouTube search (always useful for how-to / visual learners)
    yt_terms = (message or '').strip()
    if crop and crop.lower() not in low:
        yt_terms += f" {crop}"
    yt_q = quote_plus((yt_terms + " Zambia farming").strip())
    res.append({'label': 'Watch related videos on YouTube',
                'url':   f'https://www.youtube.com/results?search_query={yt_q}',
                'type':  'video'})

    # One topic-relevant authoritative source
    if any(w in low for w in ['disease', 'pest', 'insect', 'worm', 'blight', 'rust',
                              'fungus', 'virus', 'mould', 'mold', 'rot', 'spots']):
        res.append({**_CHATBOT_LINKS['fao'], 'type': 'web'})
    elif any(w in low for w in ['price', 'market', 'sell', 'selling', 'buy', 'cost']):
        res.append({**_CHATBOT_LINKS['znfu'], 'type': 'web'})
    elif any(w in low for w in ['weather', 'rain', 'forecast', 'temperature', 'climate', 'drought']):
        res.append({**_CHATBOT_LINKS['zmd'], 'type': 'web'})
    else:
        res.append({**_CHATBOT_LINKS['zari'], 'type': 'web'})

    # General web search as a catch-all
    res.append({'label': 'Search the web for more',
                'url':   f'https://www.google.com/search?q={yt_q}',
                'type':  'web'})
    return res


def _chatbot_answer(message, farmer, history):
    """Answer a question: try the AI model first (if a key is configured),
    otherwise fall back to the rule-based engine. Always append rich resources."""
    reply  = None
    engine = 'rules'

    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != 'YOUR_ANTHROPIC_API_KEY_HERE':
        try:
            reply  = _llm_chat(message, farmer, history)
            engine = 'ai'
        except Exception as e:
            print(f"[Chatbot] LLM error, falling back to rules: {e}")
            reply = None

    if reply is None:
        base  = _chatbot_response(message, farmer)
        reply = base['reply']
        base_links = base.get('links', [])
    else:
        base_links = []

    # Merge topic links + tailored resources, de-duplicating by URL
    merged, seen = [], set()
    for l in (base_links + _chatbot_resources(message, farmer)):
        url = l.get('url')
        if url and url not in seen:
            seen.add(url)
            # ensure a 'type' key for the UI
            if 'type' not in l:
                l = {**l, 'type': 'web'}
            merged.append(l)

    return {'reply': reply, 'links': merged, 'engine': engine}


@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """Farm-assistant chatbot endpoint (AI-powered with rule-based fallback)."""
    if 'user_id' not in session:
        return jsonify({'reply': 'Please log in to use the assistant.', 'links': []}), 401
    try:
        data    = request.get_json(silent=True) or {}
        message = (data.get('message') or '').strip()
        history = data.get('history') or []
        farmer  = get_current_farmer() if session.get('role') == ROLE_FARMER else None
        if not message:
            return jsonify({'reply': "Please type a question and I'll help.", 'links': []})
        return jsonify(_chatbot_answer(message, farmer, history))
    except Exception as e:
        print(f"[Chatbot] Error: {e}")
        return jsonify({'reply': "Sorry, I ran into a problem answering that. Please try again.",
                        'links': []})

# =============================================================================
# ── MARKET PRICES — live fetch + admin manual override
# =============================================================================

import urllib.request as _urllib_req
import threading as _threading
import time as _time_mod

# ── Commodity alias map ───────────────────────────────────────────────────────
_PRICE_ALIAS = {
    'white maize':'Maize','maize':'Maize',
    'soyabeans':'Soyabeans','soya beans':'Soyabeans','soya':'Soyabeans',
    'groundnuts':'Groundnuts','ground nuts':'Groundnuts',
    'cassava':'Cassava','sorghum':'Sorghum',
    'millet':'Millet','pearl millet':'Millet',
    'sunflower':'Sunflower','sunflower seed':'Sunflower',
    'irish potatoes':'Potatoes','potatoes':'Potatoes',
}

PRICE_SOURCES = {
    'znfu': 'https://www.znfu.org.zm/content/category/market-information',
}


def _fetch_live_prices():
    """Scrape commodity prices from ZNFU market information page.
    Returns dict {crop_name: price_zmw_per_tonne} or empty on failure.
    ZNFU/FRA publish HTML price tables — no public JSON API exists.
    Falls back gracefully if scraping fails or layout changes."""
    prices = {}
    import re as _re
    try:
        req = _urllib_req.Request(
            PRICE_SOURCES['znfu'],
            headers={'User-Agent': 'Mozilla/5.0 ZamFarmBot/1.0 (+zamfarm)'}
        )
        with _urllib_req.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        # Parse HTML table rows — ZNFU format: Crop | Unit | Low | High | Average
        table_rows = _re.findall(r'<tr[^>]*>(.*?)</tr>', html,
                                 _re.DOTALL | _re.IGNORECASE)
        for row in table_rows:
            cells = _re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row,
                                _re.DOTALL | _re.IGNORECASE)
            cells = [_re.sub(r'<[^>]+>', '', c).strip().lower() for c in cells]
            if len(cells) < 3:
                continue
            mapped = _PRICE_ALIAS.get(cells[0])
            if not mapped:
                continue
            for cell in cells[1:]:
                m = _re.search(r'[\d]+\.?\d*', cell.replace(',', ''))
                if m:
                    try:
                        val = float(m.group())
                        if val < 200:    val *= 20   # per 50kg bag → per tonne
                        if 100 < val < 50000:
                            prices[mapped] = round(val, 2)
                            break
                    except (ValueError, AttributeError):
                        continue
        print(f"[PriceFetch] Scraped {len(prices)} prices: {list(prices.keys())}")
    except Exception as e:
        print(f"[PriceFetch] ZNFU fetch failed ({e}) — using DB/hardcoded prices")
    return prices


def _save_prices_to_db(prices, source='auto_fetch'):
    """Write fetched prices to crops table and log to market_price_history."""
    if not prices:
        return
    try:
        cur = get_db()
        for crop, price in prices.items():
            cur.execute("""
                UPDATE crops
                SET market_price=COALESCE(%s, market_price),
                    price_source=%s, price_updated_at=NOW()
                WHERE crop_name=%s
            """, (price, source, crop))
            cur.execute("""
                INSERT INTO market_price_history
                    (crop_name, price_zmw_per_tonne, source, recorded_at)
                VALUES (%s, %s, %s, NOW())
            """, (crop, price, source))
        mysql.connection.commit()
        print(f"[PriceFetch] Saved {len(prices)} prices (source={source})")
    except Exception as e:
        print(f"[PriceFetch] DB save error: {e}")
        try: mysql.connection.rollback()
        except Exception: pass


def _price_fetch_worker():
    """Background daemon thread: fetch live prices every 24 hours."""
    _time_mod.sleep(45)
    while True:
        try:
            with app.app_context():
                prices = _fetch_live_prices()
                if prices:
                    _save_prices_to_db(prices, source='znfu_auto')
        except Exception as e:
            print(f"[PriceFetch] Worker error: {e}")
        _time_mod.sleep(86400)


# Start the background worker
_pt = _threading.Thread(target=_price_fetch_worker, daemon=True, name='PriceFetch')
_pt.start()


@app.route('/admin/market_prices', methods=['GET', 'POST'])
@role_required(ROLE_ADMIN)
def admin_market_prices():
    """Admin page: view and manually edit market prices + trigger live fetch."""
    cur = get_db()

    if request.method == 'POST':
        action = request.form.get('action', 'update')

        if action == 'fetch_now':
            prices = _fetch_live_prices()
            if prices:
                _save_prices_to_db(prices, source='admin_fetch')
                flash(f"✅ Live fetch succeeded — updated prices for: "
                      f"{', '.join(prices.keys())}", "success")
            else:
                flash("⚠️ Live fetch returned no data. ZNFU page layout may have "
                      "changed. Edit prices manually below.", "warning")
            return redirect(url_for('admin_market_prices'))

        # Manual price update
        try:
            crop_name    = request.form.get('crop_name', '').strip()
            market_price = float(request.form.get('market_price') or 0)
            input_cost   = float(request.form.get('input_cost_ha') or 0)
            notes        = request.form.get('notes', '').strip()

            if not crop_name or market_price <= 0:
                flash("Crop name and price are required.", "error")
                return redirect(url_for('admin_market_prices'))

            cur.execute("""
                UPDATE crops
                SET market_price   = %s,
                    input_cost_ha  = CASE WHEN %s > 0 THEN %s ELSE input_cost_ha END,
                    price_source   = 'admin_manual',
                    price_updated_at = NOW()
                WHERE crop_name = %s
            """, (market_price, input_cost, input_cost, crop_name))

            cur.execute("""
                INSERT INTO market_price_history
                    (crop_name, price_zmw_per_tonne, source, notes, recorded_at)
                VALUES (%s, %s, 'admin_manual', %s, NOW())
            """, (crop_name, market_price, notes))
            mysql.connection.commit()
            flash(f"✅ {crop_name} price updated → ZMW {market_price:,.2f}/T", "success")
        except Exception as e:
            flash(f"Could not update: {e}", "error")
        return redirect(url_for('admin_market_prices'))

    # GET — use IFNULL instead of COALESCE for string columns to avoid collation mismatch
    cur.execute("""
        SELECT crop_name, IFNULL(emoji, CONVERT('🌾' USING utf8mb4)), market_price,
               IFNULL(input_cost_ha, 0),
               IFNULL(CONVERT(price_source USING utf8mb4),
                      CONVERT('hardcoded' USING utf8mb4)),
               price_updated_at
        FROM crops ORDER BY crop_name
    """)
    crops = cur.fetchall()

    history = []
    try:
        cur.execute("""
            SELECT crop_name, price_zmw_per_tonne, source,
                   IFNULL(CONVERT(notes USING utf8mb4),
                           CONVERT('' USING utf8mb4)),
                   recorded_at
            FROM market_price_history
            ORDER BY recorded_at DESC LIMIT 40
        """)
        history = cur.fetchall()
    except Exception:
        history = []

    try:
        cur.execute("""SELECT MAX(recorded_at) FROM market_price_history
                       WHERE source LIKE '%fetch%'""")
        last_fetch = cur.fetchone()[0]
    except Exception:
        last_fetch = None

    return render_template('admin_market_prices.html',
                           crops=crops, history=history,
                           last_fetch=last_fetch)


@app.route('/api/market_prices')
def api_market_prices():
    """Public JSON endpoint — current crop prices for dashboard widgets."""
    try:
        cur = get_db()
        cur.execute("""
            SELECT crop_name, COALESCE(market_price,0),
                   IFNULL(CONVERT(price_source USING utf8mb4),
                           CONVERT('default' USING utf8mb4)),
                   price_updated_at
            FROM crops ORDER BY crop_name
        """)
        return app.response_class(
            response=json.dumps({
                'status': 'ok',
                'prices': {r[0]: {'price': float(r[1]), 'source': r[2],
                                  'updated': str(r[3]) if r[3] else None}
                           for r in cur.fetchall()}
            }),
            mimetype='application/json'
        )
    except Exception as e:
        return app.response_class(
            response=json.dumps({'status': 'error', 'message': str(e)}),
            status=500, mimetype='application/json'
        )


# =============================================================================
# RUN
# =============================================================================
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
# =============================================================================
# climate_routes.py
# ZamFarm Climate — Data Ingestion & Predictive Analysis Flask Routes
# FR2: Climate Data Ingestion & Management Module
#
# HOW TO USE:
#   In your app.py, add at the bottom (before app.run):
#       from climate_routes import register_climate_routes
#       register_climate_routes(app, mysql)
# =============================================================================

import os
import csv
import io
import requests
import numpy as np
from datetime import datetime, timedelta, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.utils import secure_filename

# Zambia's 72 districts with approximate lat/lon for Open-Meteo API
ZAMBIA_DISTRICTS = {
    "Lusaka":       (-15.4167,  28.2833),
    "Kitwe":        (-12.8024,  28.2132),
    "Ndola":        (-12.9587,  28.6366),
    "Livingstone":  (-17.8419,  25.8542),
    "Kabwe":        (-14.4469,  28.4464),
    "Chipata":      (-13.6333,  32.6500),
    "Kasama":       ( -10.2122, 31.1806),
    "Solwezi":      (-12.1736,  26.3972),
    "Mongu":        (-15.2539,  23.1281),
    "Choma":        (-16.8000,  26.9833),
    "Mazabuka":     (-15.8553,  27.7522),
    "Kafue":        (-15.7667,  28.1833),
    "Chingola":     (-12.5247,  27.8559),
    "Mufulira":     (-12.5500,  28.2333),
    "Luanshya":     (-13.1397,  28.4064),
    "Kalulushi":    (-12.8333,  28.1000),
    "Monze":        (-16.2728,  27.4761),
    "Nakonde":      ( -9.3667,  32.7500),
    "Mpika":        (-11.8369,  31.4533),
    "Mansa":        (-11.2000,  28.8833),
    "Samfya":       (-11.3667,  29.5500),
    "Serenje":      (-13.2333,  30.2333),
    "Petauke":      (-14.2500,  31.3333),
    "Katete":       (-13.9833,  32.0500),
    "Lundazi":      (-12.2833,  33.1833),
    "Mwinilunga":   (-11.7381,  24.4319),
    "Kaoma":        (-14.7833,  24.8000),
    "Senanga":      (-16.1167,  23.2667),
    "Sesheke":      (-17.4833,  24.3000),
    "Chavuma":      (-13.0806,  22.6972),
    "Kaputa":       ( -8.4667,  29.6667),
    "Mbala":        ( -8.8369,  31.3619),
    "Chinsali":     (-10.5500,  32.0667),
    "Isoka":        (-10.1667,  32.6167),
    "Luwingu":      (-10.2500,  29.9167),
    "Mporokoso":    ( -9.3667,  30.1167),
    "Nchelenge":    ( -9.3500,  28.7333),
    "Kawambwa":     ( -9.7875,  29.0844),
    "Chililabombwe":(-12.3667,  27.8333),
    "Chambeshi":    (-11.0000,  31.1333),
    "Chilubi":      (-11.5000,  30.3333),
    "Chibombo":     (-14.6667,  28.3500),
    "Mkushi":       (-13.6167,  29.3833),
    "Kapiri Mposhi":(-13.9711,  28.6692),
    "Mumbwa":       (-14.9833,  27.0667),
    "Ngoma":        (-15.9667,  25.9333),
    "Namwala":      (-15.7500,  26.4333),
    "Gwembe":       (-16.5000,  27.6667),
    "Sinazongwe":   (-17.2600,  27.4567),
    "Siavonga":     (-16.5333,  28.7167),
}


def register_climate_routes(app, mysql):
    """
    Register all climate-related Flask routes onto the app.
    Call this from app.py after creating the Flask app and mysql objects.
    """

    # =========================================================================
    # HELPER: Get current farmer from session
    # =========================================================================
    def get_farmer():
        if 'user_id' not in session:
            return None
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM farmers WHERE id = %s", (session['user_id'],))
        return cur.fetchone()

    # =========================================================================
    # HELPER: Get climate stats summary from DB
    # =========================================================================
    def get_climate_stats():
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT COUNT(*) FROM climate_data")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT district) FROM climate_data")
            districts = cur.fetchone()[0]
            cur.execute("SELECT DATEDIFF(MAX(date), MIN(date)) FROM climate_data")
            date_range = cur.fetchone()[0] or 0
            cur.execute("SELECT MAX(created_at) FROM climate_data")
            last = cur.fetchone()[0]
            last_str = last.strftime('%d %b %Y') if last else 'Never'
            cur.execute("SELECT COUNT(DISTINCT source) FROM climate_data")
            sources = cur.fetchone()[0]
            return {
                'total_records': total,
                'districts':     districts,
                'date_range':    date_range,
                'last_update':   last_str,
                'sources':       sources,
            }
        except Exception:
            return {'total_records': 0, 'districts': 0, 'date_range': 0, 'last_update': 'Never', 'sources': 0}

    # =========================================================================
    # HELPER: Fetch from Open-Meteo (free, no key, ERA5 historical)
    # ERA5 provides climate reanalysis data for Zambia from 1940 onward.
    # =========================================================================
    def fetch_open_meteo(district, start_date, end_date, variables):
        if district not in ZAMBIA_DISTRICTS:
            return None, f"District '{district}' not in coordinates list."

        lat, lon = ZAMBIA_DISTRICTS[district]
        vars_str = ','.join(variables) if variables else \
            'temperature_2m_max,temperature_2m_min,precipitation_sum'

        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&daily={vars_str}&timezone=Africa%2FLusaka"
        )

        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json(), None
            return None, f"Open-Meteo returned status {r.status_code}"
        except Exception as e:
            return None, str(e)

    # =========================================================================
    # HELPER: Fetch from OpenWeatherMap (current + 5-day forecast)
    # =========================================================================
    def fetch_openweathermap(district):
        API_KEY = "9a15cce295222fccf0e5cb17f852cfbd"
        url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={district},ZM&appid={API_KEY}&units=metric"
        )
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                d = r.json()
                return {
                    'temp_max':    d['main']['temp_max'],
                    'temp_min':    d['main']['temp_min'],
                    'temp_avg':    d['main']['temp'],
                    'rainfall_mm': d.get('rain', {}).get('1h', 0),
                    'humidity_pct':d['main']['humidity'],
                    'wind_speed':  d['wind']['speed'],
                }, None
            return None, f"OWM status {r.status_code}"
        except Exception as e:
            return None, str(e)

    # =========================================================================
    # HELPER: Save climate record to DB
    # =========================================================================
    def save_climate_record(district, date_val, temp_max, temp_min,
                             rainfall_mm, humidity_pct, source, wind_speed=None):
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO climate_data
                    (district, date, temp_max, temp_min,
                     rainfall_mm, humidity_pct, wind_speed, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    temp_max=VALUES(temp_max), temp_min=VALUES(temp_min),
                    rainfall_mm=VALUES(rainfall_mm), humidity_pct=VALUES(humidity_pct),
                    wind_speed=VALUES(wind_speed), source=VALUES(source)
            """, (district, date_val, temp_max, temp_min,
                  rainfall_mm, humidity_pct, wind_speed, source))
            mysql.connection.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_climate_record: {e}")
            return False

    # =========================================================================
    # ROUTE: /climate_data — Data Ingestion Dashboard
    # =========================================================================
    @app.route('/climate_data')
    def climate_data():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        farmer = get_farmer()
        stats  = get_climate_stats()

        # Fetch stored records for the table
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT district, date, temp_max, temp_min,
                       rainfall_mm, humidity_pct, source
                FROM climate_data
                ORDER BY date DESC LIMIT 500
            """)
            rows = cur.fetchall()
            # Convert tuples to dicts for easy Jinja access
            climate_records = [
                {
                    'district':    r[0], 'date':        str(r[1]),
                    'temp_max':    r[2], 'temp_min':    r[3],
                    'rainfall_mm': r[4], 'humidity_pct':r[5],
                    'source':      r[6],
                }
                for r in rows
            ]
        except Exception:
            climate_records = []

        return render_template(
            'climate_data.html',
            farmer=farmer,
            stats=stats,
            climate_records=climate_records,
            zambia_districts=sorted(ZAMBIA_DISTRICTS.keys()),
            enumerate=enumerate,
        )

    # =========================================================================
    # ROUTE: /climate_ingest_api — Ingest from OWM or Open-Meteo via POST
    # =========================================================================
    @app.route('/climate_ingest_api', methods=['POST'])
    def climate_ingest_api():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        source     = request.form.get('source', 'openweathermap')
        district   = request.form.get('district', '')
        start_date = request.form.get('start_date', '')
        end_date   = request.form.get('end_date', '')
        variables  = request.form.getlist('variables')
        records_saved = 0

        if source == 'openweathermap':
            # OWM: fetch current conditions and store as today's record
            data, err = fetch_openweathermap(district)
            if err:
                flash(f"OpenWeatherMap error: {err}", 'error')
            else:
                ok = save_climate_record(
                    district, date.today(),
                    data['temp_max'], data['temp_min'],
                    data['rainfall_mm'], data['humidity_pct'],
                    'openweathermap', data.get('wind_speed')
                )
                if ok:
                    records_saved = 1
                    flash(f"✅ Saved 1 OWM record for {district}.", 'success')
                else:
                    flash("❌ Database error saving record.", 'error')

        elif source == 'open_meteo':
            # Open-Meteo: fetch historical range (ERA5 reanalysis)
            if not start_date or not end_date:
                flash("Please provide start and end dates for Open-Meteo.", 'error')
                return jsonify({'status': 'error', 'message': 'Please provide start and end dates.'}), 400

            default_vars = [
                'temperature_2m_max', 'temperature_2m_min',
                'precipitation_sum',  'relative_humidity_2m_max'
            ]
            data, err = fetch_open_meteo(district, start_date, end_date,
                                          variables or default_vars)
            if err:
                flash(f"Open-Meteo error: {err}", 'error')
            else:
                daily = data.get('daily', {})
                dates = daily.get('time', [])
                t_max = daily.get('temperature_2m_max', [])
                t_min = daily.get('temperature_2m_min', [])
                rain  = daily.get('precipitation_sum', [])
                humid = daily.get('relative_humidity_2m_max', [])

                for i, d_str in enumerate(dates):
                    ok = save_climate_record(
                        district, d_str,
                        t_max[i] if i < len(t_max) else None,
                        t_min[i] if i < len(t_min) else None,
                        rain[i]  if i < len(rain)  else 0,
                        humid[i] if i < len(humid) else None,
                        'open_meteo'
                    )
                    if ok:
                        records_saved += 1

                flash(
                    f"✅ Ingested {records_saved} Open-Meteo records for "
                    f"{district} ({start_date} → {end_date}).",
                    'success'
                )

        # Always return JSON — the JS fetch() handler reloads the page on success
        return jsonify({'status': 'ok', 'records_saved': records_saved})

    # =========================================================================
    # ROUTE: /climate_upload_csv — Upload Zambia Met / HDX CSV
    # Expected columns:
    #   district, date, temperature_max, temperature_min,
    #   rainfall_mm, humidity_pct, source
    # =========================================================================
    @app.route('/climate_upload_csv', methods=['POST'])
    def climate_upload_csv():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        file         = request.files.get('climate_csv')
        data_source  = request.form.get('data_source', 'csv_upload')
        dataset_label = request.form.get('dataset_label', '')
        records_saved = 0
        errors        = 0

        if not file or file.filename == '':
            flash("⚠️ No file selected.", 'error')
            return jsonify({'status': 'error', 'message': 'No file selected.'}), 400

        # Read CSV content into memory (no disk write needed)
        try:
            stream = io.StringIO(file.stream.read().decode('utf-8-sig'), newline=None)
            reader = csv.DictReader(stream)

            # Normalise header names (strip spaces, lowercase)
            for row in reader:
                row = {k.strip().lower().replace(' ', '_'): v.strip() for k, v in row.items()}
                try:
                    ok = save_climate_record(
                        district     = row.get('district', ''),
                        date_val     = row.get('date', ''),
                        temp_max     = float(row.get('temperature_max', 0) or 0),
                        temp_min     = float(row.get('temperature_min', 0) or 0),
                        rainfall_mm  = float(row.get('rainfall_mm', 0) or 0),
                        humidity_pct = float(row.get('humidity_pct', 0) or 0),
                        source       = data_source,
                    )
                    if ok:
                        records_saved += 1
                    else:
                        errors += 1
                except (ValueError, KeyError):
                    errors += 1
                    continue

            msg = f"✅ CSV ingested: {records_saved} records saved, {errors} skipped."
            return jsonify({'status': 'ok', 'records_saved': records_saved, 'message': msg})

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

    # =========================================================================
    # ROUTE: /climate_manual_entry — Save a single manual climate record
    # =========================================================================
    @app.route('/climate_manual_entry', methods=['POST'])
    def climate_manual_entry():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        ok = save_climate_record(
            district     = request.form.get('district', ''),
            date_val     = request.form.get('date', ''),
            temp_max     = float(request.form.get('temp_max', 0) or 0),
            temp_min     = float(request.form.get('temp_min', 0) or 0),
            rainfall_mm  = float(request.form.get('rainfall_mm', 0) or 0),
            humidity_pct = float(request.form.get('humidity_pct', 0) or 0),
            source       = 'manual',
        )
        if ok:
            return jsonify({'status': 'ok', 'message': 'Manual record saved.'})
        return jsonify({'status': 'error', 'message': 'Error saving record.'}), 400

    # =========================================================================
    # ROUTE: /climate_template_download — Download blank CSV template
    # =========================================================================
    @app.route('/climate_template_download')
    def climate_template_download():
        template = (
            "district,date,temperature_max,temperature_min,"
            "rainfall_mm,humidity_pct,source\n"
            "Lusaka,2024-01-01,32.5,18.2,12.4,74,zambia_met\n"
            "Chipata,2024-01-02,30.1,17.8,8.0,68,zambia_met\n"
        )
        buf = io.BytesIO(template.encode('utf-8'))
        buf.seek(0)
        return send_file(
            buf, as_attachment=True,
            download_name='zamfarm_climate_template.csv',
            mimetype='text/csv'
        )

    # =========================================================================
    # ROUTE: /climate_forecast  GET=show page  POST=run prediction
    # Uses climate_model.py ClimatePredictor
    # =========================================================================
    @app.route('/climate_forecast', methods=['GET', 'POST'])
    def climate_forecast():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        farmer = get_farmer()
        forecast_result = None

        if request.method == 'POST':
            district   = request.form.get('district', farmer[7] if farmer else 'Lusaka')
            crop       = request.form.get('crop', 'Maize')
            hectares   = float(request.form.get('hectares', 1.0))
            season     = request.form.get('season', '2024_25')
            soil_type  = int(request.form.get('soil_type', 1))

            # Pull historical climate averages for this district from DB
            try:
                cur = mysql.connection.cursor()
                cur.execute("""
                    SELECT
                        AVG((temp_max + temp_min) / 2) AS avg_temp,
                        SUM(rainfall_mm)               AS total_rainfall,
                        AVG(humidity_pct)              AS avg_humidity,
                        COUNT(*)                       AS record_count
                    FROM climate_data
                    WHERE district = %s
                      AND MONTH(date) BETWEEN 11 AND 12
                         OR MONTH(date) BETWEEN 1 AND 4
                """, (district,))
                row = cur.fetchone()
                avg_temp      = float(row[0]) if row[0] else 25.0
                total_rainfall = float(row[1]) if row[1] else 800.0
                avg_humidity  = float(row[2]) if row[2] else 70.0
            except Exception:
                avg_temp, total_rainfall, avg_humidity = 25.0, 800.0, 70.0

            # Run the predictive model
            from climate_model import ClimatePredictor
            predictor = ClimatePredictor()
            result = predictor.predict_season_yield(
                district=district, crop=crop, hectares=hectares,
                avg_temp=avg_temp, total_rainfall=total_rainfall,
                soil_type=soil_type,
            )

            forecast_result = {
                'predicted_yield': result['predicted_yield'],
                'confidence':      result['confidence'],
                'avg_temp':        round(avg_temp, 1),
                'total_rainfall':  round(total_rainfall, 1),
                'district':        district,
                'season':          {
                '2024_25': '2024-2025 (Historical)',
                '2025_26': '2025-2026 (Current)',
                '2026_27': '2026-2027 (Upcoming)',
            }.get(season, season.replace('_', '/')),
                'hectares':        hectares,
                'crop_comparison': result['crop_comparison'],
            }

        return render_template(
            'climate_forecast.html',
            farmer=farmer,
            zambia_districts=sorted(ZAMBIA_DISTRICTS.keys()),
            forecast_result=forecast_result,
            is_scenario=False,
        )

    # =========================================================================
    # ROUTE: /climate_scenario — What-If Climate Scenario Simulation
    # =========================================================================
    @app.route('/climate_scenario', methods=['POST'])
    def climate_scenario():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        farmer        = get_farmer()
        district      = request.form.get('district', farmer[7] if farmer else 'Lusaka')
        temp_delta    = float(request.form.get('temp_delta', 0))
        rain_delta    = float(request.form.get('rain_delta', 0))   # percent change
        scenario_name = request.form.get('scenario_name', 'Custom Scenario')

        # Base climate for district (from DB or fallback)
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT AVG((temp_max+temp_min)/2), SUM(rainfall_mm)
                FROM climate_data WHERE district=%s
            """, (district,))
            row = cur.fetchone()
            base_temp  = float(row[0]) if row[0] else 25.0
            base_rain  = float(row[1]) if row[1] else 800.0
        except Exception:
            base_temp, base_rain = 25.0, 800.0

        # Apply scenario deltas
        scenario_temp = base_temp + temp_delta
        scenario_rain = base_rain * (1 + rain_delta / 100)

        from climate_model import ClimatePredictor
        predictor = ClimatePredictor()
        result = predictor.predict_season_yield(
            district=district, crop='Maize', hectares=1.0,
            avg_temp=scenario_temp, total_rainfall=scenario_rain,
            soil_type=1,
        )

        forecast_result = {
            'predicted_yield': result['predicted_yield'],
            'confidence':      result['confidence'],
            'avg_temp':        round(scenario_temp, 1),
            'total_rainfall':  round(scenario_rain, 1),
            'district':        district,
            'season':          f"{scenario_name} Scenario",
            'hectares':        1.0,
            'crop_comparison': result['crop_comparison'],
        }

        return render_template(
            'climate_forecast.html',
            farmer=farmer,
            zambia_districts=sorted(ZAMBIA_DISTRICTS.keys()),
            forecast_result=forecast_result,
            is_scenario=True,
            scenario_name=scenario_name,
        )

    # =========================================================================
    # ROUTE: /climate_scenarios — GET view for the scenario simulator page
    # (climate_forecast.html has a tab for scenarios — needs a GET route)
    # =========================================================================
    @app.route('/climate_scenarios')
    def climate_scenarios():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        farmer = get_farmer()
        return render_template(
            'climate_forecast.html',
            farmer=farmer,
            zambia_districts=sorted(ZAMBIA_DISTRICTS.keys()),
            forecast_result=None,
            is_scenario=True,
            scenario_name=None,
        )

    # =========================================================================
    # SEASONAL RAINFALL OUTLOOK + CROP ADVICE  (upcoming season)
    # Rule-based, reliable: estimates the coming season's total rainfall for a
    # district from historical climate data (with a regional fallback), then
    # classifies it Below/Normal/Above-Normal and recommends suitable crops.
    # =========================================================================

    # Per-crop seasonal rain profile (mm) + drought tolerance, used to rank crops
    _SEASON_CROP_PROFILE = {
        "Maize":      {"emoji": "🌽", "rain_min": 500, "rain_max": 900,  "drought": "low"},
        "Soyabeans":  {"emoji": "🫘", "rain_min": 450, "rain_max": 700,  "drought": "low"},
        "Groundnuts": {"emoji": "🥜", "rain_min": 400, "rain_max": 650,  "drought": "medium"},
        "Cassava":    {"emoji": "🍠", "rain_min": 500, "rain_max": 1200, "drought": "high"},
        "Sorghum":    {"emoji": "🌾", "rain_min": 350, "rain_max": 750,  "drought": "high"},
        "Millet":     {"emoji": "🌿", "rain_min": 300, "rain_max": 650,  "drought": "high"},
        "Sunflower":  {"emoji": "🌻", "rain_min": 400, "rain_max": 700,  "drought": "medium"},
        "Potatoes":   {"emoji": "🥔", "rain_min": 500, "rain_max": 800,  "drought": "low"},
    }

    # Approximate "normal" seasonal rainfall by agro-ecological situation.
    # Region I (south, drier) ~ 650, Region II (central) ~ 850, Region III (north, wetter) ~ 1100.
    _REGION_III = {"Kasama", "Solwezi", "Mansa", "Kabompo", "Zambezi", "Mwinilunga",
                   "Kawambwa", "Chambeshi", "Chilubi", "Mpika", "Luwingu", "Nakonde"}
    _REGION_I   = {"Livingstone", "Choma", "Mazabuka", "Gwembe", "Sinazongwe", "Siavonga",
                   "Namwala", "Ngoma", "Monze"}

    def _normal_rainfall_for(district):
        if district in _REGION_III:
            return 1100.0
        if district in _REGION_I:
            return 650.0
        return 850.0  # Region II / default (central, incl. Lusaka, Copperbelt)

    def _estimate_seasonal_rainfall(district):
        """Estimate the upcoming season's total rainfall (mm) for a district.
        Uses the district's own historical wet-season records when available,
        otherwise falls back to the agro-ecological regional normal."""
        normal = _normal_rainfall_for(district)
        estimate = normal
        have_data = False
        try:
            cur = mysql.connection.cursor()
            # Average of total wet-season rainfall per year, if records exist
            cur.execute("""
                SELECT AVG(season_total) FROM (
                    SELECT YEAR(date) AS yr, SUM(rainfall_mm) AS season_total
                    FROM climate_data
                    WHERE district = %s
                      AND (MONTH(date) BETWEEN 11 AND 12 OR MONTH(date) BETWEEN 1 AND 4)
                    GROUP BY YEAR(date)
                ) t
            """, (district,))
            row = cur.fetchone()
            if row and row[0]:
                estimate  = float(row[0])
                have_data = True
        except Exception:
            pass

        # Blend historical estimate with regional normal for stability
        if have_data:
            estimate = round(0.7 * estimate + 0.3 * normal, 0)
        else:
            estimate = round(normal, 0)

        pct = estimate / normal if normal else 1.0
        if pct < 0.80:
            category, color, icon = "Below Normal", "#EF7D00", "🌵"
        elif pct <= 1.15:
            category, color, icon = "Normal", "#198A00", "🌦️"
        else:
            category, color, icon = "Above Normal", "#2E86AB", "🌧️"

        return {
            "district":     district,
            "estimate_mm":  estimate,
            "normal_mm":    normal,
            "pct_of_normal": round(pct * 100),
            "category":     category,
            "color":        color,
            "icon":         icon,
            "have_data":    have_data,
        }

    def _recommend_crops_for_rainfall(rain_mm, category):
        """Rank the supported crops by suitability for the estimated rainfall."""
        ranked = []
        for name, p in _SEASON_CROP_PROFILE.items():
            # Suitability score 0-100 based on fit to optimal rain range
            lo, hi = p["rain_min"], p["rain_max"]
            if lo <= rain_mm <= hi:
                score = 100
            elif rain_mm < lo:
                gap = lo - rain_mm
                # drought-tolerant crops penalised less when it's dry
                penalty = gap / (3.0 if p["drought"] == "high" else 2.0 if p["drought"] == "medium" else 1.3)
                score = max(0, 100 - penalty / 5)
            else:  # rain_mm > hi (too wet)
                gap = rain_mm - hi
                score = max(0, 100 - (gap / 5) / 2)
            ranked.append({
                "crop":   name,
                "emoji":  p["emoji"],
                "score":  round(score),
                "drought": p["drought"],
            })
        ranked.sort(key=lambda x: x["score"], reverse=True)

        # Build a short, human advisory based on the category
        if category == "Below Normal":
            advice = ("A drier-than-usual season is expected. Prioritise drought-tolerant crops "
                      "(sorghum, millet, cassava, groundnuts), plant early with the first reliable rains, "
                      "and practise moisture conservation such as mulching and minimum tillage.")
        elif category == "Above Normal":
            advice = ("A wetter-than-usual season is expected. Maize and cassava should do well, but ensure "
                      "good field drainage, watch for fungal diseases, and avoid waterlogged low-lying fields.")
        else:
            advice = ("A normal season is expected. Most crops should perform within their usual range — "
                      "maize, soyabeans, and groundnuts are all good choices alongside the staples.")
        return ranked, advice

    @app.route('/api/seasonal_outlook')
    def api_seasonal_outlook():
        """JSON: estimated rainfall + recommended crops for the upcoming season."""
        if 'user_id' not in session:
            return jsonify({'error': 'auth'}), 401
        farmer   = get_farmer()
        district = request.args.get('district') or (farmer[7] if farmer else 'Lusaka')
        if district not in ZAMBIA_DISTRICTS:
            district = farmer[7] if (farmer and farmer[7] in ZAMBIA_DISTRICTS) else 'Lusaka'
        outlook = _estimate_seasonal_rainfall(district)
        ranked, advice = _recommend_crops_for_rainfall(outlook['estimate_mm'], outlook['category'])
        outlook['recommended'] = ranked
        outlook['advice']      = advice
        return jsonify(outlook)

    # =========================================================================
    # ROUTE: /climate_api_districts — JSON endpoint (for AJAX autocomplete)
    # =========================================================================
    @app.route('/climate_api_districts')
    def climate_api_districts():
        return jsonify(sorted(ZAMBIA_DISTRICTS.keys()))
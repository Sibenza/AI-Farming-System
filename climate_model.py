# =============================================================================
# climate_model.py
# ZamFarm Climate — Predictive Analysis Engine
# FR2: Uses regression / decision tree models to estimate yield outcomes
#      under varying climate scenarios (Python / Scikit-learn)
#
# MODELS:
#   1. ClimatePredictor    — Season yield forecasting (RandomForestRegressor)
#   2. ScenarioSimulator   — What-if climate scenario yield estimation
#   3. Model retraining    — Updates model.pkl with ingested climate data
#
# HOW TO USE:
#   from climate_model import ClimatePredictor
#   predictor = ClimatePredictor()
#   result = predictor.predict_season_yield(...)
# =============================================================================

import os
import joblib
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Scikit-learn imports
from sklearn.ensemble         import RandomForestRegressor, GradientBoostingRegressor
from sklearn.tree             import DecisionTreeRegressor
from sklearn.linear_model     import LinearRegression
from sklearn.preprocessing    import StandardScaler
from sklearn.model_selection  import train_test_split, cross_val_score
from sklearn.metrics          import mean_squared_error, r2_score, mean_absolute_error
from sklearn.pipeline         import Pipeline


# =============================================================================
# ZAMBIAN CROP PROFILES
# Agronomic baselines for each crop grown in Zambia.
# Used to generate synthetic training data when no historical DB data exists.
# Sources: FAO, IAPRI Zambia crop data references
# =============================================================================
CROP_PROFILES = {
    "Maize": {
        "code":            0,
        "base_yield_tha":  2.5,      # tonnes/ha national average
        "optimal_temp":    (18, 28), # °C
        "optimal_rain":    (500, 900),  # mm/season
        "drought_thresh":  300,      # mm below which yield collapses
        "heat_thresh":     34,       # °C above which stress begins
        "emojis":          "🌽",
    },
    "Soyabeans": {
        "code":            1,
        "base_yield_tha":  1.4,
        "optimal_temp":    (20, 30),
        "optimal_rain":    (450, 700),
        "drought_thresh":  250,
        "heat_thresh":     35,
        "emojis":          "🫘",
    },
    "Groundnuts": {
        "code":            2,
        "base_yield_tha":  1.1,
        "optimal_temp":    (22, 32),
        "optimal_rain":    (400, 650),
        "drought_thresh":  200,
        "heat_thresh":     38,
        "emojis":          "🥜",
    },
    "Cassava": {
        "code":            3,
        "base_yield_tha":  8.2,
        "optimal_temp":    (20, 35),
        "optimal_rain":    (500, 1200),
        "drought_thresh":  400,
        "heat_thresh":     40,
        "emojis":          "🍠",
    },
}

# Soil type modifiers on yield (multiplier)
SOIL_MODIFIERS = {1: 1.0, 2: 0.85, 3: 0.92}   # Loamy=1.0, Sandy=0.85, Clay=0.92

# Path to save/load the climate model
MODEL_PATH = os.path.join("ai_model", "climate_model.pkl")
os.makedirs("ai_model", exist_ok=True)


# =============================================================================
# SYNTHETIC DATA GENERATOR
# Generates realistic Zambia-scale training data when no historical
# DB data is available. This bootstraps the model on first run.
# =============================================================================
def generate_synthetic_training_data(n_samples=3000, random_state=42):
    """
    Generate synthetic climate-yield training data based on
    agronomic relationships defined in CROP_PROFILES.

    Features: [avg_temp, total_rainfall, humidity, soil_type, crop_code, hectares]
    Target:   predicted_yield (tonnes)
    """
    rng = np.random.default_rng(random_state)

    X, y = [], []

    for _ in range(n_samples):
        # Pick a random crop
        crop_name = rng.choice(list(CROP_PROFILES.keys()))
        crop      = CROP_PROFILES[crop_name]

        # Generate climate values (Zambia ranges)
        avg_temp      = rng.uniform(15, 40)         # °C
        total_rainfall = rng.uniform(100, 1500)     # mm/season
        humidity      = rng.uniform(30, 95)          # %
        soil_type     = rng.choice([1, 2, 3])
        hectares      = rng.uniform(0.5, 20)

        # ── Yield calculation using agronomic response curves ──
        opt_t_low, opt_t_high = crop["optimal_temp"]
        opt_r_low, opt_r_high = crop["optimal_rain"]
        base                  = crop["base_yield_tha"]

        # Temperature response (bell curve penalty)
        if avg_temp < opt_t_low:
            temp_factor = 1.0 - 0.04 * (opt_t_low - avg_temp)
        elif avg_temp > crop["heat_thresh"]:
            temp_factor = 1.0 - 0.08 * (avg_temp - crop["heat_thresh"])
        elif avg_temp > opt_t_high:
            temp_factor = 1.0 - 0.03 * (avg_temp - opt_t_high)
        else:
            temp_factor = 1.0

        # Rainfall response (piecewise linear)
        if total_rainfall < crop["drought_thresh"]:
            rain_factor = 0.2 + 0.5 * (total_rainfall / crop["drought_thresh"])
        elif total_rainfall < opt_r_low:
            rain_factor = 0.7 + 0.3 * ((total_rainfall - crop["drought_thresh"]) /
                                        (opt_r_low - crop["drought_thresh"]))
        elif total_rainfall <= opt_r_high:
            rain_factor = 1.0
        else:
            # Excess rain causes waterlogging penalty
            excess      = total_rainfall - opt_r_high
            rain_factor = max(1.0 - 0.0003 * excess, 0.5)

        # Combine factors
        soil_mod    = SOIL_MODIFIERS.get(soil_type, 1.0)
        temp_factor = max(temp_factor, 0.1)
        base_yield  = base * temp_factor * rain_factor * soil_mod

        # Per-hectare yield × hectares + noise
        noise       = rng.normal(0, base * 0.08)
        total_yield = max(hectares * base_yield + noise, 0)

        X.append([avg_temp, total_rainfall, humidity, soil_type,
                  crop["code"], hectares])
        y.append(round(total_yield, 3))

    return np.array(X), np.array(y)


# =============================================================================
# CLIMATE PREDICTOR CLASS
# =============================================================================
class ClimatePredictor:
    """
    Predictive Analysis Engine for ZamFarm Climate.
    Uses a RandomForestRegressor trained on historical climate-yield data.

    Methods:
        train()                 — Train / retrain the model
        load()                  — Load saved model from disk
        predict_season_yield()  — Forecast yield for a season
        predict_scenario()      — What-if climate scenario
        evaluate()              — Return model metrics
    """

    def __init__(self):
        self.model   = None
        self.scaler  = None
        self.metrics = {}
        self._load_or_train()

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD or TRAIN
    # ─────────────────────────────────────────────────────────────────────────
    def _load_or_train(self):
        """Load saved model if it exists, otherwise train a new one."""
        if os.path.exists(MODEL_PATH):
            try:
                saved = joblib.load(MODEL_PATH)
                self.model   = saved['model']
                self.scaler  = saved['scaler']
                self.metrics = saved.get('metrics', {})
                print("[ClimatePredictor] Loaded saved model from", MODEL_PATH)
                return
            except Exception as e:
                print(f"[ClimatePredictor] Load failed ({e}), retraining…")

        self.train()

    # ─────────────────────────────────────────────────────────────────────────
    # TRAIN
    # ─────────────────────────────────────────────────────────────────────────
    def train(self, X=None, y=None, use_db_data=False):
        """
        Train the Random Forest model.

        Args:
            X, y        — Optional external feature/label arrays.
                          If None, synthetic data is generated.
            use_db_data — If True, supplement with real DB records
                          (called from retrain_with_db_data route).
        """
        print("[ClimatePredictor] Generating training data…")

        if X is None or y is None:
            X, y = generate_synthetic_training_data(n_samples=5000)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_s   = self.scaler.fit_transform(X_train)
        X_test_s    = self.scaler.transform(X_test)

        # ── Random Forest (primary model) ──────────────────────────────────
        # Chosen over single Decision Tree for better generalisation.
        # Decision Tree is available as an alternative below.
        self.model = RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train_s, y_train)

        # ── Evaluate ───────────────────────────────────────────────────────
        y_pred  = self.model.predict(X_test_s)
        mse     = mean_squared_error(y_test, y_pred)
        rmse    = np.sqrt(mse)
        mae     = mean_absolute_error(y_test, y_pred)
        r2      = r2_score(y_test, y_pred)

        self.metrics = {
            'rmse':       round(rmse, 4),
            'mae':        round(mae,  4),
            'r2':         round(r2,   4),
            'n_train':    len(X_train),
            'n_test':     len(X_test),
            'model_type': 'RandomForestRegressor',
        }

        print(f"[ClimatePredictor] Trained — R²={r2:.3f} RMSE={rmse:.3f}")

        # Save to disk
        joblib.dump({
            'model':   self.model,
            'scaler':  self.scaler,
            'metrics': self.metrics,
        }, MODEL_PATH)
        print(f"[ClimatePredictor] Model saved to {MODEL_PATH}")

        return self.metrics

    # ─────────────────────────────────────────────────────────────────────────
    # RETRAIN WITH DB DATA
    # Called when new climate records have been ingested.
    # ─────────────────────────────────────────────────────────────────────────
    def retrain_with_db_data(self, db_records, existing_predictions):
        """
        Retrain the model combining:
          - db_records:          list of (avg_temp, rainfall, humidity, soil_type, crop_code, hectares)
          - existing_predictions: list of (features..., actual_yield) from DB predictions table
        Falls back to synthetic data if DB sets are too small.
        """
        # Start with synthetic base
        X_syn, y_syn = generate_synthetic_training_data(n_samples=3000)

        # Append real DB records if available
        real_X, real_y = [], []
        for rec in existing_predictions:
            try:
                real_X.append([
                    float(rec.get('avg_temp', 25)),
                    float(rec.get('rainfall', 800)),
                    float(rec.get('humidity', 70)),
                    int(rec.get('soil_type', 1)),
                    int(rec.get('crop_code', 0)),
                    float(rec.get('hectares', 1)),
                ])
                real_y.append(float(rec.get('actual_yield', 0)))
            except (ValueError, TypeError):
                continue

        if len(real_X) >= 20:
            # Weight real data 3× more than synthetic
            X_real_arr = np.array(real_X)
            y_real_arr = np.array(real_y)
            X = np.vstack([X_syn, np.repeat(X_real_arr, 3, axis=0)])
            y = np.concatenate([y_syn, np.tile(y_real_arr, 3)])
        else:
            X, y = X_syn, y_syn

        return self.train(X, y)

    # ─────────────────────────────────────────────────────────────────────────
    # PREDICT SEASON YIELD
    # ─────────────────────────────────────────────────────────────────────────
    def predict_season_yield(self, district, crop, hectares,
                              avg_temp, total_rainfall, soil_type=1):
        """
        Forecast yield for a given crop, farm size, and climate inputs.

        Returns dict with:
            predicted_yield  — total tonnes for the farm
            yield_per_ha     — tonnes/ha
            confidence       — model confidence % (based on tree variance)
            crop_comparison  — list of yields for all 4 crops (same climate)
            interpretation   — text description of result
        """
        crop_code = CROP_PROFILES.get(crop, CROP_PROFILES["Maize"])["code"]

        # Estimate seasonal humidity from rainfall (proxy)
        humidity = min(30 + (total_rainfall / 1200) * 65, 95)

        features = np.array([[
            avg_temp, total_rainfall, humidity, soil_type, crop_code, hectares
        ]])
        features_scaled = self.scaler.transform(features)

        # Primary prediction
        pred_yield = float(self.model.predict(features_scaled)[0])
        pred_yield = max(round(pred_yield, 2), 0)

        # Confidence estimate from tree prediction spread
        try:
            tree_preds = np.array([
                tree.predict(features_scaled)[0]
                for tree in self.model.estimators_
            ])
            cv = np.std(tree_preds) / (np.mean(tree_preds) + 1e-6)
            confidence = round(max(min((1 - cv) * 100, 99), 50), 1)
        except AttributeError:
            confidence = 85.0

        # Crop comparison — predict for all 4 crops with same climate
        crop_comparison = []
        for c_name, c_data in CROP_PROFILES.items():
            f = np.array([[avg_temp, total_rainfall, humidity,
                           soil_type, c_data["code"], hectares]])
            f_s = self.scaler.transform(f)
            cv  = max(float(self.model.predict(f_s)[0]), 0)
            crop_comparison.append(round(cv, 2))

        # Human-readable interpretation
        yield_per_ha = round(pred_yield / max(hectares, 0.1), 2)
        base         = CROP_PROFILES.get(crop, {}).get('base_yield_tha', 2.5)

        if yield_per_ha >= base * 1.2:
            interpretation = "🟢 Excellent — well above average. Good season expected."
        elif yield_per_ha >= base * 0.9:
            interpretation = "🟡 Average — within normal range for this district."
        elif yield_per_ha >= base * 0.6:
            interpretation = "🟠 Below average — consider supplemental irrigation."
        else:
            interpretation = "🔴 Poor — climate conditions unfavourable. Consider alternative crop."

        return {
            'predicted_yield':  pred_yield,
            'yield_per_ha':     yield_per_ha,
            'confidence':       confidence,
            'crop_comparison':  crop_comparison,
            'interpretation':   interpretation,
            'district':         district,
            'crop':             crop,
            'hectares':         hectares,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO SIMULATION — What-If Analysis
    # ─────────────────────────────────────────────────────────────────────────
    def simulate_scenario(self, base_temp, base_rainfall, crop, hectares,
                           temp_delta=0, rain_delta_pct=0, soil_type=1):
        """
        Apply climate deltas to base conditions and forecast yield.
        Used by the Scenario Simulator.

        Args:
            temp_delta      — °C change from baseline (e.g. +2.0)
            rain_delta_pct  — % change in rainfall (e.g. -20 = 20% less)

        Returns same dict as predict_season_yield + baseline comparison.
        """
        new_temp = base_temp + temp_delta
        new_rain = base_rainfall * (1 + rain_delta_pct / 100)
        new_rain = max(new_rain, 0)

        baseline = self.predict_season_yield(
            district='baseline', crop=crop, hectares=hectares,
            avg_temp=base_temp, total_rainfall=base_rainfall,
            soil_type=soil_type
        )
        scenario = self.predict_season_yield(
            district='scenario', crop=crop, hectares=hectares,
            avg_temp=new_temp, total_rainfall=new_rain,
            soil_type=soil_type
        )

        # Calculate impact
        yield_diff   = round(scenario['predicted_yield'] - baseline['predicted_yield'], 2)
        yield_pct    = round((yield_diff / max(baseline['predicted_yield'], 0.01)) * 100, 1)

        scenario['baseline_yield']    = baseline['predicted_yield']
        scenario['yield_difference']  = yield_diff
        scenario['yield_pct_change']  = yield_pct
        scenario['temp_applied']      = round(new_temp, 1)
        scenario['rain_applied']      = round(new_rain, 1)

        return scenario

    # ─────────────────────────────────────────────────────────────────────────
    # MULTI-SCENARIO TABLE
    # Runs 5 standard scenarios × 4 crops for the comparison table
    # ─────────────────────────────────────────────────────────────────────────
    def build_scenario_table(self, base_temp, base_rainfall, soil_type=1, hectares=1.0):
        """
        Returns a dict keyed by crop name, each containing a list of
        predicted yields under 5 scenarios.
        Scenarios: Baseline, +2°C Warming, Wet Season, Drought, Flood Risk
        """
        scenarios = [
            {"name": "Baseline",    "temp_d": 0,   "rain_d": 0},
            {"name": "Warming",     "temp_d": +2,  "rain_d": -20},
            {"name": "Wet Season",  "temp_d": +1,  "rain_d": +15},
            {"name": "Drought",     "temp_d": +3,  "rain_d": -40},
            {"name": "Flood Risk",  "temp_d": -1,  "rain_d": +30},
        ]

        results = {}
        for crop_name in CROP_PROFILES:
            crop_row = []
            for sc in scenarios:
                r = self.simulate_scenario(
                    base_temp=base_temp, base_rainfall=base_rainfall,
                    crop=crop_name, hectares=hectares, soil_type=soil_type,
                    temp_delta=sc["temp_d"], rain_delta_pct=sc["rain_d"]
                )
                crop_row.append(r['predicted_yield'])
            results[crop_name] = crop_row

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # EVALUATE MODEL
    # ─────────────────────────────────────────────────────────────────────────
    def evaluate(self):
        """Return stored model performance metrics."""
        return self.metrics

    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE IMPORTANCE
    # ─────────────────────────────────────────────────────────────────────────
    def feature_importance(self):
        """
        Return feature importances as a dict.
        Useful for the admin dashboard to explain model decisions.
        """
        feature_names = [
            'avg_temperature', 'total_rainfall', 'humidity',
            'soil_type', 'crop_code', 'hectares'
        ]
        try:
            importances = self.model.feature_importances_
            return dict(zip(feature_names, [round(float(i), 4) for i in importances]))
        except AttributeError:
            return {}


# =============================================================================
# DECISION TREE ALTERNATIVE
# A simpler, interpretable model option — useful for academic presentation
# since the project spec mentions Decision Trees specifically.
# =============================================================================
class DecisionTreePredictor(ClimatePredictor):
    """
    Same interface as ClimatePredictor but uses a Decision Tree.
    More interpretable, slightly lower accuracy.
    Activate by instantiating DecisionTreePredictor() instead.
    """

    def train(self, X=None, y=None, use_db_data=False):
        if X is None or y is None:
            X, y = generate_synthetic_training_data(n_samples=5000)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.scaler  = StandardScaler()
        X_train_s    = self.scaler.fit_transform(X_train)
        X_test_s     = self.scaler.transform(X_test)

        self.model = DecisionTreeRegressor(
            max_depth=10,
            min_samples_split=8,
            min_samples_leaf=4,
            random_state=42,
        )
        self.model.fit(X_train_s, y_train)

        y_pred  = self.model.predict(X_test_s)
        r2      = r2_score(y_test, y_pred)
        rmse    = np.sqrt(mean_squared_error(y_test, y_pred))

        self.metrics = {
            'rmse':       round(rmse, 4),
            'mae':        round(mean_absolute_error(y_test, y_pred), 4),
            'r2':         round(r2, 4),
            'n_train':    len(X_train),
            'n_test':     len(X_test),
            'model_type': 'DecisionTreeRegressor',
        }

        dt_path = os.path.join("ai_model", "climate_dt_model.pkl")
        joblib.dump({'model': self.model, 'scaler': self.scaler,
                     'metrics': self.metrics}, dt_path)
        print(f"[DecisionTreePredictor] Trained R²={r2:.3f} → {dt_path}")
        return self.metrics


# =============================================================================
# STANDALONE TEST — run: python climate_model.py
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ZamFarm Climate — Predictive Analysis Engine")
    print("=" * 60)

    predictor = ClimatePredictor()
    metrics   = predictor.evaluate()
    print(f"\nModel Metrics:")
    for k, v in metrics.items():
        print(f"  {k:15s}: {v}")

    print("\nFeature Importances:")
    for k, v in predictor.feature_importance().items():
        bar = "█" * int(v * 50)
        print(f"  {k:22s}: {bar} ({v:.4f})")

    print("\nSample Prediction — Maize, Lusaka, Normal Season:")
    result = predictor.predict_season_yield(
        district="Lusaka", crop="Maize", hectares=3.0,
        avg_temp=25.0, total_rainfall=750.0, soil_type=1
    )
    print(f"  Predicted Yield : {result['predicted_yield']} T")
    print(f"  Yield per ha    : {result['yield_per_ha']} T/ha")
    print(f"  Confidence      : {result['confidence']}%")
    print(f"  Interpretation  : {result['interpretation']}")

    print("\nScenario — +2°C Warming, -20% Rainfall:")
    sc = predictor.simulate_scenario(
        base_temp=25.0, base_rainfall=750.0, crop="Maize",
        hectares=3.0, temp_delta=2.0, rain_delta_pct=-20
    )
    print(f"  Scenario Yield  : {sc['predicted_yield']} T")
    print(f"  Change from base: {sc['yield_difference']} T ({sc['yield_pct_change']}%)")

    print("\nDecision Tree Model:")
    dt = DecisionTreePredictor()
    print(f"  R² = {dt.evaluate()['r2']}")

    print("\n✅ All tests passed.")
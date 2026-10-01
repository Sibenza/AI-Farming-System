"""
=============================================================================
ZamFarm Climate — Model Training Script (Robust Version)
=============================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib

print("=" * 70)
print("ZamFarm Climate — Model Training")
print(f"Python: {sys.version.split()[0]}")
print("=" * 70)

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import cross_val_score
    import sklearn
    print(f"sklearn: {sklearn.__version__}")
except ImportError:
    print("ERROR: pip install scikit-learn pandas numpy")
    sys.exit(1)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_MODEL_DIR = os.path.join(PROJECT_ROOT, "ai_model")
os.makedirs(AI_MODEL_DIR, exist_ok=True)

# =============================================================================
# 1. CROP RECOMMENDATION MODEL
# =============================================================================
print("\n[1/2] Training Crop Recommendation Model...")
CROP_DATA = {
    "Maize": [(720,25,1),(650,23,1),(850,26,1),(580,22,1)],
    "Soyabeans": [(580,26,1),(620,25,1),(550,24,1)],
    "Groundnuts": [(450,29,2),(380,28,2),(500,27,2)],
    "Cassava": [(950,27,1),(850,28,3),(1100,26,1)],
    "Sorghum": [(350,30,2),(420,29,2),(280,32,2)],
    "Millet": [(280,30,2),(320,29,2)],
    "Sunflower": [(550,25,1),(480,24,2)],
    "Potatoes": [(720,18,1),(650,17,3)],
}

X_crop, y_crop = [], []
for crop, samples in CROP_DATA.items():
    for s in samples:
        X_crop.append(list(s))
        y_crop.append(crop)

X_crop = np.array(X_crop, dtype=float)
y_crop = np.array(y_crop)

crop_clf = RandomForestClassifier(n_estimators=400, max_depth=12, random_state=42, class_weight='balanced')
crop_clf.fit(X_crop, y_crop)

joblib.dump(crop_clf, os.path.join(AI_MODEL_DIR, "crop_model.pkl"))
print("  ✅ Crop Recommendation Model saved")

# =============================================================================
# 2. YIELD PREDICTION MODEL
# =============================================================================
print("\n[2/2] Training Yield Prediction Model...")

csv_path = os.path.join(AI_MODEL_DIR, "crop_yield_dataset.csv")

if not os.path.exists(csv_path):
    print(f"❌ File not found: {csv_path}")
    sys.exit(1)

df = pd.read_csv(csv_path)
print(f"  Loaded {len(df)} records")

# Crop ID mapping
crop_map = {
    "Maize": 0, "Soyabeans": 1, "Soybeans": 1, "Groundnuts": 2,
    "Cassava": 3, "Sorghum": 4, "Millet": 5, "Sunflower": 6, "Potatoes": 7
}
df['crop_id'] = df['crop'].map(crop_map).fillna(0)

# Handle missing columns gracefully
feature_cols = ['hectares', 'rainfall', 'temperature', 'soil_type', 'crop_id']

# Add fertilizer if it exists, otherwise use a default
if 'fertilizer' in df.columns:
    feature_cols.insert(3, 'fertilizer')
    print("  Using 'fertilizer' column from dataset")
else:
    df['fertilizer'] = 60  # default value
    feature_cols.insert(3, 'fertilizer')
    print("  'fertilizer' column not found → using default value (60)")

X = df[feature_cols].values
y = df['yield_tonnes'].values if 'yield_tonnes' in df.columns else df['yield'].values

print(f"  Features used: {feature_cols}")

yield_reg = RandomForestRegressor(
    n_estimators=500,
    max_depth=15,
    min_samples_split=2,
    random_state=42,
    n_jobs=-1
)
yield_reg.fit(X, y)

scores = cross_val_score(yield_reg, X, y, cv=5, scoring='r2')
print(f"  Cross-val R² Score: {scores.mean():.3f} ± {scores.std():.3f}")

# Save
joblib.dump(yield_reg, os.path.join(AI_MODEL_DIR, "model.pkl"))
joblib.dump(feature_cols, os.path.join(AI_MODEL_DIR, "yield_features.pkl"))

print("  ✅ Yield Prediction Model saved successfully!")
print("\n" + "=" * 70)
print("✅ TRAINING COMPLETE!")
print("=" * 70)
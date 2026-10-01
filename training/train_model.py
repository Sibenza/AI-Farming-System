import pandas as pd
from sklearn.linear_model import LinearRegression
import joblib
import os

# Get dataset path safely
BASE_DIR = os.path.dirname(__file__)
file_path = os.path.join(BASE_DIR, "crop_yield_dataset.csv")

# Load dataset
data = pd.read_csv(file_path)

# Encode crop column
data['crop'] = data['crop'].astype('category').cat.codes

# Features
X = data[['hectares','rainfall','temperature',
          'fertilizer','soil_type','crop']]

# Target
y = data['yield']

# Train model
model = LinearRegression()
model.fit(X, y)

# Save model
model_path = os.path.join(BASE_DIR, "model.pkl")
joblib.dump(model, model_path)

print("AI Model Trained Successfully ✅")
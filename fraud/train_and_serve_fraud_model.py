# train_and_serve_fraud_model.py
from flask import Flask, request, jsonify
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

app = Flask(__name__)
MODEL_PATH = "fraud_model.joblib"

def make_data(n=2000):
    rng = np.random.RandomState(0)
    X = rng.randn(n, 5)
    y = (X[:,0] + 0.5*X[:,1] + rng.randn(n)*0.2 > 0.5).astype(int)
    return X, y

def train():
    X, y = make_data()
    m = RandomForestClassifier(n_estimators=20, random_state=0)
    m.fit(X, y)
    joblib.dump(m, MODEL_PATH)
    print("model saved")

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json.get("features")
    X = np.array(data).reshape(1, -1)
    m = joblib.load(MODEL_PATH)
    prob = float(m.predict_proba(X)[0,1])
    return jsonify({"fraud_prob": prob})

if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        train()
    app.run(host="0.0.0.0", port=5001)

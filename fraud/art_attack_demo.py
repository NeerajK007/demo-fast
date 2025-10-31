# art_attack_demo.py
import numpy as np
import joblib
import os
try:
    from art.attacks.evasion import FastGradientMethod
    from art.estimators.classification.scikitlearn import ScikitlearnClassifier
except Exception as e:
    print("ART not installed. Install adversarial-robustness-toolbox to run live attacks.")
    raise

model_path = "fraud_model.joblib"
if not os.path.exists(model_path):
    print("Model not found. Please run train_and_serve_fraud_model.py first or start the container")
    raise SystemExit(1)

model = joblib.load(model_path)
clf = ScikitlearnClassifier(model=model)

X = np.array([[ -1.5, 0.1, 0.0, 0.0, 0.0 ]])
orig_prob = clf.predict_proba(X)[0][1]
print("original fraud prob:", orig_prob)

attack = FastGradientMethod(estimator=clf, eps=0.3)
X_adv = attack.generate(X)
adv_prob = clf.predict_proba(X_adv)[0][1]
print("adversarial fraud prob:", adv_prob)
print("orig:", X, "adv:", X_adv)

"""Step 2 of the pipeline: train the ANN that predicts performance_category."""
import pandas as pd, joblib
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

df = pd.read_csv("student_performance_monitoring_dataset.csv")
# Drop IDs and the target. overall_performance_score is dropped too: the category
# is derived from it, so keeping it would be cheating (data leakage).
X = df.drop(columns=["student_id", "performance_category", "overall_performance_score"])
LABELS = ["Low", "Medium", "High"]
y = df["performance_category"].map({l: i for i, l in enumerate(LABELS)}).to_numpy()  # ints: avoids a sklearn string-label bug
num = [c for c in X.columns if c != "department"]

pre = ColumnTransformer([("num", StandardScaler(), num),
                         ("dep", OneHotEncoder(handle_unknown="ignore"), ["department"])])
ann = Pipeline([("pre", pre),
                ("mlp", MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=600,
                                      early_stopping=True, random_state=42))])

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
ann.fit(Xtr, ytr)
print(classification_report(yte, ann.predict(Xte), target_names=LABELS))
ann.fit(X, y)                      # refit on everything for the app
joblib.dump((ann, LABELS), "ann_model.joblib")
print("Saved ann_model.joblib")

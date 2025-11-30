# Check model features
import json
from pathlib import Path
import joblib

# Charger metadata
meta_path = Path('optimization/saved_models/best_classifier_metadata.json')
with open(meta_path) as f:
    meta = json.load(f)

print(f'Features dans metadata: {meta.get("n_features", "?")}')
print(f'Nombre feature_cols: {len(meta.get("feature_cols", []))}')

# Charger modele
model_path = Path('optimization/saved_models/best_classifier_latest.pkl')
model = joblib.load(model_path)

print(f'\nType modele: {type(model).__name__}')

# Verifier si Pipeline
if hasattr(model, 'steps'):
    print(f'Pipeline avec {len(model.steps)} etapes:')
    for name, step in model.steps:
        print(f'  - {name}: {type(step).__name__}')
        if hasattr(step, 'n_features_in_'):
            print(f'    n_features_in_: {step.n_features_in_}')
elif hasattr(model, 'n_features_in_'):
    print(f'Features attendues par modele: {model.n_features_in_}')

# Verifier scaler
if hasattr(model, 'named_steps'):
    if 'scaler' in model.named_steps:
        scaler = model.named_steps['scaler']
        if hasattr(scaler, 'n_features_in_'):
            print(f'\nScaler attend: {scaler.n_features_in_} features')

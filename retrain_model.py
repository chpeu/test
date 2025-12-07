# Retrain model with new params
import requests
import time

# Lancer entrainement
r = requests.post('http://localhost:5000/api/ml/train_gb')
if r.status_code != 200:
    print('Erreur:', r.status_code)
    exit()

task_id = r.json().get('task_id')
print(f'Training lance: {task_id}')

# Attendre
while True:
    time.sleep(2)
    status = requests.get(f'http://localhost:5000/api/ml/task/{task_id}').json()
    progress = status.get('progress', 0)
    stage = status.get('stage', '')
    print(f'Progress: {progress}% - {stage}')
    
    if progress >= 100 or status.get('status') == 'complete':
        print('Entrainement termine!')
        break

# Resultats
time.sleep(2)
overview = requests.get('http://localhost:5000/api/ml/models/overview').json()
for m in overview.get('models', []):
    if m.get('name') == 'best_classifier':
        metrics = m.get('metrics', {}).get('test', {})
        gap = m.get('overfitting_gap', 0)
        print(f'\nResultats:')
        print(f'  Accuracy: {metrics.get("accuracy", 0)*100:.1f}%')
        print(f'  F1: {metrics.get("f1_score", 0):.3f}')
        print(f'  Precision: {metrics.get("precision", 0):.3f}')
        print(f'  Gap: {gap:.1f}%')

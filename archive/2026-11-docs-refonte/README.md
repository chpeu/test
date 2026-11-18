# Papiers de la refonte abandonnée — mis de côté le 18/11/2026

Le code qu'ils décrivaient a été retiré le même jour (commit `8d351a2`) :
l'usine `core/factories`, les secondes implémentations `core/implementations`,
les contrats `core/interfaces` et les neuf interrupteurs de
`core/feature_flags.json`. Le robot n'a jamais emprunté ce chemin : il instancie
directement `TechnicalAnalyzer`, `ScalabilityScanner` et `PositionManager`.

Gardés ici pour l'histoire : ils expliquent pourquoi le dépôt contenait deux
moteurs côte à côte, et ce qui avait été essayé.

Le fichier `analyzer.py.backup` était une copie de secours du moteur d'analyse,
plus vieille que l'original. Elle dort ici plutôt qu'à côté du code.

Trois papiers sur les websockets sont restés dans `docs/` : ils décrivent
l'installation actuelle, pas la refonte morte.

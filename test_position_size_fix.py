#!/usr/bin/env python3
"""
Test de vérification du fix de taille de position
Bug: Le bot ouvrait 1 lot (142 USDT) au lieu de 0.1 lot (14.2 USDT) pour une config de 20 USDT
"""

# Simuler les specs du contrat SOL
class MockContractSpec:
    def __init__(self):
        self.symbol = "SOL_USDT"
        self.min_vol = 1.0  # 1 lot minimum (problème!)
        self.max_vol = 10000.0
        self.vol_unit = 0.1  # Incréments de 0.1
        self.vol_precision = 1

    def round_volume_OLD(self, vol: float) -> float:
        """VERSION BUGGÉE (ancienne)"""
        if self.vol_unit > 0:
            vol = (vol // self.vol_unit) * self.vol_unit
        vol = round(vol, self.vol_precision)
        # BUG ICI: Force min_vol
        vol = max(self.min_vol, min(self.max_vol, vol))
        return vol

    def round_volume_NEW(self, vol: float) -> float:
        """VERSION CORRIGÉE (nouvelle)"""
        if self.vol_unit > 0:
            vol = (vol // self.vol_unit) * self.vol_unit
        vol = round(vol, self.vol_precision)
        # FIX: Ne pas forcer min_vol
        if vol > self.max_vol:
            vol = self.max_vol
        return vol


def test_position_size_calculation():
    """Tester le calcul de position avec 20 USDT de size"""

    # Configuration
    size_usdt = 20.0
    entry_price = 142.04
    leverage = 1

    # Calcul quantité en lots (formule: size_usdt / entry_price)
    amount_raw = size_usdt / entry_price

    print("=" * 60)
    print("TEST CALCUL TAILLE DE POSITION - SOL/USDT")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  - Size USDT: {size_usdt} USDT")
    print(f"  - Entry price: {entry_price} USDT")
    print(f"  - Leverage: {leverage}x")
    print(f"  - Amount raw: {amount_raw:.6f} lots")
    print()

    # Specs du contrat
    spec = MockContractSpec()
    print(f"Specs contrat SOL:")
    print(f"  - min_vol: {spec.min_vol} lot")
    print(f"  - vol_unit: {spec.vol_unit} lot")
    print()

    # Test VERSION BUGGÉE
    amount_old = spec.round_volume_OLD(amount_raw)
    size_usdt_old = amount_old * entry_price

    print("XX VERSION BUGGEE (ANCIENNE):")
    print(f"  - Amount arrondi: {amount_old} lots")
    print(f"  - Size USDT reel: {size_usdt_old:.2f} USDT")
    print(f"  - Ecart: {size_usdt_old - size_usdt:+.2f} USDT ({(size_usdt_old / size_usdt - 1) * 100:+.1f}%)")
    print()

    # Test VERSION CORRIGÉE
    amount_new = spec.round_volume_NEW(amount_raw)

    print("OK VERSION CORRIGEE (NOUVELLE):")
    print(f"  - Amount arrondi: {amount_new} lots")

    # Vérifier si volume < min_vol (doit rejeter)
    if amount_new < spec.min_vol:
        print(f"  - XX REJET: Volume {amount_new} < min_vol {spec.min_vol}")
        print(f"  - Capital requis: {spec.min_vol * entry_price:.2f} USDT (min)")
        print()
        print(">> RESULTAT: L'ordre sera REJETE car le capital est insuffisant.")
        print(f"   Pour trader SOL avec ces specs, vous devez avoir au minimum:")
        print(f"   {spec.min_vol} lots x {entry_price} USDT/lot = {spec.min_vol * entry_price:.2f} USDT")
    else:
        size_usdt_new = amount_new * entry_price
        print(f"  - Size USDT reel: {size_usdt_new:.2f} USDT")
        print(f"  - Ecart: {size_usdt_new - size_usdt:+.2f} USDT ({(size_usdt_new / size_usdt - 1) * 100:+.1f}%)")
        print()
        print(">> RESULTAT: L'ordre sera ACCEPTE.")

    print()
    print("=" * 60)
    print("CONCLUSION:")
    print("=" * 60)
    print("Avec la correction, le bot:")
    print("1. Calcule correctement amount = 0.1408 lots")
    print("2. Arrondit à 0.1 lots (selon vol_unit)")
    print("3. Détecte que 0.1 < min_vol (1.0)")
    print("4. REJETTE l'ordre avec un message clair")
    print()
    print("Solution pour trader SOL avec 20 USDT:")
    print(f"  - Augmenter size_usdt à minimum {spec.min_vol * entry_price:.2f} USDT")
    print("  - OU choisir une paire avec min_vol plus faible")
    print("=" * 60)


if __name__ == "__main__":
    test_position_size_calculation()

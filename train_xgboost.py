"""
Script wrapper pour entraîner XGBoost depuis la racine du projet
Usage: python train_xgboost.py [timeframe_days] [min_trades]
"""
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    from optimization.models.xgboost_trainer import train_xgboost_cli
    
    # Parse args
    timeframe = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    min_trades = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    print(f"\n🚀 Entraînement XGBoost")
    print(f"📊 Timeframe: {timeframe} jours")
    print(f"📊 Min trades: {min_trades}\n")
    
    train_xgboost_cli(timeframe_days=timeframe, min_trades=min_trades)

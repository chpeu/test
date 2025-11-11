"""
Tests pour core/database.py
"""
import pytest
import os
import tempfile
from datetime import datetime
from core.database import TradeDatabase


class TestTradeDatabase:
    """Tests pour TradeDatabase"""

    def setup_method(self):
        """Setup avant chaque test"""
        # Créer un fichier DB temporaire
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_trades.db")

    def teardown_method(self):
        """Cleanup après chaque test"""
        # Supprimer le fichier DB temporaire
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_init_creates_database(self):
        """Test initialisation crée la base de données"""
        db = TradeDatabase(self.db_path)
        assert os.path.exists(self.db_path)
        assert db.conn is not None
        db.close()

    def test_init_creates_trades_table(self):
        """Test initialisation crée la table trades"""
        db = TradeDatabase(self.db_path)

        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == 'trades'
        db.close()

    def test_init_creates_indexes(self):
        """Test initialisation crée les index"""
        db = TradeDatabase(self.db_path)

        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        assert 'idx_symbol' in indexes
        assert 'idx_date' in indexes
        assert 'idx_timestamp' in indexes
        db.close()

    def test_insert_trade_success(self):
        """Test insertion trade réussie"""
        db = TradeDatabase(self.db_path)

        trade = {
            'timestamp': '2024-01-15T10:30:00',
            'date': '2024-01-15',
            'time': '10:30:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 51000.0,
            'gross_pnl_pct': 2.0,
            'gross_pnl_usdt': 100.0,
            'net_pnl_pct': 1.8,
            'net_pnl_usdt': 90.0,
            'fees': 5.0,
            'slippage': 5.0,
            'total_costs': 10.0,
            'reason': 'TP_HIT',
            'duration': 3600,
            'condition_types': ['EMA_CROSS', 'RSI_OVERSOLD'],
            'metadata': {'test': 'data'}
        }

        trade_id = db.insert_trade(trade)
        assert trade_id > 0
        db.close()

    def test_insert_trade_minimal_fields(self):
        """Test insertion trade avec champs minimaux"""
        db = TradeDatabase(self.db_path)

        trade = {
            'timestamp': '2024-01-15T10:30:00',
            'date': '2024-01-15',
            'time': '10:30:00',
            'symbol': 'ETH/USDT:USDT',
            'direction': 'SHORT',
            'entry': 3000.0,
            'exit': 2900.0,
            'gross_pnl_pct': 3.33,
            'gross_pnl_usdt': 100.0,
            'net_pnl_pct': 3.0,
            'net_pnl_usdt': 90.0
        }

        trade_id = db.insert_trade(trade)
        assert trade_id > 0
        db.close()

    def test_get_all_trades_empty(self):
        """Test récupération trades vide"""
        db = TradeDatabase(self.db_path)
        trades = db.get_all_trades()
        assert trades == []
        db.close()

    def test_get_all_trades_with_data(self):
        """Test récupération tous les trades"""
        db = TradeDatabase(self.db_path)

        # Insérer 3 trades
        for i in range(3):
            trade = {
                'timestamp': f'2024-01-15T10:{30+i}:00',
                'date': '2024-01-15',
                'time': f'10:{30+i}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0 + i * 100,
                'exit': 51000.0 + i * 100,
                'gross_pnl_pct': 2.0,
                'gross_pnl_usdt': 100.0,
                'net_pnl_pct': 1.8,
                'net_pnl_usdt': 90.0
            }
            db.insert_trade(trade)

        trades = db.get_all_trades()
        assert len(trades) == 3

        # Vérifier ordre DESC (plus récent en premier)
        assert trades[0]['timestamp'] > trades[1]['timestamp']
        db.close()

    def test_get_all_trades_with_limit(self):
        """Test récupération trades avec limite"""
        db = TradeDatabase(self.db_path)

        # Insérer 5 trades
        for i in range(5):
            trade = {
                'timestamp': f'2024-01-15T10:{30+i}:00',
                'date': '2024-01-15',
                'time': f'10:{30+i}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 51000.0,
                'gross_pnl_pct': 2.0,
                'gross_pnl_usdt': 100.0,
                'net_pnl_pct': 1.8,
                'net_pnl_usdt': 90.0
            }
            db.insert_trade(trade)

        trades = db.get_all_trades(limit=3)
        assert len(trades) == 3
        db.close()

    def test_get_all_trades_with_offset(self):
        """Test récupération trades avec offset"""
        db = TradeDatabase(self.db_path)

        # Insérer 5 trades
        for i in range(5):
            trade = {
                'timestamp': f'2024-01-15T10:{30+i}:00',
                'date': '2024-01-15',
                'time': f'10:{30+i}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 51000.0,
                'gross_pnl_pct': 2.0,
                'gross_pnl_usdt': 100.0,
                'net_pnl_pct': 1.8,
                'net_pnl_usdt': 90.0
            }
            db.insert_trade(trade)

        trades = db.get_all_trades(limit=2, offset=2)
        assert len(trades) == 2
        db.close()

    def test_get_trades_by_date_range(self):
        """Test récupération trades par plage de dates"""
        db = TradeDatabase(self.db_path)

        # Insérer trades sur 3 jours différents
        for day in [14, 15, 16]:
            trade = {
                'timestamp': f'2024-01-{day}T10:30:00',
                'date': f'2024-01-{day}',
                'time': '10:30:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 51000.0,
                'gross_pnl_pct': 2.0,
                'gross_pnl_usdt': 100.0,
                'net_pnl_pct': 1.8,
                'net_pnl_usdt': 90.0
            }
            db.insert_trade(trade)

        # Récupérer seulement les trades du 15
        trades = db.get_trades_by_date_range('2024-01-15', '2024-01-15')
        assert len(trades) == 1
        assert trades[0]['date'] == '2024-01-15'

        # Récupérer trades du 14 au 16
        trades = db.get_trades_by_date_range('2024-01-14', '2024-01-16')
        assert len(trades) == 3
        db.close()

    def test_get_trades_by_symbol(self):
        """Test récupération trades par symbole"""
        db = TradeDatabase(self.db_path)

        # Insérer trades pour différents symboles
        symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'BTC/USDT:USDT']
        for i, symbol in enumerate(symbols):
            trade = {
                'timestamp': f'2024-01-15T10:{30+i}:00',
                'date': '2024-01-15',
                'time': f'10:{30+i}:00',
                'symbol': symbol,
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 51000.0,
                'gross_pnl_pct': 2.0,
                'gross_pnl_usdt': 100.0,
                'net_pnl_pct': 1.8,
                'net_pnl_usdt': 90.0
            }
            db.insert_trade(trade)

        # Récupérer seulement BTC
        trades = db.get_trades_by_symbol('BTC/USDT:USDT')
        assert len(trades) == 2
        assert all(t['symbol'] == 'BTC/USDT:USDT' for t in trades)

        # Récupérer seulement ETH
        trades = db.get_trades_by_symbol('ETH/USDT:USDT')
        assert len(trades) == 1
        assert trades[0]['symbol'] == 'ETH/USDT:USDT'
        db.close()

    def test_get_trades_by_symbol_with_limit(self):
        """Test récupération trades par symbole avec limite"""
        db = TradeDatabase(self.db_path)

        # Insérer 5 trades BTC
        for i in range(5):
            trade = {
                'timestamp': f'2024-01-15T10:{30+i}:00',
                'date': '2024-01-15',
                'time': f'10:{30+i}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 51000.0,
                'gross_pnl_pct': 2.0,
                'gross_pnl_usdt': 100.0,
                'net_pnl_pct': 1.8,
                'net_pnl_usdt': 90.0
            }
            db.insert_trade(trade)

        trades = db.get_trades_by_symbol('BTC/USDT:USDT', limit=3)
        assert len(trades) == 3
        db.close()

    def test_get_statistics_empty(self):
        """Test statistiques avec base vide"""
        db = TradeDatabase(self.db_path)
        stats = db.get_statistics()

        # Devrait retourner des valeurs None ou 0
        assert stats.get('total_trades') == 0 or stats.get('total_trades') is None
        db.close()

    def test_get_statistics_with_data(self):
        """Test statistiques avec données"""
        db = TradeDatabase(self.db_path)

        # Insérer 3 wins et 2 losses
        wins = [
            {'gross_pnl_pct': 2.0, 'gross_pnl_usdt': 100.0, 'fees': 5.0, 'slippage': 2.0, 'duration': 3600},
            {'gross_pnl_pct': 3.0, 'gross_pnl_usdt': 150.0, 'fees': 6.0, 'slippage': 3.0, 'duration': 7200},
            {'gross_pnl_pct': 1.0, 'gross_pnl_usdt': 50.0, 'fees': 4.0, 'slippage': 1.0, 'duration': 1800}
        ]

        losses = [
            {'gross_pnl_pct': -1.5, 'gross_pnl_usdt': -75.0, 'fees': 5.0, 'slippage': 2.0, 'duration': 900},
            {'gross_pnl_pct': -2.0, 'gross_pnl_usdt': -100.0, 'fees': 5.0, 'slippage': 2.0, 'duration': 600}
        ]

        for i, w in enumerate(wins):
            trade = {
                'timestamp': f'2024-01-15T10:{30+i}:00',
                'date': '2024-01-15',
                'time': f'10:{30+i}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 51000.0,
                'gross_pnl_pct': w['gross_pnl_pct'],
                'gross_pnl_usdt': w['gross_pnl_usdt'],
                'net_pnl_pct': w['gross_pnl_pct'] - 0.2,
                'net_pnl_usdt': w['gross_pnl_usdt'] - 10,
                'fees': w['fees'],
                'slippage': w['slippage'],
                'duration': w['duration']
            }
            db.insert_trade(trade)

        for i, l in enumerate(losses):
            trade = {
                'timestamp': f'2024-01-15T11:{30+i}:00',
                'date': '2024-01-15',
                'time': f'11:{30+i}:00',
                'symbol': 'ETH/USDT:USDT',
                'direction': 'SHORT',
                'entry': 3000.0,
                'exit': 3050.0,
                'gross_pnl_pct': l['gross_pnl_pct'],
                'gross_pnl_usdt': l['gross_pnl_usdt'],
                'net_pnl_pct': l['gross_pnl_pct'] - 0.2,
                'net_pnl_usdt': l['gross_pnl_usdt'] - 10,
                'fees': l['fees'],
                'slippage': l['slippage'],
                'duration': l['duration']
            }
            db.insert_trade(trade)

        stats = db.get_statistics()

        assert stats['total_trades'] == 5
        assert stats['wins'] == 3
        assert stats['losses'] == 2
        assert stats['total_pnl_usdt'] == 125.0  # 100 + 150 + 50 - 75 - 100
        db.close()

    def test_close_connection(self):
        """Test fermeture connexion"""
        db = TradeDatabase(self.db_path)
        db.close()

        # Vérifier que la connexion est fermée
        # (tenter une opération devrait échouer)
        with pytest.raises(Exception):
            db.conn.cursor()

    def test_condition_types_serialization(self):
        """Test sérialisation/désérialisation condition_types"""
        db = TradeDatabase(self.db_path)

        trade = {
            'timestamp': '2024-01-15T10:30:00',
            'date': '2024-01-15',
            'time': '10:30:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 51000.0,
            'gross_pnl_pct': 2.0,
            'gross_pnl_usdt': 100.0,
            'net_pnl_pct': 1.8,
            'net_pnl_usdt': 90.0,
            'condition_types': ['EMA_CROSS', 'RSI_OVERSOLD', 'VOLUME_SPIKE']
        }

        db.insert_trade(trade)
        trades = db.get_all_trades()

        assert len(trades) == 1
        assert trades[0]['condition_types'] == ['EMA_CROSS', 'RSI_OVERSOLD', 'VOLUME_SPIKE']
        db.close()

    def test_metadata_serialization(self):
        """Test sérialisation/désérialisation metadata"""
        db = TradeDatabase(self.db_path)

        trade = {
            'timestamp': '2024-01-15T10:30:00',
            'date': '2024-01-15',
            'time': '10:30:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 51000.0,
            'gross_pnl_pct': 2.0,
            'gross_pnl_usdt': 100.0,
            'net_pnl_pct': 1.8,
            'net_pnl_usdt': 90.0,
            'metadata': {
                'rsi': 35.5,
                'volume_spike': 2.5,
                'spread_pct': 0.05
            }
        }

        db.insert_trade(trade)
        trades = db.get_all_trades()

        assert len(trades) == 1
        assert trades[0]['metadata']['rsi'] == 35.5
        assert trades[0]['metadata']['volume_spike'] == 2.5
        db.close()

    def test_init_with_default_path(self):
        """Test initialisation avec chemin par défaut"""
        import sys

        # Sauvegarder sys.argv original
        original_argv = sys.argv.copy()

        try:
            # Simuler lancement avec port 8080
            sys.argv = ['main.py', '8080']

            db = TradeDatabase()
            assert 'trades_instance_8080.db' in db.db_path
            db.close()

            # Cleanup
            if os.path.exists('trades_instance_8080.db'):
                os.remove('trades_instance_8080.db')

        finally:
            # Restaurer sys.argv
            sys.argv = original_argv

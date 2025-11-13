#!/bin/bash
echo "=== DIAGNOSTIC POSTGRESQL DATALOGGER ==="
echo ""

echo "1. Vérification fichier .env"
if [ -f .env ]; then
    echo "✅ .env existe"
    grep POSTGRES .env
else
    echo "❌ .env n'existe pas"
fi
echo ""

echo "2. Test connexion PostgreSQL"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
psql -h "${POSTGRES_HOST:-localhost}" -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-trade_cursor_ml}" -c "SELECT 'Connected' as status;" 2>&1 | head -3
echo ""

echo "3. Nombre de scans/opportunités/trades"
psql -h "${POSTGRES_HOST:-localhost}" -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-trade_cursor_ml}" << 'EOF'
SELECT
    'scan_logs' as table_name, COUNT(*) as count
FROM scan_logs
UNION ALL
SELECT 'opportunities', COUNT(*) FROM opportunities
UNION ALL
SELECT 'trades', COUNT(*) FROM trades;
EOF
echo ""

echo "4. Dernière insertion dans chaque table"
psql -h "${POSTGRES_HOST:-localhost}" -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-trade_cursor_ml}" << 'EOF'
SELECT
    'scan_logs' as table_name,
    MAX(timestamp) as last_insert
FROM scan_logs
UNION ALL
SELECT
    'trades',
    MAX(timestamp_entry)
FROM trades
UNION ALL
SELECT
    'opportunities',
    MAX(timestamp)
FROM opportunities;
EOF
echo ""

echo "5. Vérifier si le bot tourne"
ps aux | grep "python.*main.py" | grep -v grep || echo "❌ Bot non démarré"
echo ""

echo "=== INSTRUCTIONS ==="
echo "Si POSTGRES_ENABLED=false dans .env:"
echo "  1. Éditer .env et mettre POSTGRES_ENABLED=true"
echo "  2. Redémarrer le bot"
echo ""
echo "Si PostgreSQL non connecté:"
echo "  - Vérifier que PostgreSQL tourne: sudo systemctl start postgresql"
echo "  - Ou lancer avec Docker: docker-compose up -d postgres"
echo ""
echo "Si bot non démarré:"
echo "  - Démarrer: python3 main.py 5000"
echo ""
echo "Après redémarrage, vérifier les logs:"
echo "  grep 'Thread de flush périodique' logs/*.log"
echo "  grep 'PostgreSQL DataLogger' logs/*.log"

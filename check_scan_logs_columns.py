import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="trade_cursor_ml",
    user="postgres",
    password="@Cmtr1di12345"
)

cursor = conn.cursor()
cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'scan_logs' 
    ORDER BY ordinal_position
""")

print("Colonnes de scan_logs:")
for row in cursor.fetchall():
    print(f"  {row[0]} ({row[1]})")

conn.close()

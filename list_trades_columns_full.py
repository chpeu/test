import psycopg2

def list_all_columns():
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='trade_cursor_ml',
        user='postgres',
        password='@Cmtr1di12345'
    )
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'trades' ORDER BY column_name")
    columns = [c[0] for c in cur.fetchall()]
    for col in columns:
        print(col)
    conn.close()

if __name__ == "__main__":
    list_all_columns()

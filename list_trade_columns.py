import psycopg2

def list_columns():
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='trade_cursor_ml',
        user='postgres',
        password='@Cmtr1di12345'
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM trades LIMIT 0")
    colnames = [desc[0] for desc in cur.description]
    print(colnames)
    conn.close()

if __name__ == "__main__":
    list_columns()

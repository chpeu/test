from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

pw = quote_plus('@Cmtr1di12345')
e = create_engine(f'postgresql://postgres:{pw}@localhost:5432/trade_cursor_ml')
with e.connect() as c:
    r = c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='trades' ORDER BY ordinal_position"))
    print("Colonnes table trades:")
    for x in r.fetchall():
        print(f"  - {x[0]}")

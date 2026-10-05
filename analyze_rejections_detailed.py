import psycopg2
import pandas as pd

def analyze_rejections():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    print("--- GLOBAL REJECTIONS TODAY ---")
    query = """
        SELECT reject_reason, COUNT(*) as count 
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE 
        AND is_opportunity = FALSE
        AND reject_reason IS NOT NULL
        GROUP BY reject_reason 
        ORDER BY count DESC 
        LIMIT 20
    """
    df = pd.read_sql(query, conn)
    for _, row in df.iterrows():
        print(f"{row['count']:5d} | {row['reject_reason']}")

    print("\n--- MAJOR PAIRS (BTC, ETH, SOL) REJECTIONS TODAY ---")
    query_majors = """
        SELECT reject_reason, COUNT(*) as count 
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE 
        AND is_opportunity = FALSE
        AND (symbol LIKE '%BTC%' OR symbol LIKE '%ETH%' OR symbol LIKE '%SOL%')
        AND reject_reason IS NOT NULL
        GROUP BY reject_reason 
        ORDER BY count DESC
    """
    df_majors = pd.read_sql(query_majors, conn)
    for _, row in df_majors.iterrows():
        print(f"{row['count']:5d} | {row['reject_reason']}")

    conn.close()

if __name__ == "__main__":
    analyze_rejections()

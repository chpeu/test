import psycopg2
import pandas as pd

def analyze_rejections_by_category():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    print("--- REJECTION CATEGORIES TODAY ---")
    query = """
        SELECT reject_reason_category, COUNT(*) as count 
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE 
        AND is_opportunity = FALSE
        AND reject_reason_category IS NOT NULL
        GROUP BY reject_reason_category 
        ORDER BY count DESC
    """
    df = pd.read_sql(query, conn)
    for _, row in df.iterrows():
        print(f"{row['count']:5d} | {row['reject_reason_category']}")

    print("\n--- REJECTION CATEGORIES FOR MAJORS (BTC, ETH, SOL) ---")
    query_majors = """
        SELECT reject_reason_category, COUNT(*) as count 
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE 
        AND is_opportunity = FALSE
        AND (symbol LIKE '%BTC%' OR symbol LIKE '%ETH%' OR symbol LIKE '%SOL%')
        AND reject_reason_category IS NOT NULL
        GROUP BY reject_reason_category 
        ORDER BY count DESC
    """
    df_majors = pd.read_sql(query_majors, conn)
    for _, row in df_majors.iterrows():
        print(f"{row['count']:5d} | {row['reject_reason_category']}")

    conn.close()

if __name__ == "__main__":
    analyze_rejections_by_category()

#!/usr/bin/env python3
"""Analyse détaillée des mismatches P&L"""
import csv, os, re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import psycopg2
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEUIL1 = os.path.join(ROOT, "export mexc feuil 1.csv")

def clean(v): return (v or "").replace("\u200e", "").replace("\u200f", "").strip()
def norm_sym(s):
    s = clean(s).replace(" Perpétuel", "").replace("PERP", "").replace("USDT:USDT", "USDT").replace("/USDT", "USDT").replace("/", "").replace(" ", "")
    return s.upper()

def parse_dt(v):
    txt = clean(v)
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"]:
        try: return datetime.strptime(txt, fmt)
        except: pass
    return None

def parse_amt(v):
    if not v: return None
    txt = clean(v).replace("USDT", "")
    m = re.search(r"[-+]?\d+(?:[\.,]\d+)?", txt)
    return float(m.group(0).replace(",", ".")) if m else None

def load_mexc():
    recs = []
    with open(FEUIL1, "r", encoding="utf-8") as f:
        rdr = csv.reader(f, delimiter=";")
        next(rdr, None)
        for row in rdr:
            if not row or clean(row[0]) == "100.00%" or len(row) < 12: continue
            sym = clean(row[0])
            if not sym: continue
            ts = parse_dt(row[1])
            pnl = parse_amt(row[8]) or 0.0
            fee = parse_amt(row[9])
            red = clean(row[11])
            if red.lower() != "oui" and abs(pnl) < 1e-9: continue
            recs.append({"sym_raw": sym, "sym_norm": norm_sym(sym), "ts": ts, "pnl": pnl, "fee": fee, "dir": clean(row[2])})
    return recs

def get_db():
    load_dotenv()
    conn = psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB") or os.getenv("DB_NAME"),
        user=os.getenv("POSTGRES_USER") or os.getenv("DB_USER"),
        password=os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD"),
        host=os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", "5432")
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT id, symbol, direction, timestamp_entry, timestamp_exit, entry_price, exit_price, pnl_usdt, net_pnl_usdt, fees_usdt, exit_reason
        FROM trades WHERE timestamp_exit BETWEEN '2026-02-01 21:00:00' AND '2026-02-02 08:00:00'
        ORDER BY timestamp_exit ASC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    trades = []
    for r in rows:
        tid, sym, dire, tse, tsx, ep, xp, pnl, net, fee, er = r
        ts = (tsx if tsx else tse)
        if ts and ts.tzinfo:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        trades.append({"id": tid, "sym": sym, "sym_norm": norm_sym(sym), "dir": dire, "ts": ts, "ep": ep, "xp": xp, "pnl": pnl, "net": net, "fee": fee, "er": er})
    return trades

def find_matches(mexc, db):
    db_by_sym = defaultdict(list)
    for t in db: db_by_sym[t["sym_norm"]].append(t)
    for lst in db_by_sym.values(): lst.sort(key=lambda x: x["ts"] or datetime.min)
    
    matches = []
    used = set()
    SHIFT = timedelta(hours=-1)
    for m in sorted(mexc, key=lambda x: x["ts"] or datetime.min):
        ts = m["ts"] + SHIFT if m["ts"] else None
        cand = db_by_sym.get(m["sym_norm"], [])
        best = None
        bd = None
        for d in cand:
            if d["id"] in used or not ts or not d["ts"]: continue
            delta = abs(ts - d["ts"])
            if delta <= timedelta(minutes=2) and (bd is None or delta < bd):
                best, bd = d, delta
        if best:
            used.add(best["id"])
            matches.append((m, best, bd))
    return matches

def main():
    mexc = load_mexc()
    db = get_db()
    matches = find_matches(mexc, db)
    
    print("🔍 ANALYSE DÉTAILLÉE DES MISMATCHES P&L\n" + "="*80)
    
    strong_diff = []
    sign_flip = []
    
    for m, d, dt in matches:
        mp, dp = m["pnl"], (d["pnl"] or 0)
        if abs(mp - dp) > 0.01:
            strong_diff.append((m, d, dt, mp, dp))
            if mp * dp < 0:
                sign_flip.append((m, d, mp, dp))
    
    print(f"\n📊 Total matchés: {len(matches)}")
    print(f"❌ Écarts > 0.01 USDT: {len(strong_diff)}")
    print(f"🔄 Inversions de signe: {len(sign_flip)}")
    
    if sign_flip:
        print("\n" + "="*80)
        print("🚨 INVERSONS DE SIGNE (critique)")
        print("="*80)
        for m, d, mp, dp in sign_flip:
            print(f"\n{m['sym_raw']} | {m['ts']}")
            print(f"  MEXC: {mp:+.4f} USDT | DB: {dp:+.4f} USDT")
            print(f"  DB direction: {d['dir']} | exit_reason: {d['er']}")
            print(f"  Entry: {d['ep']} → Exit: {d['xp']}")
            print(f"  fees_usdt: {d['fee']}, net_pnl_usdt: {d['net']}")
    
    print("\n" + "="*80)
    print("📈 TOP 10 ÉCARTS LES PLUS IMPORTANTS")
    print("="*80)
    for m, d, dt, mp, dp in sorted(strong_diff, key=lambda x: abs(x[3]-x[4]), reverse=True)[:10]:
        diff = abs(mp - dp)
        print(f"\n{m['sym_raw']} | {m['ts']} | Δt {dt}")
        print(f"  MEXC P&L: {mp:+.4f} | DB P&L: {dp:+.4f} | Écart: {diff:.4f}")
        print(f"  DB: {d['dir']} | Entry: {d['ep']} → Exit: {d['xp']} | {d['er']}")

if __name__ == "__main__":
    main()

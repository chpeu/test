#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparer l'historique MEXC (exports CSV) avec les trades PostgreSQL.
"""
import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_FEUIL_1 = os.path.join(ROOT_DIR, "export mexc feuil 1.csv")
EXPORT_FEUIL_2 = os.path.join(ROOT_DIR, "export mexc feuil 2.csv")

TIME_TOLERANCE = timedelta(minutes=2)


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    # Supprimer les marqueurs LTR/RTL invisibles
    return value.replace("\u200e", "").replace("\u200f", "").strip()


def normalize_symbol(symbol: str) -> str:
    s = clean_text(symbol)
    s = s.replace(" Perpétuel", "")
    s = s.replace("PERP", "")
    s = s.replace("USDT:USDT", "USDT")
    s = s.replace("/USDT", "USDT")
    s = s.replace("/", "")
    s = s.replace(" ", "")
    return s.upper()


def parse_amount(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = clean_text(value)
    text = text.replace("USDT", "")
    match = re.search(r"[-+]?\d+(?:[\.,]\d+)?", text)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    text = clean_text(value)
    if not text:
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def load_mexc_feuil_1() -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    with open(EXPORT_FEUIL_1, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter=";")
        header = next(reader, None)
        _ = header
        for row in reader:
            if not row:
                continue
            if clean_text(row[0]) == "100.00%":
                continue
            if len(row) < 12:
                continue
            symbol_raw = clean_text(row[0])
            if not symbol_raw:
                continue
            timestamp = normalize_datetime(parse_datetime(row[1]))
            direction = clean_text(row[2])
            pnl_usdt = parse_amount(row[8])
            fee_usdt = parse_amount(row[9])
            reduce_only = clean_text(row[11])
            if pnl_usdt is None:
                pnl_usdt = 0.0
            is_closing = reduce_only.lower() == "oui" or abs(pnl_usdt) > 1e-9
            if not is_closing:
                continue
            records.append(
                {
                    "symbol_raw": symbol_raw,
                    "symbol_norm": normalize_symbol(symbol_raw),
                    "timestamp": timestamp,
                    "direction": direction,
                    "pnl_usdt": pnl_usdt,
                    "fees_usdt": fee_usdt,
                    "reduce_only": reduce_only,
                }
            )
    return records


def load_mexc_feuil_2() -> Dict[str, Dict[str, object]]:
    grouped: Dict[str, Dict[str, object]] = {}
    with open(EXPORT_FEUIL_2, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter=";")
        header = next(reader, None)
        _ = header
        for row in reader:
            if len(row) < 5:
                continue
            date_str = row[0]
            pair = row[2]
            entry_type = clean_text(row[3])
            if "frais de financement" in entry_type.lower():
                continue
            if "p&l" not in entry_type.lower():
                continue
            timestamp = normalize_datetime(parse_datetime(date_str))
            if not timestamp:
                continue
            pnl_usdt = parse_amount(row[4])
            if pnl_usdt is None:
                continue
            symbol_norm = normalize_symbol(pair)
            key = f"{symbol_norm}|{timestamp.isoformat()}"
            if key not in grouped:
                grouped[key] = {
                    "symbol_raw": clean_text(pair),
                    "symbol_norm": symbol_norm,
                    "timestamp": timestamp,
                    "pnl_usdt": 0.0,
                    "count": 0,
                }
            grouped[key]["pnl_usdt"] += pnl_usdt
            grouped[key]["count"] += 1
    return grouped


def get_db_connection():
    load_dotenv()
    db_name = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME")
    db_user = os.getenv("POSTGRES_USER") or os.getenv("DB_USER")
    db_password = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD")
    db_host = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", "5432")
    return psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
    )


def load_db_trades(start_ts: datetime, end_ts: datetime) -> List[Dict[str, object]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT id, symbol, direction, timestamp_entry, timestamp_exit,
               pnl_usdt, net_pnl_usdt, fees_usdt, created_at
        FROM trades
        WHERE (timestamp_exit BETWEEN %s AND %s)
           OR (created_at BETWEEN %s AND %s)
        ORDER BY COALESCE(timestamp_exit, created_at) ASC
    """
    cursor.execute(query, (start_ts, end_ts, start_ts, end_ts))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    trades: List[Dict[str, object]] = []
    for row in rows:
        (trade_id, symbol, direction, ts_entry, ts_exit, pnl_usdt, net_pnl_usdt, fees_usdt, created_at) = row
        ts = normalize_datetime(ts_exit or created_at)
        trades.append(
            {
                "id": trade_id,
                "symbol_raw": symbol,
                "symbol_norm": normalize_symbol(str(symbol)),
                "direction": direction,
                "timestamp": ts,
                "timestamp_entry": normalize_datetime(ts_entry),
                "timestamp_exit": normalize_datetime(ts_exit),
                "pnl_usdt": float(pnl_usdt) if pnl_usdt is not None else None,
                "net_pnl_usdt": float(net_pnl_usdt) if net_pnl_usdt is not None else None,
                "fees_usdt": float(fees_usdt) if fees_usdt is not None else None,
            }
        )
    return trades


def match_records(
    mexc_records: List[Dict[str, object]],
    db_records: List[Dict[str, object]],
    time_shift: timedelta = timedelta(0),
):
    db_by_symbol: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for trade in db_records:
        db_by_symbol[trade["symbol_norm"]].append(trade)
    for trades in db_by_symbol.values():
        trades.sort(key=lambda t: t["timestamp"] or datetime.min)

    matched = []
    unmatched_mexc = []
    used_db_ids = set()

    for mexc in sorted(mexc_records, key=lambda t: t["timestamp"] or datetime.min):
        candidates = db_by_symbol.get(mexc["symbol_norm"], [])
        best = None
        best_delta = None
        mexc_ts = mexc.get("timestamp")
        if mexc_ts is not None:
            mexc_ts = mexc_ts + time_shift
        for db_trade in candidates:
            if db_trade["id"] in used_db_ids:
                continue
            if mexc_ts is None or db_trade["timestamp"] is None:
                continue
            delta = abs(mexc_ts - db_trade["timestamp"])
            if delta <= TIME_TOLERANCE and (best_delta is None or delta < best_delta):
                best = db_trade
                best_delta = delta
        if best is None:
            unmatched_mexc.append(mexc)
            continue
        used_db_ids.add(best["id"])
        matched.append((mexc, best, best_delta))

    unmatched_db = [trade for trade in db_records if trade["id"] not in used_db_ids]
    return matched, unmatched_mexc, unmatched_db


def find_best_shift(mexc_records: List[Dict[str, object]], db_records: List[Dict[str, object]]) -> timedelta:
    candidates = [timedelta(minutes=offset) for offset in range(-120, 121, 30)]
    best_shift = timedelta(0)
    best_matches = -1
    for shift in candidates:
        matched, _, _ = match_records(mexc_records, db_records, time_shift=shift)
        if len(matched) > best_matches:
            best_matches = len(matched)
            best_shift = shift
    return best_shift


def print_comparison(label: str, matched, unmatched_mexc, unmatched_db):
    print("\n" + "=" * 80)
    print(label)
    print("=" * 80)
    print(f"Total MEXC: {len(matched) + len(unmatched_mexc)}")
    print(f"Total DB:   {len(matched) + len(unmatched_db)}")
    print(f"Matchés:    {len(matched)}")
    print(f"MEXC seuls: {len(unmatched_mexc)}")
    print(f"DB seuls:   {len(unmatched_db)}")

    pnl_mismatches = []
    fee_mismatches = []
    for mexc, db_trade, delta in matched:
        pnl = mexc.get("pnl_usdt")
        db_pnl = db_trade.get("pnl_usdt")
        db_net = db_trade.get("net_pnl_usdt")
        if pnl is not None and db_pnl is not None:
            if abs(pnl - db_pnl) > 0.0005:
                pnl_mismatches.append((mexc, db_trade, pnl, db_pnl, delta))
        fee = mexc.get("fees_usdt")
        db_fee = db_trade.get("fees_usdt")
        if fee is not None and db_fee is not None:
            if abs(fee - db_fee) > 0.0005:
                fee_mismatches.append((mexc, db_trade, fee, db_fee, delta))

    if pnl_mismatches:
        print("\n❌ MISMATCH P&L (pnl_usdt):")
        for mexc, db_trade, pnl, db_pnl, delta in pnl_mismatches[:20]:
            symbol_label = mexc.get("symbol_raw") or mexc.get("symbol_norm") or "?"
            print(
                f"- {symbol_label} {mexc.get('timestamp')} | MEXC {pnl:+.4f} vs DB {db_pnl:+.4f} | Δt {delta}"
            )
        if len(pnl_mismatches) > 20:
            print(f"... ({len(pnl_mismatches) - 20} autres)")
    else:
        print("\n✅ Aucun mismatch P&L (pnl_usdt)")

    if fee_mismatches:
        print("\n⚠️ MISMATCH FRAIS (fees_usdt):")
        for mexc, db_trade, fee, db_fee, delta in fee_mismatches[:20]:
            symbol_label = mexc.get("symbol_raw") or mexc.get("symbol_norm") or "?"
            print(
                f"- {symbol_label} {mexc.get('timestamp')} | MEXC {fee:+.4f} vs DB {db_fee:+.4f} | Δt {delta}"
            )
        if len(fee_mismatches) > 20:
            print(f"... ({len(fee_mismatches) - 20} autres)")
    else:
        print("\n✅ Aucun mismatch frais (fees_usdt) sur les lignes comparables")


def main():
    mexc_feuil1 = load_mexc_feuil_1()
    mexc_feuil2 = load_mexc_feuil_2()

    if not mexc_feuil1:
        print("❌ Aucun enregistrement trouvé dans Feuil 1")
        return

    timestamps = [rec["timestamp"] for rec in mexc_feuil1 if rec["timestamp"]]
    if not timestamps:
        print("❌ Impossible de déterminer la fenêtre temporelle depuis Feuil 1")
        return

    start_ts = min(timestamps) - timedelta(minutes=10)
    end_ts = max(timestamps) + timedelta(minutes=10)

    db_trades = load_db_trades(start_ts, end_ts)

    print("\n📅 Fenêtre analysée:")
    print(f"   {start_ts} → {end_ts}")
    print(f"   Trades DB trouvés: {len(db_trades)}")

    best_shift = find_best_shift(mexc_feuil1, db_trades)
    if best_shift != timedelta(0):
        print(f"\n🕒 Décalage horaire détecté: {best_shift}")

    matched, unmatched_mexc, unmatched_db = match_records(mexc_feuil1, db_trades, time_shift=best_shift)
    print_comparison("COMPARAISON FEUIL 1 (clôtures)", matched, unmatched_mexc, unmatched_db)

    # Comparaison Feuil 2 (P&L agrégé)
    mexc_feuil2_records = list(mexc_feuil2.values())
    matched2, unmatched_mexc2, unmatched_db2 = match_records(mexc_feuil2_records, db_trades, time_shift=best_shift)
    print_comparison("COMPARAISON FEUIL 2 (P&L agrégé)", matched2, unmatched_mexc2, unmatched_db2)


if __name__ == "__main__":
    main()

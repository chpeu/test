#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill trades PnL in PostgreSQL from MEXC export (Feuil 1).
Aggregates reduce-only events within each trade entry/exit window.
"""
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_FEUIL_1 = os.path.join(ROOT_DIR, "export mexc feuil 1.csv")

TIME_TOLERANCE = timedelta(minutes=2)
WINDOW_PAD = timedelta(minutes=2)


def _enable_utf8_stdout() -> None:
    if sys.platform != "win32":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.replace("\u200e", "").replace("\u200f", "").replace("\xa0", " ").strip()


def normalize_symbol(symbol: str) -> str:
    s = clean_text(symbol).upper()
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*(PERPÉTUEL|PERPETUEL|PERPETUAL|PERP)\s*$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s+", "", s)
    if ":" in s:
        s = s.split(":", 1)[0]
    s = s.replace("/", "_").replace("-", "_")
    if s.endswith("USDT") and not s.endswith("_USDT"):
        s = s[:-4] + "_USDT"
    s = re.sub(r"_+", "_", s)
    return s


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


def load_mexc_feuil_1() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with open(EXPORT_FEUIL_1, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter=";")
        _ = next(reader, None)
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
                    "pnl_usdt": float(pnl_usdt),
                    "fees_usdt": float(fee_usdt) if fee_usdt is not None else 0.0,
                }
            )
    return records


def get_db_connection():
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
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


def load_db_trades(conn, start_ts: datetime, end_ts: datetime) -> List[Dict[str, Any]]:
    query = """
        SELECT id, symbol, direction, timestamp_entry, timestamp_exit, created_at,
               size_usdt, pnl_usdt, net_pnl_usdt, fees_usdt, exit_reason
        FROM trades
        WHERE (timestamp_exit BETWEEN %s AND %s)
           OR (created_at BETWEEN %s AND %s)
        ORDER BY COALESCE(timestamp_entry, created_at) ASC
    """
    with conn.cursor() as cur:
        cur.execute(query, (start_ts, end_ts, start_ts, end_ts))
        rows = cur.fetchall()

    trades: List[Dict[str, Any]] = []
    for row in rows:
        (
            trade_id,
            symbol,
            direction,
            ts_entry,
            ts_exit,
            created_at,
            size_usdt,
            pnl_usdt,
            net_pnl_usdt,
            fees_usdt,
            exit_reason,
        ) = row
        ts_entry_norm = normalize_datetime(ts_entry)
        ts_exit_norm = normalize_datetime(ts_exit)
        created_at_norm = normalize_datetime(created_at)
        entry_ts = ts_entry_norm or created_at_norm or ts_exit_norm
        exit_ts = ts_exit_norm or created_at_norm or ts_entry_norm
        if entry_ts and exit_ts and entry_ts > exit_ts:
            entry_ts, exit_ts = exit_ts, entry_ts
        match_ts = ts_exit_norm or created_at_norm or ts_entry_norm
        trades.append(
            {
                "id": trade_id,
                "symbol_raw": symbol,
                "symbol_norm": normalize_symbol(str(symbol)),
                "direction": direction,
                "timestamp_entry": ts_entry_norm,
                "timestamp_exit": ts_exit_norm,
                "created_at": created_at_norm,
                "entry_ts": entry_ts,
                "exit_ts": exit_ts,
                "match_ts": match_ts,
                "size_usdt": float(size_usdt) if size_usdt is not None else None,
                "pnl_usdt": float(pnl_usdt) if pnl_usdt is not None else None,
                "net_pnl_usdt": float(net_pnl_usdt) if net_pnl_usdt is not None else None,
                "fees_usdt": float(fees_usdt) if fees_usdt is not None else None,
                "exit_reason": exit_reason,
            }
        )
    return trades


def match_records(
    mexc_records: List[Dict[str, Any]],
    db_records: List[Dict[str, Any]],
    time_shift: timedelta = timedelta(0),
) -> List[Tuple[Dict[str, Any], Dict[str, Any], timedelta]]:
    db_by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for trade in db_records:
        db_by_symbol[trade["symbol_norm"]].append(trade)
    for trades in db_by_symbol.values():
        trades.sort(key=lambda t: t["match_ts"] or datetime.min)

    matched = []
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
            if mexc_ts is None or db_trade["match_ts"] is None:
                continue
            delta = abs(mexc_ts - db_trade["match_ts"])
            if delta <= TIME_TOLERANCE and (best_delta is None or delta < best_delta):
                best = db_trade
                best_delta = delta
        if best is None:
            continue
        used_db_ids.add(best["id"])
        matched.append((mexc, best, best_delta))

    return matched


def find_best_shift(
    mexc_records: List[Dict[str, Any]],
    db_records: List[Dict[str, Any]],
) -> timedelta:
    candidates = [timedelta(minutes=offset) for offset in range(-120, 121, 30)]
    best_shift = timedelta(0)
    best_matches = -1
    for shift in candidates:
        matched = match_records(mexc_records, db_records, time_shift=shift)
        if len(matched) > best_matches:
            best_matches = len(matched)
            best_shift = shift
    return best_shift


def shift_events(events: List[Dict[str, Any]], shift: timedelta) -> List[Dict[str, Any]]:
    if shift == timedelta(0):
        return events
    shifted = []
    for event in events:
        ts = event.get("timestamp")
        shifted.append(
            {
                **event,
                "timestamp": (ts + shift) if ts else None,
            }
        )
    return shifted


def aggregate_events_by_trade(
    trades: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    window_pad: timedelta = WINDOW_PAD,
) -> Tuple[List[Tuple[Dict[str, Any], List[Dict[str, Any]]]], int, int]:
    events_by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("timestamp") is None:
            continue
        events_by_symbol[event["symbol_norm"]].append(event)
    for evts in events_by_symbol.values():
        evts.sort(key=lambda e: e["timestamp"])

    trades_by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        trades_by_symbol[trade["symbol_norm"]].append(trade)
    for trade_list in trades_by_symbol.values():
        trade_list.sort(key=lambda t: t["entry_ts"] or datetime.min)

    updates: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
    used_events = 0
    skipped_trades = 0

    for symbol, trade_list in trades_by_symbol.items():
        events_list = events_by_symbol.get(symbol, [])
        idx = 0
        for trade in trade_list:
            entry_ts = trade.get("entry_ts")
            exit_ts = trade.get("exit_ts")
            if not entry_ts or not exit_ts:
                skipped_trades += 1
                continue
            window_start = entry_ts - window_pad
            window_end = exit_ts + window_pad

            while idx < len(events_list) and events_list[idx]["timestamp"] < window_start:
                idx += 1
            j = idx
            trade_events = []
            while j < len(events_list) and events_list[j]["timestamp"] <= window_end:
                trade_events.append(events_list[j])
                j += 1
            idx = j
            if trade_events:
                updates.append((trade, trade_events))
                used_events += len(trade_events)
            else:
                skipped_trades += 1

    total_events = sum(len(v) for v in events_by_symbol.values())
    unmatched_events = total_events - used_events
    return updates, skipped_trades, unmatched_events


def get_trade_columns(conn) -> set:
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'trades'
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return {row[0] for row in cur.fetchall()}


def build_update_payload(
    trade: Dict[str, Any],
    events: List[Dict[str, Any]],
    columns: set,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    gross_pnl = round(sum(e.get("pnl_usdt", 0.0) for e in events), 4)
    fees_usdt = round(sum(e.get("fees_usdt", 0.0) for e in events), 4)
    net_pnl = round(gross_pnl - fees_usdt, 4)

    size_usdt = trade.get("size_usdt")
    gross_pnl_pct = None
    net_pnl_pct = None
    if size_usdt:
        gross_pnl_pct = round((gross_pnl / size_usdt) * 100.0, 6)
        net_pnl_pct = round((net_pnl / size_usdt) * 100.0, 6)

    update_map: Dict[str, Any] = {}
    if "pnl_usdt" in columns:
        update_map["pnl_usdt"] = gross_pnl
    if "gross_pnl_usdt" in columns:
        update_map["gross_pnl_usdt"] = gross_pnl
    if "net_pnl_usdt" in columns:
        update_map["net_pnl_usdt"] = net_pnl
    if "fees_usdt" in columns:
        update_map["fees_usdt"] = fees_usdt
    if "total_fees_usdt" in columns:
        update_map["total_fees_usdt"] = fees_usdt
    if gross_pnl_pct is not None:
        if "gross_pnl_pct" in columns:
            update_map["gross_pnl_pct"] = gross_pnl_pct
        if "pnl_pct" in columns:
            update_map["pnl_pct"] = gross_pnl_pct
    if net_pnl_pct is not None and "net_pnl_pct" in columns:
        update_map["net_pnl_pct"] = net_pnl_pct

    return update_map, {
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "fees_usdt": fees_usdt,
        "gross_pnl_pct": gross_pnl_pct,
        "net_pnl_pct": net_pnl_pct,
    }


def apply_updates(conn, updates, columns, execute: bool) -> int:
    updated = 0
    with conn.cursor() as cur:
        for trade, events in updates:
            update_map, _ = build_update_payload(trade, events, columns)
            if not update_map:
                continue
            set_parts = [f"{col} = %s" for col in update_map.keys()]
            params = list(update_map.values()) + [trade["id"]]
            query = f"UPDATE trades SET {', '.join(set_parts)} WHERE id = %s"
            if execute:
                cur.execute(query, params)
            updated += 1
    if execute:
        conn.commit()
    return updated


def main() -> int:
    _enable_utf8_stdout()

    execute = "--execute" in sys.argv
    print("=" * 80)
    print("BACKFILL MEXC PNL -> TRADES")
    print("=" * 80)
    if execute:
        print("Mode: EXECUTION")
    else:
        print("Mode: DRY-RUN")
        print("Use --execute to apply changes")

    if not os.path.exists(EXPORT_FEUIL_1):
        print(f"Export not found: {EXPORT_FEUIL_1}")
        return 1

    events = load_mexc_feuil_1()
    if not events:
        print("No MEXC closing events found.")
        return 1

    timestamps = [e["timestamp"] for e in events if e.get("timestamp")]
    if not timestamps:
        print("No timestamps available in MEXC export.")
        return 1

    start_ts = min(timestamps) - timedelta(minutes=10)
    end_ts = max(timestamps) + timedelta(minutes=10)

    try:
        conn = get_db_connection()
    except Exception as exc:
        print(f"DB connection failed: {type(exc).__name__}: {exc}")
        return 1

    try:
        trades = load_db_trades(conn, start_ts, end_ts)
        if not trades:
            print("No DB trades found in time window.")
            return 1

        best_shift = find_best_shift(events, trades)
        if best_shift != timedelta(0):
            print(f"Detected time shift: {best_shift}")
            events = shift_events(events, best_shift)

        updates, skipped_trades, unmatched_events = aggregate_events_by_trade(trades, events)

        print(f"Total events: {len(events)}")
        print(f"Trades in window: {len(trades)}")
        print(f"Trades with updates: {len(updates)}")
        print(f"Trades skipped (no events or timestamps): {skipped_trades}")
        print(f"Unmatched events: {unmatched_events}")

        columns = get_trade_columns(conn)

        sample = updates[:5]
        if sample:
            print("\nSample updates:")
            for trade, evts in sample:
                payload, summary = build_update_payload(trade, evts, columns)
                print(
                    f"- {trade['symbol_raw']} id={trade['id']} events={len(evts)} "
                    f"gross={summary['gross_pnl']:.4f} fees={summary['fees_usdt']:.4f} "
                    f"net={summary['net_pnl']:.4f}"
                )
                if not payload:
                    print("  (no matching columns to update)")

        updated = apply_updates(conn, updates, columns, execute=execute)

        print("\n" + "=" * 80)
        print("Summary")
        print("=" * 80)
        if execute:
            print(f"Trades updated: {updated}")
        else:
            print(f"Trades that would be updated: {updated}")

        return 0
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

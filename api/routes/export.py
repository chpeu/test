"""
Routes API pour l'exportation de données (CSV, Excel)
"""

import logging
import io
import csv
import os
from typing import Optional, List, Dict, Any, Tuple, Callable
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["export"])

# Variables globales injectées par main.py
_app_state = None

def set_app_state(as_):
    global _app_state
    _app_state = as_


def export_trade_data(format: str = "csv"):
    """Compatibilité tests: export simplifié (sync)."""
    data = _app_state.get('trade_history', []) if _app_state else []
    if format == "json":
        return data
    return {
        "format": format,
        "count": len(data),
    }

@router.get("/export/trades")
async def export_trades_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = "csv"
):
    """
    🔥 PHASE 8: Exporter trades en CSV ou JSON
    """
    trades = _app_state.get('trade_history', []) if _app_state else []
    
    # Filtrer par date si fourni
    if start_date and end_date:
        filtered_trades = [
            t for t in trades
            if start_date <= t.get('date', '') <= end_date
        ]
    else:
        filtered_trades = trades
    
    if format == "json":
        return JSONResponse(filtered_trades)
    
    # Format CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'timestamp', 'date', 'time', 'symbol', 'direction',
        'entry', 'exit', 'gross_pnl_pct', 'gross_pnl_usdt',
        'net_pnl_pct', 'net_pnl_usdt', 'fees', 'slippage',
        'total_costs', 'reason', 'duration'
    ])
    
    writer.writeheader()
    for trade in filtered_trades:
        writer.writerow({
            'timestamp': trade.get('timestamp', ''),
            'date': trade.get('date', ''),
            'time': trade.get('time', ''),
            'symbol': trade.get('symbol', ''),
            'direction': trade.get('direction', ''),
            'entry': trade.get('entry', 0),
            'exit': trade.get('exit', 0),
            'gross_pnl_pct': trade.get('gross_pnl_pct', 0),
            'gross_pnl_usdt': trade.get('gross_pnl_usdt', 0),
            'net_pnl_pct': trade.get('net_pnl_pct', 0),
            'net_pnl_usdt': trade.get('net_pnl_usdt', 0),
            'fees': trade.get('fees', 0),
            'slippage': trade.get('slippage', 0),
            'total_costs': trade.get('total_costs', 0),
            'reason': trade.get('reason', ''),
            'duration': trade.get('duration', 0)
        })
    
    output.seek(0)
    filename = f"trades_{start_date}_{end_date}.csv" if (start_date and end_date) else "trades_all.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def _get_pg_connection_for_export() -> Tuple[Any, Callable[[], None]]:
    """Obtenir une connexion PostgreSQL."""
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
    except Exception:
        pg_datalogger = None

    if pg_datalogger and getattr(pg_datalogger, "enabled", True):
        conn = pg_datalogger._get_connection()
        return conn, lambda: pg_datalogger._return_connection(conn)

    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    return conn, conn.close

@router.get("/datalogger/export/excel")
async def export_datalogger_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
):
    """
    🔥 Export des données du datalogger en Excel (.xlsx)
    """
    limit = max(1, min(limit, 10000))
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        return JSONResponse({
            "success": False, 
            "error": "openpyxl non installé. Installez-le avec 'pip install openpyxl'"
        }, status_code=500)

    try:
        conn, close_conn = _get_pg_connection_for_export()
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        wb = Workbook()
        wb.remove(wb.active)

        # Tables à exporter avec leur colonne de date pour le filtrage/tri
        tables = [
            ("trading_sessions", "start_time"),
            ("config_snapshots", "timestamp"),
            ("scan_logs", "timestamp"),
            ("opportunities", "timestamp"),
            ("trades", "timestamp_entry"),
            ("market_context", "timestamp"),
            ("scan_errors", "timestamp"),
            ("model_predictions", "timestamp"),
            ("features_engineered", "timestamp"),
            ("ml_calibration", "updated_at"),
            ("ml_calibration_history", "created_at"),
            ("circuit_breaker_events", "timestamp"),
            ("market_regime_history", "timestamp"),
            ("pair_performance_stats", "last_updated"),
            ("trade_atr_metrics", "created_at"),
            ("trade_events", "event_timestamp"),
            ("trade_post_exit_analysis", "created_at"),
            ("trade_post_exit_samples", "timestamp")
        ]

        for table_name, date_col in tables:
            query = f"SELECT * FROM {table_name}"
            params = []
            if start_date and end_date:
                query += f" WHERE {date_col}::date BETWEEN %s AND %s"
                params = [start_date, end_date]
            query += f" ORDER BY {date_col} DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            ws = wb.create_sheet(title=table_name.capitalize())
            if not rows:
                ws.append(["Aucune donnée trouvée"])
                continue

            # Header
            headers = list(rows[0].keys())
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            # Data
            for row in rows:
                ws.append([str(v) if v is not None else "" for v in row.values()])

            # Auto-column width
            for i, col in enumerate(headers):
                ws.column_dimensions[get_column_letter(i+1)].width = 20

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        close_conn()

        filename = f"datalogger_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"❌ Erreur export Excel: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get("/config/export-xlsx")
async def api_export_trading_config_xlsx():
    return await _export_trading_config_excel("xlsx")


@router.get("/config/export-xlsm")
async def api_export_trading_config_xlsm():
    """Alias legacy vers l'export XLSX (compatibilité)."""
    return await _export_trading_config_excel("xlsx")
    """Export de la configuration en XLSX (alias)"""
    categories = _organize_trading_config_for_export(TRADING_CONFIG)
    rows = _flatten_trading_config_for_excel(categories)

    wb: Workbook = Workbook()
    ws = wb.active
    ws.title = "Trading_Config"

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    alignment_center = Alignment(horizontal="center")

    headers = ["Catégorie", "Variable", "Valeur"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment_center

    for row in rows:
        ws.append([row['category'], row['variable'], row['value']])

    for col_idx in range(1, len(headers) + 1):
        column_letter = get_column_letter(col_idx)
        ws.column_dimensions[column_letter].width = 35 if col_idx == 1 else 28

    summary_sheet = wb.create_sheet("Autres_Config")
    summary_sheet.append(["Section", "Clé", "Valeur"])
    for cell in summary_sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment_center

    def append_config_block(title: str, config_dict: Dict[str, Any]):
        if not config_dict:
            return
        summary_sheet.append([title, "", ""])
        last_row = summary_sheet.max_row
        for cell in summary_sheet[last_row]:
            cell.font = Font(bold=True)
        for key, value in config_dict.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = value
            summary_sheet.append(["", key, value_str])

    append_config_block("RISK_CONFIG", RISK_CONFIG)
    append_config_block("CONDITION_WEIGHTS", CONDITION_WEIGHTS)
    append_config_block("TREND_BONUS_CONFIG", TREND_BONUS_CONFIG)
    append_config_block("RETRY_CONFIG", RETRY_CONFIG)
    append_config_block("CIRCUIT_BREAKER_CONFIG", CIRCUIT_BREAKER_CONFIG)
    append_config_block("WEBSOCKET_CONFIG", WEBSOCKET_CONFIG)

    for col_idx in range(1, 4):
        summary_sheet.column_dimensions[get_column_letter(col_idx)].width = 35 if col_idx == 1 else 30

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return output


async def _export_trading_config_excel(extension: str = "xlsx"):
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        return JSONResponse({"error": "openpyxl non installé"}, status_code=500)

    try:
        from config import TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, TREND_BONUS_CONFIG
        from config import RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    except Exception as exc:
        return JSONResponse({"error": f"Impossible de charger la configuration: {exc}"}, status_code=500)

    output = _generate_trading_config_workbook(
        TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, 
        TREND_BONUS_CONFIG, RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    )

    filename = f"trading_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

    return StreamingResponse(
        output,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _organize_trading_config_for_export(cfg: Dict[str, Any]) -> Dict[str, List[Tuple[str, Any]]]:
    """Organise TRADING_CONFIG en catégories pour Excel."""
    categories = {
        "Base & Volume": [],
        "Entry Filters": [],
        "Take Profit / Stop Loss": [],
        "Trailing Stop / MFE": [],
        "Protection MFE (Stagnation)": [],
        "Advanced Filters": [],
        "ML & Calibration": [],
        "Adaptive Sizing": [],
        "Market Regime V2": [],
        "Circuit Breaker": [],
        "Others": []
    }
    
    for k, v in cfg.items():
        if any(x in k for x in ['volume', 'multiplier', 'min_score']):
            categories["Base & Volume"].append((k, v))
        elif any(x in k for x in ['tp_', 'sl_', 'tp_sl_', 'profit_target']):
            categories["Take Profit / Stop Loss"].append((k, v))
        elif any(x in k for x in ['trailing_', 'mfe_']):
            categories["Trailing Stop / MFE"].append((k, v))
        elif 'protection_mfe' in k:
            categories["Protection MFE (Stagnation)"].append((k, v))
        elif any(x in k for x in ['use_', 'filter_', 'confirmation', 'whipsaw', 'retest', 'cooldown', 'candle_close', 'momentum', 'micro_']):
            categories["Advanced Filters"].append((k, v))
        elif any(x in k for x in ['ml_', 'calibration_', 'threshold_optimizer', 'drift_']):
            categories["ML & Calibration"].append((k, v))
        elif 'adaptive_sizing' in k:
            categories["Adaptive Sizing"].append((k, v))
        elif 'market_regime' in k:
            categories["Market Regime V2"].append((k, v))
        elif 'trading_cb_' in k or 'trading_circuit_breaker' in k:
            categories["Circuit Breaker"].append((k, v))
        elif 'snr' in k or 'atr_min' in k or 'atr_max' in k:
            categories["Entry Filters"].append((k, v))
        else:
            categories["Others"].append((k, v))
            
    return categories


def _flatten_trading_config_for_excel(categories: Dict[str, List[Tuple[str, Any]]]) -> List[Dict[str, Any]]:
    """Transforme les catégories en liste de lignes pour Excel."""
    rows = []
    for cat_name, items in categories.items():
        if not items: continue
        for var_name, value in sorted(items):
            rows.append({
                "category": cat_name,
                "variable": var_name,
                "value": str(value) if value is not None else ""
            })
    return rows


def _generate_trading_config_workbook(
    trading_config, risk_config, condition_weights, 
    trend_bonus_config, retry_config, circuit_breaker_config, websocket_config
) -> io.BytesIO:
    """Génère le workbook openpyxl."""
    import json
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    categories = _organize_trading_config_for_export(trading_config)
    rows = _flatten_trading_config_for_excel(categories)

    wb = Workbook()
    ws = wb.active
    ws.title = "Trading_Config"

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    alignment_center = Alignment(horizontal="center")

    headers = ["Catégorie", "Variable", "Valeur"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment_center

    for row in rows:
        ws.append([row['category'], row['variable'], row['value']])

    for col_idx in range(1, len(headers) + 1):
        column_letter = get_column_letter(col_idx)
        ws.column_dimensions[column_letter].width = 35 if col_idx == 1 else 28

    summary_sheet = wb.create_sheet("Autres_Config")
    summary_sheet.append(["Section", "Clé", "Valeur"])
    for cell in summary_sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment_center

    def append_config_block(title: str, config_dict: Dict[str, Any]):
        if not config_dict: return
        summary_sheet.append([title, "", ""])
        last_row = summary_sheet.max_row
        for cell in summary_sheet[last_row]:
            cell.font = Font(bold=True)
        for key, value in config_dict.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = value
            summary_sheet.append(["", key, value_str])

    append_config_block("RISK_CONFIG", risk_config)
    append_config_block("CONDITION_WEIGHTS", condition_weights)
    append_config_block("TREND_BONUS_CONFIG", trend_bonus_config)
    append_config_block("RETRY_CONFIG", retry_config)
    append_config_block("CIRCUIT_BREAKER_CONFIG", circuit_breaker_config)
    append_config_block("WEBSOCKET_CONFIG", websocket_config)

    for col_idx in range(1, 4):
        summary_sheet.column_dimensions[get_column_letter(col_idx)].width = 35 if col_idx == 1 else 30

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

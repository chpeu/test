# Endpoints API pour les logs d'erreurs - À ajouter dans main.py

@app.get("/api/logs/errors")
async def api_get_errors(limit: int = 50, offset: int = 0):
    """Récupérer les erreurs avec pagination"""
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
        
        if not pg_datalogger or not pg_datalogger.enabled:
            return JSONResponse({
                "success": True,
                "errors": [],
                "total_count": 0
            })
        
        conn = pg_datalogger._get_connection()
        if not conn:
            return JSONResponse({
                "success": True,
                "errors": [],
                "total_count": 0
            })
        
        try:
            cursor = conn.cursor()
            
            # Compter le total
            cursor.execute("SELECT COUNT(*) FROM scan_errors WHERE error_type IN ('ERROR', 'CRITICAL')")
            total_count = cursor.fetchone()[0]
            
            # Récupérer les erreurs avec pagination
            cursor.execute("""
                SELECT timestamp, error_type, error_message, error_stack
                FROM scan_errors 
                WHERE error_type IN ('ERROR', 'CRITICAL')
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            
            rows = cursor.fetchall()
            errors = []
            for row in rows:
                errors.append({
                    'id': f"error_{row[0].timestamp()}_{hash(row[2])}", 
                    'timestamp': row[0].isoformat(),
                    'level': row[1],  # error_type
                    'message': row[2],  # error_message
                    'detail': row[3]  # error_stack
                })
            
            cursor.close()
            pg_datalogger._return_connection(conn)
            
            return JSONResponse({
                "success": True,
                "errors": errors,
                "total_count": total_count
            })
            
        except Exception as e:
            cursor.close() if 'cursor' in locals() else None
            pg_datalogger._return_connection(conn)
            logger.error(f"Erreur récupération erreurs: {e}")
            return JSONResponse({
                "success": True,
                "errors": [],
                "total_count": 0
            })
            
    except Exception as e:
        logger.error(f"Erreur endpoint /api/logs/errors: {e}")
        return JSONResponse({
            "success": True,
            "errors": [],
            "total_count": 0
        })


@app.get("/api/logs/errors/recent")
async def api_get_recent_errors(limit: int = 50):
    """Récupérer les erreurs récentes"""
    return await api_get_errors(limit=limit, offset=0)


@app.post("/api/logs/errors/clear")
async def api_clear_errors():
    """Vider toutes les erreurs"""
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
        
        if not pg_datalogger or not pg_datalogger.enabled:
            return JSONResponse({"success": True, "message": "Aucune base de données à vider"})
        
        conn = pg_datalogger._get_connection()
        if not conn:
            return JSONResponse({"success": True, "message": "Impossible de se connecter à la base"})
        
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scan_errors WHERE error_type IN ('ERROR', 'CRITICAL')")
            deleted_count = cursor.rowcount
            conn.commit()
            cursor.close()
            pg_datalogger._return_connection(conn)
            
            return JSONResponse({
                "success": True,
                "message": f"{deleted_count} erreurs supprimées"
            })
            
        except Exception as e:
            cursor.close() if 'cursor' in locals() else None
            pg_datalogger._return_connection(conn)
            logger.error(f"Erreur suppression erreurs: {e}")
            return JSONResponse({"success": False, "error": str(e)})
            
    except Exception as e:
        logger.error(f"Erreur endpoint /api/logs/errors/clear: {e}")
        return JSONResponse({"success": False, "error": str(e)})

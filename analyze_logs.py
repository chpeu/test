#!/usr/bin/env python3
"""
📊 ANALYSEUR DE LOGS - Comprendre les rejets
Analyse les logs de l'application pour identifier :
- Top raisons de rejet
- Fréquence des rejets par type
- Patterns de rejet
- Statistiques de validation
"""

import re
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LogAnalyzer:
    """Analyseur de logs pour comprendre les rejets"""
    
    def __init__(self, log_file: str = None):
        self.log_file = log_file
        self.rejection_reasons = Counter()
        self.rejection_by_symbol = defaultdict(list)
        self.validation_stats = {
            'analyzed': 0,
            'valid_setups': 0,
            'no_setup': 0,
            'errors': 0
        }
        self.rejection_patterns = {
            'spread': 0,
            'orderbook': 0,
            'correlation': 0,
            'manipulation': 0,
            'recovery_mode': 0,
            'price_action': 0,
            'score_insuffisant': 0,
            'confluence': 0,
            'other': 0
        }
    
    def parse_log_line(self, line: str) -> Dict:
        """Parser une ligne de log"""
        # Format: YYYY-MM-DD HH:MM:SS - LEVEL - MESSAGE
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)', line)
        if match:
            timestamp, level, message = match.groups()
            return {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }
        return None
    
    def extract_symbol(self, message: str) -> str:
        """Extraire le symbole d'un message"""
        # Patterns possibles: "BTC/USDT:USDT", "BTC_USDT", "BTC"
        match = re.search(r'([A-Z0-9]{2,10})[/_]USDT', message)
        if match:
            return match.group(1)
        
        match = re.search(r'([A-Z0-9]{2,10})/USDT:USDT', message)
        if match:
            return match.group(1)
        
        return "UNKNOWN"
    
    def extract_rejection_reason(self, message: str) -> Tuple[str, str]:
        """
        Extraire la raison de rejet
        
        Returns:
            (category, detail)
        """
        # Spread
        if "Spread trop élevé" in message:
            match = re.search(r'Spread trop élevé \(([^)]+)\)', message)
            detail = match.group(1) if match else "N/A"
            return ("spread", detail)
        
        # Orderbook
        if "Orderbook défavorable" in message:
            match = re.search(r'ratio=([0-9.]+)', message)
            detail = match.group(1) if match else "N/A"
            return ("orderbook", detail)
        
        # Corrélation
        if "Corrélation" in message or "corrélé" in message:
            match = re.search(r'groupe: (\w+)', message)
            detail = match.group(1) if match else "N/A"
            return ("correlation", detail)
        
        # Manipulation
        if "Manipulation" in message:
            return ("manipulation", "pump_dump")
        
        # Recovery Mode
        if "Recovery Mode" in message:
            if "Score insuffisant" in message:
                match = re.search(r'Score insuffisant \(([^)]+)\)', message)
                detail = match.group(1) if match else "N/A"
                return ("recovery_mode", f"Score: {detail}")
            elif "Confluence requise" in message:
                return ("recovery_mode", "Confluence requise")
        
        # Price Action
        if "Price action incohérente" in message:
            return ("price_action", "incohérence")
        
        # Score insuffisant
        if "Score insuffisant" in message:
            match = re.search(r'Score insuffisant \(([^)]+)\)', message)
            detail = match.group(1) if match else "N/A"
            return ("score_insuffisant", detail)
        
        # Confluence
        if "Confluence" in message and "requis" in message:
            return ("confluence", "1m ET 5m requis")
        
        # Autre
        return ("other", message[:50])
    
    def analyze_log_file(self, log_file: str = None):
        """Analyser un fichier de log"""
        if log_file:
            self.log_file = log_file
        
        if not self.log_file:
            logger.error("Aucun fichier de log spécifié")
            return
        
        logger.info(f"📖 Analyse du fichier: {self.log_file}")
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parsed = self.parse_log_line(line)
                    if not parsed:
                        continue
                    
                    message = parsed['message']
                    
                    # Détecter les rejets
                    if "Setup rejeté" in message or "rejeté" in message.lower():
                        symbol = self.extract_symbol(message)
                        category, detail = self.extract_rejection_reason(message)
                        
                        # Enregistrer
                        self.rejection_reasons[f"{category}: {detail}"] += 1
                        self.rejection_by_symbol[symbol].append(category)
                        self.rejection_patterns[category] += 1
                        self.validation_stats['no_setup'] += 1
                    
                    # Détecter les validations
                    elif "Setup trouvé" in message or "Setup validé" in message:
                        self.validation_stats['valid_setups'] += 1
                    
                    # Détecter les analyses
                    elif "Analyse" in message and "paires" in message:
                        match = re.search(r'Analyse (\d+)', message)
                        if match:
                            self.validation_stats['analyzed'] += int(match.group(1))
                    
                    # Détecter les erreurs
                    elif "Erreur" in message or "ERROR" in parsed['level']:
                        self.validation_stats['errors'] += 1
            
            logger.info("✅ Analyse terminée")
            
        except FileNotFoundError:
            logger.error(f"❌ Fichier non trouvé: {self.log_file}")
        except Exception as e:
            logger.error(f"❌ Erreur lecture fichier: {e}")
    
    def generate_report(self) -> Dict:
        """Générer rapport d'analyse"""
        logger.info("\n" + "="*60)
        logger.info("📊 RAPPORT D'ANALYSE DES LOGS")
        logger.info("="*60)
        
        # Stats globales
        logger.info("\n📈 STATISTIQUES GLOBALES")
        logger.info(f"  Paires analysées: {self.validation_stats['analyzed']}")
        logger.info(f"  ✅ Setups valides: {self.validation_stats['valid_setups']}")
        logger.info(f"  ❌ Rejets: {self.validation_stats['no_setup']}")
        logger.info(f"  ⚠️ Erreurs: {self.validation_stats['errors']}")
        
        total = self.validation_stats['analyzed']
        if total > 0:
            valid_pct = self.validation_stats['valid_setups'] / total * 100
            reject_pct = self.validation_stats['no_setup'] / total * 100
            logger.info(f"  Taux validation: {valid_pct:.1f}%")
            logger.info(f"  Taux rejet: {reject_pct:.1f}%")
        
        # Top raisons de rejet
        logger.info("\n🔴 TOP 10 RAISONS DE REJET")
        for i, (reason, count) in enumerate(self.rejection_reasons.most_common(10), 1):
            pct = count / sum(self.rejection_reasons.values()) * 100 if self.rejection_reasons else 0
            logger.info(f"  {i}. {reason}: {count}× ({pct:.1f}%)")
        
        # Patterns de rejet
        logger.info("\n📊 PATTERNS DE REJET")
        total_patterns = sum(self.rejection_patterns.values())
        for category, count in sorted(self.rejection_patterns.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                pct = count / total_patterns * 100 if total_patterns > 0 else 0
                logger.info(f"  {category.upper()}: {count}× ({pct:.1f}%)")
        
        # Symboles les plus rejetés
        logger.info("\n🔴 TOP 10 SYMBOLES LES PLUS REJETÉS")
        symbol_counts = {sym: len(reasons) for sym, reasons in self.rejection_by_symbol.items()}
        sorted_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        for i, (symbol, count) in enumerate(sorted_symbols, 1):
            # Top raisons pour ce symbole
            reasons_count = Counter(self.rejection_by_symbol[symbol])
            top_reason = reasons_count.most_common(1)[0] if reasons_count else ("N/A", 0)
            logger.info(f"  {i}. {symbol}: {count}× rejets (principale: {top_reason[0]})")
        
        # Recommandations
        logger.info("\n💡 RECOMMANDATIONS")
        
        # Identifier le filtre le plus restrictif
        if self.rejection_patterns:
            top_filter = max(self.rejection_patterns.items(), key=lambda x: x[1])
            pct = top_filter[1] / total_patterns * 100 if total_patterns > 0 else 0
            
            if pct > 30:
                logger.info(f"  ⚠️ Filtre '{top_filter[0]}' très restrictif ({pct:.1f}%)")
                
                if top_filter[0] == 'spread':
                    logger.info("     → Augmenter les seuils de spread (FIXE: 0.03%→0.04%, ATR: 0.06%→0.08%)")
                elif top_filter[0] == 'orderbook':
                    logger.info("     → Assouplir les seuils orderbook (LONG: 1.1→1.05, SHORT: 0.95→0.98)")
                elif top_filter[0] == 'score_insuffisant':
                    logger.info("     → Réduire min_score_required (7.5→7.0) ou ajuster CONDITION_WEIGHTS")
                elif top_filter[0] == 'recovery_mode':
                    logger.info("     → Réduire min_score_boost en Recovery Mode (1.5→1.0)")
        
        # Rapport JSON
        report = {
            'stats_globales': self.validation_stats,
            'top_raisons': dict(self.rejection_reasons.most_common(10)),
            'patterns': self.rejection_patterns,
            'symboles_problematiques': dict(sorted_symbols),
            'timestamp': datetime.now().isoformat()
        }
        
        return report
    
    def save_report(self, output_file: str = "log_analysis_report.json"):
        """Sauvegarder le rapport en JSON"""
        report = self.generate_report()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✅ Rapport sauvegardé dans: {output_file}")


def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyser les logs de trade_cursor_py")
    parser.add_argument('log_file', nargs='?', default=None, 
                       help="Fichier de log à analyser (défaut: dernier fichier .log)")
    parser.add_argument('-o', '--output', default="log_analysis_report.json",
                       help="Fichier de sortie JSON")
    
    args = parser.parse_args()
    
    # Si pas de fichier spécifié, chercher le plus récent
    if not args.log_file:
        import glob
        log_files = glob.glob("*.log")
        if log_files:
            args.log_file = max(log_files, key=lambda f: datetime.fromtimestamp(os.path.getmtime(f)))
            logger.info(f"📁 Fichier de log détecté: {args.log_file}")
        else:
            logger.error("❌ Aucun fichier .log trouvé. Spécifiez le chemin manuellement.")
            return
    
    analyzer = LogAnalyzer(args.log_file)
    analyzer.analyze_log_file()
    analyzer.save_report(args.output)


if __name__ == "__main__":
    import os
    main()


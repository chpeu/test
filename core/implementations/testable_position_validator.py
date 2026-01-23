"""
TestablePositionValidator - Validation découplée et testable
Sépare validation métier des vérifications techniques
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from ..interfaces.position_interfaces import (
    IPositionValidator, ValidationResult, PositionSize
)

logger = logging.getLogger(__name__)


class TestablePositionValidator(IPositionValidator):
    """
    Validateur de positions testable
    
    Caractéristiques:
    - Validations isolées et pures
    - Configuration injectable
    - Messages d'erreur détaillés
    - Règles de validation paramétrables
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_rules = self._init_validation_rules()
        logger.info("✅ TestablePositionValidator initialisé")
    
    def validate_setup(self, setup: Dict[str, Any]) -> ValidationResult:
        """
        Valide la configuration complète d'un trade
        
        Args:
            setup: Configuration à valider
            
        Returns:
            ValidationResult: Résultat détaillé de la validation
        """
        errors = []
        warnings = []
        
        try:
            # 1. Validations obligatoires
            errors.extend(self._validate_required_fields(setup))
            
            # 2. Validations des valeurs
            errors.extend(self._validate_field_values(setup))
            
            # 3. Validations métier
            warnings.extend(self._validate_business_rules(setup))
            
            # 4. Validations de cohérence
            errors.extend(self._validate_consistency(setup))
            
            # 5. Validations de sécurité
            security_issues = self._validate_security_constraints(setup)
            errors.extend([issue for issue in security_issues if issue.startswith("ERREUR:")])
            warnings.extend([issue for issue in security_issues if issue.startswith("ATTENTION:")])
            
            is_valid = len(errors) == 0
            
            if is_valid:
                logger.debug(f"✅ Setup validé avec {len(warnings)} warnings")
            else:
                logger.warning(f"❌ Setup invalide: {len(errors)} erreurs, {len(warnings)} warnings")
            
            return ValidationResult(is_valid, errors, warnings)
            
        except Exception as e:
            logger.error(f"Erreur validation setup: {e}")
            return ValidationResult.error([f"Erreur validation: {str(e)}"])
    
    def validate_market_conditions(self, symbol: str) -> ValidationResult:
        """
        Valide les conditions de marché pour un symbol
        
        Args:
            symbol: Symbol à valider
            
        Returns:
            ValidationResult: Résultat de validation marché
        """
        errors = []
        warnings = []
        
        try:
            # 1. Validation format symbol
            if not self._is_valid_symbol_format(symbol):
                errors.append(f"Format symbol invalide: {symbol}")
            
            # 2. Vérification symbol actif (simulation)
            if not self._is_symbol_active(symbol):
                errors.append(f"Symbol inactif ou non tradable: {symbol}")
            
            # 3. Conditions de marché
            market_warnings = self._check_market_conditions(symbol)
            warnings.extend(market_warnings)
            
            # 4. Vérifications techniques
            tech_issues = self._check_technical_conditions(symbol)
            warnings.extend(tech_issues)
            
            is_valid = len(errors) == 0
            
            logger.debug(f"Validation marché {symbol}: {'✅' if is_valid else '❌'}")
            
            return ValidationResult(is_valid, errors, warnings)
            
        except Exception as e:
            logger.error(f"Erreur validation marché: {e}")
            return ValidationResult.error([f"Erreur validation marché: {str(e)}"])
    
    def validate_risk_parameters(self, position_size: PositionSize, capital: float) -> ValidationResult:
        """
        Valide les paramètres de risque d'une position
        
        Args:
            position_size: Taille calculée de la position
            capital: Capital disponible
            
        Returns:
            ValidationResult: Résultat validation risque
        """
        errors = []
        warnings = []
        
        try:
            # 1. Validation taille position
            if not position_size.is_valid:
                errors.append("Position size invalide")
            
            # 2. Validation capital requis
            capital_issues = self._validate_capital_requirements(position_size, capital)
            errors.extend(capital_issues)
            
            # 3. Validation risque par trade
            risk_issues = self._validate_risk_per_trade(position_size, capital)
            errors.extend([issue for issue in risk_issues if issue.startswith("ERREUR:")])
            warnings.extend([issue for issue in risk_issues if issue.startswith("ATTENTION:")])
            
            # 4. Validation distance SL/TP
            distance_issues = self._validate_sl_tp_distances(position_size)
            warnings.extend(distance_issues)
            
            # 5. Validation limites de position
            limit_issues = self._validate_position_limits(position_size, capital)
            errors.extend(limit_issues)
            
            is_valid = len(errors) == 0
            
            logger.debug(f"Validation risque: {'✅' if is_valid else '❌'} (risque: {position_size.risk_percentage:.2f}%)")
            
            return ValidationResult(is_valid, errors, warnings)
            
        except Exception as e:
            logger.error(f"Erreur validation risque: {e}")
            return ValidationResult.error([f"Erreur validation risque: {str(e)}"])
    
    def _init_validation_rules(self) -> Dict[str, Any]:
        """Initialise les règles de validation configurables"""
        return {
            'required_fields': ['symbol', 'side', 'current_price'],
            'optional_fields': ['score_1m', 'score_5m', 'atr', 'volume', 'risk_percentage'],
            'min_score': self.config.get('min_score', 3.0),
            'max_risk_per_trade': self.config.get('max_risk_per_trade', 5.0),
            'min_price': 0.00001,  # Prix minimum valide
            'max_position_value': self.config.get('max_position_value', 10000.0),
            'allowed_sides': ['long', 'short'],
            'min_atr_ratio': 0.005,  # ATR minimum = 0.5% du prix
            'max_atr_ratio': 0.10,   # ATR maximum = 10% du prix
            'min_volume': self.config.get('min_volume', 100000),  # Volume 24h minimum
        }
    
    def _validate_required_fields(self, setup: Dict[str, Any]) -> List[str]:
        """Valide les champs obligatoires"""
        errors = []
        
        for field in self.validation_rules['required_fields']:
            if field not in setup:
                errors.append(f"Champ obligatoire manquant: {field}")
            elif setup[field] is None or setup[field] == "":
                errors.append(f"Champ obligatoire vide: {field}")
        
        return errors
    
    def _validate_field_values(self, setup: Dict[str, Any]) -> List[str]:
        """Valide les valeurs des champs"""
        errors = []
        
        # Prix courant
        if 'current_price' in setup:
            try:
                price = float(setup['current_price'])
                if price <= self.validation_rules['min_price']:
                    errors.append(f"Prix trop faible: {price}")
                if price > 1000000:  # Prix maximum raisonnable
                    errors.append(f"Prix trop élevé: {price}")
            except (ValueError, TypeError):
                errors.append("Prix courant invalide (doit être numérique)")
        
        # Side
        if 'side' in setup:
            side = str(setup['side']).lower()
            if side not in self.validation_rules['allowed_sides']:
                errors.append(f"Side invalide: {side} (autorisés: {self.validation_rules['allowed_sides']})")
        
        # Scores (si présents)
        for score_field in ['score_1m', 'score_5m']:
            if score_field in setup:
                try:
                    score = float(setup[score_field])
                    if not (0.0 <= score <= 10.0):
                        errors.append(f"{score_field} hors limites: {score} (doit être 0-10)")
                except (ValueError, TypeError):
                    errors.append(f"{score_field} invalide (doit être numérique)")
        
        # ATR (si présent)
        if 'atr' in setup and 'current_price' in setup:
            try:
                atr = float(setup['atr'])
                price = float(setup['current_price'])
                atr_ratio = atr / price
                
                if atr_ratio < self.validation_rules['min_atr_ratio']:
                    errors.append(f"ATR trop faible: {atr} ({atr_ratio*100:.2f}% du prix)")
                elif atr_ratio > self.validation_rules['max_atr_ratio']:
                    errors.append(f"ATR trop élevé: {atr} ({atr_ratio*100:.2f}% du prix)")
            except (ValueError, TypeError):
                errors.append("ATR invalide (doit être numérique)")
        
        return errors
    
    def _validate_business_rules(self, setup: Dict[str, Any]) -> List[str]:
        """Valide les règles métier (warnings)"""
        warnings = []
        
        # Score minimum recommandé
        for score_field in ['score_1m', 'score_5m']:
            if score_field in setup:
                try:
                    score = float(setup[score_field])
                    if score < self.validation_rules['min_score']:
                        warnings.append(f"ATTENTION: {score_field} faible: {score} (recommandé: >{self.validation_rules['min_score']})")
                except:
                    pass  # Déjà validé dans field_values
        
        # Volume recommandé
        if 'volume' in setup:
            try:
                volume = float(setup['volume'])
                if volume < self.validation_rules['min_volume']:
                    warnings.append(f"ATTENTION: Volume faible: {volume} (recommandé: >{self.validation_rules['min_volume']})")
            except:
                pass
        
        # Cohérence scores 1m vs 5m
        if 'score_1m' in setup and 'score_5m' in setup:
            try:
                score_1m = float(setup['score_1m'])
                score_5m = float(setup['score_5m'])
                diff = abs(score_1m - score_5m)
                
                if diff > 3.0:
                    warnings.append(f"ATTENTION: Divergence scores importante: 1m={score_1m}, 5m={score_5m}")
            except:
                pass
        
        return warnings
    
    def _validate_consistency(self, setup: Dict[str, Any]) -> List[str]:
        """Valide la cohérence entre champs"""
        errors = []
        
        # Vérifier cohérence prix/ATR si les deux présents
        if 'current_price' in setup and 'atr' in setup:
            try:
                price = float(setup['current_price'])
                atr = float(setup['atr'])
                
                # ATR ne peut pas être supérieur au prix
                if atr > price:
                    errors.append(f"ATR ({atr}) supérieur au prix ({price})")
            except:
                pass  # Déjà validé ailleurs
        
        # Vérifier cohérence symbol/side (si règles spécifiques)
        # Par exemple: certains symbols ne supportent que long
        # (logique à étendre selon besoins)
        
        return errors
    
    def _validate_security_constraints(self, setup: Dict[str, Any]) -> List[str]:
        """Valide les contraintes de sécurité"""
        issues = []
        
        # Vérification des heures de trading (simulation)
        current_hour = datetime.now().hour
        if not (6 <= current_hour <= 22):  # Trading recommandé 6h-22h
            issues.append("ATTENTION: Trading en dehors des heures recommandées")
        
        # Vérification fréquence trading (éviter overtrading)
        # (simulation - en production, vérifier historique récent)
        
        # Risque configuré
        if 'risk_percentage' in setup:
            try:
                risk = float(setup['risk_percentage'])
                if risk > self.validation_rules['max_risk_per_trade']:
                    issues.append(f"ERREUR: Risque trop élevé: {risk}% (max: {self.validation_rules['max_risk_per_trade']}%)")
                elif risk > 3.0:
                    issues.append(f"ATTENTION: Risque élevé: {risk}%")
            except:
                pass
        
        return issues
    
    def _validate_capital_requirements(self, position_size: PositionSize, capital: float) -> List[str]:
        """Valide les exigences de capital"""
        errors = []
        
        if capital <= 0:
            errors.append("Capital invalide ou insuffisant")
            return errors
        
        # Capital requis pour la position
        required_capital = position_size.final_size
        if required_capital > capital:
            errors.append(f"Capital insuffisant: requis {required_capital}, disponible {capital}")
        
        # Marge de sécurité (garder au moins 20% du capital)
        safety_margin = 0.20
        max_usable_capital = capital * (1 - safety_margin)
        
        if required_capital > max_usable_capital:
            errors.append(f"Position trop importante: utilise {required_capital} sur {capital} disponible (marge sécurité: {safety_margin*100}%)")
        
        return errors
    
    def _validate_risk_per_trade(self, position_size: PositionSize, capital: float) -> List[str]:
        """Valide le risque par trade"""
        issues = []
        
        risk_pct = position_size.risk_percentage
        max_risk = self.validation_rules['max_risk_per_trade']
        
        if risk_pct > max_risk:
            issues.append(f"ERREUR: Risque par trade trop élevé: {risk_pct:.2f}% (max: {max_risk}%)")
        elif risk_pct > 3.0:
            issues.append(f"ATTENTION: Risque par trade élevé: {risk_pct:.2f}%")
        elif risk_pct < 0.5:
            issues.append(f"ATTENTION: Risque par trade très faible: {risk_pct:.2f}%")
        
        return issues
    
    def _validate_sl_tp_distances(self, position_size: PositionSize) -> List[str]:
        """Valide les distances SL/TP"""
        warnings = []
        
        sl_distance = position_size.stop_loss_distance
        tp_distance = position_size.take_profit_distance
        
        # Ratio SL/TP (risk/reward)
        if sl_distance > 0 and tp_distance > 0:
            risk_reward_ratio = tp_distance / sl_distance
            
            if risk_reward_ratio < 1.5:
                warnings.append(f"ATTENTION: Ratio risk/reward faible: 1:{risk_reward_ratio:.2f}")
            elif risk_reward_ratio > 5.0:
                warnings.append(f"ATTENTION: Ratio risk/reward très élevé: 1:{risk_reward_ratio:.2f}")
        
        # SL trop proche ou trop éloigné
        if sl_distance <= 0:
            warnings.append("ATTENTION: Distance SL invalide")
        
        if tp_distance <= 0:
            warnings.append("ATTENTION: Distance TP invalide")
        
        return warnings
    
    def _validate_position_limits(self, position_size: PositionSize, capital: float) -> List[str]:
        """Valide les limites de position"""
        errors = []
        
        # Taille minimum
        if position_size.final_size < self.config.get('min_position_size', 10.0):
            errors.append(f"Position trop petite: {position_size.final_size}")
        
        # Taille maximum
        max_size = self.validation_rules['max_position_value']
        if position_size.final_size > max_size:
            errors.append(f"Position trop importante: {position_size.final_size} (max: {max_size})")
        
        return errors
    
    def _is_valid_symbol_format(self, symbol: str) -> bool:
        """Vérifie le format du symbol"""
        if not isinstance(symbol, str) or len(symbol) < 3:
            return False
        
        # Format attendu: BTCUSDT, ETHUSDT, etc.
        if not symbol.isupper():
            return False
        
        # Doit se terminer par USDT (pour l'exemple)
        if not symbol.endswith('USDT'):
            return False
        
        return True
    
    def _is_symbol_active(self, symbol: str) -> bool:
        """Vérifie si le symbol est actif (simulation)"""
        # En production: vérifier avec l'API exchange
        # Pour simulation: accepter symbols USDT courants
        common_symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT',
            'SOLUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT', 'DOTUSDT'
        ]
        
        return symbol in common_symbols
    
    def _check_market_conditions(self, symbol: str) -> List[str]:
        """Vérifie les conditions de marché (simulation)"""
        warnings = []
        
        # Simulation: conditions de marché aléatoires
        # En production: vérifier volatilité, volume, spread, etc.
        
        return warnings
    
    def _check_technical_conditions(self, symbol: str) -> List[str]:
        """Vérifie les conditions techniques (simulation)"""
        warnings = []
        
        # Simulation: vérifications techniques
        # En production: vérifier connectivity, latence, etc.
        
        return warnings

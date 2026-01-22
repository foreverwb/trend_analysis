"""
Delta Calculation Service
Calculates 3D/5D changes for all metrics
"""
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models import HistoricalData, SectorETF, IndustryETF, MomentumStock, MarketRegime

logger = logging.getLogger(__name__)


class DeltaCalculationService:
    """Service for calculating 3D/5D delta values for all metrics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_historical_metrics(
        self, 
        symbol: str, 
        data_type: str, 
        target_date: date
    ) -> Optional[Dict]:
        """Get historical metrics for a specific date"""
        record = self.db.query(HistoricalData).filter(
            and_(
                HistoricalData.symbol == symbol,
                HistoricalData.data_type == data_type,
                HistoricalData.data_date == target_date
            )
        ).first()
        
        return record.metrics if record else None
    
    def _calculate_delta(
        self, 
        current: Any, 
        historical: Any, 
        is_percentage: bool = False
    ) -> Optional[Any]:
        """Calculate delta between current and historical value"""
        if current is None or historical is None:
            return None
        
        try:
            if isinstance(current, str):
                # Handle percentage strings like "+12.3%"
                current_val = float(current.replace('%', '').replace('+', ''))
                historical_val = float(historical.replace('%', '').replace('+', ''))
            else:
                current_val = float(current)
                historical_val = float(historical)
            
            delta = current_val - historical_val
            
            if is_percentage:
                return f"+{delta:.2f}%" if delta >= 0 else f"{delta:.2f}%"
            else:
                return round(delta, 2)
        except (ValueError, TypeError):
            return None
    
    def save_current_metrics(
        self, 
        symbol: str, 
        data_type: str, 
        metrics: Dict
    ):
        """Save current metrics as historical record"""
        today = date.today()
        
        # Check if already exists
        existing = self.db.query(HistoricalData).filter(
            and_(
                HistoricalData.symbol == symbol,
                HistoricalData.data_type == data_type,
                HistoricalData.data_date == today
            )
        ).first()
        
        if existing:
            existing.metrics = metrics
        else:
            record = HistoricalData(
                symbol=symbol,
                data_type=data_type,
                metrics=metrics,
                data_date=today
            )
            self.db.add(record)
        
        self.db.commit()
    
    def calculate_etf_deltas(self, etf: SectorETF | IndustryETF) -> Dict[str, Dict]:
        """Calculate 3D and 5D deltas for an ETF"""
        today = date.today()
        date_3d = today - timedelta(days=3)
        date_5d = today - timedelta(days=5)
        
        data_type = "sector_etf" if isinstance(etf, SectorETF) else "industry_etf"
        
        # Get historical data
        hist_3d = self._get_historical_metrics(etf.symbol, data_type, date_3d)
        hist_5d = self._get_historical_metrics(etf.symbol, data_type, date_5d)
        
        # Current metrics
        current = {
            "composite_score": etf.composite_score,
            "rel_momentum_score": etf.rel_momentum_score,
            "rel_momentum_value": etf.rel_momentum_value,
            "trend_quality_score": etf.trend_quality_score,
            "breadth_score": etf.breadth_score,
            "pct_above_50ma": etf.pct_above_50ma,
            "pct_above_200ma": etf.pct_above_200ma,
            "options_score": etf.options_score,
            "ivr": etf.ivr,
            "rs_5d": etf.rs_5d,
            "rs_20d": etf.rs_20d,
            "rs_63d": etf.rs_63d,
            "ma20_slope": etf.ma20_slope
        }
        
        # Save current as historical
        self.save_current_metrics(etf.symbol, data_type, current)
        
        delta_3d = {}
        delta_5d = {}
        
        if hist_3d:
            delta_3d = {
                "composite_score": self._calculate_delta(current["composite_score"], hist_3d.get("composite_score")),
                "rel_momentum_score": self._calculate_delta(current["rel_momentum_score"], hist_3d.get("rel_momentum_score")),
                "trend_quality_score": self._calculate_delta(current["trend_quality_score"], hist_3d.get("trend_quality_score")),
                "breadth_score": self._calculate_delta(current["breadth_score"], hist_3d.get("breadth_score")),
                "options_score": self._calculate_delta(current["options_score"], hist_3d.get("options_score")),
                "ivr": self._calculate_delta(current["ivr"], hist_3d.get("ivr")),
                "rs_20d": self._calculate_delta(current["rs_20d"], hist_3d.get("rs_20d")),
            }
        
        if hist_5d:
            delta_5d = {
                "composite_score": self._calculate_delta(current["composite_score"], hist_5d.get("composite_score")),
                "rel_momentum_score": self._calculate_delta(current["rel_momentum_score"], hist_5d.get("rel_momentum_score")),
                "trend_quality_score": self._calculate_delta(current["trend_quality_score"], hist_5d.get("trend_quality_score")),
                "breadth_score": self._calculate_delta(current["breadth_score"], hist_5d.get("breadth_score")),
                "options_score": self._calculate_delta(current["options_score"], hist_5d.get("options_score")),
                "ivr": self._calculate_delta(current["ivr"], hist_5d.get("ivr")),
                "rs_20d": self._calculate_delta(current["rs_20d"], hist_5d.get("rs_20d")),
            }
        
        return {"delta_3d": delta_3d, "delta_5d": delta_5d}
    
    def calculate_stock_deltas(self, stock: MomentumStock) -> Dict[str, Dict]:
        """Calculate 3D and 5D deltas for a momentum stock"""
        today = date.today()
        date_3d = today - timedelta(days=3)
        date_5d = today - timedelta(days=5)
        
        hist_3d = self._get_historical_metrics(stock.symbol, "momentum_stock", date_3d)
        hist_5d = self._get_historical_metrics(stock.symbol, "momentum_stock", date_5d)
        
        current = {
            "final_score": stock.final_score,
            "price": stock.price,
            "price_momentum_score": stock.price_momentum_score,
            "trend_structure_score": stock.trend_structure_score,
            "volume_price_score": stock.volume_price_score,
            "quality_filter_score": stock.quality_filter_score,
            "options_overlay_score": stock.options_overlay_score,
            "options_ivr": stock.options_ivr,
            "volume_spike": stock.volume_spike,
            "atr_percent": stock.atr_percent
        }
        
        self.save_current_metrics(stock.symbol, "momentum_stock", current)
        
        delta_3d = {}
        delta_5d = {}
        
        if hist_3d:
            delta_3d = {
                "final_score": self._calculate_delta(current["final_score"], hist_3d.get("final_score")),
                "price": self._calculate_delta(current["price"], hist_3d.get("price")),
                "price_momentum_score": self._calculate_delta(current["price_momentum_score"], hist_3d.get("price_momentum_score")),
                "trend_structure_score": self._calculate_delta(current["trend_structure_score"], hist_3d.get("trend_structure_score")),
                "volume_price_score": self._calculate_delta(current["volume_price_score"], hist_3d.get("volume_price_score")),
                "options_ivr": self._calculate_delta(current["options_ivr"], hist_3d.get("options_ivr")),
            }
        
        if hist_5d:
            delta_5d = {
                "final_score": self._calculate_delta(current["final_score"], hist_5d.get("final_score")),
                "price": self._calculate_delta(current["price"], hist_5d.get("price")),
                "price_momentum_score": self._calculate_delta(current["price_momentum_score"], hist_5d.get("price_momentum_score")),
                "trend_structure_score": self._calculate_delta(current["trend_structure_score"], hist_5d.get("trend_structure_score")),
                "volume_price_score": self._calculate_delta(current["volume_price_score"], hist_5d.get("volume_price_score")),
                "options_ivr": self._calculate_delta(current["options_ivr"], hist_5d.get("options_ivr")),
            }
        
        return {"delta_3d": delta_3d, "delta_5d": delta_5d}
    
    def calculate_market_deltas(self, regime: MarketRegime) -> Dict[str, Dict]:
        """Calculate 3D and 5D deltas for market regime"""
        today = date.today()
        date_3d = today - timedelta(days=3)
        date_5d = today - timedelta(days=5)
        
        hist_3d = self._get_historical_metrics("MARKET", "market_regime", date_3d)
        hist_5d = self._get_historical_metrics("MARKET", "market_regime", date_5d)
        
        current = {
            "spy_price": regime.spy_price,
            "vix": regime.vix,
            "breadth": regime.breadth,
            "spy_20ma_slope": regime.spy_20ma_slope
        }
        
        self.save_current_metrics("MARKET", "market_regime", current)
        
        delta_3d = {}
        delta_5d = {}
        
        if hist_3d:
            delta_3d = {
                "spy_price": self._calculate_delta(current["spy_price"], hist_3d.get("spy_price")),
                "vix": self._calculate_delta(current["vix"], hist_3d.get("vix")),
                "breadth": self._calculate_delta(current["breadth"], hist_3d.get("breadth")),
            }
        
        if hist_5d:
            delta_5d = {
                "spy_price": self._calculate_delta(current["spy_price"], hist_5d.get("spy_price")),
                "vix": self._calculate_delta(current["vix"], hist_5d.get("vix")),
                "breadth": self._calculate_delta(current["breadth"], hist_5d.get("breadth")),
            }
        
        return {"delta_3d": delta_3d, "delta_5d": delta_5d}
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove historical data older than specified days"""
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        
        self.db.query(HistoricalData).filter(
            HistoricalData.data_date < cutoff_date
        ).delete()
        
        self.db.commit()
        logger.info(f"Cleaned up historical data older than {cutoff_date}")

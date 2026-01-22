"""
Calculation Service for Scoring
Implements the scoring methodology from the design document
"""
from typing import Optional, Dict, List, Any
from datetime import datetime, date
import numpy as np
import logging
from sqlalchemy.orm import Session

from ..models import (
    SectorETF, IndustryETF, MomentumStock, MarketRegime,
    FinvizData, MarketChameleonData, FutuOptionsData, HistoricalData
)

logger = logging.getLogger(__name__)


class CalculationService:
    """Service for calculating scores based on the design methodology"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Market Regime ====================
    def calculate_market_regime(self, spy_data: Dict, vix: float, breadth_pct: float) -> str:
        """
        Calculate market regime (A/B/C)
        A档（Risk-On，满火力）: SPY > 50MA, 20MA斜率 > 0, 广度 > 50%
        B档（Neutral，半火力）: 中性
        C档（Risk-Off，低火力）: SPY < 50MA, 20D收益为负
        """
        price = spy_data.get("price", 0)
        ma50 = spy_data.get("ma50", 0)
        ma20_slope = spy_data.get("ma20_slope", 0)
        
        # A档条件
        if price > ma50 and ma20_slope > 0 and breadth_pct > 50:
            return "A"
        
        # C档条件
        if price < ma50 and ma20_slope < 0:
            return "C"
        
        # 默认B档
        return "B"
    
    def update_market_regime(self, spy_data: Dict, vix: float, breadth_pct: float) -> MarketRegime:
        """Update or create market regime record"""
        today = date.today()
        
        regime = self.db.query(MarketRegime).filter(MarketRegime.date == today).first()
        if not regime:
            regime = MarketRegime(date=today)
            self.db.add(regime)
        
        status = self.calculate_market_regime(spy_data, vix, breadth_pct)
        
        price = spy_data.get("price", 0)
        ma200 = spy_data.get("ma200", 0)
        ma50 = spy_data.get("ma50", 0)
        
        regime.status = status
        regime.spy_price = price
        regime.spy_vs_200ma = f"+{((price - ma200) / ma200 * 100):.1f}%" if ma200 > 0 else "+0.0%"
        regime.spy_vs_50ma = f"+{((price - ma50) / ma50 * 100):.1f}%" if ma50 > 0 else "+0.0%"
        regime.spy_trend = "up" if spy_data.get("ma20_slope", 0) > 0 else "down"
        regime.vix = vix
        regime.breadth = breadth_pct
        regime.spy_20ma = spy_data.get("ma20", 0)
        regime.spy_50ma = ma50
        regime.spy_200ma = ma200
        regime.spy_20ma_slope = spy_data.get("ma20_slope", 0)
        
        self.db.commit()
        return regime
    
    # ==================== ETF Scoring ====================
    def calculate_etf_composite_score(
        self,
        rel_momentum_score: float,
        trend_quality_score: float,
        breadth_score: float,
        options_score: float
    ) -> float:
        """
        Calculate composite score for ETF
        权重: 0.55 · Price/RS + 0.20 · Breadth + 0.25 · Options
        其中 Price/RS = 0.65 · RelMom + 0.35 · TrendQuality
        """
        price_rs_score = 0.65 * rel_momentum_score + 0.35 * trend_quality_score
        composite = 0.55 * price_rs_score + 0.20 * breadth_score + 0.25 * options_score
        return round(composite, 1)
    
    def calculate_rel_momentum_score(self, metrics: Dict) -> tuple:
        """
        Calculate relative momentum score
        RelMom = 0.45 · RS_20D + 0.35 · RS_63D + 0.20 · RS_5D
        """
        rs_5d = metrics.get("rs_5d", 1)
        rs_20d = metrics.get("rs_20d", 1)
        rs_63d = metrics.get("rs_63d", 1)
        
        # Convert RS ratios to percentage changes
        rs_5d_pct = (rs_5d - 1) * 100
        rs_20d_pct = (rs_20d - 1) * 100
        rs_63d_pct = (rs_63d - 1) * 100
        
        rel_mom = 0.45 * rs_20d_pct + 0.35 * rs_63d_pct + 0.20 * rs_5d_pct
        
        # Normalize to 0-100 score (assuming ±20% is extreme)
        score = min(100, max(0, 50 + rel_mom * 2.5))
        
        value = f"+{rel_mom:.1f}%" if rel_mom >= 0 else f"{rel_mom:.1f}%"
        
        return round(score, 1), value
    
    def calculate_trend_quality_score(self, metrics: Dict) -> tuple:
        """
        Calculate trend quality score
        - 价格 > 50DMA
        - 20DMA > 50DMA
        - 20DMA 斜率 > 0
        - 回撤结构
        """
        score = 50  # Base score
        
        # Price above 50DMA (+20)
        if metrics.get("price_above_50ma", False):
            score += 20
        
        # 20DMA above 50DMA (+15)
        if metrics.get("ma20_above_50ma", False):
            score += 15
        
        # 20DMA slope positive (+10)
        ma20_slope = metrics.get("ma20_slope", 0)
        if ma20_slope > 0:
            score += 10
        elif ma20_slope > -0.01:
            score += 5
        
        # Max drawdown penalty
        max_dd = abs(metrics.get("max_drawdown_20d", 0))
        if max_dd < 5:
            score += 5
        elif max_dd > 15:
            score -= 10
        
        score = min(100, max(0, score))
        
        # Determine structure label
        if score >= 80:
            structure = "Strong"
        elif score >= 60:
            structure = "Stable"
        else:
            structure = "Weak"
        
        slope_str = f"+{ma20_slope:.2f}" if ma20_slope >= 0 else f"{ma20_slope:.2f}"
        
        return round(score, 1), structure, slope_str
    
    def calculate_breadth_score(self, finviz_data: List[FinvizData]) -> tuple:
        """
        Calculate breadth/participation score
        - %Above50MA
        - %Above200MA
        """
        if not finviz_data:
            return 50, "50%", "50%"
        
        above_50ma = 0
        above_200ma = 0
        total = len(finviz_data)
        
        for item in finviz_data:
            if item.price and item.sma50 and item.price > item.sma50:
                above_50ma += 1
            if item.price and item.sma200 and item.price > item.sma200:
                above_200ma += 1
        
        pct_above_50ma = (above_50ma / total * 100) if total > 0 else 50
        pct_above_200ma = (above_200ma / total * 100) if total > 0 else 50
        
        # Score calculation
        score = (pct_above_50ma * 0.6 + pct_above_200ma * 0.4)
        
        return (
            round(score, 1),
            f"{pct_above_50ma:.0f}%",
            f"{pct_above_200ma:.0f}%"
        )
    
    def calculate_options_confirm_score(self, mc_data: List[MarketChameleonData]) -> tuple:
        """
        Calculate options confirmation score
        Based on MarketChameleon data
        """
        if not mc_data:
            return 50, "Medium", "1.0x", 50
        
        # Aggregate metrics
        total_rel_vol = sum(d.rel_vol_to_90d or 0 for d in mc_data)
        avg_rel_vol = total_rel_vol / len(mc_data) if mc_data else 1
        
        total_ivr = sum(d.ivr or 0 for d in mc_data)
        avg_ivr = total_ivr / len(mc_data) if mc_data else 50
        
        # Calculate heat
        if avg_rel_vol > 2.0:
            heat = "Very High"
            heat_score = 90
        elif avg_rel_vol > 1.5:
            heat = "High"
            heat_score = 75
        elif avg_rel_vol > 1.0:
            heat = "Medium"
            heat_score = 50
        else:
            heat = "Low"
            heat_score = 30
        
        # Combined score
        score = heat_score * 0.6 + avg_ivr * 0.4
        score = min(100, max(0, score))
        
        return (
            round(score, 1),
            heat,
            f"{avg_rel_vol:.1f}x",
            round(avg_ivr, 1)
        )
    
    def update_sector_etf_scores(
        self, 
        symbol: str, 
        ibkr_metrics: Dict,
        finviz_data: List[FinvizData],
        mc_data: List[MarketChameleonData]
    ) -> SectorETF:
        """Update sector ETF with calculated scores"""
        etf = self.db.query(SectorETF).filter(SectorETF.symbol == symbol).first()
        if not etf:
            etf = SectorETF(symbol=symbol, name=symbol)
            self.db.add(etf)
        
        # Calculate scores
        rel_mom_score, rel_mom_value = self.calculate_rel_momentum_score(ibkr_metrics)
        trend_score, structure, slope = self.calculate_trend_quality_score(ibkr_metrics)
        breadth_score, above_50, above_200 = self.calculate_breadth_score(finviz_data)
        options_score, heat, rel_vol, ivr = self.calculate_options_confirm_score(mc_data)
        
        composite = self.calculate_etf_composite_score(
            rel_mom_score, trend_score, breadth_score, options_score
        )
        
        # Update ETF record
        etf.composite_score = composite
        etf.rel_momentum_score = rel_mom_score
        etf.rel_momentum_value = rel_mom_value
        etf.rs_5d = ibkr_metrics.get("rs_5d")
        etf.rs_20d = ibkr_metrics.get("rs_20d")
        etf.rs_63d = ibkr_metrics.get("rs_63d")
        
        etf.trend_quality_score = trend_score
        etf.trend_structure = structure
        etf.trend_slope = slope
        etf.ma20_slope = ibkr_metrics.get("ma20_slope")
        etf.max_drawdown_20d = ibkr_metrics.get("max_drawdown_20d")
        
        etf.breadth_score = breadth_score
        etf.pct_above_50ma = above_50
        etf.pct_above_200ma = above_200
        
        etf.options_score = options_score
        etf.options_heat = heat
        etf.rel_vol = rel_vol
        etf.ivr = ivr
        
        self.db.commit()
        return etf
    
    # ==================== Momentum Stock Scoring ====================
    def calculate_stock_composite_score(
        self,
        price_momentum_score: float,
        trend_structure_score: float,
        volume_price_score: float,
        options_overlay_score: float,
        quality_filter_score: float
    ) -> float:
        """
        Calculate stock composite score
        0.65 · (价格动能 + 趋势结构) + 0.15 · 量能确认 + 0.20 · 期权覆盖
        质量过滤作为降权因子
        """
        price_trend = (price_momentum_score + trend_structure_score) / 2
        
        base_score = 0.65 * price_trend + 0.15 * volume_price_score + 0.20 * options_overlay_score
        
        # Apply quality filter as penalty
        quality_penalty = max(0, (100 - quality_filter_score) / 100 * 0.15)
        final_score = base_score * (1 - quality_penalty)
        
        return round(min(100, max(0, final_score)), 1)
    
    def calculate_price_momentum_score(self, metrics: Dict) -> tuple:
        """Calculate price momentum score"""
        return_20d = metrics.get("return_20d", 0)
        return_63d = metrics.get("return_63d", 0)
        near_high = metrics.get("near_high_dist", 0)
        
        # Base score from returns
        score = 50
        
        # 20D return contribution (+/- 20)
        score += min(20, max(-20, return_20d * 1.0))
        
        # 63D return contribution (+/- 15)
        score += min(15, max(-15, return_63d * 0.3))
        
        # Near high bonus
        if near_high > 95:
            score += 10
        elif near_high > 90:
            score += 5
        
        score = min(100, max(0, score))
        return round(score, 1)
    
    def calculate_trend_structure_score(self, metrics: Dict) -> float:
        """Calculate trend structure score"""
        score = 50
        
        # MA alignment
        ma_alignment = metrics.get("ma_alignment", "")
        if "P>20MA>50MA" in ma_alignment:
            score += 25
        elif "P>20MA" in ma_alignment:
            score += 10
        
        # Slope
        slope = metrics.get("slope_20d", 0)
        if slope > 0.05:
            score += 15
        elif slope > 0:
            score += 10
        
        # Continuity
        continuity = metrics.get("continuity", 0)
        score += continuity * 10
        
        return min(100, max(0, round(score, 1)))
    
    def calculate_volume_price_score(self, metrics: Dict) -> float:
        """Calculate volume/price confirmation score"""
        score = 50
        
        volume_spike = metrics.get("volume_spike", 1)
        up_down_ratio = metrics.get("up_down_vol_ratio", 1)
        
        if volume_spike > 2.0:
            score += 25
        elif volume_spike > 1.5:
            score += 15
        
        if up_down_ratio > 1.5:
            score += 25
        elif up_down_ratio > 1.0:
            score += 15
        
        return min(100, max(0, round(score, 1)))
    
    def calculate_quality_filter_score(self, metrics: Dict) -> tuple:
        """Calculate quality filter score and heat level"""
        score = 100
        
        max_dd = abs(metrics.get("max_drawdown_20d", 0))
        atr_pct = metrics.get("atr_percent", 0)
        dist_from_ma = abs(metrics.get("dist_from_20ma", 0))
        
        # Max drawdown penalty
        if max_dd > 15:
            score -= 30
        elif max_dd > 10:
            score -= 15
        elif max_dd > 5:
            score -= 5
        
        # ATR penalty
        if atr_pct > 6:
            score -= 20
        elif atr_pct > 4:
            score -= 10
        
        # Distance from MA penalty
        if dist_from_ma > 15:
            score -= 20
            heat = "Hot"
        elif dist_from_ma > 10:
            score -= 10
            heat = "Slightly Hot"
        else:
            heat = "Moderate"
        
        return max(0, round(score, 1)), heat
    
    def calculate_options_overlay_score(self, mc_data: MarketChameleonData) -> tuple:
        """Calculate options overlay score for individual stock"""
        if not mc_data:
            return 50, "Medium", "1.0x", 50, 0
        
        rel_vol = mc_data.rel_vol_to_90d or 1
        ivr = mc_data.ivr or 50
        iv30 = mc_data.iv30 or 0
        
        # Heat determination
        if rel_vol > 2.0:
            heat = "Very High"
            score = 85
        elif rel_vol > 1.5:
            heat = "High"
            score = 70
        elif rel_vol > 1.0:
            heat = "Medium"
            score = 50
        else:
            heat = "Low"
            score = 30
        
        # Adjust for IVR
        if ivr > 80:
            score += 10
        elif ivr < 30:
            score -= 10
        
        return (
            min(100, max(0, round(score, 1))),
            heat,
            f"{rel_vol:.1f}x",
            round(ivr, 1),
            round(iv30, 1)
        )
    
    def update_momentum_stock_scores(
        self,
        symbol: str,
        name: str,
        ibkr_metrics: Dict,
        mc_data: Optional[MarketChameleonData],
        sector: str,
        industry: str
    ) -> MomentumStock:
        """Update momentum stock with calculated scores"""
        stock = self.db.query(MomentumStock).filter(MomentumStock.symbol == symbol).first()
        if not stock:
            stock = MomentumStock(symbol=symbol)
            self.db.add(stock)
        
        stock.name = name
        stock.price = ibkr_metrics.get("price", 0)
        stock.sector = sector
        stock.industry = industry
        
        # Price momentum
        pm_score = self.calculate_price_momentum_score(ibkr_metrics)
        stock.price_momentum_score = pm_score
        stock.return_20d = f"+{ibkr_metrics.get('return_20d', 0):.1f}%"
        stock.return_20d_ex3 = f"+{ibkr_metrics.get('return_20d_ex3', 0):.1f}%"
        stock.return_63d = f"+{ibkr_metrics.get('return_63d', 0):.1f}%"
        stock.near_high_dist = f"{ibkr_metrics.get('near_high_dist', 0):.0f}%"
        stock.breakout_trigger = ibkr_metrics.get("breakout_trigger", False)
        stock.volume_spike = ibkr_metrics.get("volume_spike", 1)
        
        # Trend structure
        ts_score = self.calculate_trend_structure_score(ibkr_metrics)
        stock.trend_structure_score = ts_score
        stock.ma_alignment = ibkr_metrics.get("ma_alignment", "N/A")
        slope = ibkr_metrics.get("slope_20d", 0)
        stock.slope_20d = f"+{slope:.2f}" if slope >= 0 else f"{slope:.2f}"
        stock.continuity = f"{ibkr_metrics.get('continuity', 0) * 100:.0f}%"
        stock.above_20ma_ratio = ibkr_metrics.get("continuity", 0)
        
        # Volume price
        vp_score = self.calculate_volume_price_score(ibkr_metrics)
        stock.volume_price_score = vp_score
        stock.breakout_vol_ratio = ibkr_metrics.get("volume_spike", 1)
        stock.up_down_vol_ratio = ibkr_metrics.get("up_down_vol_ratio", 1)
        stock.obv_trend = "Strong" if ibkr_metrics.get("up_down_vol_ratio", 1) > 1.5 else "Moderate"
        
        # Quality filter
        qf_score, heat_level = self.calculate_quality_filter_score(ibkr_metrics)
        stock.quality_filter_score = qf_score
        stock.max_drawdown_20d = f"{ibkr_metrics.get('max_drawdown_20d', 0):.1f}%"
        stock.atr_percent = ibkr_metrics.get("atr_percent", 0)
        dist = ibkr_metrics.get("dist_from_20ma", 0)
        stock.dist_from_20ma = f"+{dist:.1f}%" if dist >= 0 else f"{dist:.1f}%"
        stock.heat_level = heat_level
        
        # Options overlay
        oo_score, heat, rel_vol, ivr, iv30 = self.calculate_options_overlay_score(mc_data)
        stock.options_overlay_score = oo_score
        stock.options_heat = heat
        stock.options_rel_vol = rel_vol
        stock.options_ivr = ivr
        stock.options_iv30 = iv30
        
        # Final composite score
        stock.final_score = self.calculate_stock_composite_score(
            pm_score, ts_score, vp_score, oo_score, qf_score
        )
        
        self.db.commit()
        return stock
    
    # ==================== Ranking ====================
    def rank_etfs(self, etfs: List[SectorETF]) -> List[SectorETF]:
        """Rank ETFs by composite score and update rank field"""
        sorted_etfs = sorted(etfs, key=lambda x: x.composite_score or 0, reverse=True)
        for i, etf in enumerate(sorted_etfs):
            etf.rel_momentum_rank = i + 1
        self.db.commit()
        return sorted_etfs

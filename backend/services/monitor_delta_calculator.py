"""
Monitor Delta Calculator Service - 监控任务 Δ3D/Δ5D 计算服务
自动计算评分的3日和5日变化值
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models_monitor import (
    MonitorTask, TaskETFConfig, TaskScoreSnapshot,
    ETFFinvizData, ETFMCData, ETFMarketData, ETFOptionsData
)

logger = logging.getLogger(__name__)


class MonitorDeltaCalculator:
    """监控任务 Delta 计算器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_and_save_scores(
        self, 
        task_id: int, 
        snapshot_date: Optional[date] = None
    ) -> Dict:
        """
        计算并保存任务评分，包含 Δ3D 和 Δ5D
        
        Args:
            task_id: 任务 ID
            snapshot_date: 快照日期，默认今天
            
        Returns:
            Dict: 计算结果统计
        """
        if snapshot_date is None:
            snapshot_date = date.today()
        
        task = self.db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        results = {
            "task_id": task_id,
            "snapshot_date": snapshot_date,
            "etf_scores": [],
            "success_count": 0,
            "error_count": 0
        }
        
        # 获取任务下所有 ETF 配置
        etf_configs = self.db.query(TaskETFConfig).filter(
            TaskETFConfig.task_id == task_id
        ).all()
        
        all_scores = []
        
        for config in etf_configs:
            try:
                # 计算当前评分
                score_data = self._calculate_etf_score(task_id, config.etf_symbol)
                
                # 获取历史评分计算 Delta
                delta_3d = self._get_delta(task_id, config.etf_symbol, snapshot_date, 3)
                delta_5d = self._get_delta(task_id, config.etf_symbol, snapshot_date, 5)
                
                score_data['delta_3d'] = delta_3d
                score_data['delta_5d'] = delta_5d
                
                all_scores.append(score_data)
                results['success_count'] += 1
                
            except Exception as e:
                logger.error(f"Error calculating score for {config.etf_symbol}: {e}")
                results['error_count'] += 1
        
        # 计算排名
        all_scores.sort(key=lambda x: x.get('overall_score') or 0, reverse=True)
        for rank, score_data in enumerate(all_scores, 1):
            score_data['rank_in_task'] = rank
        
        # 保存评分快照
        for score_data in all_scores:
            self._save_score_snapshot(task_id, snapshot_date, score_data)
        
        # 更新任务最后刷新时间
        task.last_refresh_at = datetime.utcnow()
        self.db.commit()
        
        results['etf_scores'] = all_scores
        return results
    
    def _calculate_etf_score(self, task_id: int, etf_symbol: str) -> Dict:
        """
        计算单个 ETF 的评分
        
        评分维度:
        1. 趋势得分 (trend_score): 基于 SMA50, SMA200, RSI
        2. 动量得分 (momentum_score): 基于价格变化、相对强度
        3. 相对强度得分 (rs_score): 相对于 SPY 的表现
        4. 期权得分 (options_score): 基于 IV, IVR, 交易量
        """
        # 获取 Finviz 数据
        finviz_data = self.db.query(ETFFinvizData).filter(
            ETFFinvizData.task_id == task_id,
            ETFFinvizData.etf_symbol == etf_symbol
        ).all()
        
        # 获取 MC 数据
        mc_data = self.db.query(ETFMCData).filter(
            ETFMCData.task_id == task_id,
            ETFMCData.etf_symbol == etf_symbol
        ).all()
        
        # 获取市场数据
        market_data = self.db.query(ETFMarketData).filter(
            ETFMarketData.task_id == task_id,
            ETFMarketData.etf_symbol == etf_symbol
        ).order_by(ETFMarketData.trade_date.desc()).first()
        
        # 获取期权数据
        options_data = self.db.query(ETFOptionsData).filter(
            ETFOptionsData.task_id == task_id,
            ETFOptionsData.etf_symbol == etf_symbol
        ).order_by(ETFOptionsData.trade_date.desc()).first()
        
        # 计算各维度得分
        trend_score = self._calc_trend_score(finviz_data, market_data)
        momentum_score = self._calc_momentum_score(finviz_data, market_data)
        rs_score = self._calc_rs_score(market_data)
        options_score = self._calc_options_score(mc_data, options_data)
        
        # 综合得分 (加权平均)
        weights = {
            'trend': 0.30,
            'momentum': 0.30,
            'rs': 0.20,
            'options': 0.20
        }
        
        overall_score = (
            (trend_score or 0) * weights['trend'] +
            (momentum_score or 0) * weights['momentum'] +
            (rs_score or 0) * weights['rs'] +
            (options_score or 0) * weights['options']
        )
        
        return {
            'etf_symbol': etf_symbol,
            'overall_score': round(overall_score, 2),
            'trend_score': trend_score,
            'momentum_score': momentum_score,
            'rs_score': rs_score,
            'options_score': options_score
        }
    
    def _calc_trend_score(self, finviz_data: List, market_data) -> Optional[float]:
        """计算趋势得分"""
        if not finviz_data:
            return None
        
        scores = []
        for item in finviz_data:
            item_score = 50  # 基础分
            
            # SMA50 评分: 高于均线加分
            if item.sma50:
                sma50_val = float(item.sma50)
                if sma50_val > 5:
                    item_score += 20
                elif sma50_val > 0:
                    item_score += 10
                elif sma50_val < -5:
                    item_score -= 10
            
            # SMA200 评分
            if item.sma200:
                sma200_val = float(item.sma200)
                if sma200_val > 10:
                    item_score += 15
                elif sma200_val > 0:
                    item_score += 8
                elif sma200_val < -10:
                    item_score -= 8
            
            # RSI 评分
            if item.rsi:
                rsi_val = float(item.rsi)
                if 40 < rsi_val < 70:
                    item_score += 15  # 健康区间
                elif rsi_val >= 70:
                    item_score += 5  # 可能超买
                elif rsi_val <= 30:
                    item_score -= 10  # 超卖
            
            scores.append(min(100, max(0, item_score)))
        
        return round(sum(scores) / len(scores), 2) if scores else None
    
    def _calc_momentum_score(self, finviz_data: List, market_data) -> Optional[float]:
        """计算动量得分"""
        if not finviz_data:
            return None
        
        scores = []
        for item in finviz_data:
            item_score = 50
            
            # 52周高点距离评分
            if item.week52_high:
                high_dist = float(item.week52_high)
                if high_dist > -5:
                    item_score += 25  # 接近新高
                elif high_dist > -10:
                    item_score += 15
                elif high_dist > -20:
                    item_score += 5
                else:
                    item_score -= 10  # 远离高点
            
            # ATR/价格比评分 (波动性)
            if item.atr and item.price:
                atr_pct = float(item.atr) / float(item.price) * 100
                if 2 < atr_pct < 5:
                    item_score += 10  # 适中波动
                elif atr_pct >= 5:
                    item_score += 5  # 高波动，有风险
            
            scores.append(min(100, max(0, item_score)))
        
        return round(sum(scores) / len(scores), 2) if scores else None
    
    def _calc_rs_score(self, market_data) -> Optional[float]:
        """计算相对强度得分"""
        if not market_data:
            return 50  # 无数据时返回中性分数
        
        score = 50
        
        if market_data.rs_vs_spy:
            rs = float(market_data.rs_vs_spy)
            if rs > 0.1:
                score += 30
            elif rs > 0.05:
                score += 20
            elif rs > 0:
                score += 10
            elif rs < -0.1:
                score -= 20
            elif rs < -0.05:
                score -= 10
        
        if market_data.price_change_pct:
            change = float(market_data.price_change_pct)
            if change > 2:
                score += 15
            elif change > 0:
                score += 5
            elif change < -2:
                score -= 15
        
        return round(min(100, max(0, score)), 2)
    
    def _calc_options_score(self, mc_data: List, options_data) -> Optional[float]:
        """计算期权得分"""
        scores = []
        
        # 从 MC 数据计算
        for item in mc_data:
            item_score = 50
            
            # IVR 评分
            if item.ivr:
                ivr = float(item.ivr)
                if ivr < 30:
                    item_score += 15  # 低 IV 有吸引力
                elif ivr > 70:
                    item_score -= 10  # 高 IV 风险
            
            # 相对成交量评分
            if item.rel_vol_to_90d:
                rel_vol = float(item.rel_vol_to_90d)
                if rel_vol > 1.5:
                    item_score += 20  # 活跃交易
                elif rel_vol > 1:
                    item_score += 10
            
            # Put/Call 比率评分
            if item.call_volume and item.put_volume:
                pc_ratio = item.put_volume / max(item.call_volume, 1)
                if pc_ratio < 0.8:
                    item_score += 10  # 偏看涨
                elif pc_ratio > 1.2:
                    item_score -= 5  # 偏看跌
            
            scores.append(min(100, max(0, item_score)))
        
        # 从期权数据补充
        if options_data:
            opt_score = 50
            if options_data.ivr:
                ivr = float(options_data.ivr)
                if ivr < 30:
                    opt_score += 15
                elif ivr > 70:
                    opt_score -= 10
            scores.append(opt_score)
        
        return round(sum(scores) / len(scores), 2) if scores else None
    
    def _get_delta(
        self, 
        task_id: int, 
        etf_symbol: str, 
        current_date: date, 
        days: int
    ) -> Optional[float]:
        """
        获取 N 日前的评分变化
        
        Args:
            task_id: 任务 ID
            etf_symbol: ETF 代码
            current_date: 当前日期
            days: 天数 (3 或 5)
            
        Returns:
            Delta 值或 None
        """
        # 计算目标日期（跳过周末）
        target_date = self._get_trading_date(current_date, days)
        
        # 查询历史快照
        historical_snapshot = self.db.query(TaskScoreSnapshot).filter(
            and_(
                TaskScoreSnapshot.task_id == task_id,
                TaskScoreSnapshot.etf_symbol == etf_symbol,
                TaskScoreSnapshot.snapshot_date == target_date
            )
        ).first()
        
        if not historical_snapshot or not historical_snapshot.overall_score:
            return None
        
        # 查询当前快照
        current_snapshot = self.db.query(TaskScoreSnapshot).filter(
            and_(
                TaskScoreSnapshot.task_id == task_id,
                TaskScoreSnapshot.etf_symbol == etf_symbol,
                TaskScoreSnapshot.snapshot_date == current_date
            )
        ).first()
        
        if not current_snapshot or not current_snapshot.overall_score:
            return None
        
        delta = float(current_snapshot.overall_score) - float(historical_snapshot.overall_score)
        return round(delta, 2)
    
    def _get_trading_date(self, from_date: date, days_back: int) -> date:
        """
        获取 N 个交易日前的日期（跳过周末）
        
        简化版本：仅跳过周六日
        """
        target_date = from_date
        days_counted = 0
        
        while days_counted < days_back:
            target_date -= timedelta(days=1)
            # 跳过周末
            if target_date.weekday() < 5:  # 0-4 是周一到周五
                days_counted += 1
        
        return target_date
    
    def _save_score_snapshot(
        self, 
        task_id: int, 
        snapshot_date: date, 
        score_data: Dict
    ):
        """保存评分快照"""
        # 检查是否已存在
        existing = self.db.query(TaskScoreSnapshot).filter(
            and_(
                TaskScoreSnapshot.task_id == task_id,
                TaskScoreSnapshot.etf_symbol == score_data['etf_symbol'],
                TaskScoreSnapshot.snapshot_date == snapshot_date
            )
        ).first()
        
        if existing:
            # 更新现有记录
            existing.overall_score = score_data.get('overall_score')
            existing.trend_score = score_data.get('trend_score')
            existing.momentum_score = score_data.get('momentum_score')
            existing.rs_score = score_data.get('rs_score')
            existing.options_score = score_data.get('options_score')
            existing.rank_in_task = score_data.get('rank_in_task')
            existing.delta_3d = score_data.get('delta_3d')
            existing.delta_5d = score_data.get('delta_5d')
        else:
            # 创建新记录
            snapshot = TaskScoreSnapshot(
                task_id=task_id,
                etf_symbol=score_data['etf_symbol'],
                overall_score=score_data.get('overall_score'),
                trend_score=score_data.get('trend_score'),
                momentum_score=score_data.get('momentum_score'),
                rs_score=score_data.get('rs_score'),
                options_score=score_data.get('options_score'),
                rank_in_task=score_data.get('rank_in_task'),
                delta_3d=score_data.get('delta_3d'),
                delta_5d=score_data.get('delta_5d'),
                snapshot_date=snapshot_date
            )
            self.db.add(snapshot)
    
    def recalculate_all_deltas(self, task_id: int) -> int:
        """
        重新计算任务所有历史快照的 Delta 值
        
        Returns:
            更新的快照数量
        """
        snapshots = self.db.query(TaskScoreSnapshot).filter(
            TaskScoreSnapshot.task_id == task_id
        ).order_by(TaskScoreSnapshot.snapshot_date).all()
        
        updated_count = 0
        
        for snapshot in snapshots:
            delta_3d = self._get_delta(task_id, snapshot.etf_symbol, snapshot.snapshot_date, 3)
            delta_5d = self._get_delta(task_id, snapshot.etf_symbol, snapshot.snapshot_date, 5)
            
            if delta_3d is not None or delta_5d is not None:
                snapshot.delta_3d = delta_3d
                snapshot.delta_5d = delta_5d
                updated_count += 1
        
        self.db.commit()
        return updated_count

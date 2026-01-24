"""
Data Parsers - Finviz and MarketChameleon data parsing services
数据解析器 - 解析 Finviz 和 MarketChameleon JSON 数据
"""
from typing import List, Dict, Tuple, Any, Optional
from decimal import Decimal, InvalidOperation
import re
import logging

logger = logging.getLogger(__name__)


class FinvizDataParser:
    """Finviz 数据解析器"""
    
    # 字段映射: Finviz原始字段 -> 数据库字段
    FIELD_MAPPING = {
        'Ticker': 'ticker',
        'Beta': 'beta',
        'ATR': 'atr',
        'SMA50': 'sma50',
        'SMA200': 'sma200',
        '52W_High': 'week52_high',
        '52W High': 'week52_high',
        'RSI': 'rsi',
        'Price': 'price',
        'Pirce': 'price',  # 兼容拼写错误
    }
    
    @classmethod
    def parse(cls, data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        解析 Finviz JSON 数据
        
        Args:
            data: Finviz 原始 JSON 数据列表
            
        Returns:
            Tuple[parsed_data, warnings]: 解析后的数据和警告信息
        """
        parsed = []
        warnings = []
        
        for idx, item in enumerate(data):
            try:
                # 检查必需字段
                ticker = item.get('Ticker') or item.get('ticker')
                if not ticker:
                    warnings.append(f"Row {idx + 1}: Missing Ticker field, skipped")
                    continue
                
                # 解析各字段
                record = {
                    'ticker': ticker.upper().strip(),
                    'beta': cls._parse_decimal(item.get('Beta')),
                    'atr': cls._parse_decimal(item.get('ATR')),
                    'sma50': cls._parse_decimal(item.get('SMA50')),
                    'sma200': cls._parse_decimal(item.get('SMA200')),
                    'week52_high': cls._parse_decimal(
                        item.get('52W_High') or item.get('52W High') or item.get('High_52W')
                    ),
                    'rsi': cls._parse_decimal(item.get('RSI')),
                    'price': cls._parse_decimal(
                        item.get('Price') or item.get('Pirce')  # 兼容拼写错误
                    ),
                }
                
                parsed.append(record)
                
            except Exception as e:
                warnings.append(f"Row {idx + 1}: Parse error - {str(e)}")
        
        return parsed, warnings
    
    @staticmethod
    def _parse_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
        """
        解析数值为 Decimal
        
        支持格式:
        - 数字: 1.23, -4.56
        - 字符串数字: "1.23", "-4.56"
        - 百分比: "12.5%"
        - 带逗号: "1,234.56"
        """
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, str):
            # 清理字符串
            cleaned = value.strip().replace(',', '').replace('%', '')
            if not cleaned or cleaned == '-':
                return default
            
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                return default
        
        return default
    
    @classmethod
    def validate(cls, data: List[Dict]) -> Tuple[bool, List[str]]:
        """
        验证 Finviz 数据格式
        
        Returns:
            Tuple[is_valid, errors]: 是否有效和错误信息列表
        """
        errors = []
        
        if not isinstance(data, list):
            errors.append("Data must be a JSON array")
            return False, errors
        
        if len(data) == 0:
            errors.append("Data array is empty")
            return False, errors
        
        # 检查第一条记录的字段
        first_item = data[0]
        if not isinstance(first_item, dict):
            errors.append("Each item must be a JSON object")
            return False, errors
        
        if not (first_item.get('Ticker') or first_item.get('ticker')):
            errors.append("Missing required field: Ticker")
            return False, errors
        
        return len(errors) == 0, errors


class MarketChameleonDataParser:
    """MarketChameleon 数据解析器"""
    
    # 需要移除百分号的字段
    PERCENTAGE_FIELDS = {
        'PutPct', 'SingleLegPct', 'MultiLegPct', 'ContingentPct',
        'IV30ChgPct', 'IVR', 'IV_52W_P', 'OI_PctRank', 'PriceChgPct'
    }
    
    # 需要处理单位的字段 (M/B/K)
    NOTIONAL_FIELDS = {'CallNotional', 'PutNotional'}
    
    # 需要移除逗号的整数字段
    INTEGER_FIELDS = {'CallVolume', 'PutVolume', 'Volume', 'TradeCount'}
    
    @classmethod
    def parse(cls, data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        解析 MarketChameleon JSON 数据
        
        数据格式特点:
        - 字符串格式数字: "1.22"
        - 带逗号数字: "24,635"
        - 百分比: "47.1%"
        - 带单位金额: "26.56 M"
        
        Args:
            data: MarketChameleon 原始 JSON 数据列表
            
        Returns:
            Tuple[parsed_data, warnings]: 解析后的数据和警告信息
        """
        parsed = []
        warnings = []
        
        for idx, item in enumerate(data):
            try:
                # 检查必需字段
                symbol = item.get('symbol') or item.get('Symbol')
                if not symbol:
                    warnings.append(f"Row {idx + 1}: Missing symbol field, skipped")
                    continue
                
                # 解析各字段
                record = {
                    'symbol': symbol.upper().strip(),
                    'rel_vol_to_90d': cls._parse_decimal(item.get('RelVolTo90D')),
                    'call_volume': cls._parse_integer(item.get('CallVolume')),
                    'put_volume': cls._parse_integer(item.get('PutVolume')),
                    'put_pct': cls._parse_percentage(item.get('PutPct')),
                    'single_leg_pct': cls._parse_percentage(item.get('SingleLegPct')),
                    'multi_leg_pct': cls._parse_percentage(item.get('MultiLegPct')),
                    'contingent_pct': cls._parse_percentage(item.get('ContingentPct')),
                    'rel_notional_to_90d': cls._parse_decimal(item.get('RelNotionalTo90D')),
                    'call_notional': cls._parse_notional(item.get('CallNotional')),
                    'put_notional': cls._parse_notional(item.get('PutNotional')),
                    'iv30_chg_pct': cls._parse_percentage(item.get('IV30ChgPct') or item.get('IV30_Chg')),
                    'iv30': cls._parse_decimal(item.get('IV30')),
                    'hv20': cls._parse_decimal(item.get('HV20')),
                    'hv1y': cls._parse_decimal(item.get('HV1Y')),
                    'ivr': cls._parse_percentage(item.get('IVR')),
                    'iv_52w_p': cls._parse_percentage(item.get('IV_52W_P')),
                    'volume': cls._parse_integer(item.get('Volume')),
                    'oi_pct_rank': cls._parse_percentage(item.get('OI_PctRank')),
                    'earnings': item.get('Earnings'),
                    'price_chg_pct': cls._parse_percentage(item.get('PriceChgPct')),
                }
                
                parsed.append(record)
                
            except Exception as e:
                warnings.append(f"Row {idx + 1}: Parse error - {str(e)}")
        
        return parsed, warnings
    
    @staticmethod
    def _parse_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
        """解析数值为 Decimal"""
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, str):
            cleaned = value.strip().replace(',', '')
            if not cleaned or cleaned == '-':
                return default
            
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                return default
        
        return default
    
    @staticmethod
    def _parse_percentage(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
        """
        解析百分比为 Decimal
        
        "47.1%" -> Decimal('47.1')
        "+2.5%" -> Decimal('2.5')
        "-3.4%" -> Decimal('-3.4')
        """
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, str):
            # 移除百分号和正号
            cleaned = value.strip().replace('%', '').replace('+', '')
            if not cleaned or cleaned == '-':
                return default
            
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                return default
        
        return default
    
    @staticmethod
    def _parse_integer(value: Any, default: int = 0) -> int:
        """
        解析整数
        
        "24,635" -> 24635
        """
        if value is None:
            return default
        
        if isinstance(value, int):
            return value
        
        if isinstance(value, float):
            return int(value)
        
        if isinstance(value, str):
            cleaned = value.strip().replace(',', '')
            if not cleaned or cleaned == '-':
                return default
            
            try:
                return int(float(cleaned))
            except (ValueError, InvalidOperation):
                return default
        
        return default
    
    @staticmethod
    def _parse_notional(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
        """
        解析带单位的名义金额
        
        "26.56 M" -> Decimal('26560000')
        "1.5 B" -> Decimal('1500000000')
        "500 K" -> Decimal('500000')
        """
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, str):
            cleaned = value.strip().upper()
            if not cleaned or cleaned == '-':
                return default
            
            # 处理带单位的金额
            multiplier = Decimal('1')
            if cleaned.endswith('M'):
                multiplier = Decimal('1000000')
                cleaned = cleaned[:-1].strip()
            elif cleaned.endswith('B'):
                multiplier = Decimal('1000000000')
                cleaned = cleaned[:-1].strip()
            elif cleaned.endswith('K'):
                multiplier = Decimal('1000')
                cleaned = cleaned[:-1].strip()
            
            try:
                return Decimal(cleaned.replace(',', '')) * multiplier
            except InvalidOperation:
                return default
        
        return default
    
    @classmethod
    def validate(cls, data: List[Dict]) -> Tuple[bool, List[str]]:
        """
        验证 MarketChameleon 数据格式
        
        Returns:
            Tuple[is_valid, errors]: 是否有效和错误信息列表
        """
        errors = []
        
        if not isinstance(data, list):
            errors.append("Data must be a JSON array")
            return False, errors
        
        if len(data) == 0:
            errors.append("Data array is empty")
            return False, errors
        
        # 检查第一条记录的字段
        first_item = data[0]
        if not isinstance(first_item, dict):
            errors.append("Each item must be a JSON object")
            return False, errors
        
        if not (first_item.get('symbol') or first_item.get('Symbol')):
            errors.append("Missing required field: symbol")
            return False, errors
        
        return len(errors) == 0, errors


# 工具函数
def detect_data_source(data: List[Dict]) -> Optional[str]:
    """
    自动检测数据来源
    
    Returns:
        'finviz' | 'market_chameleon' | None
    """
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    
    first_item = data[0]
    if not isinstance(first_item, dict):
        return None
    
    # Finviz 特征字段
    if first_item.get('Ticker') or first_item.get('ticker'):
        if first_item.get('Beta') is not None or first_item.get('ATR') is not None:
            return 'finviz'
    
    # MarketChameleon 特征字段
    if first_item.get('symbol') or first_item.get('Symbol'):
        if first_item.get('IVR') is not None or first_item.get('CallVolume') is not None:
            return 'market_chameleon'
    
    return None

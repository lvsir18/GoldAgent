"""
数据处理模块 - 数据清洗、时区对齐、溢价计算
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
import logging
from datetime import datetime
import pytz


logger = logging.getLogger(__name__)


class DataProcessor:
    """数据处理类"""
    
    def __init__(self, timezone: str = "Asia/Shanghai"):
        """
        初始化数据处理器
        
        Args:
            timezone: 目标时区，默认为 Asia/Shanghai
        """
        self.timezone = timezone
    
    def align_timezone(
        self,
        data: pd.DataFrame,
        from_tz: str = "UTC",
        to_tz: str = None
    ) -> pd.DataFrame:
        """
        时区对齐
        
        Args:
            data: 原始数据
            from_tz: 源时区
            to_tz: 目标时区，默认为初始化指定的时区
        
        Returns:
            对齐后的数据
        """
        if to_tz is None:
            to_tz = self.timezone
        
        # 如果索引是 naive，先 localize 再转换
        if data.index.tz is None:
            data.index = data.index.tz_localize(from_tz)
        
        data.index = data.index.tz_convert(to_tz)
        logger.info(f"时区已对齐: {from_tz} -> {to_tz}")
        
        return data
    
    def remove_weekends(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        移除周末数据
        
        Args:
            data: 原始数据
        
        Returns:
            移除周末后的数据
        """
        data = data[data.index.weekday < 5]
        logger.info("周末数据已移除")
        return data
    
    def fill_missing_values(
        self,
        data: pd.DataFrame,
        method: str = "forward"
    ) -> pd.DataFrame:
        """
        填充缺失值
        
        Args:
            data: 原始数据
            method: 填充方式 - "forward" (前向填充) / "backward" / "interpolate"
        
        Returns:
            填充后的数据
        """
        if method == "forward":
            data = data.ffill()  # pandas 2.0+ 使用 ffill() 而不是 fillna(method='ffill')
        elif method == "backward":
            data = data.bfill()  # pandas 2.0+ 使用 bfill() 而不是 fillna(method='bfill')
        elif method == "interpolate":
            data = data.interpolate(method='linear')
        
        logger.info(f"缺失值已填充 ({method})")
        return data
    
    def calculate_premium(
        self,
        intl_data: pd.DataFrame,
        dom_data: pd.DataFrame,
        intl_col: str = "close",
        dom_col: str = "close",
        fx_rate: float = 7.2,
        ounce_to_gram: float = 31.1035
    ) -> pd.DataFrame:
        """
        计算国内外黄金溢价
        
        Args:
            intl_data: 国际黄金数据
            dom_data: 国内黄金数据
            intl_col: 国际黄金价格列
            dom_col: 国内黄金价格列
            fx_rate: 溢价换算使用的 USD/CNY 汇率（用于将美元/盎司换算为人民币/克）
            ounce_to_gram: 盎司到克换算常量
        
        Returns:
            包含溢价率的数据框
        """
        # 创建副本以避免修改原数据
        intl_data_copy = intl_data.copy()
        dom_data_copy = dom_data.copy()
        
        # 对齐时间索引 - 使用 suffixes 参数处理重复列名
        merged = pd.merge_asof(
            intl_data_copy.sort_index(),
            dom_data_copy.sort_index(),
            left_index=True,
            right_index=True,
            direction='nearest',
            suffixes=('_intl', '_dom')
        )
        
        # 计算溢价 (%)
        # 统一口径：先将国际价格从 USD/oz 换算到 CNY/g，再与国内 CNY/g 比较
        # intl_cny_per_g = intl_usd_per_oz * fx_rate / 31.1035
        intl_col_name = f'{intl_col}_intl'
        dom_col_name = f'{dom_col}_dom'
        
        # 检查列是否存在
        if intl_col_name in merged.columns and dom_col_name in merged.columns:
            intl_cny_per_g = merged[intl_col_name] * fx_rate / ounce_to_gram
            merged['premium_pct'] = (
                (merged[dom_col_name] - intl_cny_per_g) / intl_cny_per_g * 100
            )
        else:
            # 列名没有后缀的情况（只有一个数据源有该列）
            if intl_col in merged.columns and dom_col in merged.columns:
                intl_cny_per_g = merged[intl_col] * fx_rate / ounce_to_gram
                merged['premium_pct'] = (
                    (merged[dom_col] - intl_cny_per_g) / intl_cny_per_g * 100
                )
            else:
                logger.warning(f"未找到价格列，溢价率设为 0")
                merged['premium_pct'] = 0
        
        logger.info("溢价率已计算")
        return merged
    
    def normalize_prices(
        self,
        data: pd.DataFrame,
        columns: list = None
    ) -> pd.DataFrame:
        """
        价格正规化 (0-1 区间)
        
        Args:
            data: 原始数据
            columns: 需要正规化的列，默认为数值列
        
        Returns:
            正规化后的数据
        """
        if columns is None:
            columns = data.select_dtypes(include=[np.number]).columns
        
        for col in columns:
            data[f'{col}_norm'] = (data[col] - data[col].min()) / (data[col].max() - data[col].min())
        
        logger.info(f"已正规化 {len(columns)} 列")
        return data
    
    def detect_outliers(
        self,
        data: pd.DataFrame,
        column: str,
        threshold: float = 3.0
    ) -> pd.DataFrame:
        """
        使用 Z-score 检测异常值
        
        Args:
            data: 原始数据
            column: 检测列
            threshold: Z-score 阈值，默认 3.0
        
        Returns:
            添加异常标记的数据框
        """
        data['z_score'] = np.abs((data[column] - data[column].mean()) / data[column].std())
        data['is_outlier'] = data['z_score'] > threshold
        
        outlier_count = data['is_outlier'].sum()
        logger.info(f"检测到 {outlier_count} 个异常值")
        
        return data
    
    def process_pipeline(
        self,
        intl_data: pd.DataFrame,
        dom_data: pd.DataFrame,
        config: dict = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        完整处理流程
        
        Args:
            intl_data: 国际黄金数据
            dom_data: 国内黄金数据
            config: 处理配置
        
        Returns:
            (处理后的国际数据, 处理后的国内数据)
        """
        if config is None:
            config = {}
        
        # 时区对齐
        if config.get('timezone'):
            intl_data = self.align_timezone(intl_data, from_tz="UTC", to_tz=config['timezone'])
            dom_data = self.align_timezone(dom_data, from_tz="Asia/Shanghai", to_tz=config['timezone'])
        
        # 移除周末
        if config.get('remove_weekends', False):
            intl_data = self.remove_weekends(intl_data)
            dom_data = self.remove_weekends(dom_data)
        
        # 填充缺失值
        fill_method = config.get('fill_missing', 'forward')
        if fill_method:
            intl_data = self.fill_missing_values(intl_data, method=fill_method)
            dom_data = self.fill_missing_values(dom_data, method=fill_method)
        
        logger.info("数据处理流程完成")
        return intl_data, dom_data

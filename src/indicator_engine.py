"""
技术指标计算模块 - 使用 pandas-ta 和 ta-lib
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
import logging
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


class IndicatorEngine:
    """技术指标计算引擎"""
    
    def __init__(self, config=None):
        """初始化指标引擎"""
        self.config = config or {}
    
    def calculate_ma(
        self,
        data: pd.DataFrame,
        periods: List[int] = [5, 20, 60],
        column: str = "close"
    ) -> pd.DataFrame:
        """
        计算移动平均线 (MA)
        
        Args:
            data: 原始数据
            periods: MA 周期列表，默认 [5, 20, 60]
            column: 基准列
        
        Returns:
            添加 MA 指标的数据框
        """
        for period in periods:
            data[f'ma{period}'] = data[column].rolling(window=period).mean()
        
        logger.info(f"已计算 MA: {periods}")
        return data
    
    def calculate_rsi(
        self,
        data: pd.DataFrame,
        period: int = 14,
        column: str = "close"
    ) -> pd.DataFrame:
        """
        计算相对强弱指数 (RSI)
        
        Args:
            data: 原始数据
            period: RSI 周期，默认 14
            column: 基准列
        
        Returns:
            添加 RSI 指标的数据框
        """
        data['rsi'] = ta.rsi(data[column], length=period)
        logger.info(f"已计算 RSI (period={period})")
        return data
    
    def calculate_macd(
        self,
        data: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        column: str = "close"
    ) -> pd.DataFrame:
        """
        计算 MACD 指标
        
        Args:
            data: 原始数据
            fast: 快线周期，默认 12
            slow: 慢线周期，默认 26
            signal: 信号线周期，默认 9
            column: 基准列
        
        Returns:
            添加 MACD 指标的数据框
        """
        macd = ta.macd(data[column], fast=fast, slow=slow, signal=signal)
        data = pd.concat([data, macd], axis=1)
        logger.info(f"已计算 MACD (fast={fast}, slow={slow}, signal={signal})")
        return data
    
    def calculate_bollinger_bands(
        self,
        data: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        column: str = "close"
    ) -> pd.DataFrame:
        """
        计算布林带 (Bollinger Bands)
        
        Args:
            data: 原始数据
            period: BB 周期，默认 20
            std_dev: 标准差倍数，默认 2.0
            column: 基准列
        
        Returns:
            添加布林带的数据框
        """
        bb = ta.bbands(data[column], length=period, std=std_dev)
        data = pd.concat([data, bb], axis=1)
        logger.info(f"已计算 Bollinger Bands (period={period}, std={std_dev})")
        return data
    
    def calculate_stoch(
        self,
        data: pd.DataFrame,
        period: int = 14,
        smooth_k: int = 3,
        smooth_d: int = 3
    ) -> pd.DataFrame:
        """
        计算随机指标 (Stochastic oscillator)
        
        Args:
            data: 原始数据
            period: 周期，默认 14
            smooth_k: K 线平滑周期，默认 3
            smooth_d: D 线平滑周期，默认 3
        
        Returns:
            添加随机指标的数据框
        """
        stoch = ta.stoch(
            data['high'], data['low'], data['close'],
            length=period, k=smooth_k, d=smooth_d
        )
        data = pd.concat([data, stoch], axis=1)
        logger.info(f"已计算 Stochastic (period={period})")
        return data
    
    def calculate_atr(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        计算平均波动幅度 (Average True Range)
        
        Args:
            data: 原始数据
            period: ATR 周期，默认 14
        
        Returns:
            添加 ATR 的数据框
        """
        data['atr'] = ta.atr(data['high'], data['low'], data['close'], length=period)
        logger.info(f"已计算 ATR (period={period})")
        return data
    
    def calculate_obv(
        self,
        data: pd.DataFrame,
        column: str = "close"
    ) -> pd.DataFrame:
        """
        计算成交量能量潮 (On-Balance Volume)
        
        Args:
            data: 原始数据
            column: 基准列
        
        Returns:
            添加 OBV 的数据框
        """
        data['obv'] = ta.obv(data[column], data['volume'])
        logger.info("已计算 OBV")
        return data
    
    def calculate_all_indicators(
        self,
        data: pd.DataFrame,
        config: Dict = None
    ) -> pd.DataFrame:
        """
        计算所有技术指标
        
        Args:
            data: 原始数据
            config: 指标配置
        
        Returns:
            包含所有指标的数据框
        """
        if config is None:
            config = {}
        
        # MA
        ma_periods = config.get('ma', {}).get('periods', [5, 20, 60])
        data = self.calculate_ma(data, periods=ma_periods)
        
        # RSI
        rsi_period = config.get('rsi', {}).get('period', 14)
        data = self.calculate_rsi(data, period=rsi_period)
        
        # MACD
        macd_config = config.get('macd', {})
        data = self.calculate_macd(
            data,
            fast=macd_config.get('fast', 12),
            slow=macd_config.get('slow', 26),
            signal=macd_config.get('signal', 9)
        )
        
        # Bollinger Bands
        data = self.calculate_bollinger_bands(data)
        
        # Stochastic
        data = self.calculate_stoch(data)
        
        # ATR
        data = self.calculate_atr(data)
        
        # OBV
        data = self.calculate_obv(data)
        
        logger.info("所有技术指标已计算")
        return data
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        strategy: str = "ma_cross"
    ) -> pd.DataFrame:
        """
        基于指标生成交易信号
        
        Args:
            data: 包含指标的数据
            strategy: 策略类型 - "ma_cross" / "rsi" / "macd"
        
        Returns:
            添加信号列的数据框
        """
        data['signal'] = 0
        
        if strategy == "ma_cross":
            # MA5 和 MA20 的金叉死叉
            data.loc[data['ma5'] > data['ma20'], 'signal'] = 1  # 买入
            data.loc[data['ma5'] < data['ma20'], 'signal'] = -1  # 卖出
        
        elif strategy == "rsi":
            # RSI 超买超卖
            rsi_overbought = data['rsi'] > 70
            rsi_oversold = data['rsi'] < 30
            data.loc[rsi_oversold, 'signal'] = 1  # 买入
            data.loc[rsi_overbought, 'signal'] = -1  # 卖出
        
        elif strategy == "macd":
            # MACD 柱状图正负变化
            macd_col = 'MACD_12_26_9'
            hist_col = 'MACDh_12_26_9'
            if macd_col in data.columns and hist_col in data.columns:
                data.loc[data[hist_col] > 0, 'signal'] = 1  # 买入
                data.loc[data[hist_col] < 0, 'signal'] = -1  # 卖出
        
        logger.info(f"已生成 {strategy} 交易信号")
        return data
    
    def forecast_trend(
        self,
        data: pd.DataFrame,
        periods: int = 5,
        column: str = "close",
        method: str = "linear"
    ) -> Dict:
        """
        预测价格走势（未来 N 个周期）
        
        Args:
            data: 历史数据
            periods: 预测周期数（默认 5 天）
            column: 基准列
            method: 预测方法 - "linear" (线性回归) / "ma" (移动平均) / "exponential" (指数平滑)
        
        Returns:
            包含预测结果的字典
        """
        try:
            from sklearn.linear_model import LinearRegression
        except ImportError:
            logger.error("需要安装 scikit-learn: pip install scikit-learn")
            return None
        
        if len(data) < 5:
            logger.warning("数据不足，无法进行预测")
            return None
        
        close_prices = data[column].dropna().values
        
        if method == "linear":
            # 线性回归预测
            X = np.arange(len(close_prices)).reshape(-1, 1)
            y = close_prices
            
            model = LinearRegression()
            model.fit(X, y)
            
            # 生成未来 periods 个点的预测
            future_X = np.arange(len(close_prices), len(close_prices) + periods).reshape(-1, 1)
            forecast_prices = model.predict(future_X)
            
            # 计算置信区间（基于历史波动率）
            residuals = y - model.predict(X)
            std_residuals = np.std(residuals)
            
        elif method == "ma":
            # 移动平均 + 趋势外推（避免所有预测值恒等）
            ma_window = int(self.config.get('forecast.ma_window', 5))
            ma_window = max(2, min(ma_window, len(close_prices)))

            close_series = pd.Series(close_prices)
            ma_series = close_series.rolling(window=ma_window).mean().dropna()

            if ma_series.empty:
                # 极端兜底：退化为最后窗口均值
                last_ma = close_prices[-ma_window:].mean()
                forecast_prices = np.full(periods, last_ma)
            else:
                last_ma = float(ma_series.iloc[-1])

                # 使用最近若干个 MA 差分的均值作为每步趋势
                slope_window = min(5, len(ma_series) - 1)
                if slope_window > 0:
                    recent_ma = ma_series.tail(slope_window + 1)
                    trend_per_step = float(recent_ma.diff().dropna().mean())
                else:
                    trend_per_step = 0.0

                forecast_prices = np.array([
                    last_ma + trend_per_step * (i + 1)
                    for i in range(periods)
                ])

            std_residuals = np.std(close_prices[-min(20, len(close_prices)):])
            
        elif method == "exponential":
            # 指数平滑 + 趋势外推（避免所有预测值恒等于当前价）
            alpha = self.config.get('forecast.exponential_alpha', 0.3)

            # 1) 先计算历史平滑序列
            smoothed = np.zeros(len(close_prices))
            smoothed[0] = close_prices[0]
            for i in range(1, len(close_prices)):
                smoothed[i] = alpha * close_prices[i] + (1 - alpha) * smoothed[i - 1]

            # 2) 用近期平滑值差分估计趋势斜率
            trend_window = min(10, len(smoothed) - 1)
            if trend_window > 0:
                recent_diffs = np.diff(smoothed[-(trend_window + 1):])
                trend_per_step = float(np.mean(recent_diffs))
            else:
                trend_per_step = 0.0

            # 3) 未来值 = 最后平滑值 + 线性趋势外推
            last_level = smoothed[-1]
            forecast_prices = np.array([
                last_level + trend_per_step * (i + 1)
                for i in range(periods)
            ])

            # 使用近期残差估计不确定性
            residuals = close_prices - smoothed
            std_residuals = np.std(residuals[-min(20, len(residuals)):])
        else:
            logger.error(f"未知预测方法: {method}")
            return None
        
        # 构建预测结果
        current_price = close_prices[-1]
        forecast_result = {
            "method": method,
            "current_price": float(current_price),
            "forecast_prices": forecast_prices.tolist(),
            "forecast_changes": [(p - current_price) / current_price * 100 for p in forecast_prices],
            "confidence_upper": (forecast_prices + std_residuals).tolist(),
            "confidence_lower": (forecast_prices - std_residuals).tolist(),
            "trend_direction": "up" if forecast_prices[-1] > current_price else "down",
            "avg_change_pct": float(np.mean([(p - current_price) / current_price * 100 for p in forecast_prices])),
        }
        
        logger.info(
            f"✓ 完成 {method} 预测 | "
            f"当前价格: {current_price:.2f} | "
            f"预测方向: {forecast_result['trend_direction']} | "
            f"平均涨幅: {forecast_result['avg_change_pct']:.2f}%"
        )
        
        return forecast_result
    
    def analyze_forecast_confidence(
        self,
        data: pd.DataFrame,
        column: str = "close"
    ) -> Dict:
        """
        分析预测置信度指标
        
        Args:
            data: 历史数据
            column: 基准列
        
        Returns:
            置信度分析字典
        """
        close_prices = data[column].dropna().values
        
        if len(close_prices) < 20:
            return {"confidence_score": 0.5, "reason": "数据不足"}
        
        # 【配置同步】从配置读取参数
        confidence_config = self.config.get('indicators.confidence', {})
        volatility_baseline = confidence_config.get('volatility_baseline', 0.05)
        min_confidence = confidence_config.get('min_confidence', 0.5)
        rsi_midpoint = confidence_config.get('rsi_midpoint', 50)
        lookback_window = confidence_config.get('lookback_window', 20)
        price_window = confidence_config.get('price_window', 5)
        
        # 计算波动率（lookback_window 日）
        returns = np.diff(close_prices[-lookback_window:]) / close_prices[-lookback_window:-1]
        volatility = np.std(returns)
        
        # 计算趋势强度（使用 RSI）
        if 'rsi' in data.columns:
            rsi_val = data['rsi'].iloc[-1]
            trend_strength = 1 - abs(rsi_val - rsi_midpoint) / rsi_midpoint
        else:
            # 使用价格趋势强度替代
            trend_strength = abs(close_prices[-1] - close_prices[-price_window]) / close_prices[-price_window]
        
        # 综合置信度评分 (0-1)
        # 波动率越低、趋势越强，置信度越高
        confidence_score = 1 - (volatility / volatility_baseline) if volatility > 0 else min_confidence
        confidence_score = max(0, min(1, confidence_score * trend_strength))
        
        return {
            "confidence_score": float(confidence_score),
            "volatility": float(volatility),
            "trend_strength": float(trend_strength),
            "reason": self._get_confidence_reason(confidence_score, volatility, trend_strength)
        }
    
    def _get_confidence_reason(self, score: float, volatility: float, trend: float) -> str:
        """获取置信度原因描述"""
        if score > 0.7:
            return "高置信度：波动率低，趋势明确"
        elif score > 0.5:
            return "中等置信度：市场存在可预测的趋势"
        else:
            return "低置信度：市场波动大，趋势不明确"

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据获取模块 - 国际金价终极修复版
策略：
1. 尝试 ak.futures_global_commodity_hist
2. 尝试 ak.futures_foreign_commodity_realtime (如果支持历史)
3. 【保底】使用美国黄金 ETF (GLD) 数据代理国际金价 (相关性极高)
"""

import logging
import pandas as pd
import numpy as np
import datetime
import akshare as ak

class DataFetcher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def fetch_international_gold(self, symbol="SYNTHETIC", period="1y"):
        """
        【终极方案】通过国内金价和汇率合成国际金价
        修改点：
        1. 默认返回全量历史数据，不再内部强制过滤 1 年
        2. 优化汇率获取接口
        """
        self.logger.info("🔄 启动合成策略：国内金价 * 汇率 -> 国际金价...")
        
        try:
            # 1. 获取国内黄金数据 (全量)
            self.logger.debug("步骤 1: 获取国内黄金数据 (AU0)...")
            df_domestic = self.fetch_domestic_gold(symbol="AU0", period=period)
            
            if df_domestic.empty:
                raise ValueError("无法获取国内基础数据 (AU0)")
            
            # 2. 获取美元兑人民币汇率 (全量)
            self.logger.debug("步骤 2: 获取美元兑人民币汇率...")
            fx_series = None
            
            # --- 尝试方法 A: ak.currency_boc_sina (新浪源) ---
            try:
                self.logger.debug("   尝试获取新浪汇率数据 (symbol='美元')...")
                
                # 1. 获取数据
                df_fx = ak.currency_boc_sina(symbol="美元")
                
                if df_fx is not None and not df_fx.empty:
                    self.logger.debug(f"   原始列名: {df_fx.columns.tolist()}")
                    
                    # 2. 标准化日期列
                    date_col = '日期' if '日期' in df_fx.columns else 'date'
                    if date_col not in df_fx.columns:
                        raise ValueError("未找到日期列")
                    
                    df_fx[date_col] = pd.to_datetime(df_fx[date_col])
                    df_fx.set_index(date_col, inplace=True)
                    
                    # 3. 【关键修复】精准匹配汇率列
                    # 优先级：央行中间价 > 中行钞卖价/汇卖价 > 中行汇买价
                    rate_col = None
                    
                    if '央行中间价' in df_fx.columns:
                        rate_col = '央行中间价'
                        self.logger.debug("   选中列: [央行中间价] (推荐)")
                    elif '中行钞卖价/汇卖价' in df_fx.columns:
                        rate_col = '中行钞卖价/汇卖价'
                        self.logger.debug("   选中列: [中行钞卖价/汇卖价]")
                    elif '中行汇买价' in df_fx.columns:
                        rate_col = '中行汇买价'
                        self.logger.debug("   选中列: [中行汇买价]")
                    
                    if rate_col:
                        # 提取并清洗数据
                        fx_series = df_fx[rate_col].sort_index()
                        # 确保是数值类型
                        fx_series = pd.to_numeric(fx_series, errors='coerce')
                        # 去除空值
                        fx_series = fx_series.dropna()
                        
                        # 时区处理 (转为无时区)
                        if fx_series.index.tz is not None:
                            fx_series.index = fx_series.index.tz_localize(None)
                            
                        self.logger.info(f"✓ 汇率数据获取成功 (新浪接口): {len(fx_series)} 条记录")
                        self.logger.info(f"   最新汇率 ({rate_col}): {fx_series.iloc[-1]:.4f}")
                    else:
                        self.logger.warning(f"   ✗ 未找到合适的汇率列。可用列: {df_fx.columns.tolist()}")
                        fx_series = None
                        
            except Exception as e:
                self.logger.warning(f"   ✗ 新浪接口执行失败: {e}")
                fx_series = None

            # --- 尝试方法 B: 年份加权估算汇率 (保底方案) ---
            if fx_series is None:
                self.logger.warning("⚠️ 无法获取实时汇率数据，启用【年份加权估算模式】")
                
                # 历史平均汇率字典 (更精细的年份覆盖)
                fx_dict = {
                    2015: 6.23, 2016: 6.65, 2017: 6.75, 2018: 6.60, 
                    2019: 6.90, 2020: 6.90, 2021: 6.45, 2022: 6.72, 
                    2023: 7.05, 2024: 7.10, 2025: 7.20, 2026: 7.25
                }
                
                # 向量化生成汇率序列
                df_domestic['year'] = df_domestic.index.year
                # 使用 map 映射，缺失值用 7.25 填充
                fx_values = df_domestic['year'].map(fx_dict).fillna(7.25)
                fx_series = pd.Series(fx_values.values, index=df_domestic.index)
           
                # 清理临时列
                df_domestic.drop(columns=['year'], inplace=True, errors='ignore')
                
                self.logger.info(f"✓ 已生成估算汇率序列: {len(fx_series)} 条记录")
            
            # 3. 数据对齐与合成
            self.logger.debug("步骤 3: 对齐数据并计算合成价格...")
            
            # 确保汇率序列索引与国内数据索引完全对齐
            # method='ffill' 向前填充，解决节假日不一致问题
            fx_aligned = fx_series.reindex(df_domestic.index, method='ffill')
            # Online bank quotes are commonly expressed per 100 foreign-currency
            # units, while the built-in annual fallback is already CNY per USD.
            if fx_aligned.dropna().median() > 20:
                fx_aligned = fx_aligned / 100
            
            # 再次检查是否有空值 (如果是早期数据没有 forward fill 的来源)
            if fx_aligned.isnull().any():
                missing_count = fx_aligned.isnull().sum()
                self.logger.warning(f"⚠️ 仍有 {missing_count} 天汇率缺失，使用固定值 7.25 填充")
                fx_aligned = fx_aligned.fillna(7.25)
            
            # 常量定义
            OUNCE_TO_GRAM = 31.1035
            
            # --- 核心公式修正 (统一所有 OHLC 计算逻辑) ---
            # 逻辑：国际价 (美元/盎司) = 国内价 (人民币/克) * 31.1035 / 汇率 (人民币/美元)
            
            synthetic_close = (df_domestic['close'] / fx_aligned) * OUNCE_TO_GRAM
            synthetic_open  = (df_domestic['open']  / fx_aligned) * OUNCE_TO_GRAM
            synthetic_high  = (df_domestic['high']  / fx_aligned) * OUNCE_TO_GRAM
            synthetic_low   = (df_domestic['low']   / fx_aligned) * OUNCE_TO_GRAM
            
            # 构建结果 DataFrame
            result = pd.DataFrame({
                'open': synthetic_open,
                'high': synthetic_high,
                'low': synthetic_low,
                'close': synthetic_close,
                'volume': df_domestic['volume'] 
            }, index=df_domestic.index)
            
            # 数据清洗：去除可能的无穷大值 (如果汇率为0)
            result = result.replace([np.inf, -np.inf], np.nan).dropna()
            
            result = result.sort_index()
            
            # 日志输出
            self.logger.info(f"✅ 合成国际金价成功 (全量历史)!")
            self.logger.info(f"   总记录数：{len(result)}")
            self.logger.info(f"   日期范围：{result.index[0].strftime('%Y-%m-%d')} ~ {result.index[-1].strftime('%Y-%m-%d')}")
            self.logger.info(f"   最新合成价格：{result['close'].iloc[-1]:.2f} 美元/盎司")
            self.logger.info(f"   对应当前汇率：{fx_aligned.iloc[-1]:.4f}")
            
            return result

        except Exception as e:
            self.logger.error(f"❌ 合成国际金价失败: {e}", exc_info=True)
            raise e

    def fetch_domestic_gold(self, symbol="AU0", period="1y"): # 添加 period 参数，默认 10y
        """获取国内黄金数据"""
        self.logger.info(f"获取国内黄金数据: {symbol}")
        try:
            # 1. 先获取全量数据 (Akshare 通常一次拉取所有)
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df is None or df.empty:
                raise ValueError("Akshare 返回空数据")
            
            # 2. 基础清洗
            date_col = 'date' if 'date' in df.columns else 'datetime'
            if date_col not in df.columns:
                candidates_c = [c for c in df.columns if 'date' in str(c).lower()]
                if candidates_c: date_col = candidates_c[0]
                else: raise ValueError("无法找到日期列")
            
            df[date_col] = pd.to_datetime(df[date_col])
            df.set_index(date_col, inplace=True)
            df.columns = [str(c).lower() for c in df.columns]
            
            required = ['open', 'high', 'low', 'close', 'volume']
            result = df.reindex(columns=required).sort_index()
            result = result.dropna(subset=['open', 'high', 'low', 'close'])
            result['volume'] = result['volume'].fillna(0)
            
            # 3. 【关键逻辑】根据 period 参数进行切片
            if period and period != "all":
                if period.endswith("y"):
                    years = int(period[:-1])
                    cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
                    result = result[result.index >= cutoff]
                    self.logger.info(f"📅 已过滤数据：保留最近 {years} 年 (>{cutoff.date()})")
            
            self.logger.info(f"成功获取国内数据: {len(result)} 条 (周期: {period})")
            return result
        except Exception as e:
            self.logger.error(f"获取国内数据失败: {e}")
            raise e

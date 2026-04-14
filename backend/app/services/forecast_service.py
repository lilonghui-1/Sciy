# -*- coding: utf-8 -*-
"""
需求预测服务

提供基于统计模型的库存需求预测功能，支持多种预测模型：
- SMA（简单移动平均）
- EMA（指数移动平均）
- Holt-Winters（三重指数平滑）
- ARIMA（自回归积分滑动平均）

自动根据数据特征选择最优模型，并提供置信区间。
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import select, func, and_, desc, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.models.inventory_transaction import InventoryTransaction

logger = logging.getLogger(__name__)


class ForecastService:
    """
    需求预测服务

    提供完整的需求预测管道：数据获取 -> 模型选择 -> 预测执行 -> 结果返回。
    支持单产品和批量预测，自动处理模型回退策略。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化预测服务

        Args:
            db: 异步数据库会话
        """
        self.db = db

    # ==================== 数据获取 ====================

    async def get_historical_data(
        self,
        product_id: int,
        warehouse_id: int,
        days: int = 90,
    ) -> pd.DataFrame:
        """
        获取历史每日出库需求数据

        从 inventory_transactions 表中聚合指定产品和仓库的每日出库量。
        仅统计 outbound 类型的事务，将 quantity_change 取绝对值（出库为负数）。

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            days: 回溯天数，默认90天

        Returns:
            DataFrame，包含 date 和 demand 两列，按日期升序排列
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(
                cast(InventoryTransaction.created_at, Date).label("date"),
                func.sum(func.abs(InventoryTransaction.quantity_change)).label("demand"),
            )
            .where(
                and_(
                    InventoryTransaction.product_id == product_id,
                    InventoryTransaction.warehouse_id == warehouse_id,
                    InventoryTransaction.transaction_type == "outbound",
                    InventoryTransaction.created_at >= since,
                )
            )
            .group_by(cast(InventoryTransaction.created_at, Date))
            .order_by(cast(InventoryTransaction.created_at, Date))
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            logger.warning(
                "产品 %d 仓库 %d 在过去 %d 天内无出库记录",
                product_id, warehouse_id, days,
            )
            return pd.DataFrame(columns=["date", "demand"])

        df = pd.DataFrame(rows, columns=["date", "demand"])
        df["date"] = pd.to_datetime(df["date"])
        df["demand"] = df["demand"].astype(float)

        logger.info(
            "产品 %d 仓库 %d 获取到 %d 天的历史需求数据",
            product_id, warehouse_id, len(df),
        )
        return df

    # ==================== 模型选择 ====================

    def auto_select_model(self, series: pd.Series) -> str:
        """
        根据数据特征自动选择最优预测模型

        选择策略：
        - 数据点 < 14：SMA（简单移动平均，数据量太少无法使用复杂模型）
        - 数据点 14-30：EMA（指数移动平均，中等数据量）
        - 数据点 >= 60 且季节性强度 > 0.2：Holt-Winters（存在明显季节性）
        - 其他情况：ARIMA（通用时间序列模型）

        Args:
            series: 需求数据时间序列

        Returns:
            模型名称字符串
        """
        n = len(series)

        if n < 14:
            logger.info("数据点 %d < 14，选择 SMA 模型", n)
            return "SMA"

        if n < 30:
            logger.info("数据点 %d 在 [14, 30) 范围内，选择 EMA 模型", n)
            return "EMA"

        # 计算季节性强度（使用自相关系数）
        seasonal_strength = self._calculate_seasonal_strength(series, period=7)

        if seasonal_strength > 0.2:
            logger.info(
                "数据点 %d >= 60，季节性强度 %.3f > 0.2，选择 Holt-Winters 模型",
                n, seasonal_strength,
            )
            return "Holt-Winters"

        logger.info(
            "数据点 %d >= 60，季节性强度 %.3f <= 0.2，选择 ARIMA 模型",
            n, seasonal_strength,
        )
        return "ARIMA"

    def _calculate_seasonal_strength(self, series: pd.Series, period: int = 7) -> float:
        """
        计算时间序列的季节性强度

        通过比较 lag=k 的自相关系数与 lag=1 的自相关系数来衡量季节性。
        季节性强度 = max(ACF(lag=period), 0) - ACF(lag=1)

        Args:
            series: 时间序列数据
            period: 季节性周期，默认7（周）

        Returns:
            季节性强度指标，范围 [0, 1]
        """
        try:
            values = series.values.astype(float)
            n = len(values)
            if n < 2 * period:
                return 0.0

            # 计算自相关系数
            mean_val = np.mean(values)
            var_val = np.var(values)
            if var_val < 1e-10:
                return 0.0

            def acf_at_lag(lag: int) -> float:
                if lag >= n:
                    return 0.0
                numerator = np.sum((values[:n - lag] - mean_val) * (values[lag:] - mean_val))
                denominator = n * var_val
                return numerator / denominator if denominator > 0 else 0.0

            acf_1 = abs(acf_at_lag(1))
            acf_period = max(acf_at_lag(period), 0.0)

            strength = max(acf_period - acf_1, 0.0)
            return min(strength, 1.0)

        except Exception as e:
            logger.warning("计算季节性强度失败: %s", e)
            return 0.0

    # ==================== 预测模型 ====================

    def forecast_sma(
        self,
        series: pd.Series,
        window: int = 7,
        periods: int = 14,
    ) -> dict:
        """
        简单移动平均预测

        使用最近 window 天的平均值作为未来预测值。
        置信区间基于历史数据的滚动标准差。

        Args:
            series: 需求数据时间序列
            window: 移动平均窗口大小，默认7天
            periods: 预测天数，默认14天

        Returns:
            预测结果字典，包含 predictions, model_name, model_params
        """
        logger.info("执行 SMA 预测: window=%d, periods=%d", window, periods)

        values = series.values.astype(float)
        n = len(values)

        # 使用最近 window 天的均值作为预测值
        actual_window = min(window, n)
        forecast_value = np.mean(values[-actual_window:])

        # 计算历史标准差用于置信区间
        if n >= actual_window:
            rolling_std = np.std(values[-actual_window:], ddof=1)
        else:
            rolling_std = np.std(values, ddof=1) if n > 1 else 0.0

        # 95% 置信区间
        z = 1.96
        lower = max(forecast_value - z * rolling_std, 0.0)
        upper = forecast_value + z * rolling_std

        # 生成预测序列
        predictions = []
        for i in range(periods):
            predictions.append({
                "predicted_demand": round(float(forecast_value), 2),
                "lower_bound": round(float(lower), 2),
                "upper_bound": round(float(upper), 2),
            })

        return {
            "predictions": predictions,
            "model_name": "SMA",
            "model_params": {"window": actual_window, "periods": periods},
        }

    def forecast_ema(
        self,
        series: pd.Series,
        span: int = 7,
        periods: int = 14,
    ) -> dict:
        """
        指数移动平均预测

        使用指数加权移动平均进行预测，近期数据权重更大。
        置信区间基于 EMA 残差的标准差。

        Args:
            series: 需求数据时间序列
            span: EMA 跨度参数，默认7
            periods: 预测天数，默认14天

        Returns:
            预测结果字典
        """
        logger.info("执行 EMA 预测: span=%d, periods=%d", span, periods)

        values = series.values.astype(float)
        n = len(values)

        # 计算 EMA
        alpha = 2.0 / (span + 1)
        ema_values = np.zeros(n)
        ema_values[0] = values[0]
        for i in range(1, n):
            ema_values[i] = alpha * values[i] + (1 - alpha) * ema_values[i - 1]

        forecast_value = ema_values[-1]

        # 计算残差标准差
        residuals = values - ema_values
        residual_std = np.std(residuals, ddof=1) if n > 2 else 0.0

        # 95% 置信区间（随预测天数增加而扩大）
        z = 1.96
        predictions = []
        for i in range(periods):
            # 置信区间随时间推移逐渐扩大
            expansion_factor = np.sqrt(1 + i * alpha)
            std_at_horizon = residual_std * expansion_factor
            lower = max(forecast_value - z * std_at_horizon, 0.0)
            upper = forecast_value + z * std_at_horizon
            predictions.append({
                "predicted_demand": round(float(forecast_value), 2),
                "lower_bound": round(float(lower), 2),
                "upper_bound": round(float(upper), 2),
            })

        return {
            "predictions": predictions,
            "model_name": "EMA",
            "model_params": {"span": span, "alpha": round(alpha, 4), "periods": periods},
        }

    def forecast_holt_winters(
        self,
        series: pd.Series,
        seasonal_periods: int = 7,
        periods: int = 14,
    ) -> dict:
        """
        Holt-Winters 三重指数平滑预测

        同时捕捉趋势和季节性成分，适用于具有明显季节性的时间序列。
        如果模型拟合失败，自动回退到 EMA 模型。

        Args:
            series: 需求数据时间序列
            seasonal_periods: 季节性周期，默认7（周）
            periods: 预测天数，默认14天

        Returns:
            预测结果字典
        """
        logger.info(
            "执行 Holt-Winters 预测: seasonal_periods=%d, periods=%d",
            seasonal_periods, periods,
        )

        values = series.values.astype(float)

        try:
            # 需要 2 个完整季节周期以上的数据
            min_required = 2 * seasonal_periods + 1
            if len(values) < min_required:
                logger.warning(
                    "数据量 %d 不足 Holt-Winters 最低要求 %d，回退到 EMA",
                    len(values), min_required,
                )
                return self.forecast_ema(series, periods=periods)

            # 尝试 additive 模型
            model = ExponentialSmoothing(
                values,
                trend="add",
                seasonal="add",
                seasonal_periods=seasonal_periods,
                damped_trend=True,
            )
            fit = model.fit(optimized=True, remove_bias=True)

            forecast_result = fit.forecast(steps=periods)

            # 计算预测区间
            residuals = values - fit.fittedvalues
            residual_std = np.std(residuals, ddof=1) if len(residuals) > 2 else 0.0
            z = 1.96

            predictions = []
            for i, val in enumerate(forecast_result):
                expansion = np.sqrt(1 + i / seasonal_periods)
                std_at_horizon = residual_std * expansion
                lower = max(float(val) - z * std_at_horizon, 0.0)
                upper = float(val) + z * std_at_horizon
                predictions.append({
                    "predicted_demand": round(float(val), 2),
                    "lower_bound": round(float(lower), 2),
                    "upper_bound": round(float(upper), 2),
                })

            return {
                "predictions": predictions,
                "model_name": "Holt-Winters",
                "model_params": {
                    "seasonal_periods": seasonal_periods,
                    "trend": "add",
                    "seasonal": "add",
                    "damped_trend": True,
                    "periods": periods,
                },
            }

        except Exception as e:
            logger.warning(
                "Holt-Winters 模型拟合失败: %s，回退到 EMA 模型", e,
            )
            return self.forecast_ema(series, periods=periods)

    def forecast_arima(
        self,
        series: pd.Series,
        order: tuple = (1, 1, 1),
        seasonal_order: tuple = (1, 1, 1, 7),
        periods: int = 14,
    ) -> dict:
        """
        ARIMA/SARIMA 预测

        使用季节性自回归积分滑动平均模型进行预测。
        如果模型拟合失败，自动回退到 EMA 模型。

        Args:
            series: 需求数据时间序列
            order: ARIMA 非季节性参数 (p, d, q)
            seasonal_order: SARIMA 季节性参数 (P, D, Q, s)
            periods: 预测天数，默认14天

        Returns:
            预测结果字典
        """
        logger.info(
            "执行 ARIMA 预测: order=%s, seasonal_order=%s, periods=%d",
            order, seasonal_order, periods,
        )

        values = series.values.astype(float)

        try:
            min_required = max(sum(order[:2]) + sum(seasonal_order[:2]) + seasonal_order[3], 10)
            if len(values) < min_required:
                logger.warning(
                    "数据量 %d 不足 ARIMA 最低要求 %d，回退到 EMA",
                    len(values), min_required,
                )
                return self.forecast_ema(series, periods=periods)

            # 使用 SARIMAX 模型
            model = SARIMAX(
                values,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fit = model.fit(disp=False, maxiter=200, method="lbfgs")

            forecast_result = fit.get_forecast(steps=periods)
            forecast_mean = forecast_result.predicted_mean
            forecast_ci = forecast_result.conf_int(alpha=0.05)

            predictions = []
            for i in range(periods):
                val = float(forecast_mean.iloc[i])
                lower = max(float(forecast_ci.iloc[i, 0]), 0.0)
                upper = float(forecast_ci.iloc[i, 1])
                predictions.append({
                    "predicted_demand": round(val, 2),
                    "lower_bound": round(lower, 2),
                    "upper_bound": round(upper, 2),
                })

            return {
                "predictions": predictions,
                "model_name": "ARIMA",
                "model_params": {
                    "order": list(order),
                    "seasonal_order": list(seasonal_order),
                    "periods": periods,
                },
            }

        except Exception as e:
            logger.warning(
                "ARIMA 模型拟合失败: %s，回退到 EMA 模型", e,
            )
            return self.forecast_ema(series, periods=periods)

    # ==================== 预测管道 ====================

    async def run_forecast(
        self,
        product_id: int,
        warehouse_id: int,
        forecast_days: int = 14,
        model_name: str | None = None,
    ) -> list[dict]:
        """
        执行完整的预测管道

        流程：获取历史数据 -> 选择模型 -> 执行预测 -> 返回结果列表。

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            forecast_days: 预测天数，默认14天
            model_name: 指定模型名称，为 None 时自动选择

        Returns:
            预测结果列表，每个元素包含 predicted_demand, lower_bound,
            upper_bound, model_name, model_params, forecast_date
        """
        logger.info(
            "开始预测: 产品=%d, 仓库=%d, 天数=%d, 模型=%s",
            product_id, warehouse_id, forecast_days, model_name,
        )

        # 获取历史数据
        hist_df = await self.get_historical_data(product_id, warehouse_id, days=90)

        if hist_df.empty:
            logger.warning(
                "产品 %d 仓库 %d 无历史数据，返回空预测", product_id, warehouse_id,
            )
            return []

        series = hist_df["demand"]

        # 选择模型
        if model_name is None:
            model_name = self.auto_select_model(series)

        # 执行预测
        model_dispatch = {
            "SMA": lambda: self.forecast_sma(series, periods=forecast_days),
            "EMA": lambda: self.forecast_ema(series, periods=forecast_days),
            "Holt-Winters": lambda: self.forecast_holt_winters(series, periods=forecast_days),
            "ARIMA": lambda: self.forecast_arima(series, periods=forecast_days),
        }

        if model_name not in model_dispatch:
            logger.warning("未知模型 '%s'，回退到自动选择", model_name)
            model_name = self.auto_select_model(series)

        result = model_dispatch[model_name]()

        # 构建返回结果，附加预测日期
        last_date = hist_df["date"].iloc[-1]
        forecast_results = []
        for i, pred in enumerate(result["predictions"]):
            forecast_date = last_date + timedelta(days=i + 1)
            forecast_results.append({
                "forecast_date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_demand": pred["predicted_demand"],
                "lower_bound": pred["lower_bound"],
                "upper_bound": pred["upper_bound"],
                "model_name": result["model_name"],
                "model_params": result["model_params"],
            })

        logger.info(
            "预测完成: 产品=%d, 仓库=%d, 模型=%s, 预测天数=%d",
            product_id, warehouse_id, result["model_name"], len(forecast_results),
        )
        return forecast_results

    async def run_batch_forecast(
        self,
        product_ids: list[int],
        warehouse_id: int,
        forecast_days: int = 14,
    ) -> list[dict]:
        """
        批量执行预测

        对多个产品并行执行预测，每个产品的预测结果合并到一个列表中。
        单个产品预测失败不影响其他产品。

        Args:
            product_ids: 产品ID列表
            warehouse_id: 仓库ID
            forecast_days: 预测天数，默认14天

        Returns:
            所有产品的预测结果列表
        """
        logger.info(
            "开始批量预测: 产品数=%d, 仓库=%d, 天数=%d",
            len(product_ids), warehouse_id, forecast_days,
        )

        all_results = []
        success_count = 0
        fail_count = 0

        for product_id in product_ids:
            try:
                results = await self.run_forecast(
                    product_id, warehouse_id, forecast_days,
                )
                for r in results:
                    r["product_id"] = product_id
                    r["warehouse_id"] = warehouse_id
                all_results.extend(results)
                success_count += 1
            except Exception as e:
                logger.error(
                    "产品 %d 预测失败: %s", product_id, e,
                    exc_info=True,
                )
                fail_count += 1

        logger.info(
            "批量预测完成: 成功=%d, 失败=%d, 总结果数=%d",
            success_count, fail_count, len(all_results),
        )
        return all_results

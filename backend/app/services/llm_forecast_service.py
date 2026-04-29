from __future__ import annotations

# -*- coding: utf-8 -*-
"""
LLM 预测服务

通过调用外部大模型（LLM）进行库存需求预测。
将历史数据序列化为结构化 prompt，调用 LLM 分析趋势和季节性，
解析返回的 JSON 预测结果，统一为标准返回格式。
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMForecastService:
    """
    LLM 预测服务

    通过外部大模型进行库存需求预测，与统计模型互补。
    LLM 擅长捕捉非规律性变化（促销、节假日、突发事件等），
    而统计模型擅长处理稳定趋势和季节性。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.forecast_llm_model
        self.temperature = settings.forecast_llm_temperature
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.enabled = settings.forecast_llm_enabled

    async def run_forecast(
        self,
        product_id: int,
        warehouse_id: int,
        forecast_days: int,
        product_info: dict,
        historical_data: list[dict],
    ) -> list[dict]:
        """
        调用 LLM 进行库存需求预测

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            forecast_days: 预测天数
            product_info: 产品信息字典（name, sku, product_type, unit 等）
            historical_data: 历史数据列表，每项包含 date 和 demand

        Returns:
            预测结果列表，格式与 ForecastService.run_forecast() 一致

        Raises:
            ValueError: LLM 预测未启用
            RuntimeError: LLM 调用失败或返回格式错误
        """
        if not self.enabled:
            raise ValueError(
                "LLM 预测模式未启用。请在配置中设置 FORECAST_LLM_ENABLED=true "
                "并确保 OPENAI_API_KEY 已配置。"
            )

        if not self.api_key:
            raise ValueError(
                "LLM 预测需要配置 OPENAI_API_KEY。"
            )

        logger.info(
            "LLM 预测: 产品=%d(%s), 仓库=%d, 天数=%d, 模型=%s",
            product_id, product_info.get("sku", ""), warehouse_id,
            forecast_days, self.model_name,
        )

        # 构建 prompt
        prompt = self._build_prompt(product_info, historical_data, forecast_days)

        # 调用 LLM
        response_text = await self._call_llm(prompt)

        # 解析响应
        predictions = self._parse_response(response_text, historical_data, forecast_days)

        logger.info(
            "LLM 预测完成: 产品=%d, 预测天数=%d",
            product_id, len(predictions),
        )
        return predictions

    def _build_prompt(
        self,
        product_info: dict,
        historical_data: list[dict],
        forecast_days: int,
    ) -> str:
        """
        构建预测 prompt

        将历史数据和产品信息格式化为结构化的 prompt，
        要求 LLM 返回 JSON 格式的预测结果。
        """
        product_name = product_info.get("name", "未知产品")
        product_sku = product_info.get("sku", "")
        product_type = product_info.get("product_type", "finished_good")
        product_type_label = "原材料" if product_type == "raw_material" else "产成品"
        unit = product_info.get("unit", "个")

        # 格式化历史数据
        history_lines = []
        for item in historical_data:
            date_str = item.get("date", "")
            demand = item.get("demand", 0)
            history_lines.append(f"  {{\"date\": \"{date_str}\", \"demand\": {demand}}}")

        history_json = ",\n".join(history_lines)

        prompt = f"""你是一个专业的库存需求预测分析师。请根据以下产品的历史需求数据，预测未来 {forecast_days} 天的需求量。

## 产品信息
- 名称: {product_name}
- SKU: {product_sku}
- 类型: {product_type_label}
- 单位: {unit}

## 历史每日需求数据（最近 {len(historical_data)} 天）
[
{history_json}
]

## 预测要求
1. 分析历史数据的趋势（上升/下降/平稳）
2. 识别可能的周期性模式（如每周、每月的规律）
3. 注意异常值（突然的峰值或谷值），判断是否为偶发事件
4. 考虑{"原材料消耗" if product_type == "raw_material" else "销售出库"}的业务特点

## 输出格式
请严格以 JSON 格式返回，不要包含任何其他文字：
{{
  "analysis": "简要的趋势分析说明（1-2句话）",
  "trend": "upward/downward/stable",
  "predictions": [
    {{"date": "YYYY-MM-DD", "predicted_demand": 数值, "confidence": "high/medium/low"}}
  ]
}}

注意：
- predictions 数组必须包含恰好 {forecast_days} 天的预测
- 日期从历史数据最后一天的下一天开始连续排列
- predicted_demand 必须为非负数值
- confidence 表示预测置信度，基于数据充足性和趋势稳定性"""

        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM API

        使用 OpenAI 兼容接口调用大模型。
        """
        try:
            from openai import AsyncOpenAI

            client_kwargs = {
                "api_key": self.api_key,
            }
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            client = AsyncOpenAI(**client_kwargs)

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的库存需求预测分析师。你只输出 JSON 格式的预测结果，不包含任何其他文字。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=2000,
            )

            return response.choices[0].message.content or ""

        except ImportError:
            raise RuntimeError(
                "openai 包未安装。请执行: pip install openai"
            )
        except Exception as e:
            logger.error("LLM 调用失败: %s", e, exc_info=True)
            raise RuntimeError(f"LLM 调用失败: {e}") from e

    def _parse_response(
        self,
        response_text: str,
        historical_data: list[dict],
        forecast_days: int,
    ) -> list[dict]:
        """
        解析 LLM 返回的 JSON 预测结果

        将 LLM 返回的 JSON 转换为与 ForecastService.run_forecast() 一致的格式。
        """
        # 提取 JSON（LLM 可能返回 markdown 代码块）
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 移除首尾的 ``` 行
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("LLM 返回的 JSON 解析失败: %s\n原始内容: %s", e, text[:500])
            raise RuntimeError(f"LLM 返回格式错误: {e}") from e

        predictions_raw = data.get("predictions", [])
        if not predictions_raw:
            raise RuntimeError("LLM 返回的预测结果为空")

        # 确定起始日期
        if historical_data:
            last_date_str = historical_data[-1].get("date", "")
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                last_date = datetime.now(timezone.utc)
        else:
            last_date = datetime.now(timezone.utc)

        # 转换为标准格式
        forecast_results = []
        for i, pred in enumerate(predictions_raw[:forecast_days]):
            forecast_date = last_date + timedelta(days=i + 1)
            predicted_demand = float(pred.get("predicted_demand", 0))
            confidence = pred.get("confidence", "medium")

            # 根据置信度设置置信区间宽度
            confidence_multiplier = {
                "high": 0.1,
                "medium": 0.2,
                "low": 0.35,
            }.get(confidence, 0.2)

            lower_bound = max(predicted_demand * (1 - confidence_multiplier), 0.0)
            upper_bound = predicted_demand * (1 + confidence_multiplier)

            forecast_results.append({
                "forecast_date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_demand": round(predicted_demand, 2),
                "lower_bound": round(lower_bound, 2),
                "upper_bound": round(upper_bound, 2),
                "model_name": f"LLM({self.model_name})",
                "model_params": {
                    "llm_model": self.model_name,
                    "temperature": self.temperature,
                    "trend": data.get("trend", "unknown"),
                    "analysis": data.get("analysis", ""),
                    "forecast_days": forecast_days,
                },
            })

        return forecast_results

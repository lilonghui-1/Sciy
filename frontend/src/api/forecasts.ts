import request from './request'

export interface ForecastData {
  id: number
  product_id: number
  product_name: string
  forecast_date: string
  predicted_demand: number
  confidence: number
  lower_bound: number
  upper_bound: number
  model_name: string
  created_at: string
}

export interface ForecastListParams {
  page?: number
  page_size?: number
  product_id?: number
  start_date?: string
  end_date?: string
}

export interface ForecastListResult {
  items: ForecastData[]
  total: number
  page: number
  page_size: number
}

export interface RunForecastParams {
  product_id: number
  days?: number
  model?: string
}

export interface RunForecastResult {
  task_id: string
  status: string
  message: string
}

/** 获取预测数据列表 */
export function getForecasts(params?: ForecastListParams) {
  return request.get<any, ForecastListResult>('/forecasts', { params })
}

/** 运行预测 */
export function runForecast(data: RunForecastParams) {
  return request.post<any, RunForecastResult>('/forecasts/run', data)
}

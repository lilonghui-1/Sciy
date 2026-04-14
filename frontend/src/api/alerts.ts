import request from './request'

export interface AlertRule {
  id: number
  name: string
  description?: string
  product_id?: number
  product_name?: string
  condition_type: 'low_stock' | 'over_stock' | 'expiry' | 'custom'
  threshold: number
  enabled: boolean
  notify_channels: string[]
  created_at: string
  updated_at: string
}

export interface AlertRuleListParams {
  page?: number
  page_size?: number
  enabled?: boolean
}

export interface AlertRuleListResult {
  items: AlertRule[]
  total: number
  page: number
  page_size: number
}

export interface CreateAlertRuleParams {
  name: string
  description?: string
  product_id?: number
  condition_type: 'low_stock' | 'over_stock' | 'expiry' | 'custom'
  threshold: number
  enabled?: boolean
  notify_channels?: string[]
}

export interface AlertEvent {
  id: number
  rule_id: number
  rule_name: string
  product_id: number
  product_name: string
  severity: 'info' | 'warning' | 'critical'
  message: string
  acknowledged: boolean
  acknowledged_by?: string
  acknowledged_at?: string
  created_at: string
}

export interface AlertEventListParams {
  page?: number
  page_size?: number
  severity?: string
  acknowledged?: boolean
}

export interface AlertEventListResult {
  items: AlertEvent[]
  total: number
  page: number
  page_size: number
}

/** 获取告警规则列表 */
export function getAlertRules(params?: AlertRuleListParams) {
  return request.get<any, AlertRuleListResult>('/alerts/rules', { params })
}

/** 创建告警规则 */
export function createAlertRule(data: CreateAlertRuleParams) {
  return request.post<any, AlertRule>('/alerts/rules', data)
}

/** 获取告警事件列表 */
export function getAlertEvents(params?: AlertEventListParams) {
  return request.get<any, AlertEventListResult>('/alerts/events', { params })
}

/** 确认告警 */
export function acknowledgeAlert(eventId: number) {
  return request.post<any, void>(`/alerts/events/${eventId}/acknowledge`)
}

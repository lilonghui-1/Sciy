import request from './request'

export interface InventoryItem {
  id: number
  product_id: number
  product_name: string
  product_sku: string
  warehouse_id: number
  warehouse_name: string
  quantity: number
  available_quantity: number
  locked_quantity: number
  updated_at: string
}

export interface InventoryListParams {
  page?: number
  page_size?: number
  product_id?: number
  warehouse_id?: number
  search?: string
  low_stock?: boolean
}

export interface InventoryListResult {
  items: InventoryItem[]
  total: number
  page: number
  page_size: number
}

export interface Transaction {
  id: number
  product_id: number
  product_name: string
  type: 'in' | 'out' | 'adjustment' | 'transfer'
  quantity: number
  previous_quantity: number
  new_quantity: number
  reference_no?: string
  remark?: string
  operator: string
  created_at: string
}

export interface TransactionListParams {
  page?: number
  page_size?: number
  product_id?: number
  type?: string
  start_date?: string
  end_date?: string
}

export interface TransactionListResult {
  items: Transaction[]
  total: number
  page: number
  page_size: number
}

export interface CreateTransactionParams {
  product_id: number
  type: 'in' | 'out' | 'adjustment' | 'transfer'
  quantity: number
  warehouse_id?: number
  reference_no?: string
  remark?: string
}

/** 获取库存列表 */
export function getInventory(params?: InventoryListParams) {
  return request.get<any, InventoryListResult>('/inventory', { params })
}

/** 获取库存事务记录 */
export function getTransactions(params?: TransactionListParams) {
  return request.get<any, TransactionListResult>('/inventory/transactions', { params })
}

/** 创建库存事务 */
export function createTransaction(data: CreateTransactionParams) {
  return request.post<any, Transaction>('/inventory/transactions', data)
}

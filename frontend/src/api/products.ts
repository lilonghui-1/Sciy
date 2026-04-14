import request from './request'

export interface Product {
  id: number
  name: string
  sku: string
  category: string
  description?: string
  unit: string
  cost_price: number
  selling_price: number
  min_stock: number
  max_stock: number
  created_at: string
  updated_at: string
}

export interface ProductListParams {
  page?: number
  page_size?: number
  search?: string
  category?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface ProductListResult {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface CreateProductParams {
  name: string
  sku: string
  category: string
  description?: string
  unit: string
  cost_price: number
  selling_price: number
  min_stock: number
  max_stock: number
}

export interface UpdateProductParams extends Partial<CreateProductParams> {}

/** 获取产品列表 */
export function getProducts(params?: ProductListParams) {
  return request.get<any, ProductListResult>('/products', { params })
}

/** 获取单个产品详情 */
export function getProduct(id: number) {
  return request.get<any, Product>(`/products/${id}`)
}

/** 创建产品 */
export function createProduct(data: CreateProductParams) {
  return request.post<any, Product>('/products', data)
}

/** 更新产品 */
export function updateProduct(id: number, data: UpdateProductParams) {
  return request.put<any, Product>(`/products/${id}`, data)
}

/** 删除产品 */
export function deleteProduct(id: number) {
  return request.delete<any, void>(`/products/${id}`)
}

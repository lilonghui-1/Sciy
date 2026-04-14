import request from './request'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  password: string
  email: string
  phone?: string
}

export interface UserInfo {
  id: number
  username: string
  email: string
  phone?: string
  role: string
}

export interface LoginResult {
  token: string
  user: UserInfo
}

/** 用户登录 */
export function login(data: LoginParams) {
  return request.post<any, LoginResult>('/auth/login', data)
}

/** 用户注册 */
export function register(data: RegisterParams) {
  return request.post<any, UserInfo>('/auth/register', data)
}

/** 获取当前用户信息 */
export function getUserInfo() {
  return request.get<any, UserInfo>('/auth/me')
}

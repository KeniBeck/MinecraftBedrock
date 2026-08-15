import { apiClient } from './client'

export type RoleName = 'super_admin' | 'admin' | 'operator' | 'viewer'

/**
 * Claves de cache de TanStack Query para el módulo IAM. No hay `listUsers`
 * (el backend no expone GET /users): `userKeys` sirve para invalidar tras
 * crear/asignar rol.
 */
export const userKeys = {
  all: ['users'] as const,
  detail: (id: string) => [...userKeys.all, id] as const,
}

/** Claves de las API keys del usuario autenticado. */
export const apiKeyKeys = {
  all: ['iam', 'api-keys'] as const,
}

/** Clave del estado 2FA del usuario autenticado (`GET /auth/2fa/status`). */
export const twoFactorKeys = {
  status: ['iam', '2fa', 'status'] as const,
}

/** Claves del catálogo de roles (`GET /roles`). */
export const roleKeys = {
  all: ['iam', 'roles'] as const,
}

/** Claves de auditoría: listado con filtros y verify de integridad. */
export const auditKeys = {
  list: (filters: AuditFilters) => [...auditKeys.all, filters] as const,
  verify: ['iam', 'audit', 'verify'] as const,
  all: ['iam', 'audit'] as const,
}

/** `UserResponse` — usuario del panel (schema IAM real). */
export interface User {
  id: string
  username: string
  display_name: string
  status: string
  roles: string[]
  created_at: string | null
  last_login_at: string | null
  email: string | null
}

/** `CreateUserRequest` — POST /users. */
export interface CreateUserRequest {
  username: string
  password: string
  display_name?: string
}

/** `UpdateUserRequest` — PUT /users/{id}. No incluye username/password. */
export interface UpdateUserRequest {
  display_name?: string
  email?: string
  status?: 'active' | 'suspended'
  roles?: RoleName[]
}

/** `RoleResponse` — rol del catálogo base (`GET /roles`). */
export interface Role {
  id: string
  name: string
  description: string
  is_system: boolean
}

/** `AuditLogResponse` — registro de auditoría (`GET /iam/audit`). */
export interface AuditLog {
  id: string
  actor_id: string | null
  actor_type: string
  action: string
  resource_type: string | null
  resource_id: string | null
  result: string
  detail: Record<string, unknown>
  ip: string | null
  ua: string | null
  created_at: string | null
  hash: string | null
  prev_hash: string | null
}

/** `AuditLogListResponse` — página de auditoría. */
export interface AuditLogPage {
  items: AuditLog[]
  total: number
}

/** Filtros y paginación de `GET /iam/audit`. */
export interface AuditFilters {
  actor_id?: string
  action?: string
  from?: string
  to?: string
  limit?: number
  offset?: number
}

/** `AssignRoleRequest` — POST /users/{id}/roles. */
export interface AssignRoleRequest {
  role: RoleName
}

/** `ApiKeyResponse` — API key del usuario autenticado. */
export interface ApiKey {
  id: string
  name: string
  scopes: string[]
  created_at: string | null
  last_used_at: string | null
  expires_at: string | null
}

/** `ApiKeyCreatedResponse` — material visible una sola vez. */
export interface ApiKeyCreated extends ApiKey {
  material: string
}

/** `ApiKeyRequest` — POST /iam/api-keys. */
export interface CreateApiKeyRequest {
  name: string
  scopes: string[]
}

/** `EnableTwoFactorResponse` — secreto + URI + backup codes (una sola vez). */
export interface EnableTwoFactor {
  secret: string
  provisioning_uri: string
  backup_codes: string[]
}

/** `BackupCodesResponse`. */
export interface BackupCodes {
  backup_codes: string[]
}

/** `TwoFactorStatusResponse`. */
export interface TwoFactorStatus {
  enabled: boolean
}

/** `AuditVerifyResponse`. */
export interface AuditVerify {
  valid: boolean
  errors: string[]
}

/** `POST /users` (201) — crear usuario (admin). */
export async function createUser(data: CreateUserRequest): Promise<User> {
  const res = await apiClient.post<User>('/users', data)
  return res.data
}

/** `POST /users/{id}/roles` — asignar rol global (admin). */
export async function assignRole(userId: string, request: AssignRoleRequest): Promise<User> {
  const res = await apiClient.post<User>(`/users/${encodeURIComponent(userId)}/roles`, request)
  return res.data
}

/** `GET /users` — listar todos los usuarios (get: iam.view). */
export async function listUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>('/users')
  return data
}

/** `GET /users/{id}` — detalle de un usuario (get: iam.view). */
export async function getUser(userId: string): Promise<User> {
  const { data } = await apiClient.get<User>(`/users/${encodeURIComponent(userId)}`)
  return data
}

/** `PUT /users/{id}` — actualizar usuario (iam.manage). */
export async function updateUser(userId: string, request: UpdateUserRequest): Promise<User> {
  const res = await apiClient.put<User>(
    `/users/${encodeURIComponent(userId)}`,
    request,
  )
  return res.data
}

/** `DELETE /users/{id}` (204) — suspender usuario, soft delete (iam.manage). */
export async function deleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${encodeURIComponent(userId)}`)
}

/** `GET /roles` — catálogo de roles del panel (get: iam.view). */
export async function listRoles(): Promise<Role[]> {
  const { data } = await apiClient.get<Role[]>('/roles')
  return data
}

/** `GET /iam/audit` — listado de auditoría con filtros y paginación. */
export async function listAuditLogs(filters: AuditFilters = {}): Promise<AuditLogPage> {
  const params: Record<string, string | number> = {}
  if (filters.actor_id) params.actor_id = filters.actor_id
  if (filters.action) params.action = filters.action
  if (filters.from) params.from = filters.from
  if (filters.to) params.to = filters.to
  if (filters.limit !== undefined) params.limit = filters.limit
  if (filters.offset !== undefined) params.offset = filters.offset
  const { data } = await apiClient.get<AuditLogPage>('/iam/audit', { params })
  return data
}

/** `GET /iam/api-keys` — API keys del usuario autenticado. */
export async function listApiKeys(): Promise<ApiKey[]> {
  const { data } = await apiClient.get<ApiKey[]>('/iam/api-keys')
  return data
}

/** `POST /iam/api-keys` (201) — crear API key (material una sola vez). */
export async function createApiKey(data: CreateApiKeyRequest): Promise<ApiKeyCreated> {
  const res = await apiClient.post<ApiKeyCreated>('/iam/api-keys', data)
  return res.data
}

/** `DELETE /iam/api-keys/{id}` (204) — revocar API key. */
export async function revokeApiKey(id: string): Promise<void> {
  await apiClient.delete(`/iam/api-keys/${encodeURIComponent(id)}`)
}

/** `POST /iam/api-keys/{id}/regenerate` — rotar API key (material una vez). */
export async function regenerateApiKey(id: string): Promise<ApiKeyCreated> {
  const res = await apiClient.post<ApiKeyCreated>(
    `/iam/api-keys/${encodeURIComponent(id)}/regenerate`,
  )
  return res.data
}

/** `GET /iam/audit/verify` — verificar integridad del audit log (admin). */
export async function verifyAuditChain(): Promise<AuditVerify> {
  const { data } = await apiClient.get<AuditVerify>('/iam/audit/verify')
  return data
}

/** `POST /auth/2fa/enable` — iniciar 2FA (secreto + backup codes una vez). */
export async function enable2FA(): Promise<EnableTwoFactor> {
  const { data } = await apiClient.post<EnableTwoFactor>('/auth/2fa/enable')
  return data
}

/** `POST /auth/2fa/verify` (204) — confirmar 2FA con un código TOTP. */
export async function confirm2FA(code: string): Promise<void> {
  await apiClient.post('/auth/2fa/verify', { code })
}

/** `POST /auth/2fa/backup` — regenerar backup codes (2FA ya confirmado). */
export async function regenerateBackupCodes(): Promise<BackupCodes> {
  const { data } = await apiClient.post<BackupCodes>('/auth/2fa/backup')
  return data
}

/** `POST /auth/2fa/disable` (204) — desactivar 2FA (limpia secreto + codes). */
export async function disable2FA(): Promise<void> {
  await apiClient.post('/auth/2fa/disable')
}

/** `GET /auth/2fa/status` — estado del 2FA del usuario autenticado. */
export async function twoFactorStatus(): Promise<TwoFactorStatus> {
  const { data } = await apiClient.get<TwoFactorStatus>('/auth/2fa/status')
  return data
}
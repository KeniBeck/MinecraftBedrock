import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  apiKeyKeys,
  assignRole,
  confirm2FA,
  createApiKey,
  createUser,
  deleteUser,
  enable2FA,
  listApiKeys,
  listAuditLogs,
  listRoles,
  listUsers,
  regenerateApiKey,
  regenerateBackupCodes,
  revokeApiKey,
  roleKeys,
  updateUser,
  userKeys,
  verifyAuditChain,
  type AssignRoleRequest,
  type AuditFilters,
  type CreateApiKeyRequest,
  type CreateUserRequest,
  type UpdateUserRequest,
} from '@/lib/api/iam'

export { apiKeyKeys, auditKeys, roleKeys, userKeys } from '@/lib/api/iam'

/** `POST /users` + rol inicial (si se indica) — crear usuario (admin). */
export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: CreateUserRequest & { role?: AssignRoleRequest['role'] }) => {
      const user = await createUser(input)
      if (input.role && input.role !== 'viewer') {
        await assignRole(user.id, { role: input.role })
      }
      return user
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all })
    },
  })
}

/** `GET /iam/api-keys` — API keys del usuario autenticado. */
export function useApiKeys() {
  return useQuery({
    queryKey: apiKeyKeys.all,
    queryFn: listApiKeys,
    refetchOnWindowFocus: false,
  })
}

/** `GET /users` — listar todos los usuarios (get: iam.view). */
export function useUsers() {
  return useQuery({
    queryKey: userKeys.all,
    queryFn: listUsers,
    refetchOnWindowFocus: false,
  })
}

/** `GET /roles` — catálogo de roles del panel (get: iam.view). */
export function useRoles() {
  return useQuery({
    queryKey: roleKeys.all,
    queryFn: listRoles,
    refetchOnWindowFocus: false,
  })
}

/** `PUT /users/{id}` — actualizar usuario (iam.manage). */
export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateUserRequest }) => updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all })
    },
  })
}

/** `DELETE /users/{id}` — suspender usuario, soft delete (iam.manage). */
export function useDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all })
    },
  })
}

/** `GET /iam/audit` — listado de auditoría con filtros y paginación. */
export function useAuditLogs(filters: AuditFilters) {
  return useQuery({
    queryKey: auditKeys.list(filters),
    queryFn: () => listAuditLogs(filters),
    refetchOnWindowFocus: false,
  })
}

/** `POST /iam/api-keys` — crear API key (material una sola vez). */
export function useCreateApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateApiKeyRequest) => createApiKey(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.all })
    },
  })
}

/** `DELETE /iam/api-keys/{id}` — revocar API key. */
export function useRevokeApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => revokeApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.all })
    },
  })
}

/** `POST /iam/api-keys/{id}/regenerate` — rotar API key. */
export function useRegenerateApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => regenerateApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.all })
    },
  })
}

/** `GET /iam/audit/verify` — verificar integridad del audit log (admin). */
export function useVerifyAuditChain() {
  return useMutation({
    mutationFn: () => verifyAuditChain(),
  })
}

/** `POST /auth/2fa/enable` — iniciar 2FA. */
export function useEnable2FA() {
  return useMutation({ mutationFn: () => enable2FA() })
}

/** `POST /auth/2fa/verify` — confirmar 2FA con un código TOTP. */
export function useConfirm2FA() {
  return useMutation({ mutationFn: (code: string) => confirm2FA(code) })
}

/** `POST /auth/2fa/backup` — regenerar backup codes. */
export function useRegenerateBackupCodes() {
  return useMutation({ mutationFn: () => regenerateBackupCodes() })
}
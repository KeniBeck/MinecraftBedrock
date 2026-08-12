import { apiClient } from './client'

/**
 * Claves de cache de TanStack Query para el módulo Template (frontend-standards
 * §13): `all(serverId)` es la lista `['templates', serverId]`; `detail` deja
 * sitio para una plantilla concreta si hiciera falta.
 */
export const templateKeys = {
  all: (serverId: string) => ['templates', serverId] as const,
  detail: (serverId: string, id: string) => [...templateKeys.all(serverId), id] as const,
}

/**
 * Tipos del módulo Template — verificados contra
 * `apps/backend/src/app/modules/template/api/schemas.py` (TemplateResponse,
 * CaptureTemplateRequest, ApplyTemplateRequest). Todas las rutas están
 * **scoped a un servidor** (`/servers/{id}/templates...`), no son globales.
 * El listado devuelve un ARRAY (`list[TemplateResponse]`), no un envoltorio.
 */

export interface Template {
  id: string
  name: string
  version: string
  size_bytes: number
  origin_server_id: string | null
  origin_world: string | null
  created_at: string | null
  updated_at: string | null
}

/** Cuerpo de `POST /servers/{id}/templates/capture` — solo `name`. */
export interface CaptureTemplateRequest {
  name: string
}

/** Cuerpo de `POST /servers/{id}/templates/{template_id}/apply`. */
export interface ApplyTemplateRequest {
  /** Si se omite, se usa el nombre del mundo capturado en la plantilla. */
  world_name?: string
}

/** `GET /servers/{id}/templates`. */
export async function listTemplates(serverId: string): Promise<Template[]> {
  const { data } = await apiClient.get<Template[]>(`/servers/${serverId}/templates`)
  return data
}

/** `GET /servers/{id}/templates/{template_id}`. */
export async function getTemplate(serverId: string, templateId: string): Promise<Template> {
  const { data } = await apiClient.get<Template>(
    `/servers/${serverId}/templates/${templateId}`,
  )
  return data
}

/** `POST /servers/{id}/templates/capture` (201). */
export async function captureTemplate(
  serverId: string,
  data: CaptureTemplateRequest,
): Promise<Template> {
  const res = await apiClient.post<Template>(`/servers/${serverId}/templates/capture`, data)
  return res.data
}

/** `POST /servers/{id}/templates/{template_id}/apply` — devuelve la plantilla. */
export async function applyTemplate(
  serverId: string,
  templateId: string,
  data: ApplyTemplateRequest,
): Promise<Template> {
  const res = await apiClient.post<Template>(
    `/servers/${serverId}/templates/${templateId}/apply`,
    data,
  )
  return res.data
}

/** `DELETE /servers/{id}/templates/{template_id}` (204). */
export async function deleteTemplate(serverId: string, templateId: string): Promise<void> {
  await apiClient.delete(`/servers/${serverId}/templates/${templateId}`)
}

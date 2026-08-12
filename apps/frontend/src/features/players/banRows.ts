import type { GlobalBanResponse, ServerBanResponse } from '@/lib/api/players'

export interface BanRow {
  banId: string
  scope: 'global' | 'server'
  gamertag: string
  reason: string | null
  expires_at: string | null
  created_at: string
  playerId: string
}

/** Convierte las respuestas del backend a filas uniformes del listado. */
export function toBanRows(global: GlobalBanResponse[], server: ServerBanResponse[]): BanRow[] {
  const globalRows: BanRow[] = global.map((ban) => ({
    banId: ban.id,
    scope: 'global',
    gamertag: ban.gamertag,
    reason: ban.reason,
    expires_at: ban.expires_at,
    created_at: ban.created_at,
    playerId: ban.id,
  }))
  const serverRows: BanRow[] = server.map((ban) => ({
    banId: ban.id,
    scope: 'server',
    gamertag: ban.gamertag,
    reason: ban.reason,
    expires_at: ban.expires_at,
    created_at: ban.created_at,
    playerId: ban.xuid ?? ban.id,
  }))
  return [...globalRows, ...serverRows].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )
}

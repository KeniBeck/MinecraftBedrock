/** Resumen numérico del dashboard, derivado de la lista de servidores + feed de eventos. */
export interface DashboardStats {
  total: number
  online: number
  offline: number
  /**
   * Jugadores online globales. `GET /servers` no expone `players` (verificado
   * en el backend) y el dashboard no abre un WS de monitoreo por servidor, por
   * lo que vale `null` (se muestra "—").
   */
  players: number | null
  recentBackups: number
}
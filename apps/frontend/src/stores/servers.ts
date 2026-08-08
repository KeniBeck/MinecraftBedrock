import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Estado UI del servidor activo (id). Es SOLO selección de UI — los datos del
 * servidor viven en TanStack Query, nunca en zustand (frontend-standards §1).
 */
interface ActiveServerState {
  activeServerId: string | null
  setActiveServer: (serverId: string | null) => void
}

export const useActiveServer = create<ActiveServerState>()(
  persist(
    (set) => ({
      activeServerId: null,
      setActiveServer: (activeServerId) => set({ activeServerId }),
    }),
    { name: 'bedrock-panel-active-server' },
  ),
)

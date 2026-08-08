import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'dark' | 'light'

export interface BackgroundDef {
  id: string
  name: string
  /** Clase CSS con `background` (gradiente/voxel) aplicada a las capas. */
  css: string
  /** Paleta de acento asociada (frontend-standards §9.2: mapa fijo). */
  accent: string
}

/**
 * Catálogo de fondos predefinidos (frontend-standards §9.2). No son URLs
 * arbitrarias: ids canónicos con su propia combinación de acento. Default:
 * cueva morada con acento verde (el del mockup).
 */
export const BACKGROUNDS: BackgroundDef[] = [
  {
    id: 'cave',
    name: 'Cueva',
    css: 'radial-gradient(1200px 800px at 70% -10%, rgba(88,28,135,0.55), transparent 60%), radial-gradient(900px 700px at 10% 110%, rgba(49,46,129,0.5), transparent 60%), linear-gradient(180deg, #090a14 0%, #0d0f1f 55%, #141329 100%)',
    accent: 'emerald',
  },
  {
    id: 'end',
    name: 'End',
    css: 'radial-gradient(1100px 750px at 20% -20%, rgba(30,58,138,0.55), transparent 60%), radial-gradient(900px 700px at 90% 110%, rgba(12,74,110,0.5), transparent 60%), linear-gradient(180deg, #020617 0%, #06121f 55%, #0a0f1e 100%)',
    accent: 'sky',
  },
  {
    id: 'nether',
    name: 'Nether',
    css: 'radial-gradient(1100px 750px at 65% -15%, rgba(190,18,60,0.45), transparent 60%), radial-gradient(900px 700px at 15% 110%, rgba(124,45,18,0.5), transparent 60%), linear-gradient(180deg, #14060a 0%, #1a0b12 55%, #241019 100%)',
    accent: 'orange',
  },
]

interface ThemeState {
  theme: Theme
  backgroundId: string
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  setBackground: (backgroundId: string) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      backgroundId: 'cave',
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === 'dark' ? 'light' : 'dark' }),
      setBackground: (backgroundId) => set({ backgroundId }),
    }),
    { name: 'bedrock-panel-theme' },
  ),
)

/** Resuelve el fondo actual; nunca devuelve undefined (fallback al default). */
export function currentBackground(state: { backgroundId: string }): BackgroundDef {
  return BACKGROUNDS.find((b) => b.id === state.backgroundId) ?? BACKGROUNDS[0]!
}

/** Aplica la clase `dark` al `<html>` (Tailwind v4 usa `.dark` como variant). */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

import { currentBackground, useThemeStore } from '@/stores/theme'

/**
 * Fondo dinámico del panel (frontend-standards §9.2): se ve detrás de las
 * superficies de glassmorphism. Al cambiar de fondo, la nueva capa se monta con
 * una animación de fade-in (CSS `@keyframes`, remount por `key`), sin gestionar
 * capas en estado React — no hay setState en effects.
 */
export function Background() {
  const backgroundId = useThemeStore((state) => state.backgroundId)
  const background = currentBackground({ backgroundId })

  return (
    <div aria-hidden className="fixed inset-0 -z-10 overflow-hidden">
      <div
        key={background.id}
        className="animate-background-fade absolute inset-0"
        style={{ background: background.css }}
      />
      {/* Vignette para que las superficies de glassmorphism respiren. */}
      <div className="absolute inset-0 bg-black/30" />
    </div>
  )
}

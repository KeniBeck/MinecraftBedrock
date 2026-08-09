import { currentBackground, useThemeStore } from '@/stores/theme'

/**
 * Fondo dinámico del panel (frontend-standards §9.2): se ve detrás de las
 * superficies de glassmorphism. Al cambiar de fondo, la nueva capa se monta con
 * una animación de fade-in (CSS `@keyframes`, remount por `key`), sin gestionar
 * capas en estado React — no hay setState en effects.
 *
 * Las imágenes reales (`type: 'image'`) se tratan como "luz ambiental difusa"
 * con un "desenfoque estratégico": `filter: blur(12px)` + `scale(1.05)` dejan
 * ver la silueta del paisaje en el centro mientras suavizan los detalles, y una
 * viñeta radial (transparente en el centro, oscura en los bordes) integra la
 * imagen con el tema oscuro del panel sin ocultarla. Un desenfoque excesivo
 * (p. ej. blur(80px)) la convierte en una mancha abstracta de color.
 */
export function Background() {
  const backgroundId = useThemeStore((state) => state.backgroundId)
  const background = currentBackground({ backgroundId })
  const isImage = background.type === 'image'

  return (
    <div aria-hidden className="fixed inset-0 -z-10 overflow-hidden">
      <div
        key={background.id}
        className="animate-background-fade absolute inset-0"
        style={{
          background: background.css,
          ...(isImage
            ? {
                filter: 'blur(12px)',
                transform: 'scale(1.05)',
              }
            : undefined),
        }}
      />
      {/* Viñeta estratégica para imágenes: centro claro, bordes fundidos con el
          tema oscuro (frontend-standards §9.2). */}
      {isImage && (
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(circle at 50% 50%, transparent 40%, rgba(9,10,20,0.85) 100%)',
          }}
        />
      )}
      {/* Vignette para que las superficies de glassmorphism respiren. */}
      <div className="absolute inset-0 bg-black/30" />
    </div>
  )
}

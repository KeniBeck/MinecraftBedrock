import type { ConfigPropertyValue } from '@/lib/api/configuration'

export type PropertyGroupId = 'general' | 'game' | 'world'

export interface PropertyGroup {
  id: PropertyGroupId
  label: string
  description: string
}

export type PropertyKind = 'string' | 'int' | 'enum'

export interface PropertyDef {
  key: string
  label: string
  hint: string
  group: PropertyGroupId
  kind: PropertyKind
  defaultValue: ConfigPropertyValue
  min?: number
  max?: number
  enum?: string[]
  /** La propiedad admite el valor vacío (p. ej. semilla opcional). */
  optional?: boolean
}

export const CONFIG_GROUPS: PropertyGroup[] = [
  { id: 'general', label: 'General', description: 'Identidad y capacidad del servidor.' },
  { id: 'game', label: 'Juego', description: 'Modo de juego, dificultad y reglas.' },
  { id: 'world', label: 'Mundo', description: 'Nivel, semilla y distancia de renderizado.' },
]

/**
 * Catálogo de propiedades editables de `server.properties`.
 *
 * El backend NO sirve un `property-definitions.json` (solo valida y proyecta a
 * variables de entorno el subconjunto de §3.7). Este catálogo es un mapa estático
 * que espeja exactamente el subconjunto que el backend aplica al contenedor
 * (`_PROPERTY_TO_ENV` en `configuration/domain/property_schema.py`); el resto de
 * claves de `server.properties` se persisten pero aún no se aplican, por lo que
 * no se exponen aquí (discrepancia documentada en el change-log).
 */
export const CONFIG_PROPERTIES: PropertyDef[] = [
  {
    key: 'server-name',
    label: 'Nombre del servidor',
    hint: 'Visible en el servidor de lista y en el perfil de juego.',
    group: 'general',
    kind: 'string',
    defaultValue: 'Dedicated Server',
  },
  {
    key: 'max-players',
    label: 'Jugadores máximos',
    hint: `Capacidad de jugadores simultáneos (máx. backend ${40}).`,
    group: 'general',
    kind: 'int',
    defaultValue: '10',
    min: 1,
    max: 40,
  },
  {
    key: 'gamemode',
    label: 'Modo de juego',
    hint: 'Modo por defecto para los jugadores que entran.',
    group: 'game',
    kind: 'enum',
    defaultValue: 'survival',
    enum: ['survival', 'creative', 'adventure', 'spectator'],
  },
  {
    key: 'difficulty',
    label: 'Dificultad',
    hint: 'Dificultad del mundo.',
    group: 'game',
    kind: 'enum',
    defaultValue: 'peaceful',
    enum: ['peaceful', 'easy', 'normal', 'hard'],
  },
  {
    key: 'level-name',
    label: 'Nombre del nivel',
    hint: 'Carpeta/mundo que BDS carga al arrancar.',
    group: 'world',
    kind: 'string',
    defaultValue: 'level',
  },
  {
    key: 'level-seed',
    label: 'Semilla del nivel',
    hint: 'Solo se aplica al generar un mundo nuevo; no regenera uno existente.',
    group: 'world',
    kind: 'string',
    defaultValue: '',
    optional: true,
  },
  {
    key: 'view-distance',
    label: 'Distancia de renderizado',
    hint: 'Chunks visibles en torno al jugador.',
    group: 'world',
    kind: 'int',
    defaultValue: '10',
    min: 2,
    max: 32,
  },
]

export function groupProperties(groupId: PropertyGroupId): PropertyDef[] {
  return CONFIG_PROPERTIES.filter((prop) => prop.group === groupId)
}

export function isDirty(
  current: Record<string, ConfigPropertyValue>,
  original: Record<string, ConfigPropertyValue>,
): boolean {
  return CONFIG_PROPERTIES.some(
    (prop) => (current[prop.key] ?? '') !== (original[prop.key] ?? ''),
  )
}
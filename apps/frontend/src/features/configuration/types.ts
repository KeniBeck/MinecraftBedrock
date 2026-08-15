import type { ConfigPropertyValue } from '@/lib/api/configuration'
import type { PropertyDef } from './properties'

/** Valores del formulario de configuración, indexados por clave de property. */
export type ConfigFormValues = Record<string, ConfigPropertyValue>

/** Errores de validación inline, indexados por clave de property. */
export type ConfigFormErrors = Record<string, string | undefined>

/** Valida un campo individual según el tipo y rangos del catálogo. */
export function validateProperty(def: PropertyDef, raw: string): string | undefined {
  if (def.kind === 'int') {
    if (!/^-?\d+$/.test(raw.trim())) return 'Debe ser un número entero.'
    const value = Number(raw)
    if (def.min !== undefined && value < def.min) return `Mínimo ${def.min}.`
    if (def.max !== undefined && value > def.max) return `Máximo ${def.max}.`
    return undefined
  }
  if (def.kind === 'enum' && def.enum) {
    if (!def.enum.includes(raw)) return 'Valor no permitido.'
    return undefined
  }
  if (def.kind === 'string' && raw.trim() === '' && !def.optional) {
    return 'Campo requerido.'
  }
  return undefined
}

/** Valida un borrador completo del formulario contra el catálogo. */
export function validateDraft(
  values: ConfigFormValues,
  defs: readonly PropertyDef[],
): ConfigFormErrors {
  const errors: ConfigFormErrors = {}
  for (const def of defs) {
    const error = validateProperty(def, values[def.key] ?? def.defaultValue)
    if (error) errors[def.key] = error
  }
  return errors
}
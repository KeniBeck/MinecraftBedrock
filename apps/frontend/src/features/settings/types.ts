import type { PanelSetting } from '@/lib/api/settings'

export type { PanelSetting }

/** Categorías del catálogo de ajustes del panel (settings/domain/defaults.py). */
export const SETTING_CATEGORIES = ['storage', 'limits', 'defaults', 'system'] as const
export type SettingCategory = (typeof SETTING_CATEGORIES)[number]

export const CATEGORY_LABELS: Record<SettingCategory, string> = {
  storage: 'Almacenamiento',
  limits: 'Límites y recursos',
  defaults: 'Valores por defecto',
  system: 'Sistema',
}

/** Agrupa los ajustes por categoría (manteniendo el orden del catálogo). */
export function groupByCategory(settings: PanelSetting[]): Record<string, PanelSetting[]> {
  return settings.reduce<Record<string, PanelSetting[]>>((acc, setting) => {
    const category = SETTING_CATEGORIES.includes(setting.category as SettingCategory)
      ? setting.category
      : 'system'
    ;(acc[category] ??= []).push(setting)
    return acc
  }, {})
}

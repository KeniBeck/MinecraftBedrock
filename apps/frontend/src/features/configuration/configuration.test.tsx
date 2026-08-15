import { describe, expect, it } from 'vitest'

import { CONFIG_PROPERTIES, groupProperties, isDirty } from './properties'
import { validateDraft, validateProperty } from './types'
import { buildPropertiesPayload } from './hooks'

describe('configuration properties catalogue', () => {
  it('proyecta el catálogo editable en los tres grupos', () => {
    expect(groupProperties('general').map((p) => p.key)).toEqual([
      'server-name',
      'max-players',
    ])
    expect(groupProperties('game').map((p) => p.key)).toEqual(['gamemode', 'difficulty'])
    expect(groupProperties('world').map((p) => p.key)).toEqual([
      'level-name',
      'level-seed',
      'view-distance',
    ])
  })

  it('detecta cambios respecto al perfil original', () => {
    expect(isDirty({ gamemode: 'creative' }, { gamemode: 'survival' })).toBe(true)
    expect(isDirty({ gamemode: 'survival' }, { gamemode: 'survival' })).toBe(false)
  })
})

describe('validateProperty', () => {
  const int = CONFIG_PROPERTIES.find((p) => p.key === 'max-players')!
  const enumDef = CONFIG_PROPERTIES.find((p) => p.key === 'gamemode')!

  it('valida enteros por rango', () => {
    expect(validateProperty(int, '20')).toBeUndefined()
    expect(validateProperty(int, 'abc')).toBe('Debe ser un número entero.')
    expect(validateProperty(int, '41')).toBe('Máximo 40.')
    expect(validateProperty(int, '0')).toBe('Mínimo 1.')
  })

  it('valida enums contra el set permitido', () => {
    expect(validateProperty(enumDef, 'adventure')).toBeUndefined()
    expect(validateProperty(enumDef, 'other')).toBe('Valor no permitido.')
  })

  it('rechaza strings vacíos', () => {
    const name = CONFIG_PROPERTIES.find((p) => p.key === 'server-name')!
    expect(validateProperty(name, 'Mi Mundo')).toBeUndefined()
    expect(validateProperty(name, '')).toBe('Campo requerido.')
  })
})

describe('validateDraft', () => {
  it('acumula errores de todos los campos', () => {
    const errors = validateDraft({ 'max-players': '41' }, CONFIG_PROPERTIES)
    expect(errors['max-players']).toBe('Máximo 40.')
  })
})

describe('buildPropertiesPayload', () => {
  const original = { 'server-name': 'A', 'max-players': '10' }

  it('incluye todas las claves del catálogo al guardar (onlyChanged=false)', () => {
    const payload = buildPropertiesPayload(
      { 'server-name': 'A', 'max-players': '10', extra: 'x' },
      original,
      false,
    )
    expect(payload).toEqual({ 'server-name': 'A', 'max-players': '10' })
    expect('extra' in payload).toBe(false)
  })

  it('solo envía las claves que difieren (onlyChanged=true)', () => {
    const payload = buildPropertiesPayload(
      { 'server-name': 'B', 'max-players': '10' },
      original,
      true,
    )
    expect(payload).toEqual({ 'server-name': 'B' })
  })
})
import { describe, expect, it } from 'vitest'
import {
  buildCronFromParts,
  describeCron,
  isValidCron,
  parseCronToParts,
} from './cron'

describe('cron helpers', () => {
  describe('parseCronToParts', () => {
    it('divide una expresión en 5 partes', () => {
      expect(parseCronToParts('0 3 * * *')).toEqual(['0', '3', '*', '*', '*'])
    })

    it('rellena con "*" si hay menos de 5 campos', () => {
      expect(parseCronToParts('* *')).toEqual(['*', '*', '*', '*', '*'])
    })

    it('ignora campos de sobra', () => {
      expect(parseCronToParts('0 3 1 2 3 4')).toEqual(['0', '3', '1', '2', '3'])
    })
  })

  describe('buildCronFromParts', () => {
    it('une las partes con un espacio', () => {
      expect(buildCronFromParts(['0', '5', '*', '*', '*'])).toBe('0 5 * * *')
    })

    it('convierte vacíos en "*"', () => {
      expect(buildCronFromParts(['0', '', '*', '*', '*'])).toBe('0 * * * *')
    })
  })

  describe('isValidCron', () => {
    it('acepta "*" y números en rango', () => {
      expect(isValidCron('* * * * *')).toBe(true)
      expect(isValidCron('0 3 * * *')).toBe(true)
      expect(isValidCron('15 9 * * 1')).toBe(true)
    })

    it('rechaza campos fuera de rango o inválidos', () => {
      expect(isValidCron('60 * * * *')).toBe(false)
      expect(isValidCron('0 24 * * *')).toBe(false)
      expect(isValidCron('* * * *')).toBe(false)
      expect(isValidCron('0 3 * * fred')).toBe(false)
    })
  })

  describe('describeCron', () => {
    it('describe "todos los días" con la hora', () => {
      expect(describeCron('0 3 * * *')).toBe('todos los días a las 03:00')
    })

    it('describe cada N minutos', () => {
      expect(describeCron('*/5 * * * *')).toBe('cada 5 minutos')
    })

    it('describe un día de la semana', () => {
      expect(describeCron('0 0 * * 1')).toBe('los lunes a las 00:00')
    })

    it('describe un día del mes', () => {
      expect(describeCron('0 0 1 * *')).toBe('el día 1 de cada mes a las 00:00')
    })

    it('describe un mes concreto', () => {
      expect(describeCron('0 12 * 6 *')).toBe('en junio a las 12:00')
    })

    it('devuelve null para expresiones no interpretables', () => {
      expect(describeCron('a b c d e')).toBe(null)
    })
  })
})
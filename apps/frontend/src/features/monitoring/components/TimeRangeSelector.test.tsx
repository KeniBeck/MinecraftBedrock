import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TimeRangeSelector } from './TimeRangeSelector'

describe('TimeRangeSelector', () => {
  it('muestra los 5 rangos y marca el activo', () => {
    render(<TimeRangeSelector value="1h" onChange={() => {}} />)

    for (const label of ['15m', '1h', '6h', '24h', '7d']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: '1h' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '6h' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('notifica el rango al hacer clic', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<TimeRangeSelector value="1h" onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: '7d' }))

    expect(onChange).toHaveBeenCalledWith('7d')
  })
})

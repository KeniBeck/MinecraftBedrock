import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { Sidebar } from '@/components/layout/Sidebar'
import { useActiveServer } from '@/stores/servers'

function renderSidebar(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="*"
          element={
            <Sidebar
              collapsed={false}
              onToggleCollapsed={() => undefined}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Sidebar', () => {
  beforeEach(() => {
    useActiveServer.setState({ activeServerId: 'srv-1' })
  })

  afterEach(() => {
    useActiveServer.setState({ activeServerId: null })
  })

  it('"Consola" navega a /servers/:id/console usando el servidor activo', () => {
    renderSidebar('/servers/srv-1/console')
    const link = screen.getByTestId('sidebar-Consola')
    expect(link).toHaveAttribute('href', '/servers/srv-1/console')
    expect(link.className).toContain('pixel-nav-active')
  })

  it('"Servidor" navega al detalle y queda inactivo en la página de consola', () => {
    renderSidebar('/servers/srv-1/console')
    const link = screen.getByTestId('sidebar-Servidor')
    expect(link).toHaveAttribute('href', '/servers/srv-1')
    expect(link.className).not.toContain('pixel-nav-active')
  })

  it('en el detalle, "Servidor" está activo y "Consola" apunta a la consola', () => {
    renderSidebar('/servers/srv-1')
    const detailLink = screen.getByTestId('sidebar-Servidor')
    const consoleLink = screen.getByTestId('sidebar-Consola')
    expect(detailLink.className).toContain('pixel-nav-active')
    expect(consoleLink).toHaveAttribute('href', '/servers/srv-1/console')
  })
})

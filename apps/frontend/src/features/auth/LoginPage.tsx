import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getApiMessage } from '@/lib/api/client'
import { loginRequest, verifyTwoFactorRequest } from '@/lib/api/auth'
import { useAuthStore } from '@/stores/auth'

type Step = 'credentials' | 'totp'

/**
 * Login de dos pasos (frontend-standards §2):
 * 1. `POST /auth/login` → si `{requires_2fa, temp_token}`, segundo paso.
 * 2. `POST /auth/verify-2fa` con `{temp_token, code}` → tokens reales.
 * Cualquier error muestra `detail.message` del backend, sin redirigir.
 */
export function LoginPage() {
  const [step, setStep] = useState<Step>('credentials')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [tempToken, setTempToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((state) => state.setSession)

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  async function handleCredentials(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const response = await loginRequest({ username, password })
      if (response.requires_2fa && response.temp_token) {
        setTempToken(response.temp_token)
        setStep('totp')
        return
      }
      if (response.access_token && response.refresh_token && response.identity) {
        setSession({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          identity: response.identity,
        })
        navigate(from, { replace: true })
        return
      }
      setError('Respuesta de login inesperada del servidor')
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo iniciar sesión'))
    } finally {
      setBusy(false)
    }
  }

  async function handleTotp(e: FormEvent) {
    e.preventDefault()
    if (!tempToken) return
    setBusy(true)
    setError(null)
    try {
      const response = await verifyTwoFactorRequest({ temp_token: tempToken, code })
      setSession({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        identity: response.identity,
      })
      navigate(from, { replace: true })
    } catch (err) {
      setError(getApiMessage(err, 'Código inválido'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">Bedrock Panel</CardTitle>
          <CardDescription>
            {step === 'credentials'
              ? 'Inicia sesión con tu usuario del panel'
              : 'Introduce el código de la app TOTP o un backup code'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div
              role="alert"
              className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          )}

          {step === 'credentials' ? (
            <form onSubmit={handleCredentials} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Usuario</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Contraseña</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? 'Iniciando…' : 'Iniciar sesión'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleTotp} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="totp-code">Código 2FA</Label>
                <Input
                  id="totp-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="6 dígitos o backup code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  minLength={6}
                  maxLength={8}
                />
              </div>
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? 'Verificando…' : 'Verificar'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setStep('credentials')
                  setTempToken(null)
                  setCode('')
                  setError(null)
                }}
              >
                Volver
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

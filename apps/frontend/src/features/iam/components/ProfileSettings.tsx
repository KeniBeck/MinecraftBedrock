import { useState } from 'react'
import { KeyRound, Palette, ShieldCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { useThemeStore, BACKGROUNDS } from '@/stores/theme'
import { twoFactorKeys } from '@/lib/api/iam'
import type { EnableTwoFactor } from '@/lib/api/iam'
import { useConfirm2FA, useDisable2FA, useEnable2FA, useRegenerateBackupCodes, useTwoFactorStatus } from '../hooks'
import { TOTPQr } from './TOTPQr'

function BackupCodes({ codes, label }: { codes: string[]; label: string }) {
  return (
    <div className="rounded-none border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
      <p className="mb-2 text-sm font-medium text-emerald-300">{label} — guárdalos en un lugar seguro.</p>
      <div className="grid grid-cols-2 gap-1 font-mono text-xs text-emerald-200 sm:grid-cols-3">
        {codes.map((code) => (
          <span key={code}>{code}</span>
        ))}
      </div>
    </div>
  )
}

/**
 * Autenticación de segundo factor (2FA/TOTP) del perfil propio. El estado
 * "activado" se inicializa consultando `GET /auth/2fa/status` al montar, de
 * modo que al volver a iniciar sesión el perfil refleja el 2FA real (no se
 * deriva solo de la sesión actual). Tras habilitar/confirmar/desactivar se
 * refresca esa fuente de verdad.
 */
function TwoFactorSection() {
  const queryClient = useQueryClient()
  const enable = useEnable2FA()
  const confirm = useConfirm2FA()
  const regenerate = useRegenerateBackupCodes()
  const disable = useDisable2FA()
  const status = useTwoFactorStatus()

  const [phase, setPhase] = useState<'idle' | 'confirm' | 'enabled'>('idle')
  const [pending, setPending] = useState<EnableTwoFactor | null>(null)
  const [code, setCode] = useState('')
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const enabled = phase === 'enabled' || (phase === 'idle' && status.data?.enabled === true)

  const handleEnable = async () => {
    setError(null)
    try {
      const result = await enable.mutateAsync(undefined)
      setPending(result)
      setPhase('confirm')
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo iniciar 2FA'))
    }
  }

  const handleConfirm = async () => {
    setError(null)
    try {
      await confirm.mutateAsync(code.trim())
      setPhase('enabled')
      setPending(null)
      setCode('')
      await queryClient.invalidateQueries({ queryKey: twoFactorKeys.status })
    } catch (err) {
      setError(getApiMessage(err, 'Código no válido'))
    }
  }

  const handleRegenerate = async () => {
    setError(null)
    try {
      const result = await regenerate.mutateAsync(undefined)
      setBackupCodes(result.backup_codes)
    } catch (err) {
      setError(getApiMessage(err, 'No se pudieron regenerar los backup codes'))
    }
  }

  const handleDisable = async () => {
    setError(null)
    try {
      await disable.mutateAsync(undefined)
      setBackupCodes(null)
      setPhase('idle')
      await queryClient.invalidateQueries({ queryKey: twoFactorKeys.status })
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo desactivar 2FA'))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <p className="text-sm text-muted-foreground">
          {enabled
            ? 'La autenticación de dos factores está activada en tu cuenta.'
            : 'Protege tu cuenta con un segundo factor (aplicación de autenticación TOTP).'}
        </p>
        {enabled && (
          <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
            <ShieldCheck className="mr-1 h-3 w-3" /> 2FA activado
          </Badge>
        )}
      </div>

      {phase === 'idle' && !enabled && (
        <Button variant="create" pixel onClick={handleEnable} disabled={enable.isPending}>
          <KeyRound className="mr-1 h-4 w-4" />
          Habilitar 2FA
        </Button>
      )}

      {phase === 'confirm' && pending && (
        <div className="space-y-3">
          <div className="rounded-none border border-white/10 bg-slate-900/60 px-4 py-3">
            <p className="mb-3 text-sm font-medium">
              Escanea el código con tu aplicación de autenticación:
            </p>
            <TOTPQr value={pending.provisioning_uri} />
          </div>
          <div>
            <p className="mb-1 text-xs text-muted-foreground">
              Secreto (manual): <code className="font-mono">{pending.secret}</code>
            </p>
            <Input
              aria-label="Código de confirmación"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Código de 6 dígitos"
              className="max-w-xs font-mono"
            />
          </div>
          <BackupCodes codes={pending.backup_codes} label="Backup codes (una sola vez)" />
          <Button
            variant="create"
            pixel
            onClick={handleConfirm}
            disabled={confirm.isPending || code.trim().length < 6}
          >
            {confirm.isPending ? 'Confirmando…' : 'Confirmar 2FA'}
          </Button>
        </div>
      )}

      {enabled && (
        <div className="flex flex-col items-start gap-3">
          {backupCodes && <BackupCodes codes={backupCodes} label="Nuevos backup codes (una sola vez)" />}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" pixel onClick={handleRegenerate} disabled={regenerate.isPending}>
              Regenerar backup codes
            </Button>
            <Button variant="outline" pixel onClick={handleDisable} disabled={disable.isPending}>
              {disable.isPending ? 'Desactivando…' : 'Desactivar 2FA'}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
    </div>
  )
}

/** Preferencias de apariencia (tema + fondo) desde el store local. */
function AppearanceSection() {
  const theme = useThemeStore((state) => state.theme)
  const toggleTheme = useThemeStore((state) => state.toggleTheme)
  const backgroundId = useThemeStore((state) => state.backgroundId)
  const setBackground = useThemeStore((state) => state.setBackground)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Tema</p>
          <p className="text-xs text-muted-foreground">Cambia entre oscuro y claro.</p>
        </div>
        <Button variant="outline" pixel onClick={toggleTheme}>
          {theme === 'dark' ? 'Oscuro' : 'Claro'}
        </Button>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Fondo</p>
        <div className="flex flex-wrap gap-2">
          {BACKGROUNDS.map((bg) => (
            <button
              key={bg.id}
              type="button"
              onClick={() => setBackground(bg.id)}
              className={`rounded-none border px-3 py-2 text-sm transition-colors ${
                backgroundId === bg.id
                  ? 'border-emerald-400 bg-emerald-500/10 text-emerald-300'
                  : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
            >
              {bg.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * Ajustes del perfil: 2FA y apariencia. El cambio de contraseña y el
 * `display_name` NO están disponibles (el backend no expone `PUT /users/me` ni
 * cambio de contraseña) — se documentan como carencia en el change-log.
 */
export function ProfileSettings() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-xl">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <ShieldCheck className="h-5 w-5 text-emerald-300" />
          Autenticación (2FA)
        </h2>
        <div className="mt-3">
          <TwoFactorSection />
        </div>
      </section>
      <section className="rounded-xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-xl">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Palette className="h-5 w-5 text-slate-300" />
          Apariencia
        </h2>
        <div className="mt-3">
          <AppearanceSection />
        </div>
      </section>
    </div>
  )
}
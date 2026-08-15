import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { CheckCircle2, RefreshCw, Save, Settings2, TriangleAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { getApiMessage } from '@/lib/api/client'
import { useCan } from '@/lib/auth/useCan'
import type { ConfigProfile } from '@/lib/api/configuration'
import { useConfig, useUpdateConfig, buildPropertiesPayload } from './hooks'
import { CONFIG_GROUPS, CONFIG_PROPERTIES, groupProperties, isDirty } from './properties'
import type { ConfigFormErrors, ConfigFormValues } from './types'
import { validateDraft, validateProperty } from './types'
import { PropertyField } from './components/PropertyField'

/** Combina el perfil del backend con los defaults del catálogo. */
function toFormValues(profile: ConfigProfile | undefined): ConfigFormValues {
  const values: ConfigFormValues = {}
  for (const prop of CONFIG_PROPERTIES) {
    values[prop.key] = profile?.properties[prop.key] ?? prop.defaultValue
  }
  return values
}

/**
 * Cuerpo del formulario. Montado con `key={profile?.updated_at}` desde la página
 * para re-inicializar el borrador cuando llega un perfil distinto (evita
 * `setState` dentro de un efecto, patrón usado en el editor cron).
 */
function ConfigFormBody({
  serverId,
  profile,
  canWrite,
}: {
  serverId: string
  profile: ConfigProfile | undefined
  canWrite: boolean
}) {
  const updateConfig = useUpdateConfig(serverId)
  const original = profile?.properties ?? {}
  const [draft, setDraft] = useState<ConfigFormValues>(() => toFormValues(profile))
  const [errors, setErrors] = useState<ConfigFormErrors>({})
  const [feedback, setFeedback] = useState<{ kind: 'ok' | 'error'; text: string } | null>(
    null,
  )
  const dirty = isDirty(draft, original)

  const setValue = (key: string, value: string) => {
    const next = { ...draft, [key]: value }
    setDraft(next)
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const handleSave = () => {
    const validation = validateDraft(draft, CONFIG_PROPERTIES)
    setErrors(validation)
    if (Object.values(validation).some(Boolean)) {
      setFeedback({ kind: 'error', text: 'Corrige los valores marcados antes de guardar.' })
      return
    }
    setFeedback(null)
    const payload = buildPropertiesPayload(draft, original, false)
    updateConfig.mutate(
      { properties: payload },
      {
        onSuccess: (updated) => {
          setDraft(toFormValues(updated))
          setFeedback({
            kind: 'ok',
            text: 'Configuración guardada. El contenedor se recreará con los cambios (en segundo plano).',
          })
        },
        onError: (err) =>
          setFeedback({
            kind: 'error',
            text: getApiMessage(err, 'No se pudo guardar la configuración'),
          }),
      },
    )
  }

  return (
    <>
      {CONFIG_GROUPS.map((group) => (
        <section
          key={group.id}
          className="rounded-xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-xl"
        >
          <h2 className="mb-1 text-lg font-semibold">{group.label}</h2>
          <p className="mb-4 text-xs text-muted-foreground">{group.description}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {groupProperties(group.id).map((prop) => {
              const err = errors[prop.key] ?? validateProperty(prop, draft[prop.key] ?? prop.defaultValue)
              return (
                <PropertyField
                  key={prop.key}
                  def={prop}
                  value={draft[prop.key] ?? prop.defaultValue}
                  disabled={!canWrite}
                  onChange={(value) => setValue(prop.key, value)}
                  {...(err ? { error: err } : {})}
                />
              )
            })}
          </div>
        </section>
      ))}

      {profile && profile.applied !== null && (
        <div className="flex items-center gap-2 rounded-none border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
          <RefreshCw className="h-3.5 w-3.5" />
          Revisión {profile.config_rev} · última vista aplicada
          {profile.applied_at ? `: ${new Date(profile.applied_at).toLocaleString()}` : ' (sin fecha)'}
        </div>
      )}

      {feedback && (
        <div
          role={feedback.kind === 'ok' ? 'status' : 'alert'}
          className={`flex items-center gap-2 rounded-none border-2 px-4 py-3 text-sm shadow-[inset_2px_2px_0_rgba(0,0,0,.3)] ${
            feedback.kind === 'ok'
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/40 bg-red-500/10 text-red-300'
          }`}
        >
          {feedback.kind === 'ok' ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <TriangleAlert className="h-4 w-4" />
          )}
          {feedback.text}
        </div>
      )}

      {canWrite && (
        <div className="flex items-center gap-3 pt-2">
          <Button
            variant="create"
            pixel
            onClick={handleSave}
            disabled={updateConfig.isPending}
          >
            <Save className="mr-1 h-4 w-4" />
            {updateConfig.isPending ? 'Guardando…' : 'Guardar cambios'}
          </Button>
          {dirty && (
            <p className="text-xs text-muted-foreground">
              Guardar recreará el contenedor para aplicar la configuración.
            </p>
          )}
        </div>
      )}
    </>
  )
}

export function ConfigurationPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const canRead = useCan('server.config.read')
  const canWrite = useCan('server.config.update')

  const { data: profile, isLoading, isError, error } = useConfig(serverId)

  if (!serverId) return null

  if (!canRead) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        No tienes permisos para ver la configuración del servidor.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <Settings2 className="h-5 w-5 text-slate-300" />
            Configuración del servidor
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Edita las propiedades de <code>server.properties</code> del servidor.
          </p>
        </div>
      </header>

      {isLoading && <div className="p-8 text-muted-foreground">Cargando configuración…</div>}

      {isError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {getApiMessage(error, 'No se pudo cargar la configuración')}
        </div>
      )}

      {!isLoading && !isError && (
        <ConfigFormBody
          key={profile?.updated_at ?? 'empty'}
          serverId={serverId}
          profile={profile}
          canWrite={canWrite}
        />
      )}
    </div>
  )
}
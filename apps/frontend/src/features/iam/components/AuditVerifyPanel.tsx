import { useState } from 'react'
import { ShieldCheck, ShieldX, Verified } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { getApiMessage } from '@/lib/api/client'
import { useVerifyAuditChain } from '../hooks'

/**
 * Auditoría: el backend expone únicamente `GET /iam/audit/verify` (integridad de
 * la cadena de hash). No hay `GET /audit` (listado con filtros), por lo que esta
 * vista se reduce a la verificación — ver change-log Fase 7.
 */
export function AuditVerifyPanel() {
  const verifyAudit = useVerifyAuditChain()
  const [result, setResult] = useState<{ valid: boolean; errors: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleVerify = () => {
    setError(null)
    verifyAudit.mutate(undefined, {
      onSuccess: (res) => setResult({ valid: res.valid, errors: res.errors }),
      onError: (err) => setError(getApiMessage(err, 'No se pudo verificar la auditoría')),
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Verifica la integridad de la cadena de hash del registro de auditoría.
        </p>
        <Button variant="create" pixel size="sm" onClick={handleVerify} disabled={verifyAudit.isPending}>
          <Verified className="mr-1 h-4 w-4" />
          {verifyAudit.isPending ? 'Verificando…' : 'Verificar cadena'}
        </Button>
      </div>

      {error && (
        <div role="alert" className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div
          role={result.valid ? 'status' : 'alert'}
          className={`rounded-none border-2 px-4 py-4 text-sm shadow-[inset_2px_2px_0_rgba(0,0,0,.3)] ${
            result.valid
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/40 bg-red-500/10 text-red-300'
          }`}
        >
          <p className="mb-1 flex items-center gap-2 font-medium">
            {result.valid ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
            {result.valid ? 'La cadena de auditoría es íntegra.' : 'Se detectaron anomalías en la cadena.'}
          </p>
          {result.errors.length > 0 && (
            <ul className="ml-6 list-disc space-y-1 text-xs">
              {result.errors.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
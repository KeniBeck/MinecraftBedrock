import { useState } from 'react'
import { UserPlus, KeyRound, ScrollText } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useCan } from '@/lib/auth/useCan'
import { CreateUserDialog } from './components/CreateUserDialog'
import { ApiKeyList } from './components/ApiKeyList'
import { AuditLogList } from './components/AuditLogList'
import { AuditVerifyPanel } from './components/AuditVerifyPanel'
import { UserList } from './components/UserList'

type Tab = 'users' | 'api-keys' | 'audit'

const TABS: readonly { id: Tab; label: string; icon: typeof UserPlus }[] = [
  { id: 'users', label: 'Usuarios', icon: UserPlus },
  { id: 'api-keys', label: 'API Keys', icon: KeyRound },
  { id: 'audit', label: 'Auditoría', icon: ScrollText },
]

/**
 * Panel de administración IAM. Visible para `iam.view` (viewer+) en modo
 * lectura; las acciones de gestión (crear/editar/suspender usuarios, API keys)
 * requieren `iam.manage` (admin/super_admin).
 */
export function IAMPage() {
  const userCanView = useCan('iam.view')
  const userCanManage = useCan('iam.manage')
  const canView = userCanView || userCanManage
  const canManage = userCanManage
  const [tab, setTab] = useState<Tab>('users')
  const [createUserOpen, setCreateUserOpen] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  if (!canView) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        No tienes permisos para ver la administración del panel.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-bold">
          <ScrollText className="h-5 w-5 text-slate-300" />
          Administración
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Gestión de usuarios, API keys y auditoría del panel.
        </p>
      </header>

      <div className="flex gap-1 border-b border-white/10">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-2 text-sm transition-colors',
              tab === id
                ? 'border-emerald-400 text-white'
                : 'border-transparent text-slate-400 hover:text-white',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {feedback && (
        <div
          role="status"
          className="rounded-none border-2 border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300"
        >
          {feedback}
        </div>
      )}

      {tab === 'users' && (
        <div className="space-y-4">
          {canManage && (
            <div className="flex items-center justify-between">
              <Button variant="create" pixel size="sm" onClick={() => setCreateUserOpen(true)}>
                <UserPlus className="mr-1 h-4 w-4" />
                Crear usuario
              </Button>
            </div>
          )}
          <UserList canManage={canManage} />
        </div>
      )}

      {tab === 'api-keys' && <ApiKeyList />}
      {tab === 'audit' && (
        <div className="space-y-6">
          <AuditLogList />
          <AuditVerifyPanel />
        </div>
      )}

      {canManage && (
        <CreateUserDialog
          open={createUserOpen}
          onOpenChange={setCreateUserOpen}
          onCreated={(username) => setFeedback(`Usuario "${username}" creado.`)}
        />
      )}
    </div>
  )
}
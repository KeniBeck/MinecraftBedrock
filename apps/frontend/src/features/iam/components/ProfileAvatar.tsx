import { useRef, useState } from 'react'
import { Camera, Upload } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getApiMessage } from '@/lib/api/client'
import { useProfile, useSetAvatar } from '../hooks'

const AVATAR_FALLBACK = `${import.meta.env.BASE_URL}avatar/skinmc-avatar.png`

/**
 * Avatar del perfil del usuario autenticado con opción de cambiarlo de forma
 * moderna: sobre el avatar hay un overlay translúcido con un botón de cámara
 * (hover) que abre un dialog con vista previa y selector de archivo. Sube vía
 * `PUT /users/me/avatar` (multipart, PNG/JPEG/WebP ≤ 1 MB — lo valida el
 * backend con `IAM.INVALID_AVATAR`). Carga el avatar desde `GET /users/me`
 * (data URL base64) con fallback al voxel estático.
 */
export function ProfileAvatar() {
  const inputRef = useRef<HTMLInputElement>(null)
  const profile = useProfile()
  const setAvatar = useSetAvatar()

  const [open, setOpen] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [selected, setSelected] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const avatarUrl = profile.data?.avatar ?? AVATAR_FALLBACK

  async function handleFile(file: File | undefined) {
    if (!file) return
    if (setAvatar.isPending) return
    setError(null)
    try {
      await setAvatar.mutateAsync(file)
      setOpen(false)
      setPreview(null)
      setSelected(null)
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo cambiar el avatar'))
    }
  }

  function selectFile(file: File | undefined) {
    if (!file) return
    const url = URL.createObjectURL(file)
    setPreview(url)
    setSelected(file)
    setError(null)
  }

  return (
    <>
      <div className="group relative" data-testid="profile-avatar-wrapper">
        <img
          src={avatarUrl}
          alt="Avatar"
          className="size-24 rounded-md border border-black bg-slate-900 object-contain shadow-[inset_2px_2px_0_rgba(255,255,255,.15),inset_-2px_-2px_0_rgba(0,0,0,.5)]"
          data-testid="profile-avatar"
        />

        {/* Overlay con botón de cámara (aparece al hover; siempre visible en touch). */}
        <button
          type="button"
          onClick={() => setOpen(true)}
          disabled={setAvatar.isPending}
          aria-label="Cambiar avatar"
          data-testid="profile-avatar-change"
          className="absolute inset-0 flex flex-col items-center justify-center gap-1 rounded-md bg-black/55 text-slate-100 opacity-0 transition-opacity duration-200 hover:opacity-100 focus-visible:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed"
        >
          <Camera className="size-5" />
          <span className="text-[10px] uppercase tracking-wider">Cambiar</span>
        </button>

        {setAvatar.isPending && (
          <div
            className="absolute inset-0 flex items-center justify-center rounded-md bg-black/60 text-xs text-slate-200"
            data-testid="profile-avatar-pending"
          >
            Subiendo…
          </div>
        )}
      </div>

      {/* Dialog: vista previa + selector de archivo. */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cambiar avatar</DialogTitle>
            <DialogDescription>
              Selecciona una imagen PNG, JPEG o WebP (máx. 1 MB).
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col items-center gap-4 py-2">
            <img
              src={preview ?? avatarUrl}
              alt="Vista previa del avatar"
              className="size-32 rounded-md border border-black bg-slate-900 object-contain shadow-[inset_2px_2px_0_rgba(255,255,255,.15),inset_-2px_-2px_0_rgba(0,0,0,.5)]"
              data-testid="avatar-preview"
            />

            {error && (
              <p role="alert" className="max-w-64 text-center text-xs text-red-300">
                {error}
              </p>
            )}

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                pixel
                disabled={setAvatar.isPending}
                onClick={() => inputRef.current?.click()}
              >
                <Upload className="size-3.5" />
                Elegir imagen
              </Button>
              {preview && (
                <Button
                  variant="create"
                  size="sm"
                  pixel
                  disabled={setAvatar.isPending || selected === null}
                  onClick={() => void handleFile(selected ?? undefined)}
                  data-testid="profile-avatar-save"
                >
                  {setAvatar.isPending ? 'Subiendo…' : 'Guardar avatar'}
                </Button>
              )}
            </div>
          </div>

          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => {
              selectFile(event.target.files?.[0])
              event.target.value = ''
            }}
            data-testid="profile-avatar-file"
          />
        </DialogContent>
      </Dialog>
    </>
  )
}

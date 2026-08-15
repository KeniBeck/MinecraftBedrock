import { QRCodeCanvas } from 'qrcode.react'

/** Logo voxel de "Server management" embebido en el centro del QR. */
const LOGO_URL = `${import.meta.env.BASE_URL}favicon.svg`

/**
 * Genera el código QR del URI de aprovisionamiento TOTP con el logo
 * del panel centrado. Se usa `QRCodeCanvas` porque dibuja la imagen embebida
 * fiablemente sobre el canvas, y `excavate` mantiene un área blanca detrás
 * del logo para no romper la lectuara.
 */
export function TOTPQr({ value }: { value: string }) {
  return (
    <div className="inline-block rounded-none border border-white/10 bg-white p-3">
      <QRCodeCanvas
        value={value}
        size={208}
        level="Q"
        marginSize={4}
        bgColor="#FFFFFF"
        fgColor="#0f172a"
        title="Sincroniza tu aplicación de autenticación"
        imageSettings={{
          src: LOGO_URL,
          height: 44,
          width: 44,
          excavate: true,
        }}
      />
    </div>
  )
}
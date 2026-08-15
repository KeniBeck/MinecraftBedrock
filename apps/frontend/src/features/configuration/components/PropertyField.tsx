import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { ConfigPropertyValue } from '@/lib/api/configuration'
import type { PropertyDef } from '../properties'

interface PropertyFieldProps {
  def: PropertyDef
  value: ConfigPropertyValue
  error?: string
  disabled: boolean
  onChange: (value: ConfigPropertyValue) => void
}

/**
 * Control de una propiedad de `server.properties` según su tipo: texto, entero
 * (con input numérico) o selector de enum. Reutiliza `FormField` (label+hint+
 * error) del kit de UI.
 */
export function PropertyField({ def, value, error, disabled, onChange }: PropertyFieldProps) {
  const id = `config-${def.key}`

  const input =
    def.kind === 'enum' && def.enum ? (
      <Select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {def.enum.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </Select>
    ) : (
      <Input
        id={id}
        type={def.kind === 'int' ? 'number' : 'text'}
        value={value}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        onChange={(e) => onChange(e.target.value)}
      />
    )

  return (
    <FormField label={def.label} htmlFor={id} hint={def.hint} error={error}>
      {input}
    </FormField>
  )
}
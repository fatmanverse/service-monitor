import { useId } from 'react'
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'

interface FieldShellProps {
  label: string
  hint?: string
  wide?: boolean
  children: (id: string) => ReactNode
}

/** Wraps a control with its label and optional hint, wiring up htmlFor/id. */
function FieldShell({ label, hint, wide, children }: FieldShellProps) {
  const id = useId()
  return (
    <div className={wide ? 'ui-field form-grid-wide' : 'ui-field'}>
      <label className="ui-field-label" htmlFor={id}>
        {label}
      </label>
      {children(id)}
      {hint && <span className="ui-field-hint">{hint}</span>}
    </div>
  )
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'className' | 'id'> & {
  label: string
  hint?: string
  wide?: boolean
}

export function TextField({ label, hint, wide, ...rest }: InputProps) {
  return (
    <FieldShell label={label} hint={hint} wide={wide}>
      {(id) => <input {...rest} id={id} className="ui-input" />}
    </FieldShell>
  )
}

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'className' | 'id'> & {
  label: string
  hint?: string
  wide?: boolean
}

export function SelectField({ label, hint, wide, children, ...rest }: SelectProps) {
  return (
    <FieldShell label={label} hint={hint} wide={wide}>
      {(id) => (
        <select {...rest} id={id} className="ui-select">
          {children}
        </select>
      )}
    </FieldShell>
  )
}

type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'className' | 'id'> & {
  label: string
  hint?: string
  wide?: boolean
}

export function TextareaField({ label, hint, wide, ...rest }: TextareaProps) {
  return (
    <FieldShell label={label} hint={hint} wide={wide}>
      {(id) => <textarea {...rest} id={id} className="ui-textarea" />}
    </FieldShell>
  )
}

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'className' | 'type'> & {
  label: string
  wide?: boolean
}

export function CheckboxField({ label, wide, ...rest }: CheckboxProps) {
  return (
    <label className={wide ? 'ui-checkbox form-grid-wide' : 'ui-checkbox'}>
      <input {...rest} type="checkbox" />
      {label}
    </label>
  )
}

/** Standalone label for composite controls that are not a single form element. */
export function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="ui-field-label">{children}</span>
}

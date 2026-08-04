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
  error?: string
  wide?: boolean
  children: (props: { id: string; describedBy?: string; invalid: boolean }) => ReactNode
}

/**
 * Wraps a control with its label, hint and error, wiring up htmlFor/id and
 * aria-describedby. An error replaces the hint so the message occupies one spot
 * instead of competing with helper text.
 */
function FieldShell({ label, hint, error, wide, children }: FieldShellProps) {
  const id = useId()
  const messageId = `${id}-message`
  const message = error ?? hint

  return (
    <div className={wide ? 'ui-field form-grid-wide' : 'ui-field'}>
      <label className="ui-field-label" htmlFor={id}>
        {label}
      </label>
      {children({ id, describedBy: message ? messageId : undefined, invalid: Boolean(error) })}
      {message && (
        <span
          className="ui-field-hint"
          id={messageId}
          data-tone={error ? 'danger' : undefined}
          role={error ? 'alert' : undefined}
        >
          {message}
        </span>
      )}
    </div>
  )
}

interface CommonProps {
  label: string
  hint?: string
  error?: string
  wide?: boolean
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'className' | 'id'> & CommonProps

export function TextField({ label, hint, error, wide, ...rest }: InputProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} wide={wide}>
      {({ id, describedBy, invalid }) => (
        <input
          {...rest}
          id={id}
          className="ui-input"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
        />
      )}
    </FieldShell>
  )
}

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'className' | 'id'> & CommonProps

export function SelectField({ label, hint, error, wide, children, ...rest }: SelectProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} wide={wide}>
      {({ id, describedBy, invalid }) => (
        <select
          {...rest}
          id={id}
          className="ui-select"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
        >
          {children}
        </select>
      )}
    </FieldShell>
  )
}

type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'className' | 'id'> &
  CommonProps & { mono?: boolean }

export function TextareaField({ label, hint, error, wide, mono, ...rest }: TextareaProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} wide={wide}>
      {({ id, describedBy, invalid }) => (
        <textarea
          {...rest}
          id={id}
          className={mono ? 'ui-textarea u-mono' : 'ui-textarea'}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
        />
      )}
    </FieldShell>
  )
}

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'className' | 'type'> & {
  label: string
  hint?: string
  wide?: boolean
}

export function CheckboxField({ label, hint, wide, ...rest }: CheckboxProps) {
  return (
    <label className={wide ? 'ui-checkbox form-grid-wide' : 'ui-checkbox'}>
      <input {...rest} type="checkbox" />
      <span className="ui-checkbox-text">
        {label}
        {hint && <small>{hint}</small>}
      </span>
    </label>
  )
}

/** Standalone label for composite controls that are not a single form element. */
export function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="ui-field-label">{children}</span>
}

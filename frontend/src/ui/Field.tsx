import { useId } from 'react'
import { Select } from './Select'
import type { SelectProps } from './Select'
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'

interface FieldShellProps {
  label: string
  hint?: string
  error?: string
  wide?: boolean
  children: (props: {
    id: string
    labelId: string
    describedBy?: string
    invalid: boolean
  }) => ReactNode
}

/**
 * Wraps a control with its label, hint and error, wiring up htmlFor/id and
 * aria-describedby. An error replaces the hint so the message occupies one spot
 * instead of competing with helper text.
 */
function FieldShell({ label, hint, error, wide, children }: FieldShellProps) {
  const id = useId()
  const labelId = `${id}-label`
  const messageId = `${id}-message`
  const message = error ?? hint

  return (
    <div className={wide ? 'ui-field form-grid-wide' : 'ui-field'}>
      <label className="ui-field-label" id={labelId} htmlFor={id}>
        {label}
      </label>
      {children({
        id,
        labelId,
        describedBy: message ? messageId : undefined,
        invalid: Boolean(error),
      })}
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

type SelectFieldProps = Omit<
  SelectProps,
  'id' | 'aria-describedby' | 'aria-invalid' | 'aria-labelledby'
> &
  CommonProps

export function SelectField({ label, hint, error, wide, children, ...rest }: SelectFieldProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} wide={wide}>
      {({ id, labelId, describedBy, invalid }) => (
        <Select
          {...rest}
          id={id}
          aria-labelledby={labelId}
          aria-describedby={describedBy}
          aria-invalid={invalid}
        >
          {children}
        </Select>
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

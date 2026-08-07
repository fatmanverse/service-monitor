import {
  Children,
  Fragment,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown } from 'lucide-react'
import { useAnchoredPanel } from './useAnchoredPanel'
import type { KeyboardEvent, OptionHTMLAttributes, ReactNode } from 'react'

/** Height of one option row plus its gap, and the tallest panel we will request. */
const OPTION_HEIGHT = 36
const PANEL_PADDING = 8
const PANEL_MAX_HEIGHT = 288

/** How long a type-ahead query stays open for more characters. */
const TYPE_AHEAD_RESET_MS = 600

/**
 * A printable single character with no modifier held, i.e. the user is typing to
 * search rather than issuing a shortcut. Space is excluded here and handled by
 * the caller, which treats it as commit or as query text depending on state.
 */
function isTypeAheadKey(event: KeyboardEvent<HTMLElement>): boolean {
  if (event.ctrlKey || event.metaKey || event.altKey) return false
  return event.key.length === 1 && event.key !== ' '
}

interface SelectOption {
  value: string
  label: string
  disabled: boolean
}

export interface SelectProps {
  value: string | number
  onChange: (event: { target: { value: string } }) => void
  children: ReactNode
  id?: string
  disabled?: boolean
  required?: boolean
  placeholder?: string
  'aria-label'?: string
  'aria-labelledby'?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean
}

/**
 * Reads the `<option>` children into plain data. Labels are flattened to text so
 * the trigger can render the selected label without cloning React nodes; option
 * content in this codebase is always text, and anything richer would not fit on
 * a single-line trigger anyway.
 *
 * Descends into fragments, because `Children.toArray` does not flatten them and
 * options grouped in a `<>...</>` would otherwise vanish without any error.
 */
function readOptions(children: ReactNode): SelectOption[] {
  return Children.toArray(children).flatMap((child) => {
    if (!isValidElement<OptionHTMLAttributes<HTMLOptionElement>>(child)) return []

    if (child.type === Fragment) {
      return readOptions((child.props as { children?: ReactNode }).children)
    }
    if (child.type !== 'option') return []

    return [
      {
        value: String(child.props.value ?? ''),
        label: flattenText(child.props.children),
        disabled: Boolean(child.props.disabled),
      },
    ]
  })
}

function flattenText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(flattenText).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return flattenText(node.props.children)
  return ''
}

/** Next selectable index in `direction`, wrapping around. Returns -1 when every option is disabled. */
function nextEnabled(options: SelectOption[], from: number, direction: 1 | -1): number {
  const total = options.length
  let index = from

  for (let step = 0; step < total; step += 1) {
    index = (index + direction + total) % total
    if (!options[index].disabled) return index
  }
  return -1
}

function firstEnabled(options: SelectOption[]): number {
  return options.findIndex((option) => !option.disabled)
}

/**
 * First selectable option whose label starts with `query`, searching forward from
 * `from` and wrapping. Mirrors the native control's type-ahead so long lists such
 * as the host picker stay usable from the keyboard.
 */
function matchPrefix(options: SelectOption[], query: string, from: number): number {
  const needle = query.toLowerCase()

  for (let step = 1; step <= options.length; step += 1) {
    const index = (from + step) % options.length
    const option = options[index]
    if (!option.disabled && option.label.toLowerCase().startsWith(needle)) return index
  }
  return -1
}

function lastEnabled(options: SelectOption[]): number {
  for (let index = options.length - 1; index >= 0; index -= 1) {
    if (!options[index].disabled) return index
  }
  return -1
}

/**
 * Listbox-pattern select. Replaces the native control so the option panel can be
 * themed with our design tokens — a native `<select>` popup is drawn by the OS
 * and ignores dark mode entirely.
 *
 * The `onChange` signature mirrors a native change event's `target.value` so
 * existing call sites keep working unchanged.
 */
export function Select({
  value,
  onChange,
  children,
  id,
  disabled,
  required,
  placeholder = '请选择',
  'aria-label': ariaLabel,
  'aria-labelledby': ariaLabelledBy,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
}: SelectProps) {
  const options = useMemo(() => readOptions(children), [children])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const typeAheadRef = useRef({ query: '', timer: 0 })

  // Ask for only as much height as the options need, so the flip decision in
  // useAnchoredPanel is based on the real panel size rather than the cap.
  const desiredHeight = Math.min(
    options.length * OPTION_HEIGHT + PANEL_PADDING,
    PANEL_MAX_HEIGHT,
  )
  const position = useAnchoredPanel(triggerRef, open, desiredHeight)

  // Ids must not depend on the optional `id` prop: RuleEditor renders Select
  // without one, and the listbox still needs to be referenceable.
  const reactId = useId()
  const listboxId = `${id ?? reactId}-listbox`
  const optionId = (index: number) => `${listboxId}-option-${index}`

  const currentValue = String(value ?? '')
  const selectedIndex = options.findIndex((option) => option.value === currentValue)
  const selected = selectedIndex === -1 ? undefined : options[selectedIndex]

  function openPanel() {
    if (disabled) return
    setActiveIndex(selectedIndex === -1 ? firstEnabled(options) : selectedIndex)
    setOpen(true)
  }

  function closePanel() {
    setOpen(false)
    setActiveIndex(-1)
  }

  function commit(option: SelectOption) {
    if (option.disabled) return
    if (option.value !== currentValue) {
      onChange({ target: { value: option.value } })
    }
    closePanel()
    triggerRef.current?.focus()
  }

  // Dismiss on an outside press, on Escape, or when focus leaves the control.
  useEffect(() => {
    if (!open) return

    function isOutside(target: Node) {
      if (triggerRef.current?.contains(target)) return false
      if (panelRef.current?.contains(target)) return false
      return true
    }

    function handlePointerDown(event: PointerEvent) {
      if (isOutside(event.target as Node)) closePanel()
    }

    /**
     * The first outside press should dismiss only this popup. React attaches its
     * handlers to the app root, below `document`, so stopping the separate
     * `mousedown` event here in the capture phase keeps an enclosing modal's
     * backdrop from tearing down both layers in one click.
     */
    function handleMouseDownCapture(event: MouseEvent) {
      if (isOutside(event.target as Node)) event.stopPropagation()
    }

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== 'Escape') return
      // Capture phase plus stopPropagation keeps an enclosing modal's
      // Escape-to-close from firing: only the dropdown collapses.
      event.stopPropagation()
      closePanel()
      triggerRef.current?.focus()
    }

    // Tab moves focus away while the panel stays mounted; close it so two
    // dropdowns can never be open at once.
    function handleFocusIn(event: FocusEvent) {
      const target = event.target as Node
      if (triggerRef.current?.contains(target)) return
      if (panelRef.current?.contains(target)) return
      closePanel()
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('mousedown', handleMouseDownCapture, true)
    document.addEventListener('keydown', handleKeyDown, true)
    document.addEventListener('focusin', handleFocusIn)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('mousedown', handleMouseDownCapture, true)
      document.removeEventListener('keydown', handleKeyDown, true)
      document.removeEventListener('focusin', handleFocusIn)
    }
  }, [open])

  // The anchor scrolled out of a clipping ancestor; a floating panel with no
  // visible owner is disorienting, so dismiss it.
  useEffect(() => {
    if (open && position?.clipped) closePanel()
  }, [open, position?.clipped])

  // Keep the active option in view. `position` is a dependency because the panel
  // only mounts on the commit after it resolves, so the first run finds no node.
  useEffect(() => {
    if (!open || activeIndex === -1 || !position) return
    panelRef.current?.querySelector(`#${CSS.escape(optionId(activeIndex))}`)?.scrollIntoView({
      block: 'nearest',
    })
  }, [open, activeIndex, position])

  // The type-ahead buffer lives in a ref, so its reset timer has to be cancelled
  // by hand when the field unmounts with a modal.
  useEffect(() => {
    const buffer = typeAheadRef.current
    return () => window.clearTimeout(buffer.timer)
  }, [])

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) {
        openPanel()
        return
      }
      const direction = event.key === 'ArrowDown' ? 1 : -1
      const from = activeIndex === -1 ? (direction === 1 ? -1 : 0) : activeIndex
      setActiveIndex(nextEnabled(options, from, direction))
      return
    }

    if (event.key === 'Home' && open) {
      event.preventDefault()
      setActiveIndex(firstEnabled(options))
      return
    }

    if (event.key === 'End' && open) {
      event.preventDefault()
      setActiveIndex(lastEnabled(options))
      return
    }

    // Let Tab move focus naturally, but do not leave the panel hanging open.
    if (event.key === 'Tab' && open) {
      closePanel()
      return
    }

    // Space extends an in-progress type-ahead query rather than committing, so
    // labels containing spaces stay reachable.
    if (event.key === 'Enter' || (event.key === ' ' && !typeAheadRef.current.query)) {
      event.preventDefault()
      if (!open) {
        openPanel()
        return
      }
      const option = options[activeIndex]
      if (option) commit(option)
      return
    }

    // Space reaches here only while a query is in flight, where it is query text.
    if (isTypeAheadKey(event) || event.key === ' ') {
      event.preventDefault()
      searchByPrefix(event.key)
    }
  }

  /**
   * Appends to the type-ahead buffer and moves the active option to the first
   * label matching it. Repeating a single character cycles through options
   * starting with it, matching the native control.
   */
  function searchByPrefix(key: string) {
    const buffer = typeAheadRef.current
    window.clearTimeout(buffer.timer)
    buffer.timer = window.setTimeout(() => {
      buffer.query = ''
    }, TYPE_AHEAD_RESET_MS)

    const repeated = buffer.query.length === 1 && buffer.query === key
    buffer.query = repeated ? key : buffer.query + key

    // While cycling on one character, start the scan after the active option.
    const from = repeated ? activeIndex : activeIndex - 1
    const match = matchPrefix(options, buffer.query, Math.max(from, -1))
    if (match === -1) return

    if (open) {
      setActiveIndex(match)
    } else {
      commit(options[match])
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className="ui-select-trigger"
        role="combobox"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        // Without this a screen reader announces nothing while arrowing the list,
        // because focus never leaves the trigger.
        aria-activedescendant={open && activeIndex !== -1 ? optionId(activeIndex) : undefined}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        aria-invalid={ariaInvalid || undefined}
        aria-required={required || undefined}
        data-placeholder={selected ? undefined : ''}
        onClick={() => (open ? closePanel() : openPanel())}
        onKeyDown={handleKeyDown}
      >
        <span className="ui-select-value">{selected ? selected.label : placeholder}</span>
        <ChevronDown className="ui-select-chevron" size={16} aria-hidden />
      </button>

      {open &&
        position &&
        createPortal(
          <div
            ref={panelRef}
            id={listboxId}
            className="ui-select-panel"
            role="listbox"
            aria-label={ariaLabel}
            aria-labelledby={ariaLabel ? undefined : ariaLabelledBy}
            data-placement={position.placement}
            style={{
              top: position.top,
              left: position.left,
              width: position.width,
              maxHeight: position.maxHeight,
            }}
            // React routes portal events through the component tree, so a press
            // here would otherwise reach an enclosing modal's backdrop handler
            // and dismiss the dialog. preventDefault keeps focus on the trigger.
            onMouseDown={(event) => {
              event.preventDefault()
              event.stopPropagation()
            }}
          >
            {options.length === 0 ? (
              <p className="ui-select-empty">暂无可选项</p>
            ) : (
              options.map((option, index) => (
                // Keyed by index: option values are not guaranteed unique. A
                // half-typed probe key in RuleEditor yields two empty values.
                <div
                  key={index}
                  id={optionId(index)}
                  className="ui-select-option"
                  role="option"
                  aria-selected={index === selectedIndex}
                  aria-disabled={option.disabled || undefined}
                  data-active={index === activeIndex ? '' : undefined}
                  data-disabled={option.disabled ? '' : undefined}
                  onPointerEnter={() => !option.disabled && setActiveIndex(index)}
                  onClick={() => commit(option)}
                >
                  <span className="ui-select-option-label">{option.label}</span>
                  {index === selectedIndex && <Check size={15} aria-hidden />}
                </div>
              ))
            )}
          </div>,
          document.body,
        )}
    </>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

/** Gap between anchor and panel, breathing room at the viewport edge, and the
    smallest panel worth showing rather than dismissing. */
const PANEL_GAP = 4
const VIEWPORT_MARGIN = 8
const MIN_PANEL_HEIGHT = 96

export interface PanelPosition {
  top: number
  left: number
  width: number
  maxHeight: number
  placement: 'top' | 'bottom'
  /** True once the anchor is scrolled out of a clipping ancestor, so the panel should dismiss. */
  clipped: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/**
 * Ancestors that can visually crop the anchor. Collected once per open so the
 * per-scroll work is only rect reads: `getComputedStyle` forces a style recalc
 * and scroll fires continuously.
 */
function collectClippingAncestors(anchor: HTMLElement): HTMLElement[] {
  const ancestors: HTMLElement[] = []

  for (let node = anchor.parentElement; node && node !== document.body; node = node.parentElement) {
    const { overflowX, overflowY } = window.getComputedStyle(node)
    if (overflowX !== 'visible' || overflowY !== 'visible') ancestors.push(node)
  }

  return ancestors
}

/**
 * Whether the anchor has scrolled out of view. A viewport test alone is not
 * enough: a field inside a scrollable modal body can be hidden by that body
 * while still sitting within the viewport.
 */
function isAnchorHidden(rect: DOMRect, clippingAncestors: HTMLElement[]): boolean {
  for (const node of clippingAncestors) {
    const bounds = node.getBoundingClientRect()
    if (rect.bottom <= bounds.top || rect.top >= bounds.bottom) return true
    if (rect.right <= bounds.left || rect.left >= bounds.right) return true
  }

  return rect.bottom <= 0 || rect.top >= window.innerHeight
}

function isSamePosition(a: PanelPosition | null, b: PanelPosition): boolean {
  if (!a) return false
  return (
    a.top === b.top &&
    a.left === b.left &&
    a.width === b.width &&
    a.maxHeight === b.maxHeight &&
    a.placement === b.placement &&
    a.clipped === b.clipped
  )
}

/**
 * Tracks viewport coordinates for a panel anchored to an element. The panel is
 * rendered through a portal with `position: fixed` so it escapes scrollable and
 * `overflow: hidden` ancestors — a modal body would otherwise clip a dropdown
 * opened near its bottom edge.
 *
 * Flips above the anchor only when the space below cannot fit the panel and the
 * space above is genuinely larger, then clamps the result into the viewport so
 * the panel can never render off-screen. Recomputes on scroll and resize.
 *
 * @param desiredHeight Height the panel would like, used to decide the flip.
 */
export function useAnchoredPanel(
  anchorRef: RefObject<HTMLElement | null>,
  open: boolean,
  desiredHeight: number,
): PanelPosition | null {
  const [position, setPosition] = useState<PanelPosition | null>(null)
  const clippingAncestorsRef = useRef<HTMLElement[]>([])
  // Read through a ref so a changing desiredHeight does not re-bind listeners.
  const desiredHeightRef = useRef(desiredHeight)
  desiredHeightRef.current = desiredHeight

  const measure = useCallback(() => {
    const anchor = anchorRef.current
    if (!anchor) return

    const rect = anchor.getBoundingClientRect()
    const viewportHeight = window.innerHeight
    const viewportWidth = window.innerWidth
    const wanted = desiredHeightRef.current

    const spaceBelow = viewportHeight - rect.bottom - PANEL_GAP - VIEWPORT_MARGIN
    const spaceAbove = rect.top - PANEL_GAP - VIEWPORT_MARGIN
    // Only flip when below genuinely cannot fit the panel and above is roomier,
    // so a select near the middle of the page keeps opening downward.
    const placeAbove = spaceBelow < wanted && spaceAbove > spaceBelow

    const available = placeAbove ? spaceAbove : spaceBelow
    // A zero-height panel would read as open while showing nothing; keep a floor
    // and let it overlap the anchor in a very short viewport.
    const maxHeight = clamp(Math.min(available, wanted), MIN_PANEL_HEIGHT, viewportHeight)
    const width = Math.min(rect.width, viewportWidth - VIEWPORT_MARGIN * 2)

    const rawTop = placeAbove ? rect.top - PANEL_GAP - maxHeight : rect.bottom + PANEL_GAP
    const maxTop = Math.max(viewportHeight - maxHeight - VIEWPORT_MARGIN, VIEWPORT_MARGIN)
    const maxLeft = Math.max(viewportWidth - width - VIEWPORT_MARGIN, VIEWPORT_MARGIN)

    const next: PanelPosition = {
      top: clamp(rawTop, VIEWPORT_MARGIN, maxTop),
      left: clamp(rect.left, VIEWPORT_MARGIN, maxLeft),
      width,
      maxHeight,
      placement: placeAbove ? 'top' : 'bottom',
      clipped: isAnchorHidden(rect, clippingAncestorsRef.current),
    }

    // Scroll fires continuously; skip the re-render when nothing actually moved.
    setPosition((current) => (isSamePosition(current, next) ? current : next))
  }, [anchorRef])

  useEffect(() => {
    if (!open) {
      setPosition(null)
      clippingAncestorsRef.current = []
      return
    }

    const anchor = anchorRef.current
    clippingAncestorsRef.current = anchor ? collectClippingAncestors(anchor) : []
    measure()

    // Capture phase so scrolling any ancestor — not just the window — is observed.
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)

    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
    }
  }, [open, measure, anchorRef])

  return position
}

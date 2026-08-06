import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'service-monitor-theme'

function prefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/**
 * Reads the persisted choice, falling back to the OS preference on first visit.
 * Kept in sync with the pre-mount script in index.html, which applies the same
 * resolution so the first paint never flashes the wrong theme.
 */
export function resolveInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return prefersDark() ? 'dark' : 'light'
}

/**
 * Owns the `.dark` class on <html>, which both the custom properties in
 * tokens.css and Tailwind's `darkMode: 'class'` utilities key off of.
 *
 * The choice is persisted only when the user toggles, so an untouched session
 * keeps following the OS instead of freezing on whatever it resolved to first.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY)) return
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    function onChange(event: MediaQueryListEvent) {
      setTheme(event.matches ? 'dark' : 'light')
    }
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
  }, [])

  return { theme, toggleTheme }
}

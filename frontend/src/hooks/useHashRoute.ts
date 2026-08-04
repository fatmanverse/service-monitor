import { useCallback, useEffect, useState } from 'react'

function currentHash() {
  return window.location.hash.replace(/^#\/?/, '')
}

/**
 * Minimal hash-based routing. Returns the raw hash segment and a setter that
 * updates the URL; callers own validation and fallback of the value.
 */
export function useHashRoute() {
  const [hash, setHash] = useState(currentHash)

  useEffect(() => {
    function onHashChange() {
      setHash(currentHash())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navigate = useCallback((next: string) => {
    if (currentHash() === next) return
    window.location.hash = `/${next}`
  }, [])

  return { hash, navigate }
}

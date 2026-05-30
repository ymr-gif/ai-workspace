import { useState, useCallback, useEffect } from 'react'

export default function useSearch(token) {
  const [searchOpen, setSearchOpen]     = useState(false)
  const [searchQuery, setSearchQuery]   = useState('')
  const [searchScope, setSearchScope]   = useState('all')
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const runSearch = useCallback(async (q, scope) => {
    if (!q.trim()) { setSearchResults(null); return }
    setSearchLoading(true)
    try {
      const qs = new URLSearchParams({ q: q.trim(), scope })
      const r = await fetch(`/api/search?${qs}`, { headers: authHeaders })
      if (r.ok) setSearchResults(await r.json())
    } catch { /* ignore */ } finally { setSearchLoading(false) }
  }, [token])

  useEffect(() => {
    if (!searchQuery.trim()) { setSearchResults(null); return }
    const tid = setTimeout(() => runSearch(searchQuery, searchScope), 300)
    return () => clearTimeout(tid)
  }, [searchQuery, searchScope])

  function clearSearch() { setSearchQuery(''); setSearchResults(null) }

  return {
    searchOpen, setSearchOpen,
    searchQuery, setSearchQuery,
    searchScope, setSearchScope,
    searchResults,
    searchLoading,
    clearSearch,
  }
}

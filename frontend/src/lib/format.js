// Display helpers. Values from the API stay machine-readable; formatting happens only here.

export function money(amount) {
  const n = Number(amount)
  if (Number.isNaN(n)) return amount
  return `Rs ${n.toLocaleString('en-PK', { maximumFractionDigits: 2 })}`
}

export function when(iso, lang) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString(lang === 'ur' ? 'ur-PK' : 'en-PK', {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  })
}

export function timeOnly(iso, lang) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString(lang === 'ur' ? 'ur-PK' : 'en-PK', { hour: 'numeric', minute: '2-digit' })
}

export async function api(path) {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`)
  return r.json()
}

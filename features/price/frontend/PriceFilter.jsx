import React, { useEffect, useMemo, useRef, useState } from 'react'
import './price.css'

// Фильтр по цене за ночь: кнопка рядом со счётчиком «N вариантов», по клику — карточка
// с сортировкой, гистограммой цен и ползунком «до N ₽». Состояние держит родитель: {sort, max}
export const NO_PRICE = { sort: null, max: null }
const STEP = 100
const BINS = 24
const SORTS = [[null, 'Рекомендуем'], ['asc', 'Дешевле'], ['desc', 'Дороже']]

const rub = n => `${n.toLocaleString('ru-RU')} ₽`
const short = n => (n >= 1000 ? `${(n / 1000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} тыс` : n)

// Применить к строкам выдачи [{h, …}]: отрезать дороже max и, если нужно, переставить по цене
export function applyPrice(rows, { sort, max }) {
  const kept = max ? rows.filter(x => x.h.price_rub <= max) : rows
  if (!sort) return kept
  const k = sort === 'asc' ? 1 : -1
  return kept.slice().sort((a, b) => k * (a.h.price_rub - b.h.price_rub))
}

const Sliders = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M4 7h9M17 7h3M4 17h3M11 17h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" />
  </svg>
)

export default function PriceFilter({ prices, value, onChange }) {
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  const lo = Math.floor(Math.min(...prices) / STEP) * STEP
  const hi = Math.ceil(Math.max(...prices) / STEP) * STEP
  const max = value.max ?? hi
  const active = value.sort || value.max

  // быстрые суммы — по квартилям реальных цен, округлённые до 500 ₽
  const quick = useMemo(() => {
    const s = prices.slice().sort((a, b) => a - b)
    return [0.25, 0.5, 0.75].map(q => Math.round(s[Math.floor(q * (s.length - 1))] / 500) * 500)
  }, [prices])
  const bins = useMemo(() => {
    const b = Array(BINS).fill(0), w = (hi - lo) / BINS
    prices.forEach(p => { b[Math.min(BINS - 1, Math.floor((p - lo) / w))]++ })
    return b
  }, [prices, lo, hi])
  const top = Math.max(...bins)
  const fit = prices.filter(p => p <= max).length

  useEffect(() => {
    if (!open) return
    const out = e => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    const esc = e => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', out)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', out); document.removeEventListener('keydown', esc) }
  }, [open])

  const set = patch => onChange({ ...value, ...patch })
  const setMax = m => set({ max: m >= hi ? null : m })
  const label = [value.max && `до ${short(value.max)} ₽`, value.sort === 'asc' && 'дешевле', value.sort === 'desc' && 'дороже']
    .filter(Boolean).join(' · ')

  return (
    <div className="pf" ref={box}>
      <button className={`pf-btn ${active ? 'on' : ''} ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}
        aria-expanded={open} aria-label="Фильтр и сортировка по цене">
        <Sliders />{label || 'Цена'}
      </button>
      {open && (
        <div className="pf-card" role="dialog" aria-label="Цена">
          <div className="pf-title">Сначала показывать</div>
          <div className="pf-seg">
            {SORTS.map(([k, t]) => (
              <button key={t} className={value.sort === k ? 'on' : ''} onClick={() => set({ sort: k })}>{t}</button>
            ))}
          </div>

          <div className="pf-head">
            <div className="pf-title">Цена за ночь</div>
            <b>{value.max ? `до ${rub(max)}` : 'любая'}</b>
          </div>
          <div className="pf-hist" aria-hidden="true">
            {bins.map((n, i) => (
              <i key={i} style={{ height: `${n ? 8 + 92 * n / top : 0}%` }}
                className={lo + (i + 0.5) * (hi - lo) / BINS <= max ? 'in' : ''} />
            ))}
          </div>
          <input className="pf-range" type="range" min={lo} max={hi} step={STEP} value={max}
            style={{ '--p': `${100 * (max - lo) / (hi - lo)}%` }}
            onChange={e => setMax(+e.target.value)} aria-label="Максимальная цена за ночь" />
          <div className="pf-scale"><span>{rub(lo)}</span><span>{rub(hi)}</span></div>
          <div className="pf-quick">
            {quick.map(q => (
              <button key={q} className={value.max === q ? 'on' : ''} onClick={() => setMax(q)}>до {short(q)} ₽</button>
            ))}
            <button className={!value.max ? 'on' : ''} onClick={() => setMax(hi)}>Любая</button>
          </div>

          <div className="pf-foot">
            <button className="pf-reset" disabled={!active} onClick={() => onChange(NO_PRICE)}>Сбросить</button>
            <button className="pf-go" onClick={() => setOpen(false)}>
              {fit ? `Показать ${fit.toLocaleString('ru-RU')}` : 'Таких нет — поднимите сумму'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

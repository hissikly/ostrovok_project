import React, { useMemo, useState } from 'react'

const rub = n => `${n.toLocaleString('ru-RU')} ₽`

export default function HotelList({ hotels, onSelect }) {
  const [q, setQ] = useState('')
  const list = useMemo(() => {
    const s = q.trim().toLowerCase()
    return hotels
      .filter(h => !s || h.name.toLowerCase().includes(s))
      .sort((a, b) => b.facts - a.facts)
  }, [hotels, q])

  return (
    <div>
      <input className="search" placeholder="Найти отель по названию" value={q} onChange={e => setQ(e.target.value)} />
      <div className="count">{list.length.toLocaleString('ru-RU')} вариантов в Сочи</div>
      {list.slice(0, 200).map(h => (
        <div key={h.id} className="row" onClick={() => onSelect(h.id)}>
          <div style={{ minWidth: 0 }}>
            <div className="nm">{h.name}</div>
            <div className="sub">
              <span>{h.kind_ru}</span>
              {h.stars && <span style={{ color: '#FFB800' }}>{'★'.repeat(h.stars)}</span>}
              {h.facts > 1 && <span className="chip lime" style={{ padding: '2px 9px', fontSize: 12 }}>О!кно: видно, что из окна</span>}
            </div>
          </div>
          <div className="pr"><b>{rub(h.price_rub)}</b><small>за ночь</small></div>
        </div>
      ))}
    </div>
  )
}

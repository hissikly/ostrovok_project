import React, { useMemo, useState } from 'react'
import { post } from '@app/api.js'
import Icon from '@app/icons.jsx'

const rub = n => `${n.toLocaleString('ru-RU')} ₽`
const STATE_ICON = { match: 'check', partial: 'half', no: 'x', unknown: 'question' }
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

// «✨ Опиши» — не чат: фраза растворяется в линзах и исчезает
function Describe({ onApply }) {
  const [text, setText] = useState('')
  const [note, setNote] = useState(null)
  const submit = async e => {
    e.preventDefault()
    if (!text.trim()) return
    const d = await post('/api/describe', { text })
    onApply(d)
    setNote(d.not_yet.length ? `Пока не умеем учитывать ${d.not_yet.join(', ')}. Скоро научимся.`
      : d.lenses.length ? null : 'Не поняли, что важно. Попробуйте «вид на море» или «рядом пляж».')
    if (d.lenses.length) setText('')
  }
  return (
    <>
      <form className="describe" onSubmit={submit}>
        <Icon name="sparkle" />
        <input placeholder="Опишите, какой отель нужен" value={text} onChange={e => setText(e.target.value)} />
        {text.trim() && <button className="go">Подобрать</button>}
      </form>
      {note && <div className="describe-note">{note}</div>}
    </>
  )
}

function Lenses({ lenses, on, toggle }) {
  return (
    <div className="lenses">
      {lenses.map(l => (
        <button key={l.id} className={on.includes(l.id) ? 'on' : ''} onClick={() => toggle(l.id)} title={l.hint}>
          <Icon name={l.icon} size={18} />{l.title}
        </button>
      ))}
    </div>
  )
}

function Row({ h, info, onSelect }) {
  const shown = info.reasons.filter(r => r.state !== 'unknown')
  const unknown = info.reasons.length - shown.length
  return (
    <div className="row result" onClick={() => onSelect(h.id)}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="nm">{h.name}</div>
        <div className="sub">
          <span>{h.kind_ru}</span>
          {h.stars && <span style={{ color: '#FFB800' }}>{'★'.repeat(h.stars)}</span>}
        </div>
        <div className="why">
          {shown.map(r => (
            <div key={r.lens} className={r.state}><Icon name={STATE_ICON[r.state]} size={16} />{r.text}</div>
          ))}
          {unknown > 0 && <div className="unknown"><Icon name="question" size={16} />
            {unknown === 1 ? 'Про одно из пожеланий пока не знаем' : `Про ${unknown} пожелания пока не знаем`}</div>}
        </div>
      </div>
      <div className="pr"><b>{rub(h.price_rub)}</b><small>за ночь</small></div>
    </div>
  )
}

export default function SearchPanel({ hotels, lenses, on, setOn, setMonth, result, onSelect }) {
  const [q, setQ] = useState('')
  const toggle = id => setOn(on.includes(id) ? on.filter(x => x !== id) : [...on, id])
  const apply = d => {
    if (d.lenses.length) setOn(d.lenses)
    if (d.month) setMonth(d.month)
  }

  const byId = useMemo(() => Object.fromEntries(hotels.map(h => [h.id, h])), [hotels])
  const list = useMemo(() => {
    const s = q.trim().toLowerCase()
    const rows = result && on.length
      ? result.hotels.map(r => ({ h: byId[r.id], info: r })).filter(x => x.h && x.info.fit !== 'none')
      : hotels.slice().sort((a, b) => b.okno - a.okno || b.facts - a.facts).map(h => ({ h, info: null }))
    return s ? rows.filter(x => x.h.name.toLowerCase().includes(s)) : rows
  }, [hotels, result, on, q, byId])

  const c = result?.counts
  const count = !on.length || !c ? `${list.length.toLocaleString('ru-RU')} вариантов в Сочи`
    : c.all ? `${c.all} ${plural(c.all, 'отель подходит', 'отеля подходят', 'отелей подходят')} по всем пожеланиям`
      : `По всем пожеланиям сразу не нашли. Ближе всего — ${list.length}`

  return (
    <div>
      <div className="block search-block">
        <h2>Что важно в поездке?</h2>
        <Describe onApply={apply} />
        <Lenses lenses={lenses} on={on} toggle={toggle} />
      </div>
      <input className="search" placeholder="Найти отель по названию" value={q} onChange={e => setQ(e.target.value)} />
      <div className="count">{count}</div>
      {list.slice(0, 120).map(({ h, info }) => info
        ? <Row key={h.id} h={h} info={info} onSelect={onSelect} />
        : (
          <div key={h.id} className="row" onClick={() => onSelect(h.id)}>
            <div style={{ minWidth: 0 }}>
              <div className="nm">{h.name}</div>
              <div className="sub">
                <span>{h.kind_ru}</span>
                {h.stars && <span style={{ color: '#FFB800' }}>{'★'.repeat(h.stars)}</span>}
                {h.okno && <span className="chip lime" style={{ padding: '2px 9px', fontSize: 12 }}>О!кно: видно, что из окна</span>}
              </div>
            </div>
            <div className="pr"><b>{rub(h.price_rub)}</b><small>за ночь</small></div>
          </div>
        ))}
    </div>
  )
}

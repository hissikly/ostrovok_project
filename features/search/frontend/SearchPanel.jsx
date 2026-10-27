import React, { useMemo, useState } from 'react'
import { post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { FitLine } from '@features/trip_plan/frontend/Interests.jsx'
import { useFit, useInterests } from '@features/trip_plan/frontend/interests.js'
import CompareButton from '@features/compare/frontend/CompareButton.jsx'
import { BaselineList, ModeSwitch, useBaseline } from '@features/compare/frontend/Baseline.jsx'

const rub = n => `${n.toLocaleString('ru-RU')} ₽`
const STATE_ICON = { match: 'check', partial: 'half', no: 'x', unknown: 'question' }
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

// «✨ Опиши» — не чат: фраза растворяется в линзах и исчезает
// То, что знает только отель (питомцы, завтрак, заезд…), — не фильтр: честно говорим и предлагаем спросить
function AskHotels({ ask, topIds }) {
  const [sent, setSent] = useState({})
  const send = async a => {
    const r = await post('/api/hotelier/questions', { hotel_ids: topIds(), topic: a.topic })
    setSent(s => ({ ...s, [a.topic]: r }))
  }
  return ask.map(a => (
    <div key={a.topic} className="ask-hotels">
      <b>{a.question}</b>
      {sent[a.topic]
        ? <div className="faq-asked"><Icon name="check" size={16} />Спросили у {sent[a.topic].asked} {plural(sent[a.topic].asked, 'отеля', 'отелей', 'отелей')} из подборки
            {sent[a.topic].known > 0 && <span>, ещё {sent[a.topic].known} уже ответили — смотрите в карточках</span>}</div>
        : <>
            <div className="muted">Этого мы пока не знаем :( Спросить у отелей? Обычно отвечают за 1–3 дня</div>
            <button className="faq-ask-btn" onClick={() => send(a)}>Спросить у отелей из подборки</button>
          </>}
    </div>
  ))
}

function Describe({ onApply, topIds }) {
  const [text, setText] = useState('')
  const [note, setNote] = useState(null)
  const [ask, setAsk] = useState([])
  const submit = async e => {
    e.preventDefault()
    if (!text.trim()) return
    const d = await post('/api/describe', { text })
    onApply(d)
    setAsk(d.ask || [])
    setNote(d.not_yet.length ? `Это пока не учитываем: ${d.not_yet.join(', ')}. Скоро научимся.`
      : d.lenses.length || d.ask?.length ? null : 'Не поняли, что важно. Попробуйте «вид на море», «продуктовый рядом» или откройте «Ещё фильтры».')
    if (d.lenses.length || d.ask?.length) setText('')
  }
  return (
    <>
      <form className="describe" onSubmit={submit}>
        <Icon name="sparkle" />
        <input placeholder="Опишите, какой отель нужен" value={text} onChange={e => setText(e.target.value)} />
        {text.trim() && <button className="go">Подобрать</button>}
      </form>
      {note && <div className="describe-note">{note}</div>}
      <AskHotels ask={ask} topIds={topIds} />
    </>
  )
}

// Поиск по фильтрам — по основам слов, как в «опиши»: «магазинчик у дома» найдёт «Продуктовый рядом»
const words = t => t.toLowerCase().replace(/ё/g, 'е').match(/[a-zа-я0-9]+/g) || []
const stem = w => (w.length <= 4 ? w : w.slice(0, Math.max(4, w.length - 2)))
function matches(l, query) {
  const hay = words([l.title, ...(l.synonyms || [])].join(' '))
  return words(query).every(q => hay.some(w => w.startsWith(stem(q)) || q.startsWith(stem(w))))
}

function Lenses({ lenses, on, toggle, reset }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const primary = lenses.filter(l => l.primary)
  const extra = lenses.filter(l => !l.primary)
  const extraOn = extra.filter(l => on.includes(l.id))
  const found = q.trim() ? extra.filter(l => matches(l, q)) : extra
  const groups = [...new Set(found.map(l => l.group))]
  const btn = l => (
    <button key={l.id} className={on.includes(l.id) ? 'on' : ''} onClick={() => toggle(l.id)} title={l.hint}>
      <Icon name={l.icon} size={18} />{l.title}
    </button>
  )
  return (
    <>
      <div className="lenses">
        {primary.map(btn)}
        {extraOn.map(btn)}
        <button className={`more ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
          {open ? 'Свернуть' : `Ещё фильтры${extra.length ? ` (${extra.length})` : ''}`}
        </button>
        {on.length > 0 && <button className="more reset" onClick={reset}><Icon name="x" size={16} />Сбросить</button>}
      </div>
      {open && (
        <div className="more-box">
          <input className="more-search" placeholder="Найти фильтр: аптека, парк, остановка…" value={q}
            onChange={e => setQ(e.target.value)} autoFocus />
          {groups.map(g => (
            <div key={g} className="more-group">
              <div className="more-title">{g}</div>
              <div className="lenses">{found.filter(l => l.group === g).map(btn)}</div>
            </div>
          ))}
          {!found.length && <div className="describe-note">Такого фильтра нет. Напишите в строку «опиши» выше: если по карте это не узнать, спросим у отелей.</div>}
        </div>
      )}
    </>
  )
}

function Row({ h, info, fit, onSelect }) {
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
        <FitLine fit={fit} />
      </div>
      <div className="pr"><b>{rub(h.price_rub)}</b><small>за ночь</small><CompareButton id={h.id} /></div>
    </div>
  )
}

export default function SearchPanel({ hotels, lenses, on, setOn, month, setMonth, result, onSelect }) {
  const [q, setQ] = useState('')
  const toggle = id => setOn(on.includes(id) ? on.filter(x => x !== id) : [...on, id])
  const apply = d => {
    // новая фраза дополняет подбор: уже включённые фильтры остаются, снять их можно кликом
    setOn(prev => [...prev, ...d.lenses.filter(id => !prev.includes(id))])
    if (d.month) setMonth(d.month)
  }

  const byId = useMemo(() => Object.fromEntries(hotels.map(h => [h.id, h])), [hotels])
  // день по интересам: без фильтров отели идут по тому, какой день из них получится
  const [interests] = useInterests()
  const fit = useFit(interests)
  const list = useMemo(() => {
    const s = q.trim().toLowerCase()
    const rows = result && on.length
      ? result.hotels.map(r => ({ h: byId[r.id], info: r })).filter(x => x.h && x.info.fit !== 'none')
      : hotels.slice().sort((a, b) => (fit ? (fit[b.id]?.score ?? -1e9) - (fit[a.id]?.score ?? -1e9) : 0) || b.okno - a.okno || b.facts - a.facts)
        .map(h => ({ h, info: null }))
    return s ? rows.filter(x => x.h.name.toLowerCase().includes(s)) : rows
  }, [hotels, result, on, q, byId, fit])

  // «было / стало»: обычная выдача сайта рядом с нашей (features/compare)
  const [mode, setMode] = useState('okno')
  const bs = useBaseline(on, month)
  const c = result?.counts
  const count = !on.length || !c ? `${list.length.toLocaleString('ru-RU')} вариантов в Сочи`
    : c.all ? `${c.all} ${plural(c.all, 'отель подходит', 'отеля подходят', 'отелей подходят')} по всем пожеланиям`
      : `По всем пожеланиям сразу не нашли. Ближе всего — ${list.length}`

  return (
    <div>
      <div className="block search-block">
        <h2>Что важно в поездке?</h2>
        <Describe onApply={apply} topIds={() => list.slice(0, 10).map(x => x.h.id)} />
        <Lenses lenses={lenses} on={on} toggle={toggle} reset={() => setOn([])} />
      </div>
      <input className="search" placeholder="Найти отель по названию" value={q} onChange={e => setQ(e.target.value)} />
      {on.length > 0 && <ModeSwitch mode={mode} setMode={setMode} />}
      {on.length > 0 && mode === 'base' ? <BaselineList data={bs} byId={byId} onSelect={onSelect} /> : <>
      <div className="count">{count}</div>
      {list.slice(0, 120).map(({ h, info }) => info
        ? <Row key={h.id} h={h} info={info} fit={fit?.[h.id]} onSelect={onSelect} />
        : (
          <div key={h.id} className="row" onClick={() => onSelect(h.id)}>
            <div style={{ minWidth: 0 }}>
              <div className="nm">{h.name}</div>
              <div className="sub">
                <span>{h.kind_ru}</span>
                {h.stars && <span style={{ color: '#FFB800' }}>{'★'.repeat(h.stars)}</span>}
                {h.okno && <span className="chip lime" style={{ padding: '2px 9px', fontSize: 12 }}>О!кно: видно, что из окна</span>}
              </div>
              <FitLine fit={fit?.[h.id]} />
            </div>
            <div className="pr"><b>{rub(h.price_rub)}</b><small>за ночь</small><CompareButton id={h.id} /></div>
          </div>
        ))}
      </>}
    </div>
  )
}

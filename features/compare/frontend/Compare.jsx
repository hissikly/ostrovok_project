import React, { useEffect, useState } from 'react'
import { post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { HOW, sureWord } from '@features/facts/frontend/FactList.jsx'
import { useCompare } from './store.js'
import './compare.css'

const rub = n => `${n.toLocaleString('ru-RU')} ₽`
const MONTH = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
const quote = n => (/[«"„“]/.test(n) ? n : `«${n}»`)

// «как узнали» — те же слова, что в карточке отеля; у оценки шума слово об уверенности лишнее
function how(c) {
  if (c.how) return c.how
  const base = HOW[c.source] || ''
  if (!c.confidence || c.source === 'computed:noise-model') return base
  return `${base} ${sureWord(c.confidence)[0][0].toUpperCase()}${sureWord(c.confidence)[0].slice(1)}.`
}

function Cell({ c, hotelId, best, open, onToggle }) {
  const [asked, setAsked] = useState(false)
  const cls = `cmp-c ${best ? 'best' : ''} ${c.win ? 'win' : ''} ${c.state === 'no' ? 'bad' : ''} ${c.state === 'unknown' ? 'unk' : ''}`
  if (c.items) return (
    <td className={cls} onClick={onToggle}>
      <div className="cmp-near">{c.items.map(i => (
        <div key={i.id} title={i.name ? quote(i.name) : undefined}><Icon name={i.icon} size={16} />{i.title}
          {i.minutes != null ? <b>{i.minutes} мин</b> : <span className="no">{i.known ? 'нет' : '?'}</span>}</div>
      ))}</div>
      {open && <div className="cmp-how">{HOW[c.source]} «Нет» — не нашли рядом за 10–20 минут пешком.</div>}
    </td>
  )
  return (
    <td className={cls} onClick={onToggle}>
      {c.split
        ? <><span className="cmp-diff">Мнения расходятся</span>
            <div className="cmp-split"><div>Отель: <b>{c.split.hotel}</b></div><div>Сайт отеля: <b>{c.split.site}</b></div></div></>
        : <><div className="v">{c.win && <span className="tick"><Icon name="check" size={13} /></span>}{c.value}</div>
            {c.sub && <div className="s">{c.sub}</div>}</>}
      {c.ask && (asked
        ? <div className="s">Спросили у отеля</div>
        : <button className="cmp-ask" onClick={e => { e.stopPropagation(); post(`/api/hotelier/${hotelId}/questions`, { topic: c.ask }).then(() => setAsked(true)) }}>Спросить у отеля</button>)}
      {open && how(c) && <div className="cmp-how">{how(c)}</div>}
    </td>
  )
}

export default function Compare({ ids, lenses, on, month, onHotel, onIds, onExit }) {
  const { set } = useCompare()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [more, setMore] = useState(false)
  const [open, setOpen] = useState(null)   // «как узнали» у одной клетки: `${row}:${hotel}`
  const key = ids.join(',')

  useEffect(() => {
    setError(null)
    if (ids.length < 2) return
    post('/api/compare', { ids, lenses: on, month }).then(setData).catch(() => setError('Не получилось сравнить — похоже, пропала связь с сервером.'))
  }, [key, on.join(','), month])

  const removeOne = id => {
    const next = ids.filter(x => x !== id)
    set(next)
    if (next.length < 2) onExit(); else onIds(next)
  }
  if (ids.length < 2) return <div className="cmp-page"><button className="back" onClick={onExit}>← К выдаче</button><p>Для сравнения нужно хотя бы два отеля.</p></div>
  if (error) return <div className="cmp-page"><button className="back" onClick={onExit}>← К выдаче</button><p>{error}</p></div>
  if (!data) return <div className="cmp-page muted">Сравниваем…</div>

  const title = l => lenses.find(x => x.id === l)
  const rows = data.rows.filter(r => !r.extra || more)
  const extra = data.rows.filter(r => r.extra)
  const n = data.hotels.length
  return (
    <div className="cmp-page">
      <button className="back" onClick={onExit}>← К выдаче</button>
      <h1>Сравнение: {n} отеля</h1>
      <p className="cmp-lead">Галочка — лучшее в строке. Нажмите на значение, и мы покажем, откуда это знаем.</p>
      <div className="chips">
        {data.lenses.map(l => title(l) && <span key={l} className="chip on"><Icon name={title(l).icon} size={16} />{title(l).title}</span>)}
        {data.month && <span className="chip"><Icon name="calendar" size={16} />{MONTH[data.month]}</span>}
      </div>
      <div className="cmp-scroll">
        <table className="cmp-t" style={{ minWidth: 150 + 230 * n }}>
          <colgroup><col className="lab" />{data.hotels.map(h => <col key={h.id} />)}</colgroup>
          <thead><tr>
            <th className="cmp-lab" />
            {data.hotels.map(h => (
              <th key={h.id} className={`cmp-c ${h.best ? 'best' : ''}`}>
                {h.best && <span className="cmp-best">{data.basis === 'query' ? 'Лучше под ваш запрос' : 'Лучше по главному'}</span>}
                <div className="cmp-hn"><span>{h.name}</span><button onClick={() => removeOne(h.id)} aria-label={`Убрать ${h.name}`}><Icon name="x" size={16} /></button></div>
                <div className="cmp-hm"><span className="cmp-rt">{h.rating.toFixed(1).replace('.', ',')}</span>
                  {h.stars && <span className="st">{'★'.repeat(h.stars)}</span>}<span className="p">{rub(h.price_rub)}</span></div>
                <div className="cmp-score"><b>{h.met} из {h.of}</b> {data.basis === 'query' ? 'условий запроса' : 'главных условий'}</div>
              </th>
            ))}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className={i === 0 ? 'first' : ''}>
                <td className="cmp-lab"><Icon name={r.icon} size={18} />{r.title}</td>
                {r.cells.map((c, j) => (
                  <Cell key={j} c={c} hotelId={data.hotels[j].id} best={data.hotels[j].best}
                    open={open === `${r.id}:${j}`} onToggle={() => setOpen(open === `${r.id}:${j}` ? null : `${r.id}:${j}`)} />
                ))}
              </tr>
            ))}
            <tr className="foot">
              <td className="cmp-lab" />
              {data.hotels.map(h => (
                <td key={h.id} className={`cmp-c ${h.best ? 'best' : ''}`}>
                  {h.minus && <div className="cmp-minus"><Icon name="alert" size={16} />{h.minus}</div>}
                  <button className="cmp-open" onClick={() => onHotel(h.id)}>Открыть отель</button>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {extra.length > 0 && (
        <button className="cmp-more" onClick={() => setMore(!more)}>
          {more ? 'Свернуть' : `Ещё: ${extra.map(r => r.title.toLowerCase()).join(', ')}`}
        </button>
      )}
    </div>
  )
}

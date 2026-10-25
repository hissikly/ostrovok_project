import React, { useState } from 'react'
import Icon from '@app/icons.jsx'

const SIDE = { N: 'север', E: 'восток', S: 'юг', W: 'запад' }
const ORDER = ['W', 'S', 'N', 'E']
const HOW = {
  'computed:dem': 'Посчитали по спутниковой карте высот рельефа',
  'computed:horizon': 'Посчитали линию обзора из окон: рельеф местности и высоты соседних домов',
  'computed:horizon+sun': 'Сопоставили линию обзора из окон с положением солнца по датам',
  hotelier: 'Ответ отеля', osm: 'Открытая карта OpenStreetMap',
}

// Уверенность — словами, без процентов (wiki/design-system.md)
export function sureWord(c) {
  return c >= 0.8 ? ['точно', 'hi'] : c >= 0.6 ? ['по расчёту', 'mid'] : ['примерно', 'lo']
}

const sideOf = f => f.scope.split(':')[1]
const M = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
const M_IN = ['', 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']

// [4,5,6,7,8,9,10] → «апр–окт», [10] → «в октябре», [4,5,9] → «апр, май, сен»
function monthRange(ms) {
  if (ms.length === 1) return `в ${M_IN[ms[0]]}`
  const solid = ms.every((m, i) => i === 0 || m === ms[i - 1] + 1)
  return solid ? `${M[ms[0]]}–${M[ms[ms.length - 1]]}` : ms.map(m => M[m]).join(', ')
}

// Факты по сторонам здания сводим в одну понятную строку
function group(facts) {
  const rows = []
  const sea = facts.filter(f => f.characteristic === 'sea_view')
  if (sea.length) {
    const by = Object.fromEntries(sea.map(f => [sideOf(f), f]))
    const lines = ORDER.filter(s => by[s]).map(s => {
      const fl = by[s].value.from_floor
      return [SIDE[s], fl ? (fl === 1 ? 'с любого этажа' : `с ${fl}-го этажа`) : 'не видно']
    })
    const any = sea.some(f => f.value.from_floor)
    rows.push({ key: 'sea', icon: 'waves', title: any ? 'Есть номера с видом на море' : 'Вида на море нет',
      lines, facts: sea })
  }
  const sun = facts.filter(f => f.characteristic === 'sunset_view')
  if (sun.length) {
    const by = Object.fromEntries(sun.map(f => [sideOf(f), f]))
    const lines = ORDER.filter(s => by[s]).map(s => [SIDE[s], monthRange(by[s].value.months)])
    rows.push({ key: 'sun', icon: 'sunset', title: 'Закат над морем из окна', lines, facts: sun })
  }
  for (const f of facts.filter(f => !['sea_view', 'sunset_view'].includes(f.characteristic))) {
    rows.push({ key: f.id, icon: 'window', title: f.value?.text || f.characteristic, text: '', facts: [f] })
  }
  return rows
}

function Row({ r }) {
  const [open, setOpen] = useState(false)
  const c = Math.min(...r.facts.map(f => f.confidence))
  const [word, cls] = sureWord(c)
  const f0 = r.facts[0]
  return (
    <div className="fact" onClick={() => setOpen(!open)}>
      <div className="ic"><Icon name={r.icon} /></div>
      <div style={{ flex: 1 }}>
        <div className="t">{r.title}</div>
        {r.text && <div className="s">{r.text}</div>}
        {r.lines && <div className="sides">{r.lines.map(([side, v]) =>
          <div key={side}><span>Окна на {side}</span><b className={v === 'не видно' ? 'no' : ''}>{v}</b></div>)}</div>}
        {open && <div className="how">
          {HOW[f0.source] || f0.source}. Проверено {new Date(f0.obtained_at).toLocaleDateString('ru-RU')}.
          {c < 0.8 && ' Высота части соседних домов известна только по числу этажей — уточняем у отеля.'}
        </div>}
      </div>
      <span className={`sure ${cls}`}>{word}</span>
    </div>
  )
}

export default function FactList({ facts }) {
  const rows = group(facts)
  if (!rows.length) return null
  return (
    <div className="block">
      <h2>Что важно знать</h2>
      <p className="lead">Этого нет в описании отеля — мы проверили сами. Нажмите, чтобы узнать как.</p>
      {rows.map(r => <Row key={r.key} r={r} />)}
    </div>
  )
}

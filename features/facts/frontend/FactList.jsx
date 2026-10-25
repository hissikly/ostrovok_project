import React, { useState } from 'react'
import Icon from '@app/icons.jsx'

const SIDE = { N: 'север', E: 'восток', S: 'юг', W: 'запад' }
const ORDER = ['W', 'S', 'N', 'E']
// Откуда мы это знаем — одной фразой, без дат и оговорок
const HOW = {
  'computed:dem': 'Посчитали по карте рельефа.',
  'computed:horizon': 'Посчитали по рельефу и высоте соседних домов.',
  'computed:horizon+sun': 'Посчитали по высоте домов вокруг и движению солнца.',
  'computed:osm-poi': 'Нашли на открытой карте ближайшее место каждого типа и посчитали путь пешком по прямой: настоящий путь может быть длиннее.',
  'computed:osm-beach': 'Измерили по открытой карте до ближайшего пляжа, по прямой: настоящий путь может быть длиннее.',
  hotelier: 'Так ответил отель.', osm: 'Взяли с открытой карты.',
}

// Уверенность — словами, без процентов (wiki/design-system.md)
export function sureWord(c) {
  return c >= 0.8 ? ['точно', 'hi'] : c >= 0.6 ? ['по расчёту', 'mid'] : ['примерно', 'lo']
}

const sideOf = f => f.scope.split(':')[1]
// что показываем в «Что рядом» сразу; остальное — «ещё N»
const NEAR_MAIN = ['grocery', 'pharmacy', 'cafe', 'park', 'playground', 'bus', 'atm']
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
      const { from_floor: fl, glimpse_from: gl } = by[s].value
      if (fl) return [SIDE[s], fl === 1 ? 'с любого этажа' : `с ${fl}-го этажа`]
      if (gl) return [SIDE[s], `краешком с ${gl}-го этажа`]
      return [SIDE[s], 'не видно']
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
  const beach = facts.find(f => f.characteristic === 'beach_distance')
  if (beach) {
    const m = beach.value.meters
    rows.push({ key: 'beach', icon: 'beach', title: `До пляжа ${m < 1000 ? `${m} м` : `${(m / 1000).toFixed(1).replace('.', ',')} км`}`,
      text: `Около ${beach.value.walk_min} мин пешком`, facts: [beach] })
  }
  // «что рядом»: одна строка-таблица, ближайшее из главного; остальное — по клику
  const near = facts.filter(f => f.characteristic.startsWith('near:') && f.value.meters != null)
    .sort((a, b) => a.value.walk_min - b.value.walk_min)
  if (near.length) {
    const main = near.filter(f => NEAR_MAIN.includes(f.characteristic.slice(5)))
    const line = f => [f.value.kind, f.value.name ? `«${f.value.name}»` : '', `${f.value.walk_min} мин`]
    rows.push({ key: 'near', icon: 'pin', title: 'Что рядом пешком', near: true,
      lines: main.map(line), more: near.filter(f => !main.includes(f)).map(line), facts: near })
  }
  for (const f of facts.filter(f => !['sea_view', 'sunset_view', 'beach_distance'].includes(f.characteristic)
    && !f.characteristic.startsWith('near:'))) {
    rows.push({ key: f.id, icon: 'window', title: f.value?.text || f.characteristic, text: '', facts: [f] })
  }
  return rows
}

function Row({ r }) {
  const [open, setOpen] = useState(false)
  const lines = r.near && open ? [...r.lines, ...r.more] : r.lines
  const c = Math.min(...r.facts.map(f => f.confidence))
  const f0 = r.facts[0]
  // уверенность — не плашкой (занимает место), а фразой в «как узнали» по клику
  const sure = { hi: 'Данные надёжные.', mid: 'Это расчёт: на месте может немного отличаться.', lo: 'Это примерная оценка.' }[sureWord(c)[1]]
  return (
    <div className="fact" onClick={() => setOpen(!open)}>
      <div className="ic"><Icon name={r.icon} /></div>
      <div style={{ flex: 1 }}>
        <div className="t">{r.title}</div>
        {r.text && <div className="s">{r.text}</div>}
        {r.near && <div className="near">{lines.map(([kind, name, time]) =>
          <div key={kind}><span>{kind}{name && <i>{name}</i>}</span><b>{time}</b></div>)}</div>}
        {!r.near && lines && <div className="sides">{lines.map(([side, v]) =>
          <div key={side}><span>{side[0].toUpperCase() + side.slice(1)}</span><b className={v === 'не видно' ? 'no' : ''}>{v}</b></div>)}</div>}
        {r.near && !open && r.more.length > 0 && <div className="more-link">Ещё {r.more.length}</div>}
        {open && <div className="how">{HOW[f0.source] || f0.source} {sure}</div>}
      </div>
    </div>
  )
}

export default function FactList({ facts }) {
  const rows = group(facts)
  if (!rows.length) return null
  return (
    <div className="block">
      <h2>Что важно знать</h2>
      <p className="lead">Этого нет в описании отеля, мы проверили сами.</p>
      {rows.map(r => <Row key={r.key} r={r} />)}
    </div>
  )
}

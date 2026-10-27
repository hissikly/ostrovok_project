import React from 'react'
import { HOW, sureWord } from '@features/facts/frontend/FactList.jsx'
import { SiteQuote } from '@features/web_sources/frontend/SiteQuote.jsx'

const MONTH_IN = ['', 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']
// даты поездки — те же, что в шапке поиска (демо)
export const tripDates = month => month === 5 ? '12–19 мая' : `Неделя в ${MONTH_IN[month]}`
export const NIGHTS = 7

export const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}
export const guestsWord = n => `${n} ${plural(n, 'гость подтвердил', 'гостя подтвердили', 'гостей подтвердили')}`

const SURE = { hi: 'Данные надёжные.', mid: 'Это расчёт: на месте может немного отличаться.', lo: 'Это примерная оценка.' }
const MORE_HOW = {
  'open-meteo': 'Средняя температура воды за последние три года по спутниковым данным.',
}

// «Как мы это узнали» для факта поездки: слова отеля — цитатой, расчёт — как посчитали и насколько уверены.
// guests — ответы «Так и было?» по этому факту: сколько подтвердили, сколько из них демо
export function HowKnown({ facts, guests }) {
  const f0 = facts[0]
  if (f0.source?.startsWith('web:')) return <div className="how">Это слова отеля, мы их не проверяли. На сайте:
    <SiteQuote quote={f0.evidence?.quote} url={f0.evidence?.url} date={f0.evidence?.fetched_at} /></div>
  const c = guests?.confidence ?? Math.min(...facts.map(f => f.confidence ?? 0.5))
  const where = f0.note && f0.level !== 'hotel' ? `${f0.note}. ` : ''
  const said = f0.source === 'hotelier' ? `${f0.note || 'Так ответил отель'}.` : (MORE_HOW[f0.source] || HOW[f0.source] || 'Посчитали по открытым данным.')
  return (
    <div className="how">
      {where}{said} {f0.source === 'hotelier' ? '' : SURE[sureWord(c)[1]]}
      {guests?.guests > 0 && <> После поездки спросили {guests.guests} {plural(guests.guests, 'гостя', 'гостей', 'гостей')}: «так и было» ответили {guests.yes}
        {guests.demo > 0 && <>, {guests.demo === guests.guests ? 'все ответы демо' : `из них демо ${guests.demo}`}</>}.</>}
    </div>
  )
}

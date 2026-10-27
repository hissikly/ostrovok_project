import React from 'react'
import Icon from '@app/icons.jsx'
import { MAX, useCompare } from './store.js'
import './compare.css'

// «Сравнить» у отеля в выдаче и в карточке: кладёт в корзинку внизу экрана (до четырёх)
export default function CompareButton({ id }) {
  const { ids, toggle } = useCompare()
  const on = ids.includes(id)
  const full = !on && ids.length >= MAX
  return (
    <button className={`cmp-btn ${on ? 'on' : ''}`} disabled={full} title={full ? `Сравнить можно до ${MAX} отелей` : undefined}
      onClick={e => { e.stopPropagation(); toggle(id) }}>
      <Icon name={on ? 'check' : 'plus'} size={15} />{on ? 'В сравнении' : 'Сравнить'}
    </button>
  )
}

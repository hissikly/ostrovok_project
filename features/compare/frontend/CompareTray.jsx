import React from 'react'
import Icon from '@app/icons.jsx'
import { useCompare } from './store.js'
import './compare.css'

// Корзинка внизу экрана: какие отели выбраны и «Сравнить N»
export default function CompareTray({ hotels, onOpen }) {
  const { ids, remove } = useCompare()
  if (!ids.length) return null
  const name = id => hotels.find(h => h.id === id)?.name || '…'
  return (
    <div className="cmp-tray">
      <div className="cmp-pills">
        {ids.map(id => (
          <span key={id} className="cmp-pill" title={name(id)}>
            <span>{name(id)}</span>
            <button onClick={() => remove(id)} aria-label={`Убрать ${name(id)}`}><Icon name="x" size={14} /></button>
          </span>
        ))}
      </div>
      <button className="cmp-go" disabled={ids.length < 2} onClick={() => onOpen(ids)}>
        {ids.length < 2 ? 'Добавьте ещё отель' : `Сравнить ${ids.length}`}
      </button>
    </div>
  )
}

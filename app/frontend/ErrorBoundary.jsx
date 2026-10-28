import React from 'react'

// Ошибка отрисовки в одном блоке не должна давать белый экран: блок показывает «Временная ошибка»,
// остальное приложение живёт. resetKey сменился (открыли другой отель) — пробуем отрисовать заново.
export default class ErrorBoundary extends React.Component {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  componentDidCatch(error) { console.error('Блок упал:', error) }

  componentDidUpdate(prev) {
    if (this.state.failed && prev.resetKey !== this.props.resetKey) this.setState({ failed: false })
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="temp-error">
        <b>Временная ошибка</b>
        <span>Этот блок не загрузился. Остальное работает</span>
        <button onClick={() => this.setState({ failed: false })}>Попробовать ещё раз</button>
      </div>
    )
  }
}

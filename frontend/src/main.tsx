import { Component, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { SceneStateProvider } from './state/SceneStateProvider'
import './styles.css'

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: string }> {
  state = { error: '' }

  static getDerivedStateFromError(error: Error) {
    return { error: error.message || 'Spatial UI failed' }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('stepin_spatial_ui_error', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <main className="boot-screen error">
          <div className="boot-mark">!</div>
          <h1>3D 工作台暂时无法加载</h1>
          <p>{this.state.error}</p>
          <a className="primary-button" href="/static/foundation.html">返回兼容工作台</a>
        </main>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')!).render(
  <AppErrorBoundary>
    <BrowserRouter basename="/app">
      <SceneStateProvider>
        <App />
      </SceneStateProvider>
    </BrowserRouter>
  </AppErrorBoundary>,
)

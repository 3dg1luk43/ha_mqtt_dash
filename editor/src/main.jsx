import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { followHaTheme } from './utils/haTheme'

// Inside Home Assistant: adopt HA's theme before the first paint
followHaTheme()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

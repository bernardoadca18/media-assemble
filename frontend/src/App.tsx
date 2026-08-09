import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Execucoes from './pages/Execucoes'
import Revisao from './pages/Revisao'
import IdeiasManuais from './pages/IdeiasManuais'
import Gameplay from './pages/Gameplay'
import Nichos from './pages/Nichos'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="execucoes" element={<Execucoes />} />
        <Route path="revisao" element={<Revisao />} />
        <Route path="ideias-manuais" element={<IdeiasManuais />} />
        <Route path="gameplay" element={<Gameplay />} />
        <Route path="nichos" element={<Nichos />} />
      </Route>
    </Routes>
  )
}

export default App

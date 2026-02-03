import './css/App.css';
import {BrowserRouter as Router, Routes, Route} from "react-router-dom";

import HomePage from './pages/HomePage';
import { ProgramProvider } from './contexts/ProgramContext';
import { ThemeProvider } from './contexts/ThemeContext';
import ThemeToggle from './components/ThemeToggle';

function App() {

  return (
    <ThemeProvider>
      <ProgramProvider>
        <div className='app-card'>
          <header className='app-header'>
            <h1>Wahlprogram Bot</h1>
            <ThemeToggle />
          </header>
        </div>
        <main className='main-content'>
          <Routes>
            <Route path='/' element={<HomePage />}/>
          </Routes>
        </main>
      </ProgramProvider>
    </ThemeProvider>
  )
}

export default App;

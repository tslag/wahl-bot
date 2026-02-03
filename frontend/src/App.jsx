import './css/App.css';
import {Routes, Route, Link, useNavigate} from "react-router-dom";

import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import { ProgramProvider } from './contexts/ProgramContext';
import { ThemeProvider } from './contexts/ThemeContext';
import ThemeToggle from './components/ThemeToggle';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

function Header() {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className='app-card'>
      <header className='app-header'>
        <h1>Wahlprogram Bot</h1>
        <div style={{display: 'flex', gap: '0.75rem', alignItems: 'center'}}>
          <ThemeToggle />
          {isAuthenticated ? (
            <button onClick={async () => { await logout(); navigate('/login'); }}>Logout</button>
          ) : (
            <Link to="/login">Login</Link>
          )}
        </div>
      </header>
    </div>
  );
}

function App() {
  return (
      <ThemeProvider>
        <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={
                <ProtectedRoute>
                  <ProgramProvider>
                    <Header />
                    <main className='main-content'>
                      <HomePage />
                    </main>
                  </ProgramProvider>
                </ProtectedRoute>
              } />
            </Routes>
        </AuthProvider>
      </ThemeProvider>
  );
}

export default App;

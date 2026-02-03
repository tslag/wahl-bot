import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import '../css/LoginPage.css';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError('Login failed. Check credentials.');
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h2>Sign in</h2>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
        </label>
        {error && <div className="login-error">{error}</div>}
        <div className="login-actions">
          <button type="submit">Sign in</button>
        </div>
      </form>
    </div>
  );
};

export default LoginPage;

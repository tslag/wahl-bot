import { createContext, useContext, useState, useEffect } from 'react';
import authService from '../services/authService';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initialize auth state from stored refresh token
    const init = async () => {
      try {
        setLoading(true);
        // Attempt to refresh access token using stored refresh token (if any)
        await authService.refreshAccessToken();
        // If refresh worked, fetch current user
        const resp = await authService.apiRequest('/auth/users/me/');
        if (resp.ok) {
          const data = await resp.json();
          setUser(data);
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
          setUser(null);
        }
      } catch (e) {
        setIsAuthenticated(false);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const login = async (username, password) => {
    try {
      const data = await authService.login(username, password);
      if (data) {
        try {
          const resp = await authService.apiRequest('/auth/users/me/');
          if (resp.ok) {
            const u = await resp.json();
            setUser(u);
          }
        } catch (e) {
          // ignore
        }
        setIsAuthenticated(true);
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  };

  const logout = async () => {
    await authService.logout();
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;

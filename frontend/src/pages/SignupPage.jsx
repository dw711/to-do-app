import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function SignupPage() {
  const { token, signup } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  if (token) return <Navigate to="/board" replace />;

  async function submit(event) {
    event.preventDefault();
    setError('');
    const form = new FormData(event.currentTarget);
    if (form.get('password') !== form.get('confirm_password')) {
      setError("Passwords don't match");
      return;
    }
    try {
      await signup({
        display_name: form.get('display_name'),
        email: form.get('email'),
        password: form.get('password'),
      });
      navigate('/board', { replace: true });
    } catch (err) {
      setError(err.message || 'Unable to create account');
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-form" onSubmit={submit}>
        <h1>Create account</h1>
        <input name="display_name" placeholder="Display name" required />
        <input name="email" type="email" placeholder="Email" required autoComplete="email" />
        <input name="password" type="password" placeholder="Password (8+ characters)" minLength="8" required autoComplete="new-password" />
        <input name="confirm_password" type="password" placeholder="Confirm password" required autoComplete="new-password" />
        {error && <div className="auth-error">{error}</div>}
        <button type="submit">Create account</button>
        <p>Already registered? <Link to="/login">Log in</Link></p>
      </form>
    </main>
  );
}

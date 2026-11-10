import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { Spinner } from './components/ui.jsx'
import { homeFor, useAuth } from './lib/auth.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import WorkerHome from './pages/worker/WorkerHome.jsx'
import Onboarding from './pages/worker/Onboarding.jsx'
import Board from './pages/worker/Board.jsx'
import WorkerJob from './pages/worker/WorkerJob.jsx'
import WorkerBookings from './pages/worker/WorkerBookings.jsx'
import BookingPage from './pages/BookingPage.jsx'
import Find from './pages/customer/Find.jsx'
import WorkerProfilePage from './pages/customer/WorkerProfilePage.jsx'
import NewRequest from './pages/customer/NewRequest.jsx'
import MyRequests from './pages/customer/MyRequests.jsx'
import RequestDetail from './pages/customer/RequestDetail.jsx'

/** Session restore + role gate. The backend still checks every action. */
function RequireRole({ role, children }) {
  const { user } = useAuth()
  const location = useLocation()
  if (user === undefined) return <Spinner />
  if (!user) return <Navigate to={`/login?role=${role}&next=${encodeURIComponent(location.pathname)}`} replace />
  if (user.role !== role) return <Navigate to={homeFor(user)} replace />
  return children
}

export default function App() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route element={<Layout role={null} />}>
        <Route index element={user === undefined ? <Spinner /> : user ? <Navigate to={homeFor(user)} replace /> : <Landing />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
      </Route>
      <Route path="w" element={<RequireRole role="worker"><Layout role="worker" /></RequireRole>}>
        <Route index element={<WorkerHome />} />
        <Route path="onboard" element={<Onboarding />} />
        <Route path="board" element={<Board />} />
        <Route path="jobs/:id" element={<WorkerJob />} />
        <Route path="bookings" element={<WorkerBookings />} />
        <Route path="bookings/:id" element={<BookingPage />} />
      </Route>
      <Route path="c" element={<RequireRole role="customer"><Layout role="customer" /></RequireRole>}>
        <Route index element={<Find />} />
        <Route path="workers/:id" element={<WorkerProfilePage />} />
        <Route path="new" element={<NewRequest />} />
        <Route path="requests" element={<MyRequests />} />
        <Route path="requests/:id" element={<RequestDetail />} />
        <Route path="bookings/:id" element={<BookingPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

import { Navigate, useLocation } from "react-router-dom";

import { isSignedIn } from "../services/auth";


/**
 * Wraps the routes that only make sense for a signed-in account.
 *
 * Without this, opening /dashboard while signed out renders the whole screen and
 * then fails every request on it, which reads as a broken application rather
 * than as "you are not signed in". Sending the visitor to the sign-in page says
 * the true thing.
 *
 * This is a routing convenience, not the security boundary. Every protected
 * endpoint identifies its user from the signed token on the request, so nothing
 * here is what keeps one account's data away from another; hiding a screen in the
 * browser protects nothing on its own. The check is deliberately only for a
 * token being present, because validity is the backend's to judge.
 *
 * Where the visitor was heading is remembered, so signing in continues to the
 * page they asked for instead of dropping them on the dashboard.
 */
function RequireAuth({ children }) {

  const location = useLocation();

  if (!isSignedIn()) {

    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }

  return children;
}


export default RequireAuth;

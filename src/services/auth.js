const API_URL = "http://localhost:8000";

export async function signup(userData) {
  const response = await fetch(
    `${API_URL}/api/auth/signup`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify(userData),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Signup failed");
  }

  return data;
}


export async function signin(userData) {
  const response = await fetch(
    `${API_URL}/api/auth/signin`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify(userData),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Signin failed");
  }

  return data;
}
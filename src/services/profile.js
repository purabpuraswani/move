const API_URL = "http://localhost:8000";


export async function completeProfile(formData) {

  const response = await fetch(
    `${API_URL}/api/profile/complete`,
    {
      method: "POST",
      body: formData,
    }
  );


  const data = await response.json();


  if (!response.ok) {
    throw new Error(
      data.detail || "Failed to save profile"
    );
  }


  return data;
}
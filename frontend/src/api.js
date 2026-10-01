const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchCurrentTopics() {
  const res = await fetch(`${API_URL}/api/topics/current`);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}
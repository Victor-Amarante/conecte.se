const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface LocationPayload {
  latitude: number;
  longitude: number;
  accuracy: number | null;
  timestamp?: number;
}

export async function sendLocation(location: LocationPayload): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/location`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        latitude: location.latitude,
        longitude: location.longitude,
        accuracy: location.accuracy,
        timestamp: location.timestamp,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `HTTP error! status: ${response.status}`
      );
    }
  } catch (error) {
    console.error("Error sending location:", error);
    throw error;
  }
}

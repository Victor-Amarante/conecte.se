import { useEffect, useRef, useState } from "react";

interface GeoLocationData {
  accuracy: number | null;
  latitude: number | null;
  longitude: number | null;
  error: string | null;
}

interface UseGeoLocationReturn {
  data: GeoLocationData;
  isTracking: boolean;
  startTracking: () => void;
  stopTracking: () => void;
  toggleTracking: () => void;
}

export function useGeoLocation(intervalMs: number = 3000): UseGeoLocationReturn {
  const [data, setData] = useState<GeoLocationData>({
    accuracy: null,
    latitude: null,
    longitude: null,
    error: null,
  });

  const [isTracking, setIsTracking] = useState(false);
  const watchIdRef = useRef<number | null>(null);
  const lastUpdateRef = useRef<number>(0);

  const startTracking = () => {
    if (watchIdRef.current !== null) return;

    if (!navigator.geolocation) {
      setData((prev) => ({
        ...prev,
        error: "Geolocation não é suportada por este navegador.",
      }));
      return;
    }

    setIsTracking(true);

    watchIdRef.current = navigator.geolocation.watchPosition(
      (position) => {
        const now = Date.now();
        if (now - lastUpdateRef.current >= intervalMs) {
          lastUpdateRef.current = now;
          const { latitude, longitude, accuracy } = position.coords;
          const data = {
            accuracy,
            latitude,
            longitude,
            timestamp: position.timestamp,
            error: null,
          };
          setData(data);
        }
      },
      (error) => {
        setData((prev) => ({
          ...prev,
          error: "Erro ao obter localização: " + error.message,
        }));
      },
      {
        enableHighAccuracy: true,
        maximumAge: intervalMs,
        timeout: 10000,
      }
    );
  };

  const stopTracking = () => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setIsTracking(false);
  };

  const toggleTracking = () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    isTracking ? stopTracking() : startTracking();
  };

  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, []);

  return {
    data,
    isTracking,
    startTracking,
    stopTracking,
    toggleTracking,
  };
}

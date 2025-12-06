import { useEffect, useState } from "react";

export default function GeoTracker() {
  const [accuracyValue, setAccuracyValue] = useState<number>();
  const [latitudeValue, setLatitudeValue] = useState<number>();
  const [longetudeValue, setLongetudeValue] = useState<number>();

  useEffect(() => {
    if (!navigator.geolocation) {
      throw new Error("Geolocation não é suportada por este navegador.");
    }
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        setAccuracyValue(accuracy);
        setLatitudeValue(latitude);
        setLongetudeValue(longitude);
      },
      (err) => {
        throw new Error("error ao obter localização: " + err.message);
      },
      {
        enableHighAccuracy: true,
        maximumAge: 0,
        timeout: 20000,
      }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  return (
    <div className="mt-4 p-4 border border-amber-300 rounded bg-amber-900/20 ">
      <h2 className="text-xl font-semibold mb-2">GeoTracker</h2>
      <p>Rastreamento de localização ativado. </p>
      <p>{accuracyValue}</p>
      <p>Latitude {latitudeValue}</p>
      <p> longitude {longetudeValue}</p>
    </div>
  );
}

import { useGeoLocation } from "../hooks/useGeoLocation";
import GpsButton from "../components/GpsButton";
import { InfoRow } from "../components/InfoRow";

enum StatusEnum {
  IDLE = "idle",
  TRACKING = "tracking",
  ERROR = "error",
}
export default function TrackerPage() {
  const { data, isTracking, toggleTracking } = useGeoLocation(3000);

  const getStatus = (): StatusEnum => {
    if (data.error) return StatusEnum.ERROR;
    if (isTracking) return StatusEnum.TRACKING;
    return StatusEnum.IDLE;
  };

  const items = [
    {
      key: "accuracy",
      label: "Precisão",
      value: data.accuracy !== null ? `${data.accuracy.toFixed(2)} m` : "—",
    },
    {
      key: "latitude",
      label: "Latitude",
      value: data.latitude !== null ? data.latitude.toFixed(6) : "—",
    },
    {
      key: "longitude",
      label: "Longitude",
      value: data.longitude !== null ? data.longitude.toFixed(6) : "—",
    },
  ];

  return (
    <div className="min-h-dvh bg-linear-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col items-center justify-center p-8">
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.1) 2px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)
          `,
          backgroundSize: "50px 50px",
        }}
      />

      <div className="relative z-10 flex flex-col items-center gap-12">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
            Conecte<span className="text-emerald-400">.se</span>
          </h1>
        </div>

        <GpsButton isActive={isTracking} onClick={toggleTracking} status={getStatus()} />

        <div className="w-full max-w-lg">
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-6 shadow-2xl">
            <div className="grid gap-4 min-w-full">
              {items.map((item) => (
                <InfoRow key={item.key} label={item.label} value={item.value} />
              ))}
              {data.error && (
                <div className="p-3 bg-red-900/20 rounded-lg border border-red-700/30">
                  <p className="text-red-400 text-sm">{data.error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

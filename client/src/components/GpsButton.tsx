import { MapPin } from "lucide-react";
import type { StatusEnum } from "../enums/StatusEnum";

interface GpsButtonProps {
  isActive: boolean;
  onClick: () => void;
  status: "idle" | "tracking" | "error";
}
const getStatusColor: Record<StatusEnum, string> = {
  idle: "text-slate-400",
  tracking: "text-emerald-400",
  error: "text-red-400",
};

const getStatusText: Record<StatusEnum, string> = {
  tracking: "Compartilhando localização...",
  error: "Erro na localização",
  idle: "Clique para iniciar",
};

export default function GpsButton({ isActive, onClick, status }: GpsButtonProps) {
  return (
    <div className="flex flex-col items-center gap-6">
      <div className="relative">
        {isActive && (
          <>
            <div
              className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping"
              style={{ animationDuration: "2s" }}
            />
            <div
              className="absolute -inset-4 rounded-full bg-emerald-500/10 animate-ping"
              style={{ animationDuration: "2.5s", animationDelay: "0.5s" }}
            />
            <div
              className="absolute -inset-8 rounded-full bg-emerald-500/5 animate-ping"
              style={{ animationDuration: "3s", animationDelay: "1s" }}
            />
          </>
        )}

        <div
          className={`absolute -inset-1 rounded-full transition-all duration-500 ${
            isActive
              ? "bg-linear-to-r from-emerald-500 via-cyan-500 to-emerald-500 opacity-75 blur-sm animate-spin"
              : "bg-linear-to-r from-slate-600 via-slate-500 to-slate-600 opacity-50 blur-sm"
          }`}
          style={{ animationDuration: "3s" }}
        />

        <div
          className={`relative rounded-full p-1 transition-all duration-300 ${
            isActive
              ? "bg-linear-to-br from-emerald-400 via-cyan-500 to-emerald-600"
              : "bg-linear-to-br from-slate-500 via-slate-600 to-slate-700"
          }`}
        >
          <button
            onClick={onClick}
            className={`
              relative w-32 h-32 rounded-full
              flex items-center justify-center
              transition-all duration-200 ease-out
              focus:outline-none focus:ring-4
              ${
                isActive
                  ? "bg-linear-to-br from-slate-800 via-slate-900 to-black focus:ring-emerald-500/50"
                  : "bg-linear-to-br from-slate-700 via-slate-800 to-slate-900 focus:ring-slate-500/50"
              }
            `}
          >
            <div
              className={`relative z-10 transition-all duration-300 ${
                isActive ? "text-emerald-400" : "text-slate-400"
              }`}
            >
              <MapPin size={50} />
            </div>

            <div
              className="absolute inset-0 rounded-full bg-linear-to-b from-white/10 to-transparent pointer-events-none"
              style={{ clipPath: "ellipse(50% 30% at 50% 20%)" }}
            />
          </button>
        </div>

        {isActive && <div className="absolute -inset-4 rounded-full bg-emerald-500/20 blur-xl -z-10 animate-pulse" />}
      </div>

      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full transition-all duration-300 ${
              isActive
                ? "bg-emerald-400 shadow-lg shadow-emerald-500/50 animate-pulse"
                : status === "error"
                ? "bg-red-400 shadow-lg shadow-red-500/50"
                : "bg-slate-600"
            }`}
          />
          <span className={`text-sm font-medium uppercase tracking-wider ${getStatusColor[status]}`}>
            {isActive ? "ATIVO" : status === "error" ? "ERRO" : "INATIVO"}
          </span>
        </div>

        <p className={`text-sm ${getStatusColor[status]} transition-colors duration-300`}>{getStatusText[status]}</p>
      </div>
    </div>
  );
}

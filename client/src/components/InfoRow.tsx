type RowProps = { label: string; value: string | number };

export const InfoRow = ({ label, value }: RowProps) => (
  <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-700/30 gap-4">
    <span className="text-slate-400 text-sm">{label}</span>
    <span className="font-mono text-white">{value}</span>
  </div>
);

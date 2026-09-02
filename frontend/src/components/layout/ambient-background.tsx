export function AmbientBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <div className="absolute -left-24 top-[-8%] h-[480px] w-[480px] animate-float rounded-full bg-emerald-600/20 blur-[120px]" />
      <div className="absolute right-[-8%] top-[15%] h-[400px] w-[400px] animate-float-delayed rounded-full bg-green-500/15 blur-[100px]" />
      <div className="absolute bottom-[-12%] left-[25%] h-[440px] w-[440px] rounded-full bg-emerald-700/15 blur-[110px]" />
      <div className="absolute left-[45%] top-[55%] h-[280px] w-[280px] rounded-full bg-green-400/8 blur-[80px]" />
    </div>
  );
}

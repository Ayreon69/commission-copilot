import { formatDate, formatMonth } from "@/lib/format";

type ContractTimelineProps = {
  subscriptionDate: string;
  effectiveDate: string;
  endDate: string;
  month: string;
};

const DAY = 86_400_000;

function toTime(iso: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const [year, month, day] = iso.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

/** Frise du contrat : souscription, période couverte et mois de calcul, à l'échelle. */
export function ContractTimeline({ subscriptionDate, effectiveDate, endDate, month }: ContractTimelineProps) {
  const subscription = toTime(subscriptionDate);
  const effective = toTime(effectiveDate);
  const end = toTime(endDate);
  const monthStart = /^\d{4}-\d{2}$/.test(month) ? toTime(`${month}-01`) : null;
  if (subscription === null || effective === null || monthStart === null) return null;

  const monthDate = new Date(monthStart);
  const monthEnd = Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() + 1, 0);
  const anniversary = Date.UTC(new Date(effective).getUTCFullYear() + 1, new Date(effective).getUTCMonth(), new Date(effective).getUTCDate());
  const start = Math.min(subscription, effective) - 12 * DAY;
  const finish = Math.max(end ?? 0, monthEnd, anniversary) + 12 * DAY;
  const position = (time: number) => `${((time - start) / (finish - start)) * 100}%`;
  const coveredEnd = end ?? monthEnd;

  const markers = [
    { time: subscription, label: "Souscription", date: subscriptionDate, below: false },
    { time: effective, label: "Effet", date: effectiveDate, below: true },
    { time: anniversary, label: "1 an", date: null, below: false },
    ...(end !== null ? [{ time: end, label: "Fin", date: endDate, below: true }] : []),
  ];

  return (
    <figure className="mt-2" aria-label="Frise du contrat">
      <div className="relative h-24">
        <div className="absolute top-1/2 right-0 left-0 h-px bg-ink/40" />
        <div
          className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-green/70 transition-all duration-500"
          style={{ left: position(effective), width: `calc(${position(Math.max(coveredEnd, effective))} - ${position(effective)})` }}
          title="Période couverte"
        />
        <div
          className="absolute top-[18%] bottom-[18%] border-x border-dashed border-vermilion bg-vermilion-soft/60"
          style={{ left: position(monthStart), width: `calc(${position(monthEnd)} - ${position(monthStart)})` }}
          title={`Mois de calcul : ${formatMonth(month)}`}
        />
        {markers.map((marker) => (
          <div
            key={marker.label}
            className="absolute top-1/2 -translate-x-1/2 transition-all duration-500"
            style={{ left: position(marker.time) }}
          >
            <span className="absolute left-1/2 block h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-card" />
            <span
              className={`absolute left-1/2 -translate-x-1/2 text-center font-mono text-[10px] leading-tight whitespace-nowrap text-ink-soft ${
                marker.below ? "top-3" : "bottom-3"
              }`}
            >
              {marker.label}
              {marker.date && <span className="block text-ink-faint">{formatDate(marker.date)}</span>}
            </span>
          </div>
        ))}
      </div>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10.5px] text-ink-faint">
        <span>
          <span className="mr-1 inline-block h-2 w-4 rounded-full bg-green/70 align-middle" />
          période couverte
        </span>
        <span>
          <span className="mr-1 inline-block h-2.5 w-3 border-x border-dashed border-vermilion bg-vermilion-soft align-middle" />
          mois de calcul ({formatMonth(month)})
        </span>
      </figcaption>
    </figure>
  );
}

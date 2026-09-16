import type { ReactNode } from "react";

type StampProps = {
  tone: "green" | "vermilion" | "ochre";
  children: ReactNode;
  title?: string;
  delay?: number;
};

const TONES = {
  green: "border-green text-green bg-green-soft/60",
  vermilion: "border-vermilion text-vermilion bg-vermilion-soft/60",
  ochre: "border-ochre text-ochre bg-ochre-soft/60",
};

/** Tampon encré, pour les règles vérifiées et les alertes. */
export function Stamp({ tone, children, title, delay = 0 }: StampProps) {
  return (
    <span
      title={title}
      style={{ animationDelay: `${delay}ms` }}
      className={`stamp inline-flex items-center gap-1.5 rounded-[3px] border-[1.5px] border-double px-2 py-0.5 font-mono text-[10.5px] font-semibold tracking-[0.08em] uppercase ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

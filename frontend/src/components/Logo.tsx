import logoMark from "@/assets/logo-mark.png";
import { S } from "@/lib/strings";
import { cn } from "@/lib/utils";

/** Full brand: symbol (PNG) + "Centinela" wordmark as HTML text in Fraunces semibold, forest green. */
export function Logo({ size = "sm", className }: { size?: "sm" | "lg"; className?: string }) {
  const lg = size === "lg";
  return (
    <span className={cn("inline-flex items-center", lg ? "gap-4" : "gap-2", className)}>
      <img src={logoMark} alt={S.logoAlt} className={lg ? "size-20" : "size-8"} width={lg ? 80 : 32} height={lg ? 80 : 32} />
      <span
        className={cn("font-display font-semibold tracking-tight text-forest", lg ? "text-5xl" : "text-xl")}
        style={{ fontVariationSettings: '"opsz" 72' }}
      >
        {S.brand}
      </span>
    </span>
  );
}

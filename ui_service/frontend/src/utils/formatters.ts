export function formatNumber(value: number, fractionDigits: number = 2): string {
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function formatPrice(
  price: number | null | undefined,
  currencySymbol: string = "$",
): string {
  if (price === null || price === undefined || Number.isNaN(Number(price))) {
    return "—";
  }
  return `${currencySymbol}${formatNumber(Number(price))}`;
}

export function formatChange(change: number | null | undefined): string {
  if (change === null || change === undefined || Number.isNaN(Number(change))) {
    return "—";
  }
  const value: number = Number(change);
  const sign: string = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value)}`;
}

export function formatPercentChange(
  percentChange: number | null | undefined,
): string {
  if (
    percentChange === null ||
    percentChange === undefined ||
    Number.isNaN(Number(percentChange))
  ) {
    return "—";
  }
  const value: number = Number(percentChange);
  const sign: string = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value)}%`;
}

export function formatCompactNumber(
  value: number | null | undefined,
  currencySymbol: string = "",
): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const amount: number = Number(value);
  const abs: number = Math.abs(amount);
  const sign: string = amount < 0 ? "-" : "";
  const tiers: Array<{ limit: number; suffix: string }> = [
    { limit: 1_000_000_000_000, suffix: "T" },
    { limit: 1_000_000_000, suffix: "B" },
    { limit: 1_000_000, suffix: "M" },
    { limit: 1_000, suffix: "K" },
  ];
  for (const tier of tiers) {
    if (abs >= tier.limit) {
      const scaled: number = abs / tier.limit;
      const digits: number = scaled >= 100 ? 0 : 1;
      return `${sign}${currencySymbol}${scaled.toFixed(digits)}${tier.suffix}`;
    }
  }
  return `${sign}${currencySymbol}${formatNumber(abs, abs >= 100 ? 0 : 2)}`;
}

export function formatVolume(volume: number | null | undefined): string {
  return formatCompactNumber(volume);
}

export function changeClassName(change: number | null | undefined): string {
  if (change === null || change === undefined || Number.isNaN(Number(change)) || change === 0) {
    return "change-neutral";
  }
  return change > 0 ? "change-up" : "change-down";
}

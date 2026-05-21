export function textOrFallback(value: string | null | undefined, fallback: string) {
  const text = value?.trim() ?? "";
  return text || fallback;
}

export function explicitTextOrError(value: string | null | undefined, label: string) {
  if (value === null || value === undefined) {
    return undefined;
  }
  const text = value.trim();
  if (!text) {
    throw new Error(`${label} cannot be blank`);
  }
  return text;
}

export function normalizeStringList(items: string[] | undefined) {
  return (items ?? []).map((item) => item.trim()).filter(Boolean);
}

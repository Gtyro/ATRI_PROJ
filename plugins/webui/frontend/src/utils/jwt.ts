interface JwtPayload {
  exp?: number;
  [key: string]: unknown;
}

function base64UrlDecode(input: string): string {
  if (!input) {
    return "";
  }
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "===".slice((normalized.length + 3) % 4);
  try {
    return atob(padded);
  } catch (_error) {
    return "";
  }
}

export function decodeJwt(token: string): JwtPayload | null {
  if (!token || typeof token !== "string") {
    return null;
  }
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  const payloadSegment = parts[1];
  if (!payloadSegment) {
    return null;
  }

  try {
    const json = base64UrlDecode(payloadSegment);
    if (!json) {
      return null;
    }
    const payload = JSON.parse(json);
    return payload && typeof payload === "object"
      ? (payload as JwtPayload)
      : null;
  } catch (_error) {
    return null;
  }
}

export function isTokenExpired(token: string, skewSeconds = 30): boolean {
  const payload = decodeJwt(token);
  if (!payload || typeof payload.exp !== "number") {
    return true;
  }
  const now = Math.floor(Date.now() / 1000);
  return payload.exp <= now + skewSeconds;
}

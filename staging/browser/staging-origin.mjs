const originError = 'Set RMS_STAGING_ORIGIN to the approved https://host:port without credentials, path, query, or fragment';
const originPattern = /^https:\/\/(?:\[[0-9a-fA-F:.]+\]|[A-Za-z0-9.-]+):([0-9]{1,5})$/;

export function stagingTarget(origin) {
  const match = typeof origin === 'string' && originPattern.exec(origin);
  if (!match || Number(match[1]) < 1 || Number(match[1]) > 65535) {
    throw new Error(originError);
  }
  let parsed;
  try {
    parsed = new URL(origin);
  } catch {
    throw new Error(originError);
  }
  if (!parsed.hostname || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new Error(originError);
  }
  return `${origin}/`;
}

export function sameOriginRequest(requestUrl, origin) {
  return new URL(requestUrl).origin === new URL(origin).origin;
}

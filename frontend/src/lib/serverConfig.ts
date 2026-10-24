/**
 * Next 서버(BFF)만 읽는 환경변수. 브라우저 번들에 들어가면 안 되므로 `lib/bff.ts`에서만 씁니다.
 */
const LOCAL_BACKEND_URL = 'http://localhost:8000';

export const serverConfig = {
  backendBaseUrl: () => process.env.API_BASE_URL ?? LOCAL_BACKEND_URL,
  internalSecret: () => process.env.BACKEND_INTERNAL_SECRET ?? '',
  /** 운영(https)에서만 쿠키에 Secure를 붙입니다. 로컬 http에서는 붙이면 쿠키가 저장되지 않습니다. */
  secureCookie: () => process.env.NODE_ENV === 'production',
};

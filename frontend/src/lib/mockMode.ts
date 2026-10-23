/**
 * 요청을 실제 백엔드로 보낼지, 모의 응답(src/mocks)으로 돌릴지 정합니다.
 * 백엔드 기능을 구현하면 BACKEND_ROUTES에 경로를 더하고 그 mock을 지웁니다.
 */

/**
 * 모의 응답 모드 (`NEXT_PUBLIC_USE_MOCK`).
 * - `1`: 전부 `src/mocks/` 스냅샷 (백엔드 없이 화면만 볼 때)
 * - `0`: 전부 실제 백엔드
 * - 그 밖(비움·`hybrid`): 아래 `BACKEND_ROUTES`만 실제 백엔드, 나머지는 mock
 */
const MOCK_MODE = process.env.NEXT_PUBLIC_USE_MOCK ?? '';
export const IS_MOCK_API = MOCK_MODE === '1';
const IS_REAL_ONLY = MOCK_MODE === '0';

/**
 * 백엔드에 구현된 경로(BFF `/api` 뒤 경로, 쿼리 제외).
 * 계정 입장 이후 mock은 저장된 세션의 persona_id로 이어서 응답합니다.
 */
// 화면 데이터가 mock인지 확인할 때 쓰는 가짜 경로(백엔드에 없음)
const SCREENS_MOCK_PROBE = '/screens';

const BACKEND_ROUTES: RegExp[] = [
  /^\/health$/,
  /^\/personas$/,
  /^\/accounts\/[^/]+$/,
  /^\/accounts\/[^/]+\/messages$/,
  /^\/accounts\/[^/]+\/resume$/,
  /^\/accounts\/[^/]+\/rounds\/current(\/recommendations)?$/,
  /^\/accounts\/[^/]+\/activities(\/[^/]+)?$/,
  /^\/accounts\/[^/]+\/facts(\/[^/]+)?$/,
];

/**
 * 로그인 이후 화면(이력서·회차·신청서 패널)이 아직 mock 대본을 쓰는지.
 * 화면 데이터 API가 백엔드로 옮겨지면 false가 됩니다.
 */
export const usesMockScreens = (): boolean => usesMock(SCREENS_MOCK_PROBE);

/** 이 경로를 mock으로 돌릴지. 혼합 모드에서는 `BACKEND_ROUTES`에 없는 경로만 mock입니다. */
export const usesMock = (path: string): boolean => {
  if (IS_MOCK_API) return true;
  if (IS_REAL_ONLY) return false;
  const pathname = path.split('?')[0];
  return !BACKEND_ROUTES.some((route) => route.test(pathname));
};

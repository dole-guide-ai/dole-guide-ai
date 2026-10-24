/** 화면 테마(밝게·어둡게). 고른 값만 브라우저에 기억하고, 고른 적이 없으면 기기 설정을 따릅니다. */
export const THEME = { LIGHT: 'light', DARK: 'dark' } as const;
export type Theme = (typeof THEME)[keyof typeof THEME];

export const THEME_STORAGE_KEY = 'dole.theme';

/**
 * 첫 그림 전에 <html data-theme>을 정하는 스크립트 (깜빡임 방지). layout의 <head>에 그대로 넣습니다.
 * 저장이 막힌 브라우저에서도 기기 설정으로 정해집니다.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');}catch(e){}if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.dataset.theme=t;})();`;

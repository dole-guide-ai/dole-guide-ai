import type { ErrorEvent } from '@/types/chat.types';

/** 오류 코드별 화면 문구 (2-0.10). `restoresInput`이면 보낸 글을 입력창에 되돌립니다. */
export const describeChatError = (error: Pick<ErrorEvent, 'code'>) => {
  switch (error.code) {
    case 'LLM_UNAVAILABLE':
      return { text: '지금 답을 만들기 어려워요. 잠시 후 다시 보내 주세요.', restoresInput: true };
    case 'RATE_LIMITED':
      return { text: '잠시 쉬었다가 다시 보내 주세요.', restoresInput: true };
    default:
      return { text: '처리 중 문제가 생겼어요. 패널 값은 바꾸지 않았어요.', restoresInput: false };
  }
};

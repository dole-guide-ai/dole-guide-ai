import { ERROR_CODES } from '@/lib/errorCodes';
import type { ErrorEvent } from '@/types/chat.types';

/**
 * 오류 코드별 화면 문구 (2-0.10). `restoresInput`이면 보낸 글을 입력창에 되돌립니다.
 * 턴 도중 `error` 이벤트와 턴 시작 전 HTTP 오류(ApiError.code)를 같은 표로 바꿉니다.
 */
export const describeChatError = (error: Pick<ErrorEvent, 'code'>) => {
  switch (error.code) {
    case ERROR_CODES.LLM_UNAVAILABLE:
      return { text: '지금 답을 만들기 어려워요. 잠시 후 다시 보내 주세요.', restoresInput: true };
    case ERROR_CODES.RATE_LIMITED:
      return { text: '잠시 쉬었다가 다시 보내 주세요.', restoresInput: true };
    case ERROR_CODES.TIMEOUT:
      return { text: '답이 너무 오래 걸려 멈췄어요. 다시 보내 주세요.', restoresInput: true };
    case ERROR_CODES.TURN_IN_PROGRESS:
      return {
        text: '앞의 답을 만드는 중이에요. 답이 끝난 뒤 다시 보내 주세요.',
        restoresInput: true,
      };
    case ERROR_CODES.CONFLICT:
      // 같은 전송이 두 번 갔을 때(Idempotency-Key). 처음 보낸 것은 이미 처리됐습니다.
      return {
        text: '이미 보낸 메시지예요. 새로고침하면 답을 볼 수 있어요.',
        restoresInput: false,
      };
    case ERROR_CODES.NETWORK_ERROR:
      return { text: '인터넷 연결을 확인하고 다시 보내 주세요.', restoresInput: true };
    default:
      return { text: '처리 중 문제가 생겼어요. 패널 값은 바꾸지 않았어요.', restoresInput: false };
  }
};

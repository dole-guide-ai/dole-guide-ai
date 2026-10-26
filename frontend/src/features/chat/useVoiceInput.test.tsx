import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useVoiceInput, VOICE_ERRORS, VOICE_STATUS } from '@/features/chat/useVoiceInput';

import { mockFetchJson } from '@/test/mockFetch';

/** 브라우저 녹음기 대신: start 뒤 stop하면 녹음 조각 하나를 내고 onstop을 부릅니다. */
class FakeRecorder {
  static last: FakeRecorder | null = null;
  state: 'inactive' | 'recording' = 'inactive';
  mimeType = 'audio/webm';
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor(public stream: MediaStream) {
    FakeRecorder.last = this;
  }
  start() {
    this.state = 'recording';
  }
  stop() {
    this.state = 'inactive';
    this.ondataavailable?.({ data: new Blob(['소리'], { type: this.mimeType }) });
    this.onstop?.();
  }
}

const stopTrack = vi.fn();
const fakeStream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;

const setMicrophone = (getUserMedia: () => Promise<MediaStream>) =>
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia },
    configurable: true,
  });

describe('useVoiceInput', () => {
  beforeEach(() => {
    vi.stubGlobal('MediaRecorder', FakeRecorder);
    setMicrophone(() => Promise.resolve(fakeStream));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    stopTrack.mockClear();
  });

  it('누르면 녹음하고, 다시 누르면 받아쓴 글을 넘기고 마이크를 놓는다', async () => {
    const fetchSpy = mockFetchJson({ text: ' 어제 지원했어요 ' });
    const onText = vi.fn();
    const { result } = renderHook(() => useVoiceInput('lee', onText));

    await act(async () => result.current.toggle());
    expect(result.current.status).toBe(VOICE_STATUS.RECORDING);

    act(() => result.current.toggle());

    await waitFor(() => expect(onText).toHaveBeenCalledWith('어제 지원했어요'));
    expect(result.current.status).toBe(VOICE_STATUS.IDLE);
    expect(stopTrack).toHaveBeenCalled();
    expect(String(fetchSpy.mock.calls[0][0])).toContain('/accounts/lee/transcriptions');
  });

  it('마이크를 허용하지 않으면 안내하고 녹음하지 않는다', async () => {
    setMicrophone(() => Promise.reject(new Error('denied')));
    const { result } = renderHook(() => useVoiceInput('lee', vi.fn()));

    await act(async () => result.current.toggle());

    expect(result.current.error).toBe(VOICE_ERRORS.DENIED);
    expect(result.current.status).toBe(VOICE_STATUS.IDLE);
  });

  it('받아쓰기가 실패하면 안내하고 대기로 돌아간다', async () => {
    mockFetchJson(
      { code: 'LLM_UNAVAILABLE', message: '잠시 후 다시', details: null },
      { status: 503 },
    );
    const onText = vi.fn();
    const { result } = renderHook(() => useVoiceInput('lee', onText));

    await act(async () => result.current.toggle());
    act(() => result.current.toggle());

    await waitFor(() => expect(result.current.error).toBe(VOICE_ERRORS.FAILED));
    expect(result.current.status).toBe(VOICE_STATUS.IDLE);
    expect(onText).not.toHaveBeenCalled();
  });

  it('녹음을 지원하지 않는 브라우저는 안내만 한다', async () => {
    vi.stubGlobal('MediaRecorder', undefined);
    const { result } = renderHook(() => useVoiceInput('lee', vi.fn()));

    await act(async () => result.current.toggle());

    expect(result.current.error).toBe(VOICE_ERRORS.UNSUPPORTED);
  });
});

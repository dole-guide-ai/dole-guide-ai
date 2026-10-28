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

  it('서버가 거절하면 서버 안내 문구를 보여 주고 대기로 돌아간다', async () => {
    mockFetchJson(
      { code: 'LLM_UNAVAILABLE', message: '잠시 후 다시 시도해 주세요.', details: null },
      { status: 503 },
    );
    const onText = vi.fn();
    const { result } = renderHook(() => useVoiceInput('lee', onText));

    await act(async () => result.current.toggle());
    act(() => result.current.toggle());

    await waitFor(() => expect(result.current.error).toBe('잠시 후 다시 시도해 주세요.'));
    expect(result.current.status).toBe(VOICE_STATUS.IDLE);
    expect(onText).not.toHaveBeenCalled();
  });

  it('서버 응답이 아닌 실패는 일반 안내를 보여 준다', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('끊김'));
    const { result } = renderHook(() => useVoiceInput('lee', vi.fn()));

    await act(async () => result.current.toggle());
    act(() => result.current.toggle());

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.status).toBe(VOICE_STATUS.IDLE);
  });

  it('권한을 묻는 동안 다시 눌러도 녹음은 하나만 시작한다', async () => {
    let grant: (stream: MediaStream) => void = () => {};
    const getUserMedia = vi.fn(() => new Promise<MediaStream>((resolve) => (grant = resolve)));
    setMicrophone(getUserMedia);
    const { result } = renderHook(() => useVoiceInput('lee', vi.fn()));

    act(() => result.current.toggle());
    act(() => result.current.toggle());
    await act(async () => grant(fakeStream));

    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe(VOICE_STATUS.RECORDING);
  });

  it('녹음 중에 화면을 떠나면 마이크를 놓고 녹음을 올리지 않는다', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const { result, unmount } = renderHook(() => useVoiceInput('lee', vi.fn()));

    await act(async () => result.current.toggle());
    unmount();

    expect(stopTrack).toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('녹음을 지원하지 않는 브라우저는 안내만 한다', async () => {
    vi.stubGlobal('MediaRecorder', undefined);
    const { result } = renderHook(() => useVoiceInput('lee', vi.fn()));

    await act(async () => result.current.toggle());

    expect(result.current.error).toBe(VOICE_ERRORS.UNSUPPORTED);
  });
});

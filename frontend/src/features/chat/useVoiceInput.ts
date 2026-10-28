import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, apiUpload } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import type { components } from '@/types/api.gen';

type TranscriptionRead = components['schemas']['TranscriptionRead'];

/** 말하기 상태: 대기 → 녹음 중 → 받아쓰는 중 → 대기 */
export const VOICE_STATUS = {
  IDLE: 'idle',
  RECORDING: 'recording',
  TRANSCRIBING: 'transcribing',
} as const;
export type VoiceStatus = (typeof VOICE_STATUS)[keyof typeof VOICE_STATUS];

/** 한 번에 녹음하는 최대 시간. 넘으면 저절로 멈추고 받아씁니다. */
export const MAX_RECORDING_MS = 60_000;

export const VOICE_ERRORS = {
  UNSUPPORTED: '이 브라우저에서는 말하기를 쓸 수 없어요. 글로 적어 주세요.',
  DENIED: '마이크를 쓸 수 없어요. 브라우저에서 마이크 사용을 허용해 주세요.',
  EMPTY: '잘 듣지 못했어요. 조금 더 크게 다시 말씀해 주세요.',
  FAILED: '말을 글로 바꾸지 못했어요. 다시 눌러 말씀하시거나 글로 적어 주세요.',
} as const;

const isSupported = () =>
  typeof window !== 'undefined' &&
  typeof window.MediaRecorder !== 'undefined' &&
  !!navigator.mediaDevices?.getUserMedia;

/**
 * 말하기 버튼 (2-0.5). 누르면 녹음하고, 다시 누르면 `POST /accounts/{id}/transcriptions`로
 * 받아쓴 글을 `onText`로 넘깁니다. 바로 보내지 않고 입력창에 넣어 사용자가 고친 뒤 보냅니다.
 * 녹음은 서버에 저장되지 않습니다.
 */
export const useVoiceInput = (personaId: string, onText: (text: string) => void) => {
  const [status, setStatus] = useState<VoiceStatus>(VOICE_STATUS.IDLE);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTextRef = useRef(onText);
  // 마이크 권한을 묻는 동안(아직 녹음 전) 다시 눌러 녹음이 둘 생기지 않게 막습니다.
  const isStartingRef = useRef(false);
  // 화면을 떠난 뒤에는 녹음을 올리지 않고 상태도 바꾸지 않습니다.
  const isMountedRef = useRef(true);
  const uploadRef = useRef<AbortController | null>(null);

  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);

  const transcribe = useCallback(
    async (blob: Blob) => {
      setStatus(VOICE_STATUS.TRANSCRIBING);
      const controller = new AbortController();
      uploadRef.current = controller;
      try {
        const file = new File([blob], 'voice', { type: blob.type });
        const { text } = await apiUpload<TranscriptionRead>(
          API_PATHS.transcriptions(personaId),
          file,
          {},
          controller.signal,
        );
        if (!isMountedRef.current) return;
        if (text.trim()) onTextRef.current(text.trim());
        else setError(VOICE_ERRORS.EMPTY);
      } catch (error) {
        if (isMountedRef.current) {
          setError(error instanceof ApiError ? error.message : VOICE_ERRORS.FAILED);
        }
      } finally {
        uploadRef.current = null;
        if (isMountedRef.current) setStatus(VOICE_STATUS.IDLE);
      }
    },
    [personaId],
  );

  const stop = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
  }, []);

  const start = useCallback(async () => {
    if (isStartingRef.current || recorderRef.current) return;
    setError(null);
    if (!isSupported()) {
      setError(VOICE_ERRORS.UNSUPPORTED);
      return;
    }
    isStartingRef.current = true;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      if (isMountedRef.current) setError(VOICE_ERRORS.DENIED);
      return;
    } finally {
      isStartingRef.current = false;
    }
    if (!isMountedRef.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    const recorder = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      if (!isMountedRef.current) return;
      const blob = new Blob(chunks, { type: recorder.mimeType });
      if (blob.size > 0) void transcribe(blob);
      else {
        setError(VOICE_ERRORS.EMPTY);
        setStatus(VOICE_STATUS.IDLE);
      }
    };
    recorderRef.current = recorder;
    recorder.start();
    setStatus(VOICE_STATUS.RECORDING);
    timerRef.current = setTimeout(stop, MAX_RECORDING_MS);
  }, [stop, transcribe]);

  const toggle = useCallback(() => {
    if (status === VOICE_STATUS.RECORDING) stop();
    else if (status === VOICE_STATUS.IDLE) void start();
  }, [start, status, stop]);

  // 화면을 떠나면 마이크를 놓고, 녹음은 올리지 않으며 올리는 중이면 취소합니다.
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
      uploadRef.current?.abort();
    };
  }, []);

  return { status, error, toggle };
};

import { useCallback, useEffect, useRef, useState } from "react";

export type PlaybackResult = "ended" | "stopped";

type ActivePlayback = {
  id: number;
  resolve: (result: PlaybackResult) => void;
};

export function useSpeechPlayer() {
  const [level, setLevel] = useState(0);
  const [playing, setPlaying] = useState(false);
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const frameRef = useRef<number | null>(null);
  const playbackIdRef = useRef(0);
  const activePlaybackRef = useRef<ActivePlayback | null>(null);
  const disposedRef = useRef(false);

  const getContext = useCallback(() => {
    const current = contextRef.current;
    if (current && current.state !== "closed") return current;
    const next = new AudioContext();
    contextRef.current = next;
    return next;
  }, []);

  const releasePlayback = useCallback(
    (result: PlaybackResult, stopSource: boolean) => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }

      const source = sourceRef.current;
      sourceRef.current = null;
      if (source) {
        source.onended = null;
        if (stopSource) {
          try {
            source.stop();
          } catch {
            // A source that has already ended cannot be stopped twice.
          }
        }
        source.disconnect();
      }

      analyserRef.current?.disconnect();
      analyserRef.current = null;

      const active = activePlaybackRef.current;
      activePlaybackRef.current = null;
      active?.resolve(result);

      if (!disposedRef.current) {
        setLevel(0);
        setPlaying(false);
      }
    },
    [],
  );

  const stop = useCallback(() => {
    playbackIdRef.current += 1;
    releasePlayback("stopped", true);
  }, [releasePlayback]);

  const prepare = useCallback(() => {
    try {
      const context = getContext();
      // This is called directly from a click/submit gesture so a later verified
      // answer may start without being rejected by the autoplay policy.
      void context.resume().catch(() => {
        // play() retries and reports an actionable failure to the caller.
      });
    } catch {
      // Some browsers require a stronger gesture; play() will try once more.
    }
  }, [getContext]);

  const play = useCallback(
    async (blob: Blob): Promise<PlaybackResult> => {
      if (!blob.size) throw new Error("语音数据为空");

      const playbackId = playbackIdRef.current + 1;
      playbackIdRef.current = playbackId;
      releasePlayback("stopped", true);

      const context = getContext();
      await context.resume();
      const buffer = await context.decodeAudioData(await blob.arrayBuffer());

      if (disposedRef.current || playbackIdRef.current !== playbackId) {
        return "stopped";
      }

      const source = context.createBufferSource();
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.62;
      source.buffer = buffer;
      source.connect(analyser);
      analyser.connect(context.destination);
      sourceRef.current = source;
      analyserRef.current = analyser;

      const samples = new Uint8Array(analyser.frequencyBinCount);
      const update = () => {
        if (playbackIdRef.current !== playbackId || disposedRef.current) return;
        analyser.getByteFrequencyData(samples);
        let total = 0;
        for (let index = 2; index < 42; index += 1) total += samples[index];
        const average = total / 40;
        setLevel(Math.min(1, Math.max(0, (average - 9) / 70)));
        frameRef.current = requestAnimationFrame(update);
      };

      const completion = new Promise<PlaybackResult>((resolve) => {
        activePlaybackRef.current = { id: playbackId, resolve };
        source.onended = () => {
          if (activePlaybackRef.current?.id === playbackId) {
            releasePlayback("ended", false);
          } else {
            resolve("stopped");
          }
        };
      });

      try {
        setPlaying(true);
        source.start();
        update();
      } catch (cause) {
        releasePlayback("stopped", false);
        throw cause;
      }
      return completion;
    },
    [getContext, releasePlayback],
  );

  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      playbackIdRef.current += 1;
      releasePlayback("stopped", true);
      const context = contextRef.current;
      contextRef.current = null;
      if (context && context.state !== "closed") void context.close().catch(() => undefined);
    };
  }, [releasePlayback]);

  return { level, playing, play, prepare, stop };
}

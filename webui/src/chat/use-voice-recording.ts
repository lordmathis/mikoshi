import { useState, useRef, useCallback } from 'react';

export interface VoiceRecordingState {
  isRecording: boolean;
  isProcessing: boolean;
  error: string | null;
}

export function useVoiceRecording() {
  const [state, setState] = useState<VoiceRecordingState>({
    isRecording: false,
    isProcessing: false,
    error: null,
  });

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Create MediaRecorder instance
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      // Collect audio data chunks
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // Start recording
      mediaRecorder.start();

      setState({
        isRecording: true,
        isProcessing: false,
        error: null,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to access microphone';
      setState({
        isRecording: false,
        isProcessing: false,
        error: errorMessage,
      });
      throw err;
    }
  }, []);

  const stopRecording = useCallback((): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      const mediaRecorder = mediaRecorderRef.current;

      if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        reject(new Error('No active recording'));
        return;
      }

      mediaRecorder.onstop = () => {
        // Create audio blob from chunks
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        
        // Stop all tracks
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
        
        setState({
          isRecording: false,
          isProcessing: false,
          error: null,
        });

        resolve(audioBlob);
      };

      mediaRecorder.onerror = (event) => {
        const error = event.error || new Error('Recording failed');
        setState({
          isRecording: false,
          isProcessing: false,
          error: error.message,
        });
        reject(error);
      };

      // Stop recording
      mediaRecorder.stop();
    });
  }, []);

  const setProcessing = useCallback((processing: boolean) => {
    setState(prev => ({
      ...prev,
      isProcessing: processing,
    }));
  }, []);

  const clearError = useCallback(() => {
    setState(prev => ({
      ...prev,
      error: null,
    }));
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
    setProcessing,
    clearError,
  };
}

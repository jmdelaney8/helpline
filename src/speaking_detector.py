import os

import utils

import silero_vad

_TMP_WAVE_FILENAME = "tmp.wav"


class SpeakingDetector:
    def __init__(self, silence_threshold_ms, sample_rate=8000):
        self._sample_rate = sample_rate
        self._silence_threshold_ms = silence_threshold_ms
        self._model = silero_vad.load_silero_vad()

    def is_speaking(self, audio_chunk):
        """Returns whether the the speaker in the audio chunk is still speaking or if
        the silence threshold has elapsed since the last utterance.
        """
        utils.ulaw_to_wav_file(audio_chunk, self._sample_rate, _TMP_WAVE_FILENAME)
        silence_duration_ms = self._silence_duration_ms(_TMP_WAVE_FILENAME)
        return silence_duration_ms < self._silence_threshold_ms
    
    def contains_speech(self, audio_chunk):
        """Returns whether the audio chunk contains any utterances at all."""
        utils.ulaw_to_wav_file(audio_chunk, self._sample_rate, _TMP_WAVE_FILENAME)
        wav = silero_vad.read_audio(_TMP_WAVE_FILENAME, self._sample_rate)
        speech_timestamps = self._speech_timestamps(wav)
        return any(speech_timestamps)


    def _silence_duration_ms(self, wav_filename):
        """Calculates the time (ms) since the last utterance"""
        wav = silero_vad.read_audio(wav_filename, sampling_rate=self._sample_rate)
        speech_probs = self._speech_timestamps(wav)

        if len(speech_probs) > 0:
            latest_utterance_sample = speech_probs[-1]["end"]
        else:
            latest_utterance_sample = 0

        ms_per_sample = 1000 / self._sample_rate
        silence_duration_ms = (len(wav) - latest_utterance_sample) * ms_per_sample

        # Debugging
        # print(
        #     f"{silence_duration_ms=}, {len(wav)=}, {latest_utterance_sample=}, "
        #     f"{speech_probs=}"
        # )

        return silence_duration_ms
    
    def _speech_timestamps(self, wav):
        return silero_vad.get_speech_timestamps(
            wav,
            self._model,
            sampling_rate=self._sample_rate,
            min_speech_duration_ms=20,
            min_silence_duration_ms=300,
        )

    def __del__(self):
        os.remove(_TMP_WAVE_FILENAME)

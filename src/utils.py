import array
import wave

def ulaw_to_pcm16(data):
    """Convert G.711 µ-law bytes to 16-bit PCM."""
    # MULAW_MAX = 0x1FFF
    BIAS = 0x84

    exp_lut = [0, 132, 396, 924, 1980, 4092, 8316, 16764]

    pcm_samples = array.array("h")
    for byte in data:
        byte = ~byte & 0xFF
        sign = byte & 0x80
        exponent = (byte & 0x70) >> 4
        mantissa = byte & 0x0F
        sample = exp_lut[exponent] + (mantissa << (exponent + 3))
        sample -= BIAS
        if sign != 0:
            sample = -sample
        pcm_samples.append(sample)
    return pcm_samples.tobytes()


def ulaw_to_wav_file(audio, sample_rate, wav_filename):
    pcm_audio = ulaw_to_pcm16(audio)

    with wave.open(wav_filename, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_audio)
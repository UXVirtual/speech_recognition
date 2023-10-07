from __future__ import annotations

import os
import time
from io import BytesIO

import numpy as np
import soundfile as sf
import faster_whisper

from speech_recognition.audio import AudioData
from speech_recognition.exceptions import SetupError

def recognize_faster_whisper(
    recognizer,
    audio_data: "AudioData",
    **kwargs,
):
    """
    Performs speech recognition on ``audio_data`` (an ``AudioData`` instance), using the Faster Whisper implementation of OpenAI Whisper.

    This is a stub function which calls perform_recognize_faster_whisper in a separate process using multiprocessing. Otherwise, there is
    a significant memory leak in the calling program. All kwargs are passed directly through using **kwargs.

    Detail: https://github.com/guillaumekln/faster-whisper

    Most options are identical to the original Whisper function. New options are:

    {beam_size}: Allows overriding the default beam size if desired.
    {device}: Allows setting the device, e.g. "auto", "cpu", "cuda", etc.
    {compute_type}: Allows setting the compute type, e.g. "int8", "float16", etc.
    {download_root}: Allows setting the model cache root path

    The return dict is also customized to avoid returning a mess of FasterWhisper objects.
    """

    


    assert isinstance(audio_data, AudioData), "Data must be audio data"

    import multiprocessing as mp
    queue = mp.Queue(maxsize=1)
    proc = mp.Process(target=perform_recognize_faster_whisper, args=(queue, recognizer, audio_data), kwargs=kwargs)
    #mp.set_start_method(perform_recognize_faster_whisper,True)
    dll_load_start = time.time()
    print(f"Loading CUDA DLL")
    proc.start()
    print(f"Loaded CUDA DLL ({round(time.time()-dll_load_start,2)}s)")
    result = queue.get()
    #print(f"Got Whisper Recognizer Process Result ({time.time()})")
    proc.join()
    return result

def perform_recognize_faster_whisper(
    queue,
    recognizer,
    audio_data: "AudioData",
    model="base",
    download_root=None,
    beam_size=5,
    device="auto",
    compute_type="int8",
    show_dict=False,
    language=None,
    translate=False,
    **transcribe_options
):
    """
    This function performs the actual faster_whisper transcribing in a spearate process to avoid a memory leak. It returns the results
    back to the calling stub function with a Queue.
    """

    start_time = time.time()

    #print(f"INIT WHISPER ({start_time})")
    #print(f"STARTING TRANSCRIPTION - model: {model}, download_root: {download_root}, beam_size: {beam_size}, device: {device}, compute_type: {compute_type}, language: {language}, translate: {translate}")

    # See this discussion on multithreading and multi GPU inference: https://github.com/guillaumekln/faster-whisper/issues/100
    whisper_model = faster_whisper.WhisperModel(model, device=device, compute_type=compute_type, download_root=download_root)
    print(f"LOADED WHISPER MODEL ({round(time.time()-start_time,2)}s)")

    # 16 kHz https://github.com/openai/whisper/blob/28769fcfe50755a817ab922a7bc83483159600a9/whisper/audio.py#L98-L99
    wav_bytes = audio_data.get_wav_data(convert_rate=16000)
    #print(f"CONVERTED AUDIO STREAM TO 16Khz ({time.time()})")
    wav_stream = BytesIO(wav_bytes)
    audio_array, sampling_rate = sf.read(wav_stream)
    audio_array = audio_array.astype(np.float32)

    segments, info = whisper_model.transcribe(
        audio_array,
        beam_size=beam_size,
        language=language,
        task="translate" if translate else None,
        **transcribe_options
    )
    found_text = list()
    found_tokens = list()
    # transcribe only runs gpu inference when iterating over the segments
    for segment in segments:
        # segment properties: 'avg_logprob', 'compression_ratio', 'count', 'end', 'id', 'index', 'no_speech_prob', 'seek', 'start', 'temperature', 'text', 'tokens', 'words'
        found_text.append(segment.text)
        found_tokens.append(segment.tokens)
        print(f"Transcript not contain speech?: {segment.no_speech_prob}")
        # TODO: skip output if one or more segments did not contain speech
    text = ' '.join(found_text).strip()
    print("------------------------------------------------------------")
    print(f"FINISHED TRANSCRIPTION ({round(time.time()-start_time, 2)}s): {text}")
    print(f"Tokens: {found_tokens}")
    print(f"Input audio duration: {info.duration_after_vad}s")
    print("------------------------------------------------------------")
    if show_dict:
        result = {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }
    else:
        result = text

    queue.put(result)

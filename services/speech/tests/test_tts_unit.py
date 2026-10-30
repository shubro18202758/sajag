"""Svara-TTS plumbing that needs no model: token decoding, prompt, cache key."""

from __future__ import annotations

from speech_service.tts import (
    AUDIO_TOKENS_START,
    BOS,
    END_OF_HUMAN,
    END_OF_SPEECH,
    END_OF_TURN,
    START_OF_HUMAN,
    START_OF_SPEECH,
    prompt_ids,
    TTSCache,
    codes_from_tokens,
    redistribute,
    speaker_for,
    split_sentences,
)


def test_speaker_ids() -> None:
    assert speaker_for("mr", "female") == "Marathi (Female)"
    assert speaker_for("en", "male") == "English (Indian) (Male)"
    assert speaker_for("hi", "female") == "Hindi (Female)"


def test_codes_from_tokens_undoes_the_per_position_offsets() -> None:
    raw = [5, 6, 7, 8, 9, 10, 11]  # one frame of SNAC codes
    toks = [AUDIO_TOKENS_START + c + i * 4096 for i, c in enumerate(raw)]
    assert codes_from_tokens([1, 2] + toks + [END_OF_SPEECH] + toks) == raw


def test_codes_drop_partial_frames() -> None:
    toks = [AUDIO_TOKENS_START + i * 4096 for i in range(10)]
    assert len(codes_from_tokens(toks)) == 7


def test_redistribute_layers() -> None:
    l0, l1, l2 = redistribute(list(range(14)))
    assert l0 == [0, 7]
    assert l1 == [1, 4, 8, 11]
    assert l2 == [2, 3, 5, 6, 9, 10, 12, 13]


def test_split_sentences_marathi_danda_and_long_runs() -> None:
    parts = split_sentences("हिंदमाता येथे पाणी साचले आहे. पर्यायी मार्ग वापरा! Thank you.")
    assert parts == ["हिंदमाता येथे पाणी साचले आहे.", "पर्यायी मार्ग वापरा!", "Thank you."]
    long = ", ".join(["रस्ता बंद"] * 60)
    assert all(len(p) <= 221 for p in split_sentences(long))


def test_cache_key_is_stable_and_sensitive() -> None:
    k = TTSCache.key("m", "mr", "female", "<clear>", "मजकूर")
    assert k == TTSCache.key("m", "mr", "female", "<clear>", "मजकूर")
    assert k != TTSCache.key("m", "mr", "male", "<clear>", "मजकूर")
    assert k != TTSCache.key("m", "en", "female", "<clear>", "मजकूर")
    assert len(k) == 64


class _Tok:
    def __call__(self, text, add_special_tokens=False):
        class R:
            input_ids = [ord(c) for c in text]
        assert add_special_tokens is False
        return R()


def test_prompt_is_one_human_turn_the_model_completes() -> None:
    ids = prompt_ids(_Tok(), "पाणी", "Marathi (Female)", "<clear>")
    assert ids[:2] == [START_OF_HUMAN, BOS]
    assert ids[-2:] == [END_OF_TURN, END_OF_HUMAN]
    body = "".join(chr(i) for i in ids[2:-2])
    assert body == "Marathi (Female): पाणी <clear>"


def test_codes_start_after_the_last_start_of_speech() -> None:
    frame = [AUDIO_TOKENS_START + 3 + i * 4096 for i in range(7)]
    junk = [AUDIO_TOKENS_START + 9 + i * 4096 for i in range(7)]
    assert codes_from_tokens(junk + [START_OF_SPEECH] + frame + [END_OF_SPEECH]) == [3] * 7

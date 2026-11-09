# Sound

Nothing here makes music, and no music ships with it. The sound for a film comes from the person: music they bring, or music you make with whatever music tools they have. What this repository gives you is the order of work, and the tools to clean up, finish and sync whatever audio you end up with.

## The order

```text
describe → essay → options → pick → cleanup → final → sync
```

1. **Describe.** The person says what they want to hear, in their words. Save them verbatim at the top of `song/essay.md`.
2. **Essay.** You write the song before anyone makes a sound (below).
3. **Options.** Make several, from the essay, with the person's tools. Often four: two close to the essay, one experiment, one well outside it. Put them in `song/options/`.
4. **Pick.** `python3 tools/options.py <film> page` puts them side by side with the essay; the person listens and says which, or which parts of which. Record it in their words: `python3 tools/options.py <film> pick options/<file> --said "<their words>"`. If they want a mix of two, make the mix, put it in `song/options/`, and pick that.
5. **Cleanup.** The picked audio goes through Ardour (below), so what ships is an editable session, not just a file.
6. **Final.** Master it to the loudness you chose: `python3 tools/master.py <in> <out.wav> --lufs -16 --tp -1`.
7. **Sync.** Once the picture is drafted at 24 fps or more, check every sound lands on its picture: `python3 tools/sync.py <film>`.

**When the person brings finished audio,** skip to the pick: put the file in `song/options/` and record their words. **A film with no sound** is a pick too: `python3 tools/options.py <film> silent --said "<their words>"`.

## Writing a song essay

An essay is the song described in words, before it exists, so that every option is made against the same intention and the person can say which one kept it. Copy `templates/essay.md`. It answers, in plain sentences:

- **What it is for.** The film's one sentence, and what the sound must do for it: carry excitement the picture keeps calm, hold still under an explanation, or lift on the result.
- **Where it sits.** The film's beats (`beats.json`), and what the music does at each: where it enters, where it builds, where it breathes, where it peaks, and where it lets go. Use the beats' seconds.
- **The arc.** How it starts, how it grows, what the biggest moment is and where it falls, and how it ends. One climax is easier to land than two.
- **The tunes.** Each melody, named and described: its shape, how long it is, and how it comes back changed. A single hook repeated is not a song.
- **The voices.** Which instruments or sounds carry the tune, which support it, and when each one joins or leaves.
- **Tempo, key and metre**, and any change in them, placed on the beats.
- **Words**, if it has them: the lyric sheet, and where each line falls. Keep stage directions out of the lyrics; a generator may sing them.
- **What it must not do.** A short list. This is often the most useful part.
- **References**, described by what they do (*"strings that hold one note under the whole explanation"*), never by copying a melody.

## An agent cannot hear

You can measure; only a person can listen. Say which one you did.

- A file of the right length that decodes cleanly can still be the wrong music. It does not prove the requested instruments, words or changes happened.
- Measure what you can: loudness per section (`ffmpeg -af ebur128`), silences and dropouts, true peak. A sound that drops out for less than a second and comes back is a fault until shown to be deliberate.
- When the person names a moment ("at 0:42 the voice disappears"), measure that moment first, every layer of it, before changing anything.

## Cleanup in Ardour

`tools/ardour.py` builds an editable Ardour session from stereo audio and bounces it without a GUI. Use it to finish a picked song, and to rescue recorded sound: a narration with room rumble, a demo's captured audio with clicks and uneven levels.

```json
{"rate": 48000, "seconds": 42.0, "parts": [{"name": "voice", "file": "voice.wav"}, {"name": "music", "file": "music.wav", "gain_db": -6}]}
```
```json
{"inserts": [{"tracks": "voice", "plugin": "eq_7band", "params": {"hpf_on": 1, "hpf_freq": 80}},
             {"tracks": "voice", "plugin": "compressor", "params": {"ratio": 3, "threshold": -20}}],
 "levels": {"music": -9}}
```
```
python3 tools/ardour.py song/stems.json --session song/session --bounce song/clean.wav --desk song/desk.json
```

Every part must be stereo (`ffmpeg -i in.wav -ac 2 out.wav`). The session folder must be new; a failed build never replaces a good one.

**Narration under music** is the same tool with two parts, the voice and the music, and a desk you write for them: how much to cut the voice's rumble, how hard to compress it, and how far the music sits under it. Listen-test the result with the person; the right balance depends on the voice and the music.

## Sync

A sound written on a beat's second plays early, because pictures take frames to appear. Render the picture at 24 fps or more, then:

```
python3 tools/sync.py <film> --video <film.mp4> --write-visible
```

It measures when each picture pops and when each sound starts, and writes the picture's real second into `beats.json` as `visible`. Move each sound to its `visible` second where you wrote it. Fix early sounds first; a viewer notices them sooner. Never stretch the audio, and never re-render the picture to fix the sound. A cue it calls `no-pop` (a fade, a slow build) has nothing to be early against: look at its frames.

**Never stretch an approved piece of music to fit the picture.** Cut the picture to the music.

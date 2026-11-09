# Finishing a film

Finish only when the person says the film is done. Until then everything is a draft.

`python3 tools/film.py finish <name>` does every step below and reports each as done or failed. A failed step means the film is not finished: fix it and run again, since every step is safe to repeat.

1. **Render at full rate** (60 fps unless `spec.md` says otherwise), resuming if the browser dies (`tools/render-resume.sh`).
2. **Encode** with H.264, `-crf 16 -preset slow -pix_fmt yuv420p -movflags +faststart`, the sound muxed at its own speed. The sound is never stretched to fit the picture; the picture is cut to the sound.
3. **Check the result:** duration, frame count, size, that the audio decodes all the way through, and that its loudness and true peak are where `song.md` says.
4. **Write the record**, `finish/record.json`: the film's name, the person's words when they said it was done (verbatim), the date, the source files with their checksums, the sound's source, and the command that rebuilt the film.
5. **Write `SHA256SUMS`** over every file in `finish/`.
6. **Make a poster**: one still at the film's most telling second.
7. **Write the review page** for the finished film and check it plays (`tools/deliver.py`).

Footage and sound never go into git: `films/` is ignored. Keep finished films wherever the person keeps their media.

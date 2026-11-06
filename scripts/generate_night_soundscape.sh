#!/usr/bin/env bash
set -euo pipefail
# Run from the repository root. Original procedural tones + existing CC0 crickets.
# -n preserves an existing output; choose a new filename for future revisions.
ffmpeg -hide_banner -loglevel warning -n \
  -f lavfi -i "aevalsrc=0.16*sin(2*PI*55*t)*(0.75+0.25*sin(2*PI*0.05*t))+0.07*sin(2*PI*65.4*t)+0.05*sin(2*PI*82.4*t):s=44100:d=40" \
  -f lavfi -i "anoisesrc=color=brown:amplitude=0.1:sample_rate=44100:duration=40:seed=17" \
  -stream_loop -1 -i frontend/public/assets/audio/night-crickets.mp3 \
  -filter_complex "[0:a]lowpass=f=240[drone];[1:a]highpass=f=70,lowpass=f=550,volume=0.7[wind];[2:a]atrim=duration=40,highpass=f=900,lowpass=f=3400,volume=0.12[crickets];[drone][wind][crickets]amix=inputs=3:normalize=0,afade=t=in:d=1,afade=t=out:st=39:d=1,alimiter=limit=0.65[out]" \
  -map '[out]' -t 40 -c:a libvorbis -q:a 4 frontend/public/assets/audio/night-ominous.ogg

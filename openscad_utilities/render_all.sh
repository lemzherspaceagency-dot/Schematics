#!/usr/bin/env bash
# Re-render every model in models/ to stl/ (and a preview to png/).
# Usage: ./render_all.sh            # all models
#        ./render_all.sh knob       # just one
# Override parameters with -D, e.g.:
#   openscad -o knob_m8.stl -D size=8 -D knob_d=45 models/knob.scad
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p stl png
names=("$@")
[ ${#names[@]} -eq 0 ] && names=($(ls models/*.scad | xargs -n1 basename | sed 's/\.scad$//'))
for n in "${names[@]}"; do
  echo "== $n"
  openscad -o "stl/$n.stl" "models/$n.scad"
  if command -v xvfb-run >/dev/null; then
    xvfb-run -a openscad -o "png/$n.png" --imgsize=600,450 --viewall --autocenter \
      --colorscheme=Tomorrow --camera=0,0,0,55,0,25,0 "models/$n.scad" >/dev/null 2>&1 || true
  fi
done

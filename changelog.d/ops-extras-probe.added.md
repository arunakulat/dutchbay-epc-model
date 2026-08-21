Added `app/ops/extras.py` — an optional-extra availability probe that reads declared pins from
the installed distribution's own metadata, so a running instance can report which extras it
actually has without shell or deploy access to the machine. Distinguishes `installed` (metadata)
from `importable` (opt-in deep probe), because a package can be installed yet fail to import — a
WeasyPrint missing pango/cairo is the case that matters. Degrades on every runtime failure rather
than raising, since a health probe that can crash is worse than none.

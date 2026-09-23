- `docs/deploy/DEPLOY.md` listed the image's WeasyPrint runtime libraries and omitted
  `libharfbuzz-subset0`, which the runtime stage has installed since
  [#1266](https://github.com/arunakulat/dutchbay-epc-model/pull/1266). It is now documented.
- It is called out in its own paragraph rather than appended to the existing list, because
  appending it would have made the surrounding sentence false. That sentence says dropping one of
  those libraries leaves the package importable but failing "at the first PDF request", which is
  true of pango/cairo and not of this one: WeasyPrint `dlopen`s it with `allow_fail=True`, so
  dropping it fails nothing and silently moves every render onto the deprecated fontTools subsetter.
  The paragraph says so, and says which gate catches it, since neither `verify_deployment.py
  --deep` nor `/health` can.

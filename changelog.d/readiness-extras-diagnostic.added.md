`GET /health/readiness` now also reports the CASPER availability of the optional extras the
deployed image installs (`[api,jobs,report]`) and the runtime identity, so a deployed instance
can be verified without shell or deploy access. `?deep=true` additionally import-checks each
package, catching the installed-but-unimportable case — WeasyPrint present while pango/cairo
are missing from the image. Purely additive: `ready` keeps its original meaning as the AND of
the environment checks only, and a probe failure degrades to an explicit `extras_error` rather
than a 5xx.

Documented post-deploy verification in `docs/deploy/DEPLOY.md`: how to confirm a running
instance's extras, pins and importability without `flyctl` access, when `--deep` matters (any
change to the image or its system libraries — WeasyPrint imports as metadata but fails at the
first PDF request if pango/cairo are dropped from the runtime stage), and the exit codes that
make it a CI gate. Amended the Limitations section, which previously left "what a running
instance contains" unverifiable, and added the honest boundary that the check reports what the
instance says about itself and is not a substitute for the `docker-build` workflow.

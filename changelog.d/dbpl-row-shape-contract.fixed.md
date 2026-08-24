Fixed a silent content loss in DBPL-rendered documents. The v2 template reads `row.cells` /
`row.group`, but the gap-dossier adapter still emitted bare lists, so every table row rendered as
nothing — the regenerated dossier kept all 38 gap headings while losing roughly 85% of its body
text, which made the output look complete. The adapter now emits the v2 shape, and the template
raises on a malformed row instead of dropping it.

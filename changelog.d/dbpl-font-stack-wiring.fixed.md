Fixed a silent wiring gap in the DBPL: the `@font-face` rules loaded the bundled Source
superfamily while `DBPL_FONT_STACKS` still named Liberation, so every document embedded Times New
Roman and Arial — and the provenance reported "substituted: none", because it verified that fonts
had been *provisioned* rather than that the stylesheet had *asked* for them. The stacks are now
derived from the same declaration the `@font-face` rules come from, and `render_dbpl_pdf`
inspects the finished PDF to confirm which families were actually embedded. That check is
tri-state: `None` (unverifiable) is a different claim from `False` (a fallback happened).

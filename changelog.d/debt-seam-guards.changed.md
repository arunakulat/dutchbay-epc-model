- Tightened the test-side guards around the `finance.debt` package (the #1502 review's
  P-7 and P-8 follow-up; tests only, no engine byte changes). The boundary lint's rule 2
  no longer advises patching the module that defines a function, which misses the calls
  from the other engine modules that import it. It now points to a shared helper,
  `tests/_debt_seams.wrap_everywhere`, which replaces a function in every engine module
  that binds it, found by identity so a binding under another name is caught too. The
  #1516 config-copy test uses that helper, and a new test shows a patch on the defining
  module alone records no calls. Rule 2 now also catches `mocker` and fully spelled
  `unittest.mock` patches, `delattr`, `del`, `patch.multiple`, `patch.dict` and writes to
  the façade's `__dict__`, plus `finance.debt_v14.<name>` after `import finance`. Rule 1
  catches a `finance.debt.<module>` attribute chain in production code. A new rule 3
  makes the package's own modules import names, never another package module as a
  module, so a seam can't be called through a module attribute. The refinance
  no-default guard and the #586a header guard now read `finance/debt/__init__.py` too.

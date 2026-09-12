**Supplemental evidence-path receipt — unavailable-source limitation resolved.** This supplements the preserved round-three domain review; its **ACCEPT** disposition for commit `c9921e47106c915651d20112bd9d01c9432e8cb2` remains unchanged.

Using the governed Python 3.12.13 environment in the same independent read-only `gpt-6-astra` / `xhigh` role, I successfully read and hashed [the retired macOS crash report](/Users/aruna/Library/Logs/DiagnosticReports/Retired/Python-2026-09-08-195419.ips):

```text
path: /Users/aruna/Library/Logs/DiagnosticReports/Retired/Python-2026-09-08-195419.ips
size_bytes: 166675
sha256: 8b7a09b7d3a7f4d85abee64c232c12d372b49f79035bb96cf576cec62b295080
expected_source_hash_match: PASS
capture_time: 2026-09-08 19:54:12.1707 +0530
exception: EXC_BAD_ACCESS / SIGSEGV
faulting_thread: 0
```

Independent parsing confirmed faulting-thread frames for `llvm::ValueSymbolTable::~ValueSymbolTable()`, `llvm::Module::~Module()`, LLVM linker operations, `LLVMLinkModules2` and `LLVMPY_LinkModules`.

The original-path lookup failure remains an accurate historical observation. The matching bytes are now independently verified at the `Retired` path, resolving the earlier inability to rehash the source report. This adds no application-test attribution, native-crash-fix claim, full-suite pass or authority uplift. No files or external state were modified.

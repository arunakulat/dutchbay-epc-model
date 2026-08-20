# Report and API test architecture

## Outcome

GWTF TEST-04 separates report transport and renderer contracts from the two
complete live qualification paths. The ordinary suite still exercises a real
finance-to-report HTTP flow, but response-only tests no longer rerun finance,
tornado, Morris, and PAWN merely to assert a status, media type, error mapping,
or download header.

The controlling CESSPIT source is `config/report_test_policy.yaml`.

## Assurance levels

| Level | Ordinary or qualification | What it proves |
| --- | --- | --- |
| API transport | Ordinary | HTML/PDF response assembly and deterministic dependency-error mapping against a known `ReportContext` |
| Renderer contracts | Ordinary | Templates render required sections, values, and empty states from known contexts |
| Representative live E2E | Ordinary | Authenticated HTTP route, timeout shell, real finance service, report builder, renderer, and response work together; supplemental sensitivity is replaced only at its service seams |
| Live supplemental sensitivity | Qualification | Production report builder computes and renders tornado, Morris, and PAWN blocks |
| Real PDF backend | Qualification | The explicitly installed report backend renders a live deterministic context to PDF bytes |

The two qualification tests are not deleted or weakened. They run with:

```bash
make test-report-qualification
```

GitHub runs the same `report_qualification` marker on Python 3.12 for
scheduled/manual Test Suite events and tagged releases. Ordinary PR tests use
`DUTCHBAY_TEST_MODE=full`, which collects but skips both stochastic and report
qualification tests.

## Before-state timing checkpoint

The clean pre-change baseline was measured on Python 3.12.13 at
`origin/main@037fb3d3510fd1e08f44d9e73d4815a48a93bf51` with coverage and the
repository default addopts disabled so the result measures only the five calls:

| Test | Call duration |
| --- | ---: |
| `test_run_case_report_html_renders` | 30.47 s |
| `test_run_case_report_pdf_503_without_weasyprint` | 30.28 s |
| `test_production_path_renders_sensitivity_sections` | 27.76 s |
| `test_run_case_report_pdf_success_path` | 27.69 s |
| `test_lender_report_renders_through_the_auth_gated_http_route` | 27.33 s |

All five passed in 157.92 seconds. This timing is an observed checkpoint, not a
cross-machine performance guarantee.

## After-state timing checkpoint

The identical five-node command was rerun on Python 3.12.13 after TEST-04, from
a worktree based on `origin/main@e2712672be0f1cd0f44d50d3b6132042f3b60902`:

| Test | Ordinary-suite outcome | Call duration |
| --- | --- | ---: |
| `test_run_case_report_html_renders` | passed | 0.06 s |
| `test_run_case_report_pdf_503_without_weasyprint` | passed | 0.01 s |
| `test_production_path_renders_sensitivity_sections` | governed qualification skip | <0.01 s |
| `test_run_case_report_pdf_success_path` | passed | 0.01 s |
| `test_lender_report_renders_through_the_auth_gated_http_route` | passed | 0.41 s |

The exact command completed with four passed, one governed skip, and zero
failures in 1.96 seconds: a 98.8% reduction from the 157.92-second observed
baseline on this machine. The separately invoked qualification target then
completed both retained live paths successfully:

```text
make test-report-qualification
2 passed in 30.84 seconds
```

The committed `.test_durations` weights are repinned to these ordinary-suite
call durations so pytest-split does not keep assigning historical 27–46 second
weights to millisecond transport tests or to qualification-only paths.

The repository-wide ordinary coverage gate also improved on the same Python
3.12 machine: the post-TEST-03 checkpoint was 5,455 passed, 17 skipped, 95.69%
coverage in 952.59 seconds; the TEST-04 working tree completed with 5,459
passed, 19 governed skips, 95.70% coverage in 659.61 seconds. That observed
4-minute-53-second reduction (30.8%) includes machine and scheduling effects and
is not a performance guarantee, but the exact five-node comparison above
isolates the intended architectural change.

## Evidence boundary

A green ordinary suite proves regression and coverage behavior only. A green
report qualification gate proves that the selected complete software paths ran;
it does not by itself establish model adequacy, financial correctness,
bankability, lender acceptance, or release approval. Those claims require their
own governed inputs, results, hashes, limitations, and sign-off.

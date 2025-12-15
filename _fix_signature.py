import pathlib


def main() -> None:
    p = pathlib.Path("analytics/contracts/__init__.py")
    s = p.read_text()

    # Fix the broken parameter line in build_casper_payload signature.
    s = s.replace(
        "    meta Optional[Dict[str, Any]] = None,",
        "    meta Optional[Dict[str, Any]] = None,",
    )
    s = s.replace(
        "    meta Dict[str, Any] | None = None,",
        "    meta Optional[Dict[str, Any]] = None,",
    )

    p.write_text(s)

    print("Fixed. Relevant signature lines:")
    for ln in s.splitlines():
        if "meta Dict" in ln or "meta Optional" in ln or "meta" in ln:
            print(ln)


if __name__ == "__main__":
    main()

import pathlib


def patch_calculate_tax_signature(repo_root: pathlib.Path) -> list[str]:
    patched: list[str] = []
    for path in repo_root.rglob("*.py"):
        sp = str(path)
        if "/.venv" in sp or "/.git/" in sp or "__pycache__" in sp:
            continue
        try:
            s = path.read_text(encoding="utf-8")
        except Exception:
            continue

        needle = "def calculate_tax("
        idx = s.find(needle)
        if idx == -1:
            continue

        # Find matching closing paren for the signature.
        i = idx + len(needle)
        depth = 1
        while i < len(s) and depth:
            ch = s[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth != 0:
            continue
        close_paren_pos = i - 1

        sig_block = s[idx : close_paren_pos + 1]
        if "statutory_profile" in sig_block:
            continue

        # Decide whether signature is single-line or multi-line.
        after_open = idx + len(needle)
        newline_pos = s.find("\n", after_open, close_paren_pos)

        if newline_pos == -1:
            # Single-line signature.
            new_s = (
                s[:close_paren_pos] + ", statutory_profile=None" + s[close_paren_pos:]
            )
        else:
            # Multi-line signature: use indentation from first param line.
            j = newline_pos + 1
            while j < len(s) and s[j] in " \t":
                j += 1
            param_indent = s[newline_pos + 1 : j]
            insert = "\n" + param_indent + "statutory_profile=None,"
            new_s = s[:close_paren_pos] + insert + s[close_paren_pos:]

        path.write_text(new_s, encoding="utf-8")
        patched.append(str(path))

    return patched


if __name__ == "__main__":
    root = pathlib.Path(".")
    patched = patch_calculate_tax_signature(root)
    print("patched_files:")
    for p in patched:
        print("-", p)

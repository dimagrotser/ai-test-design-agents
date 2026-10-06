from importlib.resources import files


def load_prompt(name: str) -> str:
    path = files("atda.prompts").joinpath(f"{name}.md")
    if not path.is_file():
        raise FileNotFoundError(f"no prompt named {name!r}")
    return path.read_text(encoding="utf-8").strip()

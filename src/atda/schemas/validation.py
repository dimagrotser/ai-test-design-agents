from pydantic import ValidationError


def format_validation_error(error: ValidationError) -> str:
    problems = []
    for problem in error.errors():
        where = ".".join(str(part) for part in problem["loc"])
        problems.append(f"{where}: {problem['msg']}" if where else problem["msg"])
    return "; ".join(problems)

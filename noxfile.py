import nox # type: ignore

@nox.session
def lock(session: nox.Session) -> None:
    session.install("pip-tools")
    session.run("pip-compile", "--generate-hashes", "--resolver=backtracking", "requirements.in")


@nox.session(python=["3.11", "3.10", "3.9", "3.8", "3.7"])
def env(session: nox.Session) -> None:
    session.install("--require-hashes", "--only-binary=:all:", "--no-deps", "-r", "requirements.txt")

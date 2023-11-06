# py-pip
An experimental "pip" subcommand for the [Python Launcher for Unix](https://python-launcher.app)

## Goals
- Use pip with the Python interpreter that would be selected by the Python Launcher
- Automatically create a minimal virtual environment if one does not exist
- Update pip automatically
- Keep a single copy of pip

## Installation
Simply download a `py-pip.pyz` file from any of the [releases](https://github.com/brettcannon/py-pip/releases).

If you want to build a `py-pip.pyz` from source, run `nox build` and find the file in the `dist` directory.

## Usage
If you make `py-pip.pyz` executable, you can run it directly like it was `pip`, passing arguments to it that pip itself would accept.

```console
py-pip.pyz <pip arguments>
```

This causes several things to happen:
1. The Python Launcher is used to find the appropriate Python interpreter to use
1. If `~/.cache/py-pip/pip.pyz` does not exist, download it from https://bootstrap.pypa.io/pip/pip.pyz (the directory is determined by the [XDG](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) cache directory)
1. If the found interpreter is not within a virtual environment, a minimal one will be created (i.e., pip will not be installed into the virtual environment)
1. Effectively run `py ~/.cache/py-pip/pip.pyz`, passing along all arguments
1. In the background, check if `pip.pyz` is outdated, and update it if necessary

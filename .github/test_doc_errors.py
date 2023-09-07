if __name__ == "__main__":
    import pathlib

    module_path = pathlib.Path(__file__).parent.absolute()
    repo = module_path.parent
    dirpath = repo / "docs" / "build" / "_html" / "reports"
    error_files = list(dirpath.glob("*err.log"))

    if error_files:
        for error_file in error_files:
            error = error_file.read_text()
            print(error)
        raise ValueError(f"{len(error_files)} errors in notebooks")

import marimo

__generated_with = "0.23.16"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import sys
    sys.path.append("src")
    return


@app.cell
def _():
    from GMA.utilts.test_fun import test_fun

    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

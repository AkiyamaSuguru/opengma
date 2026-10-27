import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return


@app.cell
def _():
    import sys
    sys.path.append("src")
    return


@app.cell
def _():
    from GMA.CM.XRD.loader import XRDLoader

    return (XRDLoader,)


@app.cell
def _(XRDLoader):
    reader = XRDLoader(reader="D8 Advance")
    return (reader,)


@app.cell
def _(reader):
    r = reader.read(r"C:\Users\jiema\Desktop\G2_BE_S1_1.txt")
    return (r,)


@app.cell
def _():
    import matplotlib.pyplot as plt

    return


@app.cell
def _(r):
    r[0].plot()
    return


@app.cell
def _(r):
    r[1]
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

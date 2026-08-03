import marimo

__generated_with = "0.23.16"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return


app._unparsable_cell(
    r"""
    from src.GMA.CM
    """,
    name="_"
)


if __name__ == "__main__":
    app.run()

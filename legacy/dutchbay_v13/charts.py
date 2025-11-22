from __future__ import annotations
from pathlib import Path
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import pandas as pd


def tornado_chart(
    df: pd.DataFrame, path: str | Path, metric: str = "delta_irr", sort: str = "abs"
) -> None:
    # expects columns: parameter, delta_irr
    series = df.groupby("parameter")[metric].sum()
    if sort == "abs":
        d = series.reindex(series.abs().sort_values(ascending=False).index)
    elif sort == "asc":
        d = series.sort_values(ascending=True)
    else:
        d = series.sort_values(ascending=False)
    plt.figure(figsize=(8, 6))
    y = range(len(d))
    plt.barh(list(y), list(d.values))
    plt.yticks(list(y), list(d.index))
    plt.xlabel("Δ Equity IRR")
    plt.title("Tornado Chart (Δ IRR)")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def dscr_series(df_annual: pd.DataFrame, path: str | Path) -> None:
    plt.figure(figsize=(8, 4))
    plt.plot(df_annual["year"], df_annual["dscr"])
    plt.xlabel("Year")
    plt.ylabel("DSCR")
    plt.title("DSCR over time")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def equity_fcf_series(df_annual: pd.DataFrame, path: str | Path) -> None:
    plt.figure(figsize=(8, 4))
    plt.plot(df_annual["year"], df_annual["equity_fcf_usd"])
    plt.xlabel("Year")
    plt.ylabel("Equity FCF (USD)")
    plt.title("Equity FCF over time")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def pareto_chart(
    frontier_df: pd.DataFrame, path: str | Path, grid_df: pd.DataFrame | None = None
) -> None:
    plt.figure(figsize=(6, 5))
    if grid_df is not None and not grid_df.empty:
        # background cloud
        plt.scatter(grid_df["min_dscr"], grid_df["equity_irr"], marker=".", s=10)
    if frontier_df is not None and not frontier_df.empty:
        # frontier line
        fr = frontier_df.sort_values(
            by=["min_dscr", "equity_irr"], ascending=[True, False]
        )
        plt.plot(fr["min_dscr"], fr["equity_irr"], marker="o")
    plt.xlabel("Min DSCR")
    plt.ylabel("Equity IRR")
    plt.title("Pareto Frontier (IRR vs DSCR)")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

#!/usr/bin/env python3
from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "rpe_analysis_individual"
CSV_BASENAMES = [
    "covariance_metrics_optimized.csv",
    "covariance_metrics_latest.csv",
]
CSV_ROLE_LABELS = {
    "covariance_metrics_latest.csv": "Latest frame",
    "covariance_metrics_optimized.csv": "Oldest frame",
}
RPE_TARGETS = ["rpe_translation_m", "rpe_rotation_deg"]
ROTATION_DETAIL_PLOTS = 4
REPROJECTION_COLUMNS = [
    "avg_reprojection_error_px",
    "max_reprojection_error_px",
    "reprojection_sample_count",
    "latest_frame_active_reprojection_sum_px",
    "latest_frame_active_reprojection_mean_px",
    "latest_frame_active_reprojection_sample_count",
]
PLOT_CLIP_LOWER_Q = 0.01
PLOT_CLIP_UPPER_Q = 0.99
EXCLUDE_FROM_HEATMAP = {
    "matched_gt_time_sec",
    "gt_time_diff_sec",
    "reference_time_sec",
    "frame_count",
}
EXCLUDE_FROM_RANKING = {
    "matched_gt_time_sec",
    "gt_time_diff_sec",
    "reference_time_sec",
    "frame_count",
    "time_sec",
}
CORRELATION_COLUMNS = [
    "target",
    "variable",
    "n",
    "pearson_r",
    "pearson_p",
    "spearman_rho",
    "spearman_p",
    "abs_spearman_rho",
]
DISPLAY_LABELS = {
    "time_sec": "Time [s]",
    "submit_to_publish_latency_sec": "Submit-to-publish latency [s]",
    "rpe_translation_m": "Translation RPE [m]",
    "rpe_rotation_deg": "Rotation RPE [deg]",
    "pose_position_cov_trace_m2": "Pose position covariance trace [m^2]",
    "pose_rotation_cov_trace_rad2": "Pose rotation covariance trace [rad^2]",
    "feature_count": "Feature count",
    "tracked_feature_count": "Tracked feature count",
    "long_track_count": "Long track count",
    "new_feature_count": "New feature count",
    "outlier_count": "Outlier count",
    "avg_parallax_px": "Average parallax [px]",
    "avg_reprojection_error_px": "Average reprojection error [px]",
    "max_reprojection_error_px": "Max reprojection error [px]",
    "reprojection_sample_count": "Reprojection sample count",
    "latest_frame_active_reprojection_sum_px": "Latest-frame reprojection sum [px]",
    "latest_frame_active_reprojection_mean_px": "Latest-frame reprojection mean [px]",
    "latest_frame_active_reprojection_sample_count": "Latest-frame reprojection sample count",
    "marginalization_flag": "Marginalization flag",
    "frame_count": "Frame count",
}


def safe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def rmse(series: pd.Series) -> float:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return float("nan")
    return float(np.sqrt(np.mean(np.square(vals.to_numpy()))))


def compute_correlations(df: pd.DataFrame, target: str) -> pd.DataFrame:
    rows = []
    y = pd.to_numeric(df[target], errors="coerce")
    for col in df.columns:
        if col == target or col in EXCLUDE_FROM_RANKING:
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        mask = x.notna() & y.notna()
        if int(mask.sum()) < 20:
            continue
        xv = x[mask]
        yv = y[mask]
        if xv.nunique() <= 1:
            continue
        pearson_r, pearson_p = pearsonr(xv, yv)
        spearman_rho, spearman_p = spearmanr(xv, yv)
        rows.append(
            {
                "target": target,
                "variable": col,
                "n": int(mask.sum()),
                "pearson_r": float(pearson_r),
                "pearson_p": float(pearson_p),
                "spearman_rho": float(spearman_rho),
                "spearman_p": float(spearman_p),
                "abs_spearman_rho": abs(float(spearman_rho)),
            }
        )
    corr_df = pd.DataFrame(rows, columns=CORRELATION_COLUMNS)
    if corr_df.empty:
        return corr_df
    return corr_df.sort_values(by=["target", "abs_spearman_rho"], ascending=[True, False])


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def metric_label(name: str) -> str:
    return DISPLAY_LABELS.get(name, name.replace("_", " "))


def target_label(target: str) -> str:
    return metric_label(target)


def target_color(target: str) -> str:
    if target == "rpe_translation_m":
        return "#1f77b4"
    if target == "rpe_rotation_deg":
        return "#d62728"
    return "#4c78a8"


def metric_rows(
    corr_df: pd.DataFrame, target: str, allowed: list[str] | None = None
) -> pd.DataFrame:
    subset = corr_df[corr_df["target"] == target].copy()
    subset = subset[~subset["variable"].isin(RPE_TARGETS)]
    if allowed is not None:
        subset = subset[subset["variable"].isin(allowed)]
    if subset.empty:
        return subset
    return subset.sort_values("abs_spearman_rho", ascending=False).reset_index(drop=True)


def plot_heatmap(df: pd.DataFrame, stem: str, out_dir: Path) -> None:
    cols = []
    for col in df.columns:
        if col in EXCLUDE_FROM_HEATMAP:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() < 20 or series.nunique(dropna=True) <= 1:
            continue
        cols.append(col)

    if not cols:
        return

    corr = df[cols].corr(method="spearman")
    labels = [metric_label(c).replace(" ", "\n") for c in corr.columns]

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(corr.to_numpy(), cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title(f"{stem}: Spearman Correlation Heatmap")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Spearman rho")
    fig.tight_layout()
    fig.savefig(out_dir / f"{stem}_correlation_heatmap.png", dpi=180)
    plt.close(fig)


def plot_rpe_timeseries(df: pd.DataFrame, target: str, out_dir: Path) -> None:
    time_sec = pd.to_numeric(df["time_sec"], errors="coerce")
    vals = pd.to_numeric(df[target], errors="coerce")
    mask = time_sec.notna() & vals.notna()
    if int(mask.sum()) < 2:
        return

    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.plot(time_sec[mask], vals[mask], linewidth=1.2, color=target_color(target))
    ax.set_title(f"{target_label(target)}: Time Series")
    ax.set_ylabel(target_label(target))
    ax.set_xlabel(metric_label("time_sec"))
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "timeseries.png", dpi=180)
    plt.close(fig)


def plot_rpe_histogram(df: pd.DataFrame, target: str, out_dir: Path) -> None:
    vals = pd.to_numeric(df[target], errors="coerce").dropna()
    if vals.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.hist(vals, bins=35, color=target_color(target), alpha=0.85, edgecolor="white")
    ax.axvline(vals.mean(), color="black", linestyle="--", linewidth=1, label="mean")
    ax.axvline(
        math.sqrt(np.mean(np.square(vals))),
        color="gray",
        linestyle=":",
        linewidth=1.5,
        label="RMSE",
    )
    ax.set_title(f"{target_label(target)}: Histogram")
    ax.set_xlabel(target_label(target))
    ax.set_ylabel("Count")
    ax.grid(alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "histogram.png", dpi=180)
    plt.close(fig)


def plot_rpe_boxplot(df: pd.DataFrame, target: str, out_dir: Path) -> None:
    vals = pd.to_numeric(df[target], errors="coerce").dropna()
    if vals.empty:
        return

    fig, ax = plt.subplots(figsize=(4.5, 6))
    ax.boxplot(
        vals.to_numpy(),
        vert=True,
        patch_artist=True,
        boxprops={"facecolor": target_color(target), "alpha": 0.55},
        medianprops={"color": "black", "linewidth": 1.2},
    )
    ax.set_title(f"{target_label(target)}: Boxplot")
    ax.set_ylabel(target_label(target))
    ax.set_xticks([1])
    ax.set_xticklabels([target_label(target)])
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_dir / "boxplot.png", dpi=180)
    plt.close(fig)


def plot_rpe_ecdf(df: pd.DataFrame, target: str, out_dir: Path) -> None:
    vals = pd.to_numeric(df[target], errors="coerce").dropna()
    if vals.empty:
        return

    sorted_vals = np.sort(vals.to_numpy())
    probs = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(sorted_vals, probs, color=target_color(target), linewidth=1.5)
    ax.set_title(f"{target_label(target)}: ECDF")
    ax.set_xlabel(target_label(target))
    ax.set_ylabel("Empirical CDF")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "ecdf.png", dpi=180)
    plt.close(fig)


def plot_correlation_bars(
    corr_df: pd.DataFrame,
    target: str,
    out_dir: Path,
    filename: str,
    title: str,
    allowed: list[str] | None = None,
) -> None:
    subset = metric_rows(corr_df, target, allowed=allowed)
    if subset.empty:
        return

    subset = subset.sort_values("spearman_rho")
    fig_height = max(5.0, 0.42 * len(subset) + 1.8)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    labels = subset["variable"].map(metric_label)
    ax.barh(labels, subset["spearman_rho"], color="#4c78a8")
    ax.set_xlim(-1, 1)
    ax.set_xlabel("Spearman rho")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    for idx, val in enumerate(subset["spearman_rho"]):
        x = val + (0.03 if val >= 0 else -0.03)
        ha = "left" if val >= 0 else "right"
        ax.text(x, idx, f"{val:.2f}", va="center", ha=ha, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / filename, dpi=180)
    plt.close(fig)


def zscore(series: pd.Series) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce")
    std = vals.std()
    if pd.isna(std) or std == 0:
        return vals * np.nan
    return (vals - vals.mean()) / std


def clip_for_plot(
    series: pd.Series,
    lower_q: float = PLOT_CLIP_LOWER_Q,
    upper_q: float = PLOT_CLIP_UPPER_Q,
) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce")
    finite = vals.dropna()
    if finite.empty:
        return vals
    lo = finite.quantile(lower_q)
    hi = finite.quantile(upper_q)
    if pd.isna(lo) or pd.isna(hi) or lo == hi:
        return vals
    return vals.clip(lower=lo, upper=hi)


def plot_metric_scatter(
    df: pd.DataFrame,
    target: str,
    metric_row: pd.Series,
    out_dir: Path,
    rank: int,
) -> None:
    metric = str(metric_row["variable"])
    x = pd.to_numeric(df[metric], errors="coerce")
    y = pd.to_numeric(df[target], errors="coerce")
    mask = x.notna() & y.notna()
    if int(mask.sum()) < 2:
        return

    scatter_dir = out_dir / "scatter"
    scatter_dir.mkdir(exist_ok=True)
    xv = x[mask]
    yv = y[mask]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(xv, yv, s=12, alpha=0.35, color="#4c78a8", edgecolors="none")
    if len(xv) >= 2 and xv.nunique() > 1:
        slope, intercept = np.polyfit(xv, yv, 1)
        xs = np.linspace(float(xv.min()), float(xv.max()), 100)
        ax.plot(xs, slope * xs + intercept, color="#d62728", linewidth=1.5)
    ax.set_xlabel(metric_label(metric))
    ax.set_ylabel(target_label(target))
    ax.set_title(
        f"{metric_label(metric)} vs {target_label(target)}\n"
        f"rho={metric_row['spearman_rho']:.2f}, "
        f"pearson={metric_row['pearson_r']:.2f}, n={int(metric_row['n'])}"
    )
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(
        scatter_dir / f"{rank:02d}_{slugify(metric)}_vs_{slugify(target)}_scatter.png",
        dpi=180,
    )
    plt.close(fig)


def plot_metric_overlay_normalized(
    df: pd.DataFrame,
    target: str,
    metric_row: pd.Series,
    out_dir: Path,
    rank: int,
) -> None:
    metric = str(metric_row["variable"])
    time_sec = pd.to_numeric(df["time_sec"], errors="coerce")
    rpe_z = zscore(clip_for_plot(df[target]))
    metric_z = zscore(clip_for_plot(df[metric]))
    mask = time_sec.notna() & rpe_z.notna() & metric_z.notna()
    if int(mask.sum()) < 2:
        return

    overlay_dir = out_dir / "overlay_normalized"
    overlay_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.plot(time_sec[mask], rpe_z[mask], color="#d62728", linewidth=1.2, label=target_label(target))
    ax.plot(
        time_sec[mask],
        metric_z[mask],
        color="#1f77b4",
        linewidth=1.0,
        alpha=0.9,
        label=metric_label(metric),
    )
    ax.axhline(0, color="black", linewidth=0.7, alpha=0.25)
    ax.grid(alpha=0.2)
    ax.set_title(
        f"{target_label(target)} vs {metric_label(metric)}\n"
        f"normalized overlay, rho={metric_row['spearman_rho']:.2f}, "
        f"clipped {int(PLOT_CLIP_LOWER_Q*100)}-{int(PLOT_CLIP_UPPER_Q*100)} pct"
    )
    ax.set_ylabel("z-score")
    ax.set_xlabel(metric_label("time_sec"))
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(
        overlay_dir / f"{rank:02d}_{slugify(metric)}_vs_{slugify(target)}_normalized.png",
        dpi=180,
    )
    plt.close(fig)


def plot_metric_overlay_raw(
    df: pd.DataFrame,
    target: str,
    metric_row: pd.Series,
    out_dir: Path,
    rank: int,
) -> None:
    metric = str(metric_row["variable"])
    time_sec = pd.to_numeric(df["time_sec"], errors="coerce")
    rpe_vals = clip_for_plot(df[target])
    metric_vals = clip_for_plot(df[metric])
    mask = time_sec.notna() & rpe_vals.notna() & metric_vals.notna()
    if int(mask.sum()) < 2:
        return

    overlay_dir = out_dir / "overlay_raw"
    overlay_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.plot(time_sec[mask], rpe_vals[mask], color="#d62728", linewidth=1.2, label=target_label(target))
    ax.set_ylabel(target_label(target), color="#d62728")
    ax.tick_params(axis="y", labelcolor="#d62728")
    ax.grid(alpha=0.2)
    ax.set_xlabel(metric_label("time_sec"))

    ax2 = ax.twinx()
    ax2.plot(
        time_sec[mask],
        metric_vals[mask],
        color="#1f77b4",
        linewidth=1.0,
        alpha=0.85,
        label=metric_label(metric),
    )
    ax2.set_ylabel(metric_label(metric), color="#1f77b4")
    ax2.tick_params(axis="y", labelcolor="#1f77b4")
    ax.set_title(
        f"{target_label(target)} vs {metric_label(metric)}\n"
        f"raw overlay, rho={metric_row['spearman_rho']:.2f}, "
        f"clipped {int(PLOT_CLIP_LOWER_Q*100)}-{int(PLOT_CLIP_UPPER_Q*100)} pct"
    )

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(
        overlay_dir / f"{rank:02d}_{slugify(metric)}_vs_{slugify(target)}_raw.png",
        dpi=180,
    )
    plt.close(fig)


def plot_target_summary_suite(
    df: pd.DataFrame,
    corr_df: pd.DataFrame,
    target: str,
    out_dir: Path,
) -> None:
    out_dir.mkdir(exist_ok=True)
    plot_rpe_timeseries(df, target, out_dir)
    plot_rpe_histogram(df, target, out_dir)
    plot_rpe_boxplot(df, target, out_dir)
    plot_rpe_ecdf(df, target, out_dir)
    plot_correlation_bars(
        corr_df,
        target,
        out_dir,
        "all_correlations.png",
        f"{target}: All Metric Correlations",
    )
    plot_correlation_bars(
        corr_df,
        target,
        out_dir,
        "reprojection_correlations.png",
        f"{target}: Reprojection Correlations",
        allowed=REPROJECTION_COLUMNS,
    )


def plot_target_metric_details(
    df: pd.DataFrame,
    corr_df: pd.DataFrame,
    target: str,
    out_dir: Path,
    max_metrics: int | None = None,
) -> None:
    rows = metric_rows(corr_df, target)
    if max_metrics is not None:
        rows = rows.head(max_metrics)
    if rows.empty:
        return

    for rank, (_, row) in enumerate(rows.iterrows(), start=1):
        plot_metric_scatter(df, target, row, out_dir, rank)
        plot_metric_overlay_normalized(df, target, row, out_dir, rank)
        plot_metric_overlay_raw(df, target, row, out_dir, rank)


def plot_sequence_latency_comparison(
    sequence_name: str,
    dfs_by_basename: dict[str, pd.DataFrame],
    out_dir: Path,
) -> None:
    traces = []
    for basename, color in [
        ("covariance_metrics_latest.csv", "#d62728"),
        ("covariance_metrics_optimized.csv", "#1f77b4"),
    ]:
        df = dfs_by_basename.get(basename)
        if df is None or "submit_to_publish_latency_sec" not in df.columns:
            continue
        time_sec = pd.to_numeric(df["time_sec"], errors="coerce")
        latency = pd.to_numeric(df["submit_to_publish_latency_sec"], errors="coerce")
        mask = time_sec.notna() & latency.notna()
        if int(mask.sum()) < 2:
            continue
        traces.append(
            {
                "label": CSV_ROLE_LABELS.get(basename, basename),
                "color": color,
                "time_sec": time_sec[mask],
                "latency": latency[mask],
            }
        )

    fig, ax = plt.subplots(figsize=(14, 4.8))
    if not traces:
        ax.set_title(f"{sequence_name}: Latest vs Oldest Submit-to-publish Latency")
        ax.set_xlabel(metric_label("time_sec"))
        ax.set_ylabel(metric_label("submit_to_publish_latency_sec"))
        ax.grid(alpha=0.25)
        ax.text(
            0.5,
            0.5,
            "No submit-to-publish latency samples in latest or oldest CSV",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        fig.tight_layout()
        fig.savefig(out_dir / "latest_vs_oldest_submit_to_publish_latency.png", dpi=180)
        plt.close(fig)
        return

    for trace in traces:
        ax.plot(
            trace["time_sec"],
            trace["latency"],
            linewidth=1.2,
            color=trace["color"],
            label=trace["label"],
        )
    ax.set_title(f"{sequence_name}: Latest vs Oldest Submit-to-publish Latency")
    ax.set_xlabel(metric_label("time_sec"))
    ax.set_ylabel(metric_label("submit_to_publish_latency_sec"))
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_dir / "latest_vs_oldest_submit_to_publish_latency.png", dpi=180)
    plt.close(fig)


def build_signed_correlation_lines(
    corr_df: pd.DataFrame,
    target: str,
    top_k: int = 5,
) -> list[str]:
    lines = [f"{target_label(target)}:"]
    rows = metric_rows(corr_df, target)
    if rows.empty:
        lines.append("  No valid correlations.")
        return lines

    positive_rows = rows[rows["spearman_rho"] > 0].sort_values(
        "spearman_rho", ascending=False
    ).head(top_k)
    negative_rows = rows[rows["spearman_rho"] < 0].sort_values(
        "spearman_rho", ascending=True
    ).head(top_k)

    lines.append("  Top positive correlations:")
    if positive_rows.empty:
        lines.append("    None.")
    else:
        for rank, (_, row) in enumerate(positive_rows.iterrows(), start=1):
            lines.append(
                "    "
                f"{rank}. {metric_label(str(row['variable']))} ({row['variable']}): "
                f"spearman={float(row['spearman_rho']):+.3f}, "
                f"pearson={float(row['pearson_r']):+.3f}, "
                f"n={int(row['n'])}"
            )

    lines.append("  Top negative correlations:")
    if negative_rows.empty:
        lines.append("    None.")
    else:
        for rank, (_, row) in enumerate(negative_rows.iterrows(), start=1):
            lines.append(
                "    "
                f"{rank}. {metric_label(str(row['variable']))} ({row['variable']}): "
                f"spearman={float(row['spearman_rho']):+.3f}, "
                f"pearson={float(row['pearson_r']):+.3f}, "
                f"n={int(row['n'])}"
            )

    return lines


def build_sequence_top_correlation_report(
    sequence_name: str,
    corr_by_basename: dict[str, pd.DataFrame],
    top_k: int = 5,
) -> str:
    lines = [f"Sequence: {sequence_name}", ""]

    for basename in CSV_BASENAMES:
        corr_df = corr_by_basename.get(basename)
        if corr_df is None:
            continue
        lines.append(f"{CSV_ROLE_LABELS.get(basename, basename)} ({basename})")
        lines.extend(
            build_signed_correlation_lines(
                corr_df,
                "rpe_translation_m",
                top_k=top_k,
            )
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_summary_row(
    sequence_name: str, path: Path, df: pd.DataFrame
) -> dict[str, float | int | str]:
    ref_delta = pd.to_numeric(df["time_sec"], errors="coerce") - pd.to_numeric(
        df["reference_time_sec"], errors="coerce"
    )
    translation = pd.to_numeric(df["rpe_translation_m"], errors="coerce")
    rotation = pd.to_numeric(df["rpe_rotation_deg"], errors="coerce")
    latency = pd.to_numeric(df.get("submit_to_publish_latency_sec"), errors="coerce")
    return {
        "sequence": sequence_name,
        "file": path.name,
        "rows": int(len(df)),
        "translation_rpe_n": int(translation.notna().sum()),
        "translation_rmse_m": rmse(translation),
        "translation_mean_m": float(translation.mean()),
        "translation_median_m": float(translation.median()),
        "translation_p95_m": float(translation.quantile(0.95)),
        "rotation_rpe_n": int(rotation.notna().sum()),
        "rotation_rmse_deg": rmse(rotation),
        "rotation_mean_deg": float(rotation.mean()),
        "rotation_median_deg": float(rotation.median()),
        "rotation_p95_deg": float(rotation.quantile(0.95)),
        "latency_n": int(latency.notna().sum()),
        "latency_mean_sec": float(latency.mean()),
        "latency_median_sec": float(latency.median()),
        "latency_p95_sec": float(latency.quantile(0.95)),
        "reference_gap_median_sec": float(ref_delta.median()),
        "reference_gap_mean_sec": float(ref_delta.mean()),
        "reference_gap_max_sec": float(ref_delta.max()),
    }


def resolve_sequence_dirs(root: Path) -> list[Path]:
    sequence_dirs = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name == OUT_DIR.name:
            continue
        if any((path / basename).exists() for basename in CSV_BASENAMES):
            sequence_dirs.append(path)

    if sequence_dirs:
        return sequence_dirs

    if any((root / basename).exists() for basename in CSV_BASENAMES):
        return [root]

    return []


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    summary_rows = []
    global_report_sections = []
    sequence_dirs = resolve_sequence_dirs(ROOT)

    for sequence_dir in sequence_dirs:
        sequence_name = sequence_dir.name
        sequence_out_dir = OUT_DIR if sequence_dir == ROOT else OUT_DIR / sequence_name
        sequence_out_dir.mkdir(exist_ok=True)
        dfs_by_basename: dict[str, pd.DataFrame] = {}
        corr_by_basename: dict[str, pd.DataFrame] = {}

        for basename in CSV_BASENAMES:
            path = sequence_dir / basename
            if not path.exists():
                continue

            df = safe_numeric(pd.read_csv(path))
            dfs_by_basename[basename] = df
            stem = path.stem
            file_out_dir = sequence_out_dir / stem
            if file_out_dir.exists():
                shutil.rmtree(file_out_dir)
            file_out_dir.mkdir(exist_ok=True)
            summary_rows.append(build_summary_row(sequence_name, path, df))

            corr_tables = []
            for target in RPE_TARGETS:
                corr_table = compute_correlations(df, target)
                if not corr_table.empty:
                    corr_tables.append(corr_table)
            if corr_tables:
                corr_df = pd.concat(corr_tables, ignore_index=True)
            else:
                corr_df = pd.DataFrame(columns=CORRELATION_COLUMNS)
            corr_by_basename[basename] = corr_df
            corr_df.to_csv(file_out_dir / "rpe_correlations.csv", index=False)

            plot_heatmap(df, stem, file_out_dir)
            for target in RPE_TARGETS:
                target_out_dir = file_out_dir / target
                plot_target_summary_suite(df, corr_df, target, target_out_dir)

            plot_target_metric_details(
                df,
                corr_df,
                "rpe_translation_m",
                file_out_dir / "rpe_translation_m",
            )
            plot_target_metric_details(
                df,
                corr_df,
                "rpe_rotation_deg",
                file_out_dir / "rpe_rotation_deg",
                max_metrics=ROTATION_DETAIL_PLOTS,
            )

        plot_sequence_latency_comparison(sequence_name, dfs_by_basename, sequence_out_dir)
        sequence_report = build_sequence_top_correlation_report(
            sequence_name,
            corr_by_basename,
            top_k=5,
        )
        (sequence_out_dir / "top_correlations_report.txt").write_text(sequence_report)
        global_report_sections.append(sequence_report.rstrip())

    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "rpe_summary.csv", index=False)
    (OUT_DIR / "top_correlations_report.txt").write_text(
        "\n\n".join(global_report_sections).rstrip() + "\n"
    )


if __name__ == "__main__":
    main()

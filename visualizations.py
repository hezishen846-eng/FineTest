"""Section A3 / B2：统一单位、色盲友好配色和空数据保护的图表。"""

import os
from pathlib import Path
import tempfile

# 后台绘图不依赖 macOS GUI；缓存放入可写目录，避免污染用户的全局设置。
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ev_exam_mpl"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", palette="colorblind", context="notebook")


def empty_axis(ax, message="No matching observations"):
    """空筛选与无法估计的关系要明确说明，不能画出虚假的零趋势。"""
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()


def hourly_telemetry(data):
    """同一充电站同一时刻的遥测可能重复附在多条会话上，先去重再跨站相加。

    仅代表所选会话带有的观测，不代表连续、完整的校园电网测量。
    同一站点/时刻有不同数值时取中位数；审阅者应检查原始传感器质量。
    """
    columns = ["grid_load_kw", "solar_generation_kw"]
    by_hub = data.groupby(["session_start", "hub_id"])[columns].median()
    snapshots = by_hub.groupby(level="session_start").sum(min_count=1)
    return snapshots.resample("h").agg(
        {"grid_load_kw": "max", "solar_generation_kw": "mean"}
    )


def operational_panels(data):
    """三联图：观测负荷峰值、用户费用分布、温度与供电量关系。"""
    fig, axes = plt.subplots(3, 1, figsize=(11, 12), constrained_layout=True)
    if (
        "supplement_origin" in data
        and data.supplement_origin.eq("SIMULATED_FOR_DEMONSTRATION").any()
    ):
        fig.suptitle(
            "DEMONSTRATION — dates, site and telemetry are simulated", fontsize=11
        )
    if data.empty:
        for ax in axes:
            empty_axis(ax)
        return fig
    telemetry = {"session_start", "hub_id", "grid_load_kw", "solar_generation_kw"}
    if telemetry.issubset(data.columns):
        hourly = hourly_telemetry(data)
        axes[0].plot(
            hourly.index,
            hourly["grid_load_kw"],
            label="Observed grid peak",
            color="#0072B2",
        )
        axes[0].plot(
            hourly.index,
            hourly["solar_generation_kw"],
            label="Mean solar generation",
            color="#009E73",
        )
        axes[0].set(
            title="A. Hourly grid demand and solar generation",
            xlabel="Local session time",
            ylabel="Power (kW)",
        )
        axes[0].legend(frameon=False)
        axes[0].tick_params(axis="x", rotation=20)
    else:
        empty_axis(
            axes[0],
            "Grid / solar panel unavailable\nRequired telemetry and dates were not supplied",
        )
    sns.boxplot(
        data=data,
        x="user_type",
        y="net_billable_amount",
        order=["Student", "Staff", "Visitor"],
        color="#80B1D3",
        ax=axes[1],
    )
    axes[1].set(
        title="B. Session cost by user type",
        xlabel="User type",
        ylabel="Billable amount (MYR)",
    )
    colors = {"AC": "#0072B2", "DC": "#D55E00"}
    for charger, group in data.groupby("charger_type"):
        if len(group) >= 3 and group["battery_temperature_c"].nunique() > 1:
            sns.regplot(
                data=group,
                x="battery_temperature_c",
                y="energy_kwh",
                ci=None,
                scatter_kws={"alpha": 0.45, "s": 18},
                color=colors[charger],
                label=charger,
                ax=axes[2],
            )
        else:
            axes[2].scatter(
                group["battery_temperature_c"],
                group["energy_kwh"],
                label=f"{charger} (insufficient variation for trend)",
                color=colors[charger],
            )
    axes[2].set(
        title="C. Battery temperature and energy delivered",
        xlabel="Battery temperature (°C)",
        ylabel="Energy (kWh)",
    )
    axes[2].legend(frameon=False)
    return fig


def executive_panels(data):
    """并列柱图与相关热图：统一小时轴，相关系数范围固定为 [-1, 1]。"""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), constrained_layout=True)
    if (
        "supplement_origin" in data
        and data.supplement_origin.eq("SIMULATED_FOR_DEMONSTRATION").any()
    ):
        fig.suptitle(
            "DEMONSTRATION — dates, site and telemetry are simulated", fontsize=11
        )
    if data.empty:
        for ax in axes:
            empty_axis(ax)
        return fig
    hourly = data.pivot_table(
        index="start_hour",
        columns="charger_type",
        values="net_billable_amount",
        aggfunc="sum",
        fill_value=0,
    )
    hourly = hourly.reindex(index=range(24), columns=["AC", "DC"], fill_value=0)
    hourly.plot.bar(ax=axes[0], color=["#0072B2", "#D55E00"], width=0.8)
    axes[0].set(
        title="Revenue by start hour and charger type",
        xlabel="Hour of day",
        ylabel="Revenue (MYR)",
    )
    axes[0].tick_params(axis="x", rotation=0)
    variables = ["ambient_temperature_c", "duration_minutes", "grid_load_kw"]
    if not set(variables).issubset(data.columns):
        empty_axis(
            axes[1],
            "Requested correlation unavailable\nAmbient temperature and grid load were not supplied",
        )
        return fig
    corr = data[variables].corr()
    if len(data) < 3 or corr.isna().all().all():
        empty_axis(axes[1], "Insufficient variation for correlation")
    else:
        sns.heatmap(
            corr,
            mask=corr.isna(),
            annot=True,
            fmt=".2f",
            cmap="vlag",
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            xticklabels=["Ambient °C", "Duration min", "Grid kW"],
            yticklabels=["Ambient °C", "Duration min", "Grid kW"],
            ax=axes[1],
        )
        axes[1].set_title("Pearson correlation (not causation)")
    return fig


def save_charts(data, folder):
    """同时导出 300 DPI PNG 和矢量 PDF，供报告插图使用。"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, factory in [
        ("operational_panels", operational_panels),
        ("executive_panels", executive_panels),
    ]:
        fig = factory(data)
        for suffix in ("png", "pdf"):
            fig.savefig(folder / f"{name}.{suffix}", dpi=300, bbox_inches="tight")
        plt.close(fig)

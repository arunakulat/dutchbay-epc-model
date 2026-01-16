"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
import numpy as np

from analytics.contracts_v14 import ParameterRangeConfig
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, RegularPolygon
from matplotlib.path import Path
from matplotlib.projections import register_projection
from matplotlib.projections.polar import PolarAxes
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D
from analytics.sensitivity import (
    SensitivityRequest,
    run_multi_metric_tornado,
    run_tornado_sensitivity,
    tornado_suite_to_dataframe,
)

# Quick UI for scenario and drivers (customize as needed)
st.title("Sensitivity Dashboard (Tornado/Spider Explorer)")

config_path = st.text_input(
    "Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml"
)
params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=-20,
        high_pct=20,
        steps=5,
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=-10,
        high_pct=10,
        steps=5,
    ),
    # Add or make this dynamic as needed
]

def radar_factory(num_vars, frame='circle'):
    """
    Create a radar chart with `num_vars` Axes.

    This function creates a RadarAxes projection and registers it.

    Parameters
    ----------
    num_vars : int
        Number of variables for radar chart.
    frame : {'circle', 'polygon'}
        Shape of frame surrounding Axes.

    """
    # calculate evenly-spaced axis angles
    theta = np.linspace(0, 2*np.pi, num_vars, endpoint=False)

    class RadarTransform(PolarAxes.PolarTransform):

        def transform_path_non_affine(self, path):
            # Paths with non-unit interpolation steps correspond to gridlines,
            # in which case we force interpolation (to defeat PolarTransform's
            # autoconversion to circular arcs).
            if path._interpolation_steps > 1:
                path = path.interpolated(num_vars)
            return Path(self.transform(path.vertices), path.codes)

    class RadarAxes(PolarAxes):

        name = 'radar'
        PolarTransform = RadarTransform

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # rotate plot such that the first axis is at the top
            self.set_theta_zero_location('N')

        def fill(self, *args, closed=True, **kwargs):
            """Override fill so that line is closed by default"""
            return super().fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default"""
            lines = super().plot(*args, **kwargs)
            for line in lines:
                self._close_line(line)

        def _close_line(self, line):
            x, y = line.get_data()
            # FIXME: markers at x[0], y[0] get doubled-up
            if x[0] != x[-1]:
                x = np.append(x, x[0])
                y = np.append(y, y[0])
                line.set_data(x, y)

        def set_varlabels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels)

        def _gen_axes_patch(self):
            # The Axes patch must be centered at (0.5, 0.5) and of radius 0.5
            # in axes coordinates.
            if frame == 'circle':
                return Circle((0.5, 0.5), 0.5)
            elif frame == 'polygon':
                return RegularPolygon((0.5, 0.5), num_vars,
                                      radius=.5, edgecolor="k")
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

        def _gen_axes_spines(self):
            if frame == 'circle':
                return super()._gen_axes_spines()
            elif frame == 'polygon':
                # spine_type must be 'left'/'right'/'top'/'bottom'/'circle'.
                spine = Spine(axes=self,
                              spine_type='circle',
                              path=Path.unit_regular_polygon(num_vars))
                # unit_regular_polygon gives a polygon of radius 1 centered at
                # (0, 0) but we want a polygon of radius 0.5 centered at (0.5,
                # 0.5) in axes coordinates.
                spine.set_transform(Affine2D().scale(.5).translate(.5, .5)
                                    + self.transAxes)
                return {'polar': spine}
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

    register_projection(RadarAxes)
    return theta

def run_tornado_analysis(sens_req: SensitivityRequest):
    """Runs tornado sensitivity and returns the results as a DataFrame."""
    suite = run_tornado_sensitivity(sens_req)
    return tornado_suite_to_dataframe(suite)


def plot_tornado_chart(df):
    """Generates a tornado chart from a DataFrame."""
    fig, ax = plt.subplots()
    ax.barh(df['parameter_name'], df['sensitivity'])
    ax.set_xlabel("Sensitivity")
    ax.set_title("Tornado Chart")
    return fig

def run_and_plot_spider_analysis(sens_req: SensitivityRequest):
    """Runs multi-metric analysis and returns a spider chart figure."""
    multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])

    # Extract data for plotting
    labels = [result.parameter_name for result in multi_suite.results]
    data = np.array([result.sensitivity_values for result in multi_suite.results])

    # Create the spider chart
    num_vars = len(labels)
    theta = radar_factory(num_vars, frame='polygon')

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(projection='radar'))
    fig.subplots_adjust(top=0.85, bottom=0.05)

    colors = ['b', 'r']
    for i, metric in enumerate(multi_suite.metrics):
        ax.plot(theta, data[:, i], color=colors[i], label=metric)
        ax.fill(theta, data[:, i], facecolor=colors[i], alpha=0.25)

    ax.set_varlabels(labels)
    ax.legend(loc=(0.9, .95), labelspacing=0.1, fontsize='small')
    ax.set_title("Multi-Metric Spider Chart", weight='bold', size='large', position=(0.5, 1.1))

    return fig


sens_req = SensitivityRequest(config_path, params)

with st.spinner("🌪️ Running Tornado Analysis... Please wait."):
    df = run_tornado_analysis(sens_req)
    st.write("Tornado Analysis Results:")
    st.dataframe(df)
    st.write("Tornado Chart:")
    tornado_fig = plot_tornado_chart(df)
    st.pyplot(tornado_fig)

with st.spinner("🕷️ Generating Spider Chart... This may take a moment."):
    st.write("Multi-metric (Spider) Chart:")
    spider_fig = run_and_plot_spider_analysis(sens_req)
    st.pyplot(spider_fig)

st.success("Try changing params in the code for more exploration.")

from datetime import timedelta
from math import floor

from matplotlib.pyplot import show, subplots
import numpy as np


def convert_timings_seconds(timings: list[str]) -> list[int]:
    """
    Converts timing strings to number of seconds.

    Strings in form "MM:SS" are converted to integer number of seconds.
    """
    deltas: list[int] = []
    for timing in timings:
        minutes, _, seconds = timing.partition(':')
        deltas.append(int(minutes) * 60 + int(seconds))
    return deltas


def convert_timings_timedelta(timings: list[str]) -> list[timedelta]:
    deltas: list[timedelta] = []
    for timing in timings:
        minutes, _, seconds = timing.partition(':')
        deltas.append(timedelta(minutes=int(minutes), seconds=int(seconds)))
    return deltas


def timedelta_formatter(seconds: float, pos: float):
    delta_minutes = floor(seconds // 60)
    delta_seconds = floor(seconds % 60)
    return f'{delta_minutes}:{delta_seconds}'


def clustered_bar_plot(timings: dict[str, list[str]],
                       x_groups: list[str],
                       x_label: str,
                       y_label: str,
                       title: str) -> None:
    """
    Plots a clustered bar chart.
    
    :param timings: Set of timings per named experiment.
    :param x_groups: Names for timing buckets.
    :param x_label: X-axis label.
    :param y_label: Y-axis label.
    :param title: Plot title.
    """
    sizes = [len(data) for data in timings.values()]
    if min(sizes) != max(sizes):
        raise RuntimeException("Ragged data not supported")
    number_of_readings = sizes[0]

    figure, axes = subplots()

    x_label_locations = np.arange(number_of_readings)
    bucket_width = 0.8
    bar_width = bucket_width / len(timings.keys())

    for count, group in enumerate(timings.keys()):
        bar_x = x_label_locations - bucket_width / 2 + bar_width * count
        values = convert_timings_seconds(timings[group])
        axes.bar(bar_x, values, width=bar_width, label=group)

    axes.set_xticks(x_label_locations)
    axes.set_xticklabels(x_groups)
    axes.set_xlabel(x_label)
    axes.yaxis.set_major_formatter(timedelta_formatter)
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.legend()

    show()

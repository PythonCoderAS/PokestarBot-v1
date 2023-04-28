# Sourced from https://gist.github.com/ahwillia/c7e54f875913ebc3de3852e9f51ccc69

# Majority of credit goes to Chris Holdgraf, @choldgraf, and this StackOverflow
# post: http://stackoverflow.com/questions/5320205/matplotlib-text-dimensions

import io
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams['font.family'] = 'serif'
plt.rcParams["mathtext.fontset"] = "dejavuserif"


def latex_as_png(eq: str, fontsize: int = 16, padding: float = 0, **kwargs: Any) -> io.BytesIO:
    """Plot an equation as a matplotlib figure."""

    kwargs.setdefault("dpi", 600)

    # set up figure
    f: matplotlib.pyplot.Figure = plt.figure()
    ax: matplotlib.pyplot.Axes = plt.axes([0, 0, 1, 1])
    r = f.canvas.get_renderer()

    # display equation
    t = ax.text(0.5, 0.5, eq, fontsize=fontsize,
                horizontalalignment='center', verticalalignment='center')

    # resize figure to fit equation
    bb = t.get_window_extent(renderer=r)
    w, h = bb.width / f.dpi, np.ceil(bb.height / f.dpi)
    f.set_size_inches((padding + w, padding + h))

    # set axis limits so equation is centered
    plt.xlim([0, 1])
    plt.ylim([0, 1])
    ax.grid(False)
    ax.set_axis_off()

    bio = io.BytesIO()

    plt.savefig(bio, **kwargs)
    bio.seek(0)

    plt.close(f)

    return bio

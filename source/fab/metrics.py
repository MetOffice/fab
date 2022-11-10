##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
A module for recording and summarising metrics, with the following concepts:

init
    create pipes
    create reading process - daemonic, exits with main process

send
    group, name, value -> reading process
    overwrites any previous value for group[name]

reading process
    creates and add to metrics dict
    finishes -> send whole lot down a summary pipe and close

stop
    closes pipes & process
    return metrics from summary pipe

"""

# todo: replace this module with something like prometheus & grafana?

import datetime
import json
import logging
from collections import defaultdict
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Optional, Dict

JSON_FILENAME = 'metrics.json'

logger = logging.getLogger(__name__)

# the pipe for individual metrics
_metric_recv_conn: Optional[Connection] = None
_metric_send_conn: Optional[Connection] = None

# the process which receives individual metrics
_metric_recv_process: Optional[Process] = None


def init_metrics(metrics_folder: Path):
    """
    Create the pipe for sending metrics, the process to read them, and another pipe to push the final collated data.

    Only one call to init_metrics can be called before calling stop_metrics.

    :param metrics_folder:
        The folder where we will write metrics.

    """
    global _metric_recv_conn, _metric_send_conn
    global _metric_recv_process

    if any([_metric_recv_conn, _metric_send_conn, _metric_recv_process]):
        raise ConnectionError('Metrics already initialised. Only one concurrent user of init_metrics is expected.')

    # the pipe connections for individual metrics
    _metric_recv_conn, _metric_send_conn = Pipe(duplex=False)

    # start the receiving process
    _metric_recv_process = Process(
        target=_read_metric,
        daemon=True,  # todo: test this thoroughly, manually
        kwargs={'metrics_folder': metrics_folder},
    )
    _metric_recv_process.start()


def _read_metric(metrics_folder: Path):
    """
    Intended to run as a child process, reading metrics created by other child processes.

    Reads from the metric pipe until the pipe is closed,
    at which point it pushes the collated metrics onto the "collated metrics" pipe and ends.

    :param metrics_folder:
        The folder where we will write metrics.

    """
    # An example metric is the time taken to preprocess a file; metrics['preprocess c']['my_file.c']
    metrics: Dict[str, Dict[str, float]] = defaultdict(dict)

    # todo: can we do this better?
    # we run in a subprocess, so we get a copy of _metric_send_conn before it closes.
    # when the calling process finally does close it, we'll still have an open copy of it,
    # so the connection will still be considered open!
    # therefore we close *OUR* copy of it now.
    _metric_send_conn.close()  # type: ignore

    logger.debug('read_metric: waiting for metrics')
    num_recorded = 0
    while True:
        try:
            metric = _metric_recv_conn.recv()  # type: ignore
        except EOFError:
            break

        # todo: consider protecting against using up too much memory
        group, name, value = metric
        metrics[group][name] = value
        num_recorded += 1

    logger.debug(f"read_metric: recorded {num_recorded} metrics")

    metrics_folder.mkdir(parents=True, exist_ok=True)
    with open(metrics_folder / JSON_FILENAME, 'wt') as outfile:
        json.dump(metrics, outfile, indent='\t')


def send_metric(group: str, name: str, value):
    """
    Pass a metric to the reader process.

    Metrics will be written to a json file after build steps have run.

    Example::

        send_metric('my step', 'reading took', 123)
        send_metric('my step', 'writing took', 456)

    :param group:
        Name of the metrics group.
    :param name:
        Name of the metric.
    :param value:
        Value of the metric.

    """
    _metric_send_conn.send([group, name, value])  # type: ignore


def stop_metrics():
    """
    Close the metrics pipe and reader process.

    """
    global _metric_recv_conn, _metric_send_conn
    global _metric_recv_process

    # Close the metrics recording pipe.
    # The metrics recording process will notice and finish,
    # and send the total metrics to the "collated metrics" pipe, which it then closes.
    _metric_send_conn.close()  # type: ignore
    _metric_recv_process.join(1)  # type: ignore

    # set these to none so metrics can be initialised again
    _metric_recv_conn = _metric_send_conn = _metric_recv_process = None


def metrics_summary(metrics_folder: Path):
    """
    Create various summary charts from the metrics json.

    """

    #
    # metrics[group][item] = value
    #
    # metrics['run']['time taken'] = total time taken
    # metrics['run']['machine'] = machine name
    #
    # metrics['steps']['compile fortran'] = step time taken
    #
    # metrics['compile fortran'][filename] = {'time_taken': timer.taken, 'start': timer.start}
    #

    try:
        import matplotlib  # type: ignore
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        logger.warning('matplotlib not installed, no metrics summary charts produced')
        return

    with open(metrics_folder / JSON_FILENAME, 'rt') as outfile:
        metrics = json.load(outfile)

    logger.info('creating metrics summary')
    logger.debug(f'metrics_summary: got metrics for: {metrics.keys()}')
    metrics_folder.mkdir(parents=True, exist_ok=True)

    metric_names = [
        'preprocess fortran', 'preprocess c',
        'compile fortran', 'compile fortran stage 1', 'compile fortran stage 2'
    ]

    # histogram
    for step_name in metric_names:
        # do we have these metrics?
        if step_name not in metrics:
            continue

        values = metrics[step_name].values()
        run_times = [value['time_taken'] for value in values]

        plt.hist(run_times, 10)
        plt.figtext(0.99, 0.01, f"{metrics['run']['datetime']}", horizontalalignment='right', fontsize='x-small')
        plt.xlabel('time (s)')

        fbase = metrics_folder / ('hist_' + step_name.replace(' ', '_'))
        plt.savefig(f"{fbase}.png")
        plt.close()

    # busby style plot -  https://www.osti.gov/biblio/1393322
    for step_name in metric_names:
        # do we have these metrics?
        if step_name not in metrics:
            continue

        sorted_items = sorted(metrics[step_name].items(), key=lambda item: item[1]['start'])
        values = [item[1] for item in sorted_items]
        t0 = values[0]['start']
        starts = [value['start'] - t0 for value in values]
        durations = [value['time_taken'] for value in values]

        # taller plot after 500 files
        # todo: we should also increase the width when lots of quick files become sub-pixel
        size = max(10.0, 10 * len(values) / 500)
        plt.figure(figsize=[10, size])

        plt.barh(
            y=list(range(len(values))),
            width=durations,
            left=starts,
            height=1,
        )

        fbase = metrics_folder / ('busby_' + step_name.replace(' ', '_'))
        plt.savefig(f"{fbase}.png")
        plt.close()

    # overall pie chart of time taken by each step
    run = metrics['run']
    time_taken = datetime.timedelta(seconds=int(run['time taken']))
    min_label_thresh = time_taken.seconds * 0.01
    step_totals = metrics.get('steps')
    if step_totals:
        step_metrics = step_totals.items()
        step_times = [kv[1] for kv in step_metrics]
        step_labels = [kv[0] if kv[1] > min_label_thresh else "" for kv in step_metrics]

        plt.pie(step_times, labels=step_labels, normalize=True,
                wedgeprops={"linewidth": 1, "edgecolor": "white"})
        plt.suptitle(f"{run['label']} took {time_taken}\n"
                     f"on {run['sysname']}, {run['nodename']}, {run['machine']}")
        plt.figtext(0.99, 0.01, f"{metrics['run']['datetime']}", horizontalalignment='right', fontsize='x-small')
        plt.savefig(metrics_folder / "pie.png")
        plt.close()
    else:
        logger.info("no metrics data 'steps' for step totals pie chart")

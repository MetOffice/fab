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


def init_metrics(metrics_folder):
    """
    Create the pipe for sending metrics, the process to read them, and another pipe to push the final collated data.

    Only one call to init_metrics can be called before calling stop_metrics.

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

    """
    _metric_send_conn.send([group, name, value])  # type: ignore


def stop_metrics():
    """
    Close the metrics pipe and reader process.

    Return the final collection of metrics.

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
    Create various summaries for the metrics, including charts if matplotlib is installed.

    """
    try:
        import matplotlib  # type: ignore
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        plt = None

    with open(metrics_folder / JSON_FILENAME, 'rt') as outfile:
        metrics = json.load(outfile)

    logger.debug(f'metrics_summary: got metrics for: {metrics.keys()}')
    metrics_folder.mkdir(parents=True, exist_ok=True)

    # graphs for individual steps
    step_names = ['preprocess fortran', 'preprocess c', 'compile fortran']
    for step_name in step_names:
        if step_name not in metrics or step_name not in metrics['steps']:
            continue

        fbase = metrics_folder / step_name.replace(' ', '_')

        values = metrics[step_name].values()
        total_time = datetime.timedelta(seconds=int(metrics["steps"][step_name]))

        if plt:
            plt.hist(values, 10)
            plt.suptitle(f'{step_name} histogram\n'
                         f'{len(values)} files took {total_time}')
            plt.figtext(0.99, 0.01, f"{metrics['run']['datetime']}", horizontalalignment='right', fontsize='x-small')
            plt.xlabel('time (s)')
            plt.savefig(f"{fbase}.png")
            plt.close()

        top_ten = sorted(metrics[step_name].items(), key=lambda kv: kv[1], reverse=True)[:10]
        with open(f"{fbase}.txt", "wt") as txt_file:
            txt_file.write("top ten\n")
            for i in top_ten:
                txt_file.write(f"{i}\n")

    # overall pie chart of time taken by each step
    if plt:
        run = metrics['run']
        time_taken = datetime.timedelta(seconds=int(run['time taken']))
        min_label_thresh = time_taken.seconds * 0.01
        step_metrics = metrics['steps'].items()
        step_times = [kv[1] for kv in step_metrics]
        step_labels = [kv[0] if kv[1] > min_label_thresh else "" for kv in step_metrics]

        plt.pie(step_times, labels=step_labels, normalize=True,
                wedgeprops={"linewidth": 1, "edgecolor": "white"})
        plt.suptitle(f"{run['label']} took {time_taken}\n"
                     f"on {run['sysname']}, {run['nodename']}, {run['machine']}")
        plt.figtext(0.99, 0.01, f"{metrics['run']['datetime']}", horizontalalignment='right', fontsize='x-small')
        plt.savefig(metrics_folder / "pie.png")
        plt.close()

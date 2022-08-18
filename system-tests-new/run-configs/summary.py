#!/usr/bin/env python3
import json
from argparse import ArgumentParser
from pathlib import Path

if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('workspace', default='.')
    args = arg_parser.parse_args()

    print('\ncompile fortran durations (s)\n')
    for proj in Path(args.workspace).iterdir():
        if not proj.is_dir():
            continue

        metrics_folder = (proj / 'metrics')
        if not metrics_folder.exists():
            continue

        for f in metrics_folder.iterdir():
            metrics_file = f / 'metrics.json'
            if not metrics_file.exists():
                continue

            j = json.load(open(metrics_file))

            try:
                print(f'{proj.name}  --  {j["steps"]["compile fortran"]:.0f}')
            except KeyError:
                continue

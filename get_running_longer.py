#!/usr/bin/env python

from z3_noodler_eval import *

if __name__ == "__main__":
    benchmarks = [Benchmark.kaluza]
    df = get_running_longer(df_all, Tool.noodler_underapprox, 50, benchmarks)
    # df = get_running_longer(df_all, Tool.noodler, 50, benchmarks, include_nan=False)
    for index, row in df.iterrows():
        print(row["name"])

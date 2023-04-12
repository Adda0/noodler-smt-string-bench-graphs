#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""z3-noodler-eval.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1h4ihmOTkqqzykem30rYNc7v4SMMef5-8
"""
import contextlib
import datetime
import pathlib
import enum
import sys

import numpy as np
import pandas as pd
import re as re
import tabulate as tab
import plotnine as p9
import math
import mizani.formatters as mizani
import warnings
warnings.filterwarnings('ignore')

from plotnine.themes.themeable import legend_key_width
# in seconds
TIMEOUT = 120
TIMEOUT_VAL = TIMEOUT * 1.1
TIME_MIN = 0.01

# For reading in files
def read_file(filename):
    """Reads a CSV file into Panda's data frame"""
    df_loc = pd.read_csv(
        filename,
        sep=";",
        comment="#",
        #na_values=['ERR', 'TO', 'MISSING'],
        #na_values=['TO'],
        )

    for col in df_loc.columns:
        if re.search(r"-result$", col):
            df_loc[col] = df_loc[col].apply(lambda x: x.strip())
            df_loc.loc[~df_loc[col].isin(['sat', 'unsat', 'unknown', 'TO']), col] = 'ERR'

    for col in df_loc.columns:
        if re.search(r"-runtime$", col):
            [tool_name, _] = col.rsplit('-', 1)
            tool_result_name = f"{tool_name}-result"
            df_loc.loc[df_loc[tool_result_name].isin(['ERR', 'TO', 'unknown']), col] = np.nan
            df_loc[col] = df_loc[col].astype(float)

    return df_loc


# For printing scatter plots
def scatter_plot(df, xcol, ycol, domain, xname=None, yname=None, log=False, width=6, height=6, clamp=True, tickCount=5, show_legend=False):
    assert len(domain) == 2

    POINT_SIZE = 1.0
    DASH_PATTERN = (0, (6, 2))

    if xname is None:
        xname = xcol
    if yname is None:
        yname = ycol

    # formatter for axes' labels
    ax_formatter = mizani.custom_format('{:n}')

    if clamp:  # clamp overflowing values if required
        df = df.copy(deep=True)
        df.loc[df[xcol] > domain[1], xcol] = domain[1]
        df.loc[df[ycol] > domain[1], ycol] = domain[1]

    # generate scatter plot
    scatter = p9.ggplot(df)
    scatter += p9.aes(x=xcol, y=ycol, color="benchmark")
    scatter += p9.geom_point(size=POINT_SIZE, na_rm=True, show_legend=show_legend)
    scatter += p9.labs(x=xname, y=yname)
    scatter += p9.theme(legend_key_width=2)
    scatter += p9.scale_color_hue(l=0.4, s=0.9, h=0.1)

    # rug plots
    scatter += p9.geom_rug(na_rm=True, sides="tr", alpha=0.05)

    if log:  # log scale
        scatter += p9.scale_x_log10(limits=domain, labels=ax_formatter)
        scatter += p9.scale_y_log10(limits=domain, labels=ax_formatter)
    else:
        scatter += p9.scale_x_continuous(limits=domain, labels=ax_formatter)
        scatter += p9.scale_y_continuous(limits=domain, labels=ax_formatter)

    # scatter += p9.theme_xkcd()
    scatter += p9.theme_bw()
    scatter += p9.theme(panel_grid_major=p9.element_line(color='#666666', alpha=0.5))
    scatter += p9.theme(panel_grid_minor=p9.element_blank())
    scatter += p9.theme(figure_size=(width, height))
    scatter += p9.theme(axis_text=p9.element_text(size=24, color="black"))
    scatter += p9.theme(axis_title=p9.element_text(size=24, color="black"))
    legend_text_size = 20
    scatter += p9.theme(legend_title=p9.element_text(size=legend_text_size),
                        legend_text=p9.element_text(size=legend_text_size))
    if not show_legend:
        scatter += p9.theme(legend_position='none')

    # generate additional lines
    scatter += p9.geom_abline(intercept=0, slope=1, linetype=DASH_PATTERN)  # diagonal
    scatter += p9.geom_vline(xintercept=domain[1], linetype=DASH_PATTERN)  # vertical rule
    scatter += p9.geom_hline(yintercept=domain[1], linetype=DASH_PATTERN)  # horizontal rule

    res = scatter

    return res


# Print a matrix of plots
def matrix_plot(list_of_plots, cols):
    assert len(list_of_plots) > 0
    assert cols >= 0

    matrix_plot = None
    row = None
    for i in range(0, len(list_of_plots)):
        if i % cols == 0:  # starting a new row
            row = list_of_plots[i]
        else:
            row |= list_of_plots[i]

        if (i + 1) % cols == 0 or i + 1 == len(list_of_plots):  # last chart in a row
            if not matrix_plot:  # first row finished
                matrix_plot = row
            else:
                matrix_plot &= row

    return matrix_plot


# table to LaTeX file
def table_to_file(table, headers, out_file):
    with open(f"tables/{out_file}.tex", mode='w+') as fl:
        print(tab.tabulate(table, headers=headers, tablefmt="latex"), file=fl)

def sanity_check(df):
    """Sanity check"""
    pt = df[["name", "z3-result", "cvc5-result", Tool.noodler.value+"-result"]]
    pt = pt.dropna()
    pt = pt[(pt["cvc5-result"] != pt[Tool.noodler.value + "-result"]) | (pt["z3-result"] != pt[Tool.noodler.value + "-result"])]
    return pt


def generate_cactus_plot(df, file_name: str, start: int = 0, end: int = 27000):
    concat = pd.DataFrame()
    tseries1 = pd.Series(name="vbs1")
    tseries2 = pd.Series(name="vbs2")
    m = 0

    for t in df.columns:
        tseries1 = pd.Series(df[t].tolist())
        tseries1 = tseries1[start:]
        concat.insert(0, t.rsplit('-', 1)[0], tseries1)

    inc = int((end-start)/5)
    plt = concat.plot.line(xticks=range(start,end,inc), figsize=(6,6), grid=True, fontsize=10, lw=2)
    plt.set_yscale('log')
    plt.set_xlabel("instances", fontsize=16)
    plt.set_ylabel("runtime [s]", fontsize=16)
    plt.legend(loc=6,prop={"size": 8})
    plt.figure.savefig(f"graphs/fig-cactus-{file_name}.pdf", dpi=1000)

def gen_cactus_plot(df, tools1, tools2, legend1, legend2):
    concat = pd.DataFrame()
    tseries1 = pd.Series(name="vbs1")
    tseries2 = pd.Series(name="vbs2")
    m = 0
    start = 0
    #start = 19000

    for t in tools1:
      #proj_t = df[t+"-runtime"]
      #tseries1 = tseries1.combine(proj_t, min, fill_value=TIMEOUT_VAL)
      #tseries1 = tseries1[tseries1 < TIMEOUT_VAL]
      #tseries1 = tseries1.sort_values()
      tseries1 = pd.Series(df[t+"-runtime"].tolist())
      tseries1 = tseries1[start:]
      if t == too:
        concat.insert(0, "Noodler", tseries1)
      else:
        concat.insert(0, t, tseries1)

    # for t in tools2:
    #   proj_t = df[t+"-runtime"]
    #   proj_t = proj_t.rename("vbs2")
    #   tseries2 = tseries2.combine(proj_t, min, fill_value=TIMEOUT_VAL)

    # tseries1 = tseries1[tseries1 < TIMEOUT_VAL]
    # tseries1 = tseries1.sort_values()
    # tseries1 = pd.Series(tseries1.tolist())
    # tseries1 = tseries1[start:]

    # tseries2 = tseries2[tseries2 < TIMEOUT_VAL]
    # tseries2 = tseries2.sort_values()
    # tseries2 = pd.Series(tseries2.tolist())
    # tseries2 = tseries2[start:]

    # concat.insert(0, "VBS({0})".format(",".join(legend1)), tseries1)
    # concat.insert(0, "VBS({0})".format(",".join(legend2)), tseries2)

    inc = int((end-start)/5)
    plt = concat.plot.line(xticks=range(start,end,inc), figsize=(6,6), grid=True, fontsize=10, lw=2)
    plt.set_xlabel("instances", fontsize=16)
    plt.set_ylabel("runtime [s]", fontsize=16)
    plt.legend(loc=6,prop={"size": 8})
    plt.figure.savefig("graphs/fig-cactus.pdf", dpi=1000)


def gen_vbs_plot(df, tools1, tools2, legend1, legend2):
    concat = pd.DataFrame()
    tseries1 = pd.Series(name="vbs1")
    tseries2 = pd.Series(name="vbs2")
    m = 0
    start = 19526

    for t in tools1:
        proj_t = df[t + "-runtime"]
        proj_t = proj_t.rename("vbs1")
        tseries1 = tseries1.combine(proj_t, min, fill_value=TIMEOUT_VAL)

    for t in tools2:
        proj_t = df[t + "-runtime"]
        proj_t = proj_t.rename("vbs2")
        tseries2 = tseries2.combine(proj_t, min, fill_value=TIMEOUT_VAL)

    tseries1 = tseries1[tseries1 < TIMEOUT_VAL]
    tseries1 = tseries1.sort_values()
    tseries1 = pd.Series(tseries1.tolist())
    tseries1 = tseries1[start:]

    tseries2 = tseries2[tseries2 < TIMEOUT_VAL]
    tseries2 = tseries2.sort_values()
    tseries2 = pd.Series(tseries2.tolist())
    tseries2 = tseries2[start:]

    concat.insert(0, "VBS({0})".format(",".join(legend1)), tseries1)
    concat.insert(0, "VBS({0})".format(",".join(legend2)), tseries2)

    inc = int((20023 - start) / 10)
    plt = concat.plot.line(xticks=range(start, 20023, inc), figsize=(15, 6), grid=True, fontsize=10, lw=3)
    plt.set_xlabel("instances", fontsize=20)
    plt.set_ylabel("runtime [s]", fontsize=20)
    plt.legend(prop={"size": 12})
    plt.figure.savefig("/home/fig-vbs.pdf", dpi=1000)
    print(plt)

# generate evaluation
def gen_evaluation(df, main_tool, all_tools, timeout_time=120, benchmark_name=None):

    #print(f"time:  {datetime.datetime.now()}")
    print(f"Benchmark: {benchmark_name}")
    print(f"# of formulae: {len(df)}")

    summary_times = dict()
    for col in df.columns:
        if re.search('-result$', col):
            summary_times[col] = dict()
            df[col] = df[col].str.strip()
            summary_times[col]['unknowns'] = df[df[col] == "unknown"].shape[0] #[df[col] == "unknown"].shape[0]

    # Remove unknowns
    df = df.drop(df[df[main_tool.value + "-result"] == "unknown"].index)

    for col in df.columns:
        if re.search('-runtime$', col):
            timeouts_num = df[col].isna().sum()
            time_sum = df[col].sum()
            summary_times[col] = dict()
            summary_times[col]['sum'] = time_sum
            summary_times[col]['sum_with_timeouts'] = time_sum + timeout_time * timeouts_num
            summary_times[col]['max'] = df[col].max()
            summary_times[col]['min'] = df[col].min()
            summary_times[col]['mean'] = df[col].mean()
            summary_times[col]['median'] = df[col].median()
            summary_times[col]['std'] = df[col].std()
            summary_times[col]['timeouts'] = timeouts_num

    df_summary_times = pd.DataFrame(summary_times).transpose()



    tab_interesting = []
    for i in all_tools:
        row = df_summary_times.loc[i.value + '-runtime']
        unknown_row = dict(df_summary_times.loc[i.value + '-result'])
        row_dict = dict(row)
        row_dict.update({'name': i.value})
        tab_interesting.append([row_dict['name'],
                                # row_dict['min'],
                                row_dict['sum'],
                                row_dict['sum_with_timeouts'],
                                row_dict['max'],
                                row_dict['mean'],
                                row_dict['median'],
                                row_dict['std'],
                                row_dict['timeouts'],
                                unknown_row["unknowns"]])

    headers = ["method", "sum", "sum with timeouts", "max", "mean", "median", "std. dev", "timeouts", "unknowns"]
    print("Table 1: " + benchmark_name)
    print(tab.tabulate(tab_interesting, headers=headers, tablefmt="github"))
    print()
    table_to_file(tab_interesting, headers=headers, out_file=f"table1-{benchmark_name}")

    tab_basic_time = []
    for i in all_tools:
        row = df_summary_times.loc[i.value + '-runtime']
        unknown_row = dict(df_summary_times.loc[i.value + '-result'])
        row_dict = dict(row)
        row_dict.update({'name': i.value})
        tab_basic_time.append([
            row_dict['name'],
            row_dict['timeouts'],
            row_dict['sum_with_timeouts'],
            row_dict['sum'],
        ])

    headers_basic_time = ["method", "T/Os", "time", "time-T/Os"]
    print("Table basic time: " + benchmark_name)
    print(tab.tabulate(tab_basic_time, headers=headers_basic_time, tablefmt="github"))
    print()
    table_to_file(tab_basic_time, headers=headers_basic_time, out_file=f"table-basic-time-{benchmark_name}")

    # sanitizing NAs
    for col in df.columns:
        if re.search('-runtime$', col):
            df[col].fillna(TIMEOUT_VAL, inplace=True)
            df.loc[df[col] < TIME_MIN, col] = TIME_MIN  # to remove 0 (in case of log graph)


    # comparing wins/loses
    compare_methods = []
    for t in all_tools:
      if t == main_tool:
        continue
      compare_methods.append((main_tool.value + "-runtime", t.value + "-runtime"))
      
    
    # compare_methods = [("noodler-runtime", "z3-runtime"),
    #                    ("noodler-runtime", "cvc4-runtime")
    #                   ]

    tab_wins = []
    for left, right in compare_methods:
        left_over_right = df[df[left] < df[right]]
        right_timeouts = left_over_right[left_over_right[right] == TIMEOUT_VAL]

        right_over_left = df[df[left] > df[right]]
        left_timeouts = right_over_left[right_over_left[left] == TIMEOUT_VAL]

        tab_wins.append([right.rsplit('-', 1)[0], len(left_over_right), len(right_timeouts), len(right_over_left), len(left_timeouts)])

    #benchmark_clean_names = { full_name : full_name.split("/")[-2] for full_name in FILES }
    #df.benchmark = df.benchmark.map(benchmark_clean_names)

    headers_wins = ["method", "wins", "wins-timeouts", "loses", "loses-timeouts"]
    print("Table 2: " + benchmark_name)
    print(tab.tabulate(tab_wins, headers=headers_wins, tablefmt="github"))
    table_to_file(tab_wins, headers_wins, f"table2-{benchmark_name}")
    print()

    #print("##############    other claimed results    ###############")

    ############# the best solution ##########
    # df['other_min-runtime'] = df[
    #     ['cvc4-runtime',]].min(axis=1)


    to_cmp2 = []
    for t in all_tools:
      if t == main_tool:
        continue
      to_cmp2.append({'x': main_tool.value, 'y': t.value,
          #'xname': Tool.noodler.value[:Tool.noodler.value.rfind("-")] ,
          'xname': "Tool",
          'yname': t.value,
          'max': TIMEOUT_VAL, 'tickCount': 3})
      
    # to_cmp2 = [{'x': "noodler", 'y': "cvc4",
    #             'xname': 'Noodler', 'yname': 'CVC4',
    #             'max': TIMEOUT_VAL, 'tickCount': 3},
    #            {'x': "noodler", 'y': "z3",
    #             'xname': 'Noodler', 'yname': 'Z3',
    #             'max': TIMEOUT_VAL, 'tickCount': 3}
    #           ]

    # add fields where not present
    for params in to_cmp2:
        if 'xname' not in params:
            params['xname'] = None
        if 'yname' not in params:
            params['yname'] = None
        if 'max' not in params:
            params['max'] = TIMEOUT_VAL
        if 'tickCount' not in params:
            params['tickCount'] = 5
        if 'filename' not in params:
            params['filename'] = "graphs/fig_"
            if benchmark_name:
                params['filename'] += benchmark_name + "_"

            params['filename'] += params['x'] + "_vs_" + params['y'] + ".pdf"

    size = 8
    plot_list = [
        ( params['x'],
          params['y'],
          params['filename'],
          scatter_plot(
              df,
              xcol=params['x'] + '-runtime',
              ycol=params['y'] + '-runtime',
              xname=params['xname'], yname=params['yname'],
              domain=[TIME_MIN, params['max']],
              tickCount=params['tickCount'],
              log=True, width=size, height=size
          )
        )
        for params in to_cmp2]
    plot_list += [
    ( params['x'],
      params['y'],
      params['filename'].split('.')[0] + "_legend.pdf",
      scatter_plot(
          df,
          xcol=params['x'] + '-runtime',
          ycol=params['y'] + '-runtime',
          xname=params['xname'], yname=params['yname'],
          domain=[TIME_MIN, params['max']],
          tickCount=params['tickCount'],
          show_legend=True,
          log=True, width=size, height=size
      )
    )
    for params in to_cmp2]

    #print("\n\n")
    #print("Generating plots...")
    for x, y, filename, plot in plot_list:
        if plot:
            #filename = f"plots/{out_prefix}_{filename}.pdf"
            #print(f"plotting x: {x}, y: {y}... saving to {filename}")
            # plot.save(filename, scale_factor=2)
            plot.save(filename=filename, dpi=1000)
            #print(plot)

    # return benchmarks solvable only by 'engine'
    def only_solves(df, engine):
        # select those where engine finishes
        res = df[df[engine + '-runtime'] != TIMEOUT_VAL]
        for col in res.columns:
            if re.search('-runtime$', col) and not re.search(engine, col):
                res = res[res[col] == TIMEOUT_VAL]

        return res


    # engines = ["z3",
    #            "cvc4",
    #            "noodler"
    #           ]

    #for i in all_tools:
        #i_only_solves = only_solves(df, i.value)
        #print(f"only {i} = " + str(len(i_only_solves)))
        #if len(i_only_solves) > 0:
        #    print()
        #    print(tab.tabulate(i_only_solves, headers='keys'))
        #    print()

    def none_solves(df):
        # select those where engine finishes
        res = df
        for col in res.columns:
            if re.search('-runtime$', col):
                res = res[res[col] == TIMEOUT_VAL]

        return res

    #unsolvable = none_solves(df)
    #print("unsolvable: " + str(len(unsolvable)))
    #print(tab.tabulate(unsolvable, headers='keys'))
    #print("\n\n\n\n\n")


def create_dfs(files, noodler_version, noodler_underapprox_version):
    dfs = dict()
    dfs_normal = dict()
    dfs_underapprox = {}
    for file in files:
        benchmark_name = file.parent.name
        df = read_file(file)
        df["benchmark"] = benchmark_name
        if benchmark_name in ["leetcode"]:
            df["z3-noodler-common-runtime"] = df[noodler_version.value + "-runtime"]
            df["z3-noodler-common-result"] = df[noodler_version.value + "-result"]
            #dfs_underapprox[benchmark_name] = df
            dfs_normal[benchmark_name] = df
        if benchmark_name in ["kaluza"]:
            df["z3-noodler-common-runtime"] = df[noodler_underapprox_version.value + "-runtime"]
            df["z3-noodler-common-result"] = df[noodler_underapprox_version.value + "-result"]
            dfs_underapprox[benchmark_name] = df
        else:
            df["z3-noodler-common-runtime"] = df[noodler_version.value + "-runtime"]
            df["z3-noodler-common-result"] = df[noodler_version.value + "-result"]
            dfs_normal[benchmark_name] = df
        dfs[benchmark_name] = df
    df_normal = pd.concat(dfs_normal)
    sanity_check(df_normal)
    dfs_normal["kaluza"] = dfs["kaluza"]
    df_all = pd.concat(dfs_normal)
    df_underapprox = pd.concat(dfs_underapprox)

    return dfs, df_all, df_normal, df_underapprox



class Benchmark(enum.Enum):
    slog = "slog"
    slent = "slent"
    norn = "norn"
    leetcode = "leetcode"
    sygus_qgen = "sygus_qgen"
    kaluza = "kaluza"


BENCHMARKS = [
    "slog",
    "slent",
    "norn",
    "leetcode",
    "sygus_qgen",
    "kaluza",
]

BENCHMARKS_FOLDER_PATH = pathlib.Path("../smt-string-bench-results/")
BENCHMARKS_DATA_FILE_NAME = "to120.csv"

FILES = [BENCHMARKS_FOLDER_PATH / benchmark_name / BENCHMARKS_DATA_FILE_NAME for benchmark_name in BENCHMARKS]

class Tool(enum.Enum):
    noodler = "z3-noodler-9f5e602"
    noodler_underapprox = "z3-noodler-9f5e602-underapprox"
    noodler_common = "z3-noodler-common"
    cvc5 = "cvc5"
    z3 = "z3"
    z3_str_re = "z3strRE"
    z3_trau = "z3-trau"
    z3_str_4 = "z3str4"
    ostrich = "ostrich"


def generate_cactus_plot_csvs(dfs, tools_to_print: list[Tool], tools_for_virtual_best_solver: list[Tool], benchmarks: list[Benchmark], file_name: str):
    new_dfs = {}
    benchmark_names = [benchmark.value for benchmark in benchmarks]
    for benchmark, df in dfs.items():
        if benchmark not in benchmark_names:
            continue
        new_dfs[benchmark] = df
    dfs_all = pd.concat(new_dfs)

    # Add virtual best solver.
    tool_runtime_names = [f"{tool.value}-runtime" for tool in tools_for_virtual_best_solver]
    df_runtimes = dfs_all.loc[:, tool_runtime_names]
    dfs_all["virtual-best-runtime"] = np.nanmin(df_runtimes, axis=1)

    tools_to_print_columns = [f"{tool.value}-runtime" for tool in tools_to_print]
    tools_to_print_columns.append("virtual-best-runtime")
    dfs_tools = dfs_all[tools_to_print_columns].reset_index(drop=True)
    #print(dfs_tools)
    for col in dfs_tools:
        #print(col)
        #print(dfs_tools[col])
        #print(dfs_tools[col].sort_values(ignore_index=True))
        dfs_tools[col] = dfs_tools[col].sort_values(ignore_index=True)
    #print()
    dfs_tools.to_csv(f"csvs/cactus_plot_{file_name}.csv", index=False)

    return dfs_tools



dfs, df_all, df_normal, df_underapprox = create_dfs(FILES, Tool.noodler, Tool.noodler_underapprox)

# Generate CSVs for cactus plot.
df_cactus = generate_cactus_plot_csvs(dfs,
                          tools_to_print=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4, Tool.ostrich],
                          tools_for_virtual_best_solver=[Tool.cvc5, Tool.z3],
                          benchmarks=[Benchmark.slog, Benchmark.norn, Benchmark.slent, Benchmark.sygus_qgen],
                          file_name="cvc5_z3")
generate_cactus_plot(df_cactus, "quick_cvc5_z3_start_0", 0, 5000)
df_cactus = generate_cactus_plot_csvs(dfs,
                          tools_to_print=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4, Tool.ostrich],
                          tools_for_virtual_best_solver=[Tool.noodler_common, Tool.cvc5, Tool.z3],
                          benchmarks=[Benchmark.slog, Benchmark.norn, Benchmark.slent, Benchmark.sygus_qgen],
                          file_name="cvc5_z3_noodler")
generate_cactus_plot(df_cactus, "quick_cvc5_z3_noodler_start_0", 0, 5000)


df_cactus = generate_cactus_plot_csvs(dfs,
                          tools_to_print=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4, Tool.ostrich],
                          tools_for_virtual_best_solver=[Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4, Tool.ostrich],
                          benchmarks=[Benchmark.slog, Benchmark.norn, Benchmark.slent, Benchmark.sygus_qgen, Benchmark.leetcode, Benchmark.kaluza],
                          file_name="all_without_noodler")
generate_cactus_plot(df_cactus, "all_cvc5_z3_start_0", 0, 27_000)
generate_cactus_plot(df_cactus, "all_cvc5_z3_start_15k", 15_000, 27_000)
generate_cactus_plot(df_cactus, "all_cvc5_z3_start_21k", 21_000, 27_000)
df_cactus = generate_cactus_plot_csvs(dfs,
                          tools_to_print=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4, Tool.ostrich],
                          tools_for_virtual_best_solver=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4, Tool.ostrich],
                          benchmarks=[Benchmark.slog, Benchmark.norn, Benchmark.slent, Benchmark.sygus_qgen, Benchmark.leetcode, Benchmark.kaluza],
                          file_name="all_with_noodler")
generate_cactus_plot(df_cactus, "all_cvc5_z3_noodler_start_0", 0, 27_000)
generate_cactus_plot(df_cactus, "all_cvc5_z3_noodler_start_15k", 15_000, 27_000)
generate_cactus_plot(df_cactus, "all_cvc5_z3_noodler_start_21k", 21_000, 27_000)

exit()


with open("statistics", "w+") as out_file:
    out_stream = contextlib.redirect_stdout(out_file)

    with out_stream:
        other_tools = [Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_trau, Tool.z3_str_4]
        all_tools = [Tool.noodler] + other_tools
        all_tools_common = [Tool.noodler_common] + other_tools
        all_tools_underapprox = [Tool.noodler_underapprox] + other_tools
        gen_evaluation(df_normal.loc[~df_normal["benchmark"].isin(["leetcode"])], Tool.noodler, all_tools + [Tool.ostrich], benchmark_name="quick")
        gen_evaluation(df_normal, Tool.noodler, all_tools + [Tool.ostrich], benchmark_name="normal_all")
        gen_evaluation(df_underapprox, Tool.noodler_underapprox, all_tools_underapprox, benchmark_name="underapprox")
        for benchmark in BENCHMARKS:
            if benchmark in ["kaluza"]:
                gen_evaluation(dfs[benchmark], Tool.noodler_underapprox, all_tools_underapprox, benchmark_name=benchmark + "_underapprox")
            elif benchmark in ["leetcode"]:
                gen_evaluation(dfs[benchmark], Tool.noodler, all_tools + [Tool.ostrich], benchmark_name=benchmark)
            else:
                gen_evaluation(dfs[benchmark], Tool.noodler, all_tools + [Tool.ostrich], benchmark_name=benchmark)

        gen_evaluation(df_all, Tool.noodler_common, all_tools_common, benchmark_name="all")

        # Evaluate experiments for OSTRICH.
        gen_evaluation(df_all.loc[~df_all["benchmark"].isin(["kaluza"])], Tool.noodler_common, [Tool.noodler_common, Tool.ostrich], benchmark_name="all_ostrich")

        # Evaluate experiments for Z3-trau.
        gen_evaluation(df_all.loc[~df_all["benchmark"].isin(["norn", "slent"])], Tool.noodler_common, all_tools_common, benchmark_name="all_trau")





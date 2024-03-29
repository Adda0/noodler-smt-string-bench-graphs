#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""z3-noodler-eval.ipynb

Generate tables and graphs for Z3-Noodler experiments.
"""
import contextlib
import datetime
import itertools
import pathlib
import enum
import sys

import numpy as np
import pandas as pd
import re as re
import seaborn as sns

import pylab
import tabulate as tab
import plotnine as p9
import matplotlib as mplt
import math
import mizani.formatters as mizani
import warnings

from z3_noodler_config import *

warnings.filterwarnings('ignore')

BENCHMARKS_FOLDER_PATH = pathlib.Path("../smt-string-bench-results/")
BENCHMARKS_DATA_FILE_NAME = "to120.csv"
FILES = [BENCHMARKS_FOLDER_PATH / benchmark_name / BENCHMARKS_DATA_FILE_NAME for benchmark_name in Benchmark.values()]

def get_powerset(iterable):
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(1, len(s) + 1))


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
            #df_loc.loc[df_loc[tool_result_name].isin(['ERR', 'TO', 'unknown']), col] = np.nan
            df_loc.loc[df_loc[tool_result_name].isin(['ERR', 'TO']), col] = np.nan
            df_loc[col] = df_loc[col].astype(float)

    return df_loc


# For printing scatter plots
def scatter_plot(df, xcol, ycol, domain, xname=None, yname=None, log=False, width=6, height=6, clamp=True, tickCount=5, show_legend=False):
    assert len(domain) == 2

    POINT_SIZE = 5
    DASH_PATTERN = (0, (6, 2))

    if xname is None:
        xname = xcol
    if yname is None:
        tool_names = {
            "cvc5": "cvc5",
            "z3": "Z3",
            "z3strRE": "Z3str3RE",
            "z3-trau": "Z3-Trau",
            "z3str4": "Z3str4",
            "ostrich": "OSTRICH"
        }
        yname = tool_names[ycol]

    # formatter for axes' labels
    ax_formatter = mizani.custom_format('{:n}')

    if clamp:  # clamp overflowing values if required
        df = df.copy(deep=True)
        df.loc[df[xcol] > domain[1], xcol] = domain[1]
        df.loc[df[ycol] > domain[1], ycol] = domain[1]

    df_ordered = df.assign(benchmark=pd.Categorical(df['benchmark'], Benchmark.values()))

    # generate scatter plot
    scatter = p9.ggplot(df_ordered) \
        + p9.aes(x=xcol, y=ycol, color="benchmark") \
        + p9.geom_point(size=POINT_SIZE, na_rm=True, show_legend=show_legend) \
        + p9.labs(x=xname, y=yname) \
        + p9.theme(legend_key_width=2) \
        + p9.scale_color_brewer(type="qual", palette="Dark2", name="Benchmark", drop=True, direction=-1)
    # + p9.geom_jitter(width=0.2, height=0.2, size=POINT_SIZE) \

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
    if show_legend:
        scatter += p9.theme(figure_size=(width + 2.3, height))
    else:
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


def generate_cactus_plot(df, file_name: str, start: int = 0, end: int = 27000, logarithmic_y_axis: bool = True):
    concat = pd.DataFrame()

    for t in df.columns:
        #print(df[t])
        tseries1 = pd.Series(df[t].tolist())
        tseries1 = tseries1[start:]
        concat.insert(0, t.rsplit('-', 1)[0], tseries1)

    plt = concat.plot.line(grid=True, fontsize=10, lw=2, figsize=(10, 3))
    ticks = np.linspace(start, end, 5, dtype=int)
    # labels_ticks = [end - tick for tick in ticks]
    labels_ticks = ticks
    # plt.set_xticks(ticks, labels_ticks)
    plt.set_xticks(ticks)
    plt.set_xlim([start, end])
    if logarithmic_y_axis:
        plt.set_yscale('log')
    plt.set_xlabel("Instances", fontsize=16)
    plt.set_ylabel("Runtime [s]", fontsize=16)
    plt.get_legend().remove()
    # plt.legend(loc='upper right',prop={"size": 12})
    # plt.legend(bbox_to_anchor=(1.04, 1), loc='upper left')
    # plt.axvline(x=end)
    figlegend = pylab.figure(figsize=(4,4))
    figlegend.legend(plt.get_children(), concat.columns, loc='center', frameon=False)
    figlegend.savefig(f"graphs/fig-cactus-{file_name}-legend.pdf", dpi=1000, bbox_inches='tight')
    plt.figure.savefig(f"graphs/fig-cactus-{file_name}.pdf", dpi=1000, bbox_inches='tight')


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


def gen_evaluation(df, main_tool, all_tools, timeout_time=120, benchmark_name=None):
    """Generate multiple types of evaluations for passed data."""

    #print(f"time:  {datetime.datetime.now()}")
    print(f"Benchmark: {benchmark_name}")
    print(f"# of formulae: {len(df)}")

    summary_times = dict()
    for col in df.columns:
        if re.search('-result$', col):
            summary_times[col] = dict()
            df[col] = df[col].str.strip()
            summary_times[col]['unknowns'] = df[df[col] == "unknown"].shape[0] #[df[col] == "unknown"].shape[0]
            summary_times[col]['errors'] = df[df[col] == "ERR"].shape[0] #[df[col] == "unknown"].shape[0]
            summary_times[col]['timeouts'] = df[df[col] == "TO"].shape[0] #[df[col] == "unknown"].shape[0]

    #print(summary_times)

    # Remove unknowns
    df = df.drop(df[df[main_tool.value + "-result"] == "unknown"].index)

    for col in df.columns:
        if re.search('-runtime$', col):
            col_tool_name = col.rsplit('-', 1)[0]
            col_result_name = f"{col_tool_name}-result"
            timeouts_err_unknown_num = df[col].isna().sum()
            timeouts_num: int = summary_times[col_result_name]["timeouts"]
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
            summary_times[col]['errors'] = summary_times[col_result_name]["errors"]
            summary_times[col]['unknowns'] = summary_times[col_result_name]["unknowns"]

    #print(summary_times)

    df_summary_times = pd.DataFrame(summary_times).transpose()

    tab_interesting = []
    for i in all_tools:
        row = df_summary_times.loc[i.value + '-runtime']
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
                                row_dict['errors'],
                                row_dict['unknowns']
                               ])

    headers = ["method", "sum", "sum with timeouts", "max", "mean", "median", "std. dev", "timeouts", "errors", "unknowns"]
    print("Table 1: " + benchmark_name)
    print(tab.tabulate(tab_interesting, headers=headers, tablefmt="github"))
    print()
    table_to_file(tab_interesting, headers=headers, out_file=f"table1-{benchmark_name}")

    tab_basic_time = []
    for i in all_tools:
        row = df_summary_times.loc[i.value + '-runtime']
        row_dict = dict(row)
        row_dict.update({'name': i.value})
        tab_basic_time.append([
            row_dict['name'],
            row_dict['timeouts'],
            row_dict['errors'],
            row_dict['unknowns'],
            row_dict['sum_with_timeouts'],
            row_dict['sum'],
        ])
    #pd.DataFrame(tab_basic_time).to_csv("csvs/test.csv")


    headers_basic_time = ["Method", "T/Os", "Errors", "Unknowns", "Time", "Time-T/Os"]
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
          'xname': "Z3-Noodler",
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

    # Generate separate legends. Currently broken.
    #for params in to_cmp2:
    #    # fig = sns.scatterplot(data=df, x=params['x'] + '-runtime', y=params['y'] + '-runtime', hue="benchmark", style=)
    #    fig = mplt.pyplot.scatter(x=df[params['x'] + '-runtime'], y=df[params['y'] + '-runtime'])

    #    figlegend = pylab.figure(figsize=(10,10))
    #    labels = df["benchmark"].unique().tolist()
    #    labels.sort()

    #    figlegend.legend(fig.get_children(),
    #                     labels,
    #                     # scatterpoints=1,
    #                     loc='center',
    #                     ncol=3,
    #                     fontsize=8)
    #    figlegend.legend(fig.get_children(), labels, loc='center', frameon=False)
    #    figlegend.savefig(f"{params['filename'].split('.')[0] + '_legend_separate.pdf'}", dpi=1000)

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


def generate_cactus_plot_csvs(dfs, tools_to_print: list[Tool], tools_for_virtual_best_solver: list[Tool],
                              benchmarks: list[Benchmark], csv_file_name: str,
                              tools_for_virtual_best_solver_improvement: list[Tool] | None = None):
    new_dfs = {}
    benchmark_names = [benchmark.value for benchmark in benchmarks]
    for benchmark, df in dfs.items():
        if benchmark not in benchmark_names:
            continue
        new_dfs[benchmark] = df
    dfs_all = pd.concat(new_dfs)

    # Rename Noodler to Tool.
    for col in dfs_all.columns:
        if re.search(r"z3-noodler-common", col):
            col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
            dfs_all.rename(columns={ col: col_split }, inplace=True)

    for col in dfs_all.columns:
        if re.search(r"z3-noodler", col):
            col_split = re.sub(r"z3-noodler", "Z3-Noodler", col)
            dfs_all.rename(columns={ col: col_split }, inplace=True)

    tools_names = [tool.value for tool in tools_to_print]
    for i, col in enumerate(tools_names):
        if re.search(r"z3-noodler-common", col):
            col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
            tools_names[i] = col_split
    tools_virtual_names = [tool.value for tool in tools_for_virtual_best_solver]
    for i, col in enumerate(tools_virtual_names):
        if re.search(r"z3-noodler-common", col):
            col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
            tools_virtual_names[i] = col_split

    tools_to_print_columns = [f"{tool}-runtime" for tool in tools_names]

    # Add virtual best solver.
    tool_runtime_names = [f"{tool}-runtime" for tool in tools_virtual_names]
    df_runtimes = dfs_all.loc[:, tool_runtime_names]
    #print(df_runtimes)

    virtual_best_name = '+'.join([tool for tool in tools_virtual_names])
    #print(virtual_best_name)

    dfs_all[f"virtual-{virtual_best_name}-runtime"] = np.nanmin(df_runtimes, axis=1)
    tools_to_print_columns.insert(0, f"virtual-{virtual_best_name}-runtime")


    if tools_for_virtual_best_solver_improvement:
        #for permutation in get_powerset(tools_for_virtual_best_solver):
        for permutation in [tools_for_virtual_best_solver]:
            tools_virtual_names = [tool.value for tool in permutation]
            for i, col in enumerate(tools_virtual_names):
                if re.search(r"z3-noodler-common", col):
                    col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
                    tools_virtual_names[i] = col_split

            improvement_tools = [tool.value for tool in tools_for_virtual_best_solver_improvement]
            for i, col in enumerate(improvement_tools):
                if re.search(r"z3-noodler-common", col):
                    col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
                    improvement_tools[i] = col_split
            tools = [tool for tool in improvement_tools + tools_virtual_names]
            for i, col in enumerate(tools):
                 if re.search(r"z3-noodler-common", col):
                    col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
                    tools[i] = col_split
                 #print(tools[i])
            tool_runtime_names = [f"{tool}-runtime" for tool in tools]
            df_runtimes = dfs_all.loc[:, tool_runtime_names]
            #print(df_runtimes)

            virtual_best_improvement_name = '+'.join(improvement_tools + tools_virtual_names)
            dfs_all[f"virtual-{virtual_best_improvement_name}-runtime"] = np.nanmin(df_runtimes, axis=1)
            tools_to_print_columns.insert(0, f"virtual-{virtual_best_improvement_name}-runtime")

            special_virt_solver_names = [f"{tool.value}-runtime" for tool in [Tool.noodler_common, Tool.cvc5]]
            for i, col in enumerate(special_virt_solver_names):
                if re.search(r"z3-noodler-common", col):
                    col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)
                    special_virt_solver_names[i] = col_split
            virtual_best_improvement_name = '+'.join([f"{tool.value}" for tool in [Tool.noodler_common, Tool.cvc5]])
            # print(dfs_all.columns)
            df_runtimes = dfs_all.loc[:, special_virt_solver_names]
            dfs_all[f"virtual-{virtual_best_improvement_name}-runtime"] = np.nanmin(df_runtimes, axis=1)
            tools_to_print_columns.insert(0, f"virtual-{virtual_best_improvement_name}-runtime")

            # special_virt_solver_names = [f"{tool.value}-runtime" for tool in [Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_4]]
            # for i, col in enumerate(special_virt_solver_names):
            #     if re.search(r"z3-noodler-common", col):
            #         col_split = re.sub(r"z3-noodler-common", "Tool", col)
            #         special_virt_solver_names[i] = col_split
            # virtual_best_improvement_name = '+'.join([f"{tool.value}" for tool in [Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_4]])
            # print(dfs_all.columns)
            # df_runtimes = dfs_all.loc[:, special_virt_solver_names]
            # dfs_all[f"virtual-{virtual_best_improvement_name}-runtime"] = np.nanmin(df_runtimes, axis=1)
            # tools_to_print_columns.insert(0, f"virtual-{virtual_best_improvement_name}-runtime")


    dfs_tools = dfs_all[tools_to_print_columns].reset_index(drop=True)

    # Rename Noodler to Tool.
    for col in dfs_tools.columns:
        if re.search(r"z3-noodler-common", col):
            col_split = re.sub(r"z3-noodler-common", "Z3-Noodler", col)

            dfs_tools.rename(columns={ col: col_split }, inplace=True)

    #print(dfs_tools)
    for col in dfs_tools:
        #print(col)
        #print(dfs_tools[col])
        #print(dfs_tools[col].sort_values(ignore_index=True))
        dfs_tools[col] = dfs_tools[col].sort_values(ignore_index=True)
        dfs_tools[col] = dfs_tools[col].cumsum()
    #print()

    # Rename Noodler to Tool.
    for col in dfs_tools.columns:
        if re.search(r"virtual-", col):
            col_split = re.sub(r"virtual-", "", col)

            dfs_tools.rename(columns={ col: col_split }, inplace=True)

    for col in dfs_tools.columns:
        if re.search(r"z3strRE", col):
            col_split = re.sub(r"z3strRE", "z3str3RE", col)

            dfs_tools.rename(columns={ col: col_split }, inplace=True)

    dfs_tools.to_csv(f"csvs/cactus_plot_{csv_file_name}.csv", index=False)

    return dfs_tools


def generate_requested_cactus_plots():
    df_cactus = generate_cactus_plot_csvs(
        dfs,
        tools_to_print=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4],
        tools_for_virtual_best_solver=[Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4],
        tools_for_virtual_best_solver_improvement=[Tool.noodler_common],
        benchmarks=Benchmark.items(),
        csv_file_name="all_no_ostrich_trau_improvement_noodler")
    generate_cactus_plot(df_cactus, "mult_virtual_all_no_ostrich_trau_improvement_noodler_start_26k_not_logarithmic", 26_000, 26_558, logarithmic_y_axis=False)
    df_cactus = generate_cactus_plot_csvs(
        dfs,
        tools_to_print=[Tool.noodler_common, Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4],
        tools_for_virtual_best_solver=[Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_str_4],
        tools_for_virtual_best_solver_improvement=[Tool.noodler_common],
        benchmarks=[Benchmark.slog, Benchmark.slent, Benchmark.norn, Benchmark.leetcode, Benchmark.sygus_qgen],
        csv_file_name="no_kaluza_no_ostrich_trau_improvement_noodler")
    generate_cactus_plot(df_cactus, "mult_virtual_no_kaluza_no_ostrich_trau_improvement_noodler_start_6_8k_not_logarithmic", 6_600, 7_126, logarithmic_y_axis=False)

def get_running_longer(df, tool: Tool, threshold: int = TIMEOUT, benchmarks: list[Benchmark] | None = None,
                       include_nan: bool = True):
    """Filter instances running longer than threshold, optionally include NaN runtime values."""
    if benchmarks:
        df = df.loc[df["benchmark"].isin([benchmark.value for benchmark in benchmarks])]
    df = df.loc[(df[f"{tool.value}-runtime"] >= threshold) | (include_nan & df[f"{tool.value}-runtime"].isnull())]
    return df
#print(df_all)
#benchmarks = ["regex/to120_nomembership.csv"]
#df = get_running_longer(df_all, NOODLER, 50, benchmarks)
#df = get_running_longer(df_all, NOODLER, 50, benchmarks, include_nan=False)
#df



dfs, df_all, df_normal, df_underapprox = create_dfs(FILES, Tool.noodler, Tool.noodler_underapprox)


if __name__ == "__main__":
    # Generate CSVs for cactus plot.
    generate_requested_cactus_plots()

    # Generate statistics, tables and scatter graphs.
    with open("statistics", "w+") as out_file:
        out_stream = contextlib.redirect_stdout(out_file)

        with out_stream:
            other_tools = [Tool.cvc5, Tool.z3, Tool.z3_str_re, Tool.z3_trau, Tool.z3_str_4, Tool.ostrich]
            all_tools = [Tool.noodler] + other_tools
            all_tools_common = [Tool.noodler_common] + other_tools
            all_tools_underapprox = [Tool.noodler_underapprox] + other_tools
            gen_evaluation(df_normal.loc[~df_normal["benchmark"].isin(["leetcode"])], Tool.noodler, all_tools, benchmark_name="quick")
            gen_evaluation(df_normal, Tool.noodler, all_tools, benchmark_name="normal_all")
            gen_evaluation(df_underapprox, Tool.noodler_underapprox, all_tools_underapprox, benchmark_name="underapprox")
            for benchmark in Benchmark.values():
                if benchmark in ["kaluza"]:
                    gen_evaluation(dfs[benchmark], Tool.noodler_underapprox, all_tools_underapprox, benchmark_name=benchmark + "_underapprox")
                elif benchmark in ["leetcode"]:
                    gen_evaluation(dfs[benchmark], Tool.noodler, all_tools, benchmark_name=benchmark)
                else:
                    gen_evaluation(dfs[benchmark], Tool.noodler, all_tools, benchmark_name=benchmark)

            gen_evaluation(df_all, Tool.noodler_common, all_tools_common, benchmark_name="all")

            # Evaluate experiments for OSTRICH.
            gen_evaluation(df_all.loc[~df_all["benchmark"].isin([Benchmark.slog.value])], Tool.noodler_common, [Tool.noodler_common, Tool.ostrich], benchmark_name="all_ostrich")

            # Evaluate experiments for Z3-trau.
            gen_evaluation(df_all.loc[~df_all["benchmark"].isin(["norn", "slent"])], Tool.noodler_common, all_tools_common, benchmark_name="all_trau")

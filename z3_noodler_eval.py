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
        na_values=['ERR', 'TO', 'MISSING'],
        # na_values=['TO'],
        )
    return df_loc


# For printing scatter plots
def scatter_plot(df, xcol, ycol, domain, xname=None, yname=None, log=False, width=6, height=6, clamp=True, tickCount=5):
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
    scatter += p9.geom_point(size=POINT_SIZE, na_rm=True)
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
    scatter += p9.theme(legend_text=p9.element_text(size=12))

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
    with open(f"plots/{out_file}.tex", mode='w') as fl:
        print(tab.tabulate(table, headers=headers, tablefmt="latex"), file=fl)

def sanity_check(df):
    """Sanity check"""
    pt = df[["name", "z3-result", "cvc5-result", NOODLER+"-result"]]
    pt = pt.dropna()
    pt = pt[(pt["cvc5-result"] != pt[NOODLER+"-result"]) | (pt["z3-result"] != pt[NOODLER+"-result"])]
    return pt


# generate evaluation
def gen_evaluation(df, main_tool, all_tools, benchmark_name=None):

    #print(f"time:  {datetime.datetime.now()}")
    print(f"# of formulae: {len(df)}")

    summary_times = dict()
    for col in df.columns:
        if re.search('-result$', col):
            summary_times[col] = dict()
            df[col] = df[col].str.strip()
            summary_times[col]['unknowns'] = df[df[col] == "unknown"].shape[0] #[df[col] == "unknown"].shape[0]

    # Remove unknowns
    df = df.drop(df[df[main_tool + "-result"] == "unknown"].index)

    for col in df.columns:
        if re.search('-runtime$', col):
            summary_times[col] = dict()
            summary_times[col]['sum'] = df[col].sum()
            summary_times[col]['max'] = df[col].max()
            summary_times[col]['min'] = df[col].min()
            summary_times[col]['mean'] = df[col].mean()
            summary_times[col]['median'] = df[col].median()
            summary_times[col]['std'] = df[col].std()
            summary_times[col]['timeouts'] = df[col].isna().sum()

    df_summary_times = pd.DataFrame(summary_times).transpose()



    tab_interesting = []
    for i in all_tools:
        row = df_summary_times.loc[i + '-runtime']
        unknown_row = dict(df_summary_times.loc[i + '-result'])
        row_dict = dict(row)
        row_dict.update({'name': i})
        tab_interesting.append([row_dict['name'],
                                # row_dict['min'],
                                row_dict['sum'],
                                row_dict['max'],
                                row_dict['mean'],
                                row_dict['median'],
                                row_dict['std'],
                                row_dict['timeouts'],
                                unknown_row["unknowns"]])

    headers = ["method", "sum", "max", "mean", "median", "std. dev", "timeouts", "unknowns"]
    print("Table 1: " + benchmark_name)
    print(tab.tabulate(tab_interesting, headers=headers, tablefmt="github"))
    print()

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
      compare_methods.append((main_tool + "-runtime", t + "-runtime"))
      
    
    # compare_methods = [("noodler-runtime", "z3-runtime"),
    #                    ("noodler-runtime", "cvc4-runtime")
    #                   ]

    tab_wins = []
    for left, right in compare_methods:
        left_over_right = df[df[left] < df[right]]
        right_timeouts = left_over_right[left_over_right[right] == TIMEOUT_VAL]

        right_over_left = df[df[left] > df[right]]
        left_timeouts = right_over_left[right_over_left[left] == TIMEOUT_VAL]

        tab_wins.append([right, len(left_over_right), len(right_timeouts), len(right_over_left), len(left_timeouts)])

    #benchmark_clean_names = { full_name : full_name.split("/")[-2] for full_name in FILES }
    #df.benchmark = df.benchmark.map(benchmark_clean_names)

    headers_wins = ["method", "wins", "wins-timeouts", "loses", "loses-timeouts"]
    print("Table 2: " + benchmark_name)
    print(tab.tabulate(tab_wins, headers=headers_wins, tablefmt="github"))
    #table_to_file(tab_wins, headers_wins, out_prefix + "_table1right")
    print()

    #print("##############    other claimed results    ###############")

    ############# the best solution ##########
    # df['other_min-runtime'] = df[
    #     ['cvc4-runtime',]].min(axis=1)


    to_cmp2 = []
    for t in all_tools:
      if t == main_tool:
        continue
      to_cmp2.append({'x': main_tool, 'y': t,
                'xname': NOODLER[:NOODLER.rfind("-")], 'yname': t,
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
    plot_list = [(params['x'],
                  params['y'],
                  params['filename'],
                  scatter_plot(df,
                               xcol=params['x'] + '-runtime',
                               ycol=params['y'] + '-runtime',
                               xname=params['xname'], yname=params['yname'],
                               domain=[TIME_MIN, params['max']],
                               tickCount=params['tickCount'],
                               log=True, width=size, height=size)) for params
                 in to_cmp2]

    #print("\n\n")
    #print("Generating plots...")
    for x, y, filename, plot in plot_list:
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

    for i in all_tools:
        i_only_solves = only_solves(df, i)
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

    unsolvable = none_solves(df)
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
            df["z3-noodler-common-runtime"] = df[noodler_version + "-runtime"]
            df["z3-noodler-common-result"] = df[noodler_version + "-result"]
            dfs_underapprox[benchmark_name] = df
            dfs_normal[benchmark_name] = df
        if benchmark_name in ["kaluza"]:
            df["z3-noodler-common-runtime"] = df[noodler_underapprox_version + "-runtime"]
            df["z3-noodler-common-result"] = df[noodler_underapprox_version + "-result"]
            dfs_underapprox[benchmark_name] = df
        else:
            df["z3-noodler-common-runtime"] = df[noodler_version + "-runtime"]
            df["z3-noodler-common-result"] = df[noodler_version + "-result"]
            dfs_normal[benchmark_name] = df
        dfs[benchmark_name] = df
    df_normal = pd.concat(dfs_normal)
    sanity_check(df_normal)
    dfs_normal["kaluza"] = dfs["kaluza"]
    df_all = pd.concat(dfs_normal)
    df_underapprox = pd.concat(dfs_underapprox)

    return dfs, df_all, df_normal, df_underapprox


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

NOODLER_COMMON = "z3-noodler-common"
NOODLER = "z3-noodler-69838f6"
NOODLER_UNDERAPPROX = "z3-noodler-69838f6-underapprox"
# NOODLER_OLD = "z3-noodler-bab4579"
# NOODLER_OLD = "noodler"
NOODLER_OLD = ""

dfs, df_all, df_normal, df_underapprox = create_dfs(FILES, NOODLER, NOODLER_UNDERAPPROX)

#if NOODLER_OLD:
#  gen_evaluation(df_normal, NOODLER, [NOODLER, NOODLER_OLD, "cvc5", "z3"])
#else:
#  gen_evaluation(df_normal, NOODLER, [NOODLER, "cvc5", "z3"])

with open("statistics", "w+") as out_file:
    out_stream = contextlib.redirect_stdout(out_file)

    with out_stream:
        gen_evaluation(df_normal.loc[~df_normal["benchmark"].isin(["leetcode"])], NOODLER, [NOODLER, "cvc5", "z3"], benchmark_name="quick")
        gen_evaluation(df_normal, NOODLER, [NOODLER, "cvc5", "z3"], benchmark_name="normal_all")
        gen_evaluation(df_underapprox, NOODLER_UNDERAPPROX, [NOODLER_UNDERAPPROX, "cvc5", "z3"], benchmark_name="kaluza_leetcode_underapprox")
        for benchmark in BENCHMARKS:
            if benchmark in ["kaluza"]:
                gen_evaluation(dfs[benchmark], NOODLER_UNDERAPPROX, [NOODLER_UNDERAPPROX, "cvc5", "z3"], benchmark_name=benchmark + "_underapprox")
            elif benchmark in ["leetcode"]:
                gen_evaluation(dfs[benchmark], NOODLER_UNDERAPPROX, [NOODLER_UNDERAPPROX, "cvc5", "z3"], benchmark_name=benchmark + "_underapprox")
                gen_evaluation(dfs[benchmark], NOODLER, [NOODLER, "cvc5", "z3"], benchmark_name=benchmark)
            else:
                gen_evaluation(dfs[benchmark], NOODLER, [NOODLER, "cvc5", "z3"], benchmark_name=benchmark)

        gen_evaluation(df_all, NOODLER_COMMON, [NOODLER_COMMON, "cvc5", "z3"], benchmark_name="all")  # FIXME: Evaluate Noodler_underapprox for kaluza.




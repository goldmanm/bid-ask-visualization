#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script saves bid and ask data for specified ETFs to files for each day
during market open hours.

It assumes the computer is at US East Coast Time.

@author: mark
"""

import os

import pandas as pd
import numpy as np

from itertools import product

import streamlit as st

from bokeh.plotting import figure
from bokeh.models.tools import HoverTool
from bokeh.models import NumeralTickFormatter, DatetimeTickFormatter, Rect, ColumnDataSource, VBar, LabelSet

from streamlit_metrics import metric_row

def display_method_to_choose_etfs(selected_method_choose_dates, all_etfs, etf_data, sl_obj):
    """
    Generates various streamlit options for selecting which ETFs to display.

    Parameters
    ----------
    selected_method_choose_dates : list of str
        Strings of the various methods of selecting ETFs.
    all_etfs : list of str
        List of all ETF tickers.
    etf_data : pd.DataFrame
        Dataframe containing bulk data about ETFs.
    sl_obj : streamlit
        Stremlit object to place the elements.

    Returns
    -------
    selected_etfs : list of str
        List of str tickers chosen by users.

    """
    selected_etfs = all_etfs
    if 'By volume traded' in selected_method_choose_dates:
        selection_data = etf_data['volume (shares/day)']
        log_min = float(np.floor(np.log10(selection_data.min())))
        log_max = float(np.ceil(np.log10(selection_data.max())))
        min_vol, max_vol = sl_obj.slider('Average Volume (shares/day)',
                         min_value=float(log_min),
                         max_value=float(log_max),
                         value=(float(log_min), float(log_max)),
                         step=float(log_min - log_max) / 100,
                         format='10^%.1f'
                         )
        selected = (selection_data >= 10**min_vol) & (selection_data <= 10**max_vol)
        selected_etfs = list(set(selected_etfs) & set(selection_data[selected].index))
    if 'By market cap' in selected_method_choose_dates:
        selection_data = etf_data['net assets (million USD)']
        log_min = float(np.floor(np.log10(selection_data.min())))
        log_max = float(np.ceil(np.log10(selection_data.max())))
        min_vol, max_vol = sl_obj.slider('Market Cap as of 2021-02-21 (million USD)',
                         min_value=float(log_min),
                         max_value=float(log_max),
                         value=(float(log_min), float(log_max)),
                         step=float(log_min - log_max) / 100,
                         format='10^%.1f'
                         )
        selected = (selection_data >= 10**min_vol) & (selection_data <= 10**max_vol)
        selected_etfs = list(set(selected_etfs) & set(selection_data[selected].index))
    if 'Only ESG ETFs' in selected_method_choose_dates:
        esg_etfs = etf_data[etf_data['esg'] == True].index
        selected_etfs = list(set(selected_etfs) & set(esg_etfs))
    if 'choose specific ETFs' in selected_method_choose_dates:
        selected_etfs = sl_obj.multiselect('Which ETFs do you want to look at', list(selected_etfs), ['ESGV','VTI','BND', 'VCEB', 'VSGX'])
    return selected_etfs

def get_averages(data, selected_dates, selected_etfs):
    """
    Obtain average values of various ETFs across the trading day.

    Parameters
    ----------
    data : pd.DataFrame
        data of various days and ETFs.
    selected_dates : list of str
        list of dates in format YYYY-MM-DD.
    selected_etfs : list of str
        list of ETF tickers.

    Returns
    -------
    pd.Series
        Data frame of average values in ETFs at various times during tradiing day.

    """
    potential_columns = product(selected_dates, selected_etfs)
    actual_columns = [x for x in potential_columns if x in data.columns]
    return data[actual_columns].T.groupby(level=['etf']).mean().T

def add_trade_windows(p, t_new, t_old, ymax):
    """
    Add trade windows to plot

    Parameters
    ----------
    p : Bokeh figure
        Figure to add trading windows to.
    t_new : tuple of timestamps
        Starting and ending timestamp of the old trading window.
    t_old : tuple of timestamps
        Starting and ending timestamp of the new trading window.
    ymax : float
        Maxs value to extend trading windows.

    Returns
    -------
    None.

    """
    source = ColumnDataSource(dict(x=[t_old[0]+0.5*(t_old[1]-t_old[0]),t_new[0]+0.5*(t_new[1]-t_new[0])],
                          y=[ymax-0.0002, ymax-0.0002 ],
                          w=[t_old[1]-t_old[0], t_new[1]-t_new[0]],
                          h =[2,2],
                          desc=['Old', 'New']))
    if ymax > 2:
        patch = {'h' : [ (0, ymax), (1, ymax) ],}
        source.patch(patch)
    boxes = Rect(x='x',y='y',width='w', height='h', fill_color='grey', fill_alpha=0.1,
                 line_width=0)
    boxes_select = Rect(x='x',y='y',width='w', height='h', fill_color='grey', fill_alpha=.2,
                 line_width=0)
    box_rend = p.add_glyph(source, boxes)
    box_rend.hover_glyph = boxes_select
    tooltips = [('trade window','@desc')]
    p.add_tools(HoverTool(tooltips=tooltips, renderers=[box_rend]))

def format_plots(p, ymax=None):
    """
    Format bokeh plots for quoted spreads across market times

    Parameters
    ----------
    p : Bokeh figure plot
        Bokeh plot object to format
    ymax : TYPE, optional
        Max yaxis value. The default is None.

    Returns
    -------
    None

    """
    if ymax is None:
        num_formatter='0.00%'
    else:
        num_zeros = int(np.log10(1/ymax)-.4)
        num_formatter = '0.'+''.join(['0' for x in range(num_zeros)])+'%'
    p.yaxis.formatter = NumeralTickFormatter(format=num_formatter)
    p.xaxis.formatter = DatetimeTickFormatter(hours='%H:%M')
    p.xaxis.axis_label = 'Market Time'

    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None
    p.toolbar.autohide = True
    
def make_multi_etf_plot(selected_etfs, selected_dates, t_new, t_old, quoted_spread):
    """
    Make plot with multiple ETF averages

    Parameters
    ----------
    selected_etfs : list of str
        List of ETF tickers
    selected_dates : list of str
        List of dates to obtain averages of. In format YYYY-MM-DD.
    t_new : tuple of timestamps
        Starting and ending timestamp of the old trading window.
    t_old : tuple of timestamps
        Starting and ending timestamp of the new trading window.
    quoted_spread : pd.DataFrame
        Quoted spread data for various times, days, and ETFs.

    Returns
    -------
    p : Bokeh figure
        Plot of multiple ETF averages.

    """
    t_all = t_new + t_old
    average_data = get_averages(quoted_spread, selected_dates, selected_etfs)

    p = figure(plot_width=400, plot_height=400, x_axis_type="datetime",
               toolbar_location='below', title='quoted Bid-Ask Spread for various ETFs',
               x_range=(pd.Timestamp('2021-01-01 9:30'), max(t_all)+pd.Timedelta(hours=1.5)),
               y_range=(0, average_data.max().max()+0.0001))
    #trading windows
    add_trade_windows(p, t_new, t_old, average_data.max().max())

    # etf lines
    renders = []
    for etf in selected_etfs:
        renders.append(p.line(average_data.index, average_data[etf],# set visual properties for selected glyphs
                        hover_color="firebrick",
                        hover_alpha=1,
                        # set visual properties for non-selected glyphs
                        color="grey",
                        alpha=0.5,
                        name=etf))
    tooltips = [('etf','$name'),
                ('time','$x{%H:%M}'),
                ('Bid-Ask spread', '$y{"0.00%"}')]
    formatters = { "$x": "datetime",}
    p.add_tools(HoverTool(tooltips=tooltips, renderers=renders, formatters=formatters))

    format_plots(p, ymax=average_data.max().max()+0.0001)

    return p

def make_single_etf_plot(selected_etf, selected_dates, t_new, t_old, quoted_spread, supress_hover_after= 10000):
    """
    Plots data for a single ETF for multiple days.

    Parameters
    ----------
    selected_etfs : list of str
        List of ETF tickers
    selected_dates : list of str
        List of dates to plot. In format YYYY-MM-DD.
    t_new : tuple of timestamps
        Starting and ending timestamp of the old trading window.
    t_old : tuple of timestamps
        Starting and ending timestamp of the new trading window.
    quoted_spread : pd.DataFrame
        Quoted spread data for various times, days, and ETFs.
    supress_hover_after : int, optional
        Do not show hover functionality if there are more than this number of days. The default is 10000.

    Returns
    -------

    p : Bokeh figure
        Plot of single ETF over various days.
    """
    t_all = t_new + t_old
    average_data = get_averages(quoted_spread, selected_dates, [selected_etf])

    p = figure(plot_width=400, plot_height=400, x_axis_type="datetime",
               toolbar_location='below', title='Quoted spread for {}'.format(selected_etf),
               x_range=(pd.Timestamp('2021-01-01 9:30'), max(t_all)+pd.Timedelta(hours=1.5)),
               y_range=(0, average_data.max().max()+0.0001))
    add_trade_windows(p, t_new, t_old, average_data.max().max())
    # etf lines
    renders = []
    if len(selected_dates) > 1:
        for date in selected_dates:
            try:
                render = p.line(quoted_spread.index, quoted_spread.loc[:,(date,selected_etf)],# set visual properties for selected glyphs
                            hover_color="firebrick",
                            hover_alpha=0.33,
                            color="grey",
                            alpha=0.25,
                            name=date)
            except KeyError:
                continue
            if len(selected_dates) < supress_hover_after:
                renders.append(render)
        average_name = 'average'
    else:
        average_name = selected_dates[0]
    renders.append(p.line(average_data.index, average_data[selected_etf],# set visual properties for selected glyphs
                    hover_color="firebrick",
                    hover_alpha=0.75,
                    color="black",
                    alpha=0.5,
                    name=average_name))
    tooltips = [('date','$name'),
                ('time','$x{%H:%M}'),
                ('Bid-Ask spread', '$y{"0.00%"}')]
    formatters = { "$x": "datetime",}
    p.add_tools(HoverTool(tooltips=tooltips, renderers=renders, formatters=formatters))

    format_plots(p)
    return p
 
def make_bid_ask_plot(selected_etf, selected_date, t_new, t_old, directory):
    """
    Plots bid and ask prices over one trading day for one ETF.

    Parameters
    ----------
    selected_etf : str
        ETF ticker of data to show.
    selected_date : str
        Date of data to show. In format YYYY-MM-DD.
    t_new : tuple of timestamps
        Starting and ending timestamp of the old trading window.
    t_old : tuple of timestamps
        Starting and ending timestamp of the new trading window.
    directory : str
        Folder containing ETF bid and ask price data. File must be in format date_etf.csv.

    Returns
    -------
    p : Bokeh figure
        Plot of bid and ask prices.

    """
    data = pd.read_csv(os.path.join(directory, '{}_{}.csv'.format(selected_date, selected_etf)), index_col=0)
    basetime =  pd.to_datetime('2021-01-01') + pd.Timedelta(hours=9, minutes=30)
    timedeltas = pd.TimedeltaIndex([pd.Timedelta(seconds=x) for x in data.index])
    data.index = timedeltas + basetime
    t_all = t_new + t_old
    bid = data.bid
    ask = data.ask
    p = figure(plot_width=400, plot_height=400, x_axis_type="datetime",
               toolbar_location='below', title='Bid & ask prices for {} on {}'.format(selected_etf, selected_date),
               x_range=(pd.Timestamp('2021-01-01 9:30'), max(t_all)+pd.Timedelta(hours=1.5)),
               y_range=(min(bid.min(),ask.min())-0.2, max(bid.max(),ask.max())+0.2))
    add_trade_windows(p, t_new, t_old, max(bid.max(),ask.max()))
    renders = []
    renders.append(p.line(bid.index, bid.values,# set visual properties for selected glyphs
                    hover_color="blue",
                    hover_alpha=1,
                    color="blue",
                    alpha=.5,
                    name='bid'))
    renders.append(p.line(ask.index, ask.values,# set visual properties for selected glyphs
                    hover_color="firebrick",
                    hover_alpha=1,
                    color="firebrick",
                    alpha=0.5,
                    name='ask'))
    tooltips = [('type','$name'),
                ('time','$x{%H:%M}'),
                ('price', '$y{"$0.00"}')]
    formatters = { "$x": "datetime",}
    p.add_tools(HoverTool(tooltips=tooltips, renderers=renders, formatters=formatters))
    format_plots(p)
    p.yaxis.formatter = NumeralTickFormatter(format="$0.00")    
    return p

def make_relative_fee_amount(selected_ratios, t_new_text = ''):
    """
    Generate a bar plot for the ratio of quoted spread to expense ratio.

    Parameters
    ----------
    selected_ratios : pd.Series
        Data of ratio of quoted spread to expense ratio.
    t_new_text : str
        Time range to place in title of plot.
    Returns
    -------
    p : Bokeh figure
        Produced plot.

    """
    p = figure(plot_width=400, plot_height=400, 
               x_axis_label="ETFs", x_minor_ticks=len(selected_ratios),
               toolbar_location='below', title='Ratio of quoted spread to expense ratio {}'.format(t_new_text))
    source = ColumnDataSource(dict(x=range(len(selected_ratios)),
                          top=selected_ratios.values,
                          desc=selected_ratios.index,))
    glyph = VBar(x='x', top='top', bottom=0, width=0.5, fill_color='grey',
                 line_width=0, fill_alpha=0.5)
    glyph_hover = VBar(x='x', top='top', bottom=0, width=0.5, fill_color='firebrick',
                 line_width=0, fill_alpha=1)
    rend = p.add_glyph(source, glyph)
    rend.hover_glyph = glyph_hover
    labels = LabelSet(x='x', level='glyph', source=source, render_mode='canvas')
    tooltips = [('etf','@desc'),
                ('ratio','@top')]

    p.add_tools(HoverTool(tooltips=tooltips, renderers=[rend])) 
    
    num_zeros = int(np.log10(1/selected_ratios.max())-.4)
    num_formatter = '0.'+''.join(['0' for x in range(num_zeros)])+'%'
    p.yaxis.formatter = NumeralTickFormatter(format=num_formatter)
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None
    p.toolbar.autohide = True    
    p.xaxis.bounds = (-.5,len(selected_ratios)-.5)
    p.xaxis.ticker = list(range(len(selected_ratios)))
    p.xaxis.major_label_overrides = dict(zip(range(len(selected_ratios)), list(selected_ratios.index)))
    p.xaxis.major_label_orientation = 3.14/2
    return p

def get_quoted_spread_change(selected_etfs, selected_dates, t_old, t_new, quoted_spread):
    """
    Get the relative change in average quoted spread between the two time windows.

    Parameters
    ----------
    selected_etfs : list of str
        List of ETF tickers
    selected_dates : list of str
        List of dates to obtain averages of. In format YYYY-MM-DD.
    t_new : tuple of timestamps
        Starting and ending timestamp of the old trading window.
    t_old : tuple of timestamps
        Starting and ending timestamp of the new trading window.
    quoted_spread : pd.DataFrame
        Quoted spread data for various times, days, and ETFs.

    Returns
    -------
    pd.Series
        The relative change in average quoted spread between the two time windows.

    """
    df = get_averages(quoted_spread, selected_dates, selected_etfs)
    old_quotes = df[(df.index > t_old[0]) & (df.index < t_old[1])].mean(0)
    new_quotes = df[(df.index > t_new[0]) & (df.index < t_new[1])].mean(0)
    return (new_quotes / old_quotes).sort_values(ascending=False)

def create_metrics(fractional_increase, nwide=4, container=st, max_rows=2):
    """
    Print information about fractional change in quoted spreads in metric form

    Parameters
    ----------
    fractional_increase : pd.Series
        Data of the increase in fees between two windows.
    nwide : int, optional
        Number of metrics to print side-by-side. The default is 4.
    container : streamlit object, optional
        Object to display metrics. The default is st.
    max_rows : int, optional
        Max number of rows to present data for. The default is 2.

    Returns
    -------
    None.

    """
    metrics = {}
    rows = 0
    for etf, val in dict(fractional_increase).items():
        if len(metrics) == nwide:
            with container:
                metric_row(metrics)
            metrics = {}
            rows += 1
            if rows == max_rows:
                break
        metrics[etf] = '{:.0f}%'.format((val-1)*100)
    if len(metrics) > 0:
        with container:
            metric_row(metrics)

st.write("# Bid-Ask spreads. Does time of day matter?")
st.write("#### By Mark Goldman")
st.write('first published March 10, 2021')

intro = st.beta_expander("Introduction")
data_selection = st.beta_expander("Data selection")
results = st.beta_expander("Results")
conclusion = st.beta_expander("Conclusion")
methods = st.beta_expander("Methods")
disclaimer = st.beta_expander("Disclaimer")

quoted_spread = pd.read_pickle('data/quoted_spread.pkl')

# remove outliers that impact average
del quoted_spread[('2020-12-16', 'SPCX')] # high value on second day of trading
del quoted_spread[('2020-03-12', 'ESGU')] # short high value on during large uncertainty
del quoted_spread[('2020-03-17', 'DRIV')] # short high value on during large uncertainty
del quoted_spread[('2020-02-03', 'EAGG')] # short high value on during large uncertainty

all_dates = list(quoted_spread.columns.levels[0])
all_dates.sort()
all_etfs = list(quoted_spread.columns.levels[1])
etf_data = pd.read_csv('etf.csv', index_col='Symbol')
etf_data = etf_data[etf_data['for_data'] == True]
start, end = data_selection.select_slider('Dates to analyze', all_dates, (all_dates[0], all_dates[-1]))
selected_dates = all_dates[all_dates.index(start):all_dates.index(end)]
method_choose_etfs = data_selection.multiselect('Methods for selecting ETFs',
                                    ['By volume traded', 'By market cap', 'Only ESG ETFs', 'choose specific ETFs'], ['choose specific ETFs'])

selected_etfs = display_method_to_choose_etfs(method_choose_etfs, all_etfs,etf_data,sl_obj=data_selection)

left_column, right_column = data_selection.beta_columns(2)
t_old = right_column.slider('Old trading window timing',
                         min_value=pd.Timestamp('2021-01-01 9:30').to_pydatetime(),
                         max_value=pd.Timestamp('2021-01-01 16:00').to_pydatetime(),
                         value=(pd.Timestamp('2021-01-01 10:00').to_pydatetime(), pd.Timestamp('2021-01-01 10:15').to_pydatetime()),
                         step=pd.Timedelta(minutes=5).to_pytimedelta(),
                         format='H:mm'
                         )
t_new = left_column.slider('New trading window timing',
                         min_value=pd.Timestamp('2021-01-01 9:30').to_pydatetime(),
                         max_value=pd.Timestamp('2021-01-01 16:00').to_pydatetime(),
                         value=(pd.Timestamp('2021-01-01 9:30').to_pydatetime(), pd.Timestamp('2021-01-01 9:45').to_pydatetime()),
                         step=pd.Timedelta(minutes=5).to_pytimedelta(),
                         format='H:mm'
                         )

if len(selected_dates) == 0:
    results.write("Please select at least one date.")
if len(selected_etfs) == 0:
    results.write("Please select at least one ETF.")
elif len(selected_etfs) == 1:
    results.bokeh_chart(make_single_etf_plot(selected_etfs[0],selected_dates,t_new, t_old, quoted_spread, supress_hover_after=50))
else:
    results.bokeh_chart(make_multi_etf_plot(selected_etfs,selected_dates, t_new, t_old, quoted_spread))

results.write(r"Quoted spreads $\left(\frac{ask - bid}{(ask + bid)/2}\right)$ were obtained from full volume stock market data")

results.write("#### Relative increase in Bid-Ask spread when moving to new time window:")

relative_spreads = get_quoted_spread_change(selected_etfs, selected_dates, t_old, t_new, quoted_spread)
create_metrics(relative_spreads, container = results)

results.write("""This spread is not the only fee that ETF investors might face. Another prominent one
              is an annual fee that ETF funds charge, known as the [expense ratio](https://en.wikipedia.org/wiki/Expense_ratio). Let's compare
              it with quoted spreads in the new trade window by taking the ratio of the two.""")   

df = get_averages(quoted_spread, selected_dates, selected_etfs)
new_quotes = df[(df.index > t_new[0]) & (df.index < t_new[1])].mean(0)
t_new_text = '{}:{}-{}:{}'.format(t_new[0].hour, t_new[0].minute,t_new[1].hour, t_new[1].minute)
ratio = (new_quotes / (etf_data.loc[selected_etfs,'expense ratio']/100)).sort_values(ascending=False)
results.bokeh_chart(make_relative_fee_amount(ratio,t_new_text))

results.write("""To put this ratio in perspective, a ratio of 100% in the plot above indicates that if:
              
1. you were to buy and one year later sell that ETF with this bid-ask spread,
2. the market maker doesn't give a significant reduction in bid-ask spread, and
3. the real value of the fund is halfway between the bid and ask price
              
then the cost due to the bid-ask spread is approximately equal to the expense
ratio that you paid to the fund.
""")

def write_intro():
    
    intro.write("""     
    One investment cost that investors may overlook is the [bid-ask spread](https://en.wikipedia.org/wiki/Bid%E2%80%93ask_spread),
    which is the difference between the selling and buying price for a stock. When executing trades, your broker will send
    your order to a [market maker](https://en.wikipedia.org/wiki/Market_maker), which makes money by giving the seller less money 
    than they take from the buyer and keeping the difference (known as the effective spread). 
    U.S. [regulations](https://www.schwab.com/execution-quality/price-improvement) 
    prevent this difference from being greater than the bid-ask spread listed on the exchange (known as the quoted spread).

    The higher the bid-ask spread, the higher the cut the market maker may take.
    Market makers often pass part of the cut back to the brokerage that sent them your trades (known as payment for order flow).
    While this incentivizes brokers to send trades to places that give them a larger cut, they
    are also regulated to ensure the [best execution](https://www.finra.org/rules-guidance/guidance/reports/2019-report-exam-findings-and-observations/best-execution)
    of trades for investors when deciding which market maker
    to send trades to.

    From a broker's perspective, this can be a significant revenue source.
    Barrons recently cited a CFRA analyst that [estimated](https://www.barrons.com/articles/after-the-gamestop-frenzy-robinhood-faces-a-new-set-of-risks-51612573317?mod=hp_minor_pos17)
    80% of Robinhood's revenue came from payment for order flow.

    Since [volatility](https://www.investopedia.com/ask/answers/06/bidaskspread.asp) increases bid-ask spread and one period of higher volatility is when a market opens, I wondered how much buying at the start of the trading day influences this cost. This is quite relevant for investors using [M1 Finance LLC](https://www.m1finance.com/), a company that offers automatic rebalancing but restricts users to set trade times.
    On July 1 2020, M1 shifted their morning trading window from starting at 10:00 am to the market opening time of 9:30 am. 
    The reasons behind this, according to [M1 press release](https://www.m1finance.com/blog/trade-window-change/)
    was to enable customers to invest when market volume is high, when the prices are similar to overnight
    prices, because customers have asked for it, and because they can.
    What was not mentioned in the press release was how the timing change will affect costs of trading.

    I wanted to understand how much the bid-ask spread changes over the course of the day and if that even was significant to investors using M1. Below is one example showing quoted bid and ask prices, where you can see the higher gap during
    the start of trading.
    """)
    
    intro.bokeh_chart(make_bid_ask_plot('ESGV','2021-02-03',t_new, t_old, 'data/'))
    
    intro.write("""

    Unfortunately unlike commissions or expense ratios, the bid-ask 
    spread costs are less transparent. The quoted prices on the exchange are not the same as the prices the market makers give.
    While most brokers must report how much they receive in payment from market makers, 
    they do not have to publish price improvement data, which is what more directly impacts investors.
    
    M1 is also less transparent than many other brokers. Since M1 [doesn't hold](https://m1-production-agreements.s3.amazonaws.com/documents/M1+Rules+606+%26+607+Disclosures.pdf)
    investors' assets, they are not required to, nor do they voluntarily, provide regular reports of their payment from order flow. They do provide payment for order flow data for an individual trader's trades upon request, but this does not allow comparison on an aggregate basis. In addition, M1, unlike [other](https://www.fidelity.com/trading/execution-quality/overview) [brokers](https://www.schwab.com/execution-quality/price-improvement), does not show clients how much better than the quoted bid-ask spread their trade executed for, reducing transparancy when executing trades. 
    
    Without adequate M1 specific data, I scraped bid and ask prices for 41 ETFs between July 1 2019 and Feb 19 2021. Click the results tab to see how much the change in trade time affected bid-ask spreads for a few of Vanguard's ETFs and how this compares to the expense ratio, another significant fee when investing in ETFs.
    Then check out the 'Data selection' tab to view different ETFs, dates, and trading window timings. If you want to dig 
    deeper than this analysis, read the methods section, download the [repository](https://github.com/goldmanm/bid-ask-visualization), and start playing with your own data.

    """)

def write_methods():
    methods.write(r"""
    Raw bid and ask prices, while important, are not the most useful quantity to consider. 
    Derived from these values is the [quoted spread](https://en.wikipedia.org/wiki/Bid%E2%80%93ask_spread),
    which gives an indication of the percent
    cost an investor might face when trading. Another metric, the effective spread, would give 
    a better indication of the cost (by taking into account market makers' price improvements), but 
    M1 does not make this data available, so this can't be used. 
    
    Quoted spread is defined as the ask price minus the bid price,
    divided by the midpoint between the two. Its usefulness is best shown with an example. 
    Let's say you chose to change your investment allocation and need to sell \$10,000 of stock A, 
    which has a quoted spread of 0.2%, and buy \$10,000 of stock B, which has a quoted 
    spread of 0.1%, that transaction would cost you up to \$15 (depending how much of a price improvement
    the market makers give), 
    assuming the actual value of the stock is halfway between the two. 
    (maximum calculated by $\frac{10,000\times 0.002}{2} + \frac{10,000\times 0.001}{2}$). 

    Bid and ask price data originated from full-volume historical quotes obtained from [polygon.io](https://polygon.io/).
    For each data point, the quoted bid-ask spread was calculated by subtracting the bid from 
    the ask and dividing by the midpoint of the two.  The quoted spreads were 
    consolidated into 5 second, time-weighted averages and stored locally. Daily volume data 
    also comes from [polygon.io](https://polygon.io/).

    When plotting, times were further consolidated into 1 minute chunks. The points on the graph 
    are shown at the midpoint of the averaged region (e.g. data from 9:30:00 to 9:31:00 would be shown at 9:30:30).
    
    The quoted spread for a particular trading window is the average of the values within that 
    window. The default trading window used in this analysis ends 15 minutes after the start 
    of the window. The relative cost of moving the trading window (shown by the numbers below the first graph in the results section) is the difference 
    between the the new and old quoted spreads divided by the old quoted spread.
    
    Four days were removed from the data set since they had large bid-ask spread outliers which noticeably 
    impacted the average values. The four removed days are:
 
    1. EAGG on 2020-02-03
    2. ESGU on 2020-03-12
    3. DRIV on 2020-03-17
    4. SPCX on 2020-12-16
    
    If anyone is curious about these specific days, they can download the [repository](https://github.com/goldmanm/bid-ask-visualization), check out the data, and remove the lines in `app.py` which exclude these days.
    
    Data about market cap and expense ratio were obtained after trading hours on 24 Feb. 2021 from Yahoo Finance.
    
    
    ETFs were chosen
    because either they are commonly traded, they screen for Environmental, Social, or Governance 
    (ESG) qualities, or they cover specific sectors. ETFs were not added nor removed based on expected change in price ratio."
    
    """)
def write_conclusion():
    conclusion.write("""
For the vast majority of ETFs evaluated here, trading at the market opening window had substantially wider quoted spreads. 
This is true for both ETF behemoths (e.g. VTI) and newcomers (e.g. VCEB) across a wide range of sectors. 
Some of the additional spread  at market opening can be taken by the market makers, leading traders to pay a higher cost. Investors should take note of this cost when deciding when to execute trades. 
                     
M1 finance moved the trading window to a time where the customers may be paying more, and this does not seem to be in the customer's interest (which I believe should have been disclosed when [announcing](https://www.m1finance.com/blog/trade-window-change/) the change), 
and appears to go against the spirit of FINRA's [best execution](https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310) requirement,
though it may follow the letter of the requirement.
                     
If M1's revenue from order flow is proportional to bid-ask spreads, it also seems like there could be an unmitigated conflict of interest at play 
when M1 decided to move its trading window. Without full information, it is impossible to evaluate how much M1's revenue increased from changing the trading window. 
When I reached out to M1 referencing their [607 disclosure document](https://m1-production-agreements.s3.amazonaws.com/documents/M1+Rules+606+%26+607+Disclosures.pdf), M1 told me how much they receive in payment for order flow for my trades
over the past 6 months. They made 15.5 cents per hundred shares on my trades (which involved buying eight distinct ETFs). 
This is typically within the average payments that Apex Clearing (which is where M1 holds the shares) [receives](https://public.s3.com/rule606/apex/), and is
significantly lower than [Robinhood](https://cdn.robinhood.com/assets/robinhood/legal/RHS%20SEC%20Rule%20606a%20and%20607%20Disclosure%20Report%20Q4%202020.pdf)  and
higher than [TD Ameritrade](https://www.tdameritrade.com/content/dam/tda/retail/marketing/en/pdf/cftc/tdainc-TDA2055-q2-2021.pdf) and [Schwab](https://content.schwab.com/drupal_dependencies/psr/606/2020-Q4-Schwab-Quarterly-Report.pdf).
This comparison isn't perfect given that my eight ETFs are not representative of all the non-S&P 500 equities (which is the lumped category which companies report payment for order flow from). Given the lack of data, it is unclear whether M1 actually increased revenue from moving the trading time. 

Like any project, this analysis leaves many unanswered questions:

1. What other data sources and reasoning led M1 to move the market window? 
2. How does the price improvement that market makers offer change between the two windows? 
3. Did the changed window timing increase M1's revenue for order flow?
4. If there is a larger effective spread at the start of the trade day, why did M1 not inform investors of the potential increase in spread when moving to the new trading window?                     

Time may help answer some of these questions, though it's unlikely to happen without significant transparency on M1's part.
I truly hope that the change in timing was in the best interest of investors, but I have yet to see much evidence of that.
    """)

def write_disclaimer():
    disclaimer.write("""I received no compensation for working on this project, nor do I hold a stake in
                     M1 or its competitors (except for what is in the broad-based ETFs that I invest in). 

This analysis and code is listed under an [MIT licence](https://mit-license.org/), which does not include any warranty of any kind. 
This information is not intended to inform investment decisions. If you notice any mistakes, feel free to post an issue on [github](https://github.com/goldmanm/bid-ask-visualization).""")

write_intro()
write_methods()
write_conclusion()
write_disclaimer()

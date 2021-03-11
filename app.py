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
               toolbar_location='below', title='quoted Bid-Ask Spread for {}'.format(selected_etf),
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
               toolbar_location='below', title='Bid & Ask Prices for {} on {}'.format(selected_etf, selected_date),
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

def make_relative_fee_amount(selected_ratios):
    """
    Generate a bar plot for the ratio of quoted spread to expense ratio.

    Parameters
    ----------
    selected_ratios : pd.Series
        Data of ratio of quoted spread to expense ratio.

    Returns
    -------
    p : Bokeh figure
        Produced plot.

    """
    p = figure(plot_width=400, plot_height=400, 
               x_axis_label="ETFs", x_minor_ticks=len(selected_ratios),
               toolbar_location='below', title='Ratio of quoted spread to expense ratio')
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
st.write('first published March 6, 2021')

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
                                    ['By volume traded', 'By market cap', 'Only ESG ETFs', 'choose specific ETFs'], [])

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

results.write("""This spread is not the only fee that ETF investors might face. Another prominant one
              is a fee that ETF funds remove annually, known as the [expense ratio](https://en.wikipedia.org/wiki/Expense_ratio). Below let's compare
              it with quoted spreads in the new trade window by taking the ratio of the two.""")   

df = get_averages(quoted_spread, selected_dates, selected_etfs)
new_quotes = df[(df.index > t_new[0]) & (df.index < t_new[1])].mean(0)
ratio = (new_quotes / (etf_data.loc[selected_etfs,'expense ratio']/100)).sort_values(ascending=False)
results.bokeh_chart(make_relative_fee_amount(ratio))

results.write("""To put this ratio in perspective, a ratio of 100% in the plot above indicates that if:
              
              1. you were to buy and one year later sell that ETF with this bid ask spread,
              2. the money maker doesn't give a significant reduction in bid-ask spread, and
              3. the real value of the fund is halfway between the bid and ask price
              
              the cost you lost due to the bid-ask spread is approximately equal to the expense
              ratio that you paid to the fund, which is definitely not a negligable amount
""")   


def write_intro():
    
    intro.write("""     
    One convoluted investment cost that investors may overlook is the [bid-ask spread](https://en.wikipedia.org/wiki/Bid%E2%80%93ask_spread),
    which is the difference between the stated selling and buying price. When executing trades, your broker will send
    your order to a [market maker](https://en.wikipedia.org/wiki/Market_maker), which makes money by giving the seller less money 
    than they take from the buyer and keeping the difference. 
    Fortunately, U.S. [regulations](https://www.schwab.com/execution-quality/price-improvement) 
    prevent this difference from being greater than the bid-ask spread, and it can sometimes be smaller.

    The higher the bid-ask spread, the higher the cut the market maker may take.
    Market makers often pass part of the cut back to the brokerage that sent them your trades.
    While this incentivizes brokers to send trades to places that give them a larger cut, they
    are also regulated to ensure the [best execution](https://www.finra.org/rules-guidance/guidance/reports/2019-report-exam-findings-and-observations/best-execution)
    of trades for investors when deciding which market maker
    to send trades to.

    From a broker's perspective, this is not small money either.
    CFRA analyst Pauline Bell [estimates](https://www.barrons.com/articles/after-the-gamestop-frenzy-robinhood-faces-a-new-set-of-risks-51612573317?mod=hp_minor_pos17)
    80% of Robbinhood's revenue comes from payment from market makers.
                
    So what determines the bid-ask spread? Less frequently traded equities typically have higher 
    bid-ask spreads. Periods of time that are [more volatile](https://www.investopedia.com/ask/answers/06/bidaskspread.asp) can also leads to a wider gap. 
        
    Since one period of higher volatility is market open, I wondered about 
    a policy change at M1 finance, a company that offers automatic rebalancing using set trade times.
    On July 1 2020, M1 Finance shifted their morning trading window from starting at 10:00 am to starting at 9:30 am. 
    The reasons behind this, according to [M1 press release](https://www.m1finance.com/blog/trade-window-change/)
    was to enable customers to invest when market volume is high, when the prices are similar to overnight
    prices, because many customers have asked for it, and because they can.

    What was not mentioned in the press release was how the timing change will affect 
    the Bid-Ask spread, but is this even significant?

    Below is one example of the bid-ask spread, where you can see the higher gap during
    the start of trading.
    """)
    
    intro.bokeh_chart(make_bid_ask_plot('ESGV','2021-02-03',t_new, t_old, 'data/'))
    
    intro.write("""

    Of course data from one stock in one day is not enough to determine if it holds at other times.
    
    Could M1's trading time change affect clients costs? 
    
    Unfortunately unlike commissions or expense ratios, the bid-ask 
    spread costs are less transparent. Brokers that hold assets must report how much they recieve for
    forwarding trades to market makers, but since M1 [doesn't hold](https://m1-production-agreements.s3.amazonaws.com/documents/M1+Rules+606+%26+607+Disclosures.pdf)
    the assets themselves, they don't 
    provide regular reports of their revenue from order flow. If when the trading window changed there was a 
    corresponding increase in payment from order flow, that would support the idea that customers
    are incurring higher spreads.
    
    M1, unlike other brokers such as [CharlesSchwab](https://www.schwab.com/execution-quality/price-improvement), does 
    not show clients how much better than the bid-ask spread their trade executed for, leading to even less transparcency when executing trades.
    
    I reached out to M1 for data about my trade execution and order flow, as described in their [order routing disclosure](https://m1-production-agreements.s3.amazonaws.com/documents/M1+Rules+606+%26+607+Disclosures.pdf).
    Fourteen days have past since filing the request, and they have not provided any data.
    
    Without any M1 specific data, I scraped Bid-Ask spreads for various ETFs between July 1 2019 and Feb 20 2021. 
    
    While I am happy to share what I found for myself, I encourage you to play with the data I've 
    gathered to see for yourself how M1's change could affect those trading on its platform. If you want to dig 
    deeper than this analysis, read the methods section, download the [repository](), and start 
    playing with your own data.
    
    
    In these results, instead of presenting bid and ask prices, I use quoted spreads, which represents the maximum fraction that a market maker can take when they exchange a share.
    You can think of this amount as a percentage fee for buying and selling a share""")

def write_methods():
    methods.write("""
    Raw bid and ask prices, while important, are not the most useful quantity to consider. 
    Derived from these values is the [quoted spread](https://en.wikipedia.org/wiki/Bid%E2%80%93ask_spread),
    which gives an indication of the percent
    cost an investor might face when trading. Another metric, the effective spread, would give 
    a better indication of the cost (by taking into account market makers' price improvements), but 
    M1 does not make this data available, so this can't be used. 
    
    Quoted spread is defined as the ask price minus the bid price,
    divided by the midpoint between the two. Its usefulness is best shown with an example. 
    Let's say you chose to change your investment allocation and need to sell $10,000 of stock A, 
    which has a quoted spread of 0.2%, and buy $10,000 of stock B, which has a quoted 
    spread of 0.1%, that transaction would cost you up to $15 (depending how much price improvement
    the market makers give), 
    assuming the actual value of the stock is halfway between the two. 
    (calculated by ($10,000 * 0.2% + $10,000 * 0.1%) / 2). 

    Bid and ask price data originated from full-volume historical quotes obtained from polygon.io.
    For each data point, the quoted bid-ask spread was calculated by subtracting the bid from 
    the ask and dividing by the midpoint of the two.  The bid, ask, and quoted spreads were 
    consolidated into 5 second, time-weighted averages and stored locally. Daily volume data 
    also comes from polygon.io.

    When plotting, times were further consolidated into 5 minute chunks. The points on the graph 
    represent the midpoint of the averaged region.
    
    The quoted spread for a particular trading window is the average of the values within that 
    window. The default trading window used in this analysis is 15 minutes after the start 
    of the window. The relative cost of moving the trading window is the difference 
    between the the new and old quoted spreads divided by the old quoted spread.
    
    Four days were removed from the data set since they had large bid-ask spread outliers, one of which was over 100%, which noticably 
    impacted the average values. The four removed days are:
 
    1. EAGG on 2020-02-03
    2. ESGU on 2020-03-12
    3. DRIV on 2020-03-17
    4. SPCX on 2020-12-16
    
    Data about market cap and expense ratio were obtained after trading hours on 24 Feb. 2021 from Yahoo Finance.
    
    """)
#"""    ETFs were chosen 
#    because either they are commonly traded, they screen for Environmental, Social, or Governance 
#    (ESG) qualities, or they are in my portfolio (which often means that they fall into one of the first 
#                                                  two buckets)."
def write_conclusion():
    conclusion.write("""
                     Certain regulations exist on brokerages to protect investors. While I am not an expert on these regulations, moving the trading 
                     window to a time where the customers are statistically more likely to lose money from
                     wider bid-ask spreads (while potentially making more money), seems rife with conflict of interest. 
                     
                     When I chose a broker, I want them to act as much as possible in my best interest.
                     Based on the data of bid-ask spreads, M1's decision to shift the trading time earlier most likely
                     noticably increased the cost of investing for me.
                     And they did this without informing investors of the potential [increase](https://www.m1finance.com/blog/trade-window-change/) in cost.
                     
                     
                     Like any research project, this analysis leaves many unanswered questions:
                     
                         1. What other data sources and reasoning led M1 to move the market window? 
                         2. Does the price improvement that market makers offer change between the two windows? 
                         3. Did the changed window increase M1's revenue from market makers?
                         4. Why did M1 not inform investors of the potential increase in loss with the new trading window?                     
                     
                     Time may help answer some of these questions, though it's unlikely to happen without significant transparency on M1's part (or an investigation by FINRA).
                     I truely hope that the change in timing was in the best interest of investors, but I have yet to see any evidence of that.
    """)

def write_disclaimer():
    disclaimer.write("""I recieved no compensation for working on this project, nor do I hold a stake in
                     M1 or its competitors (except for what is in the broad-based etfs that I invest in). 

                     The information presented here is for informational purposes only and is not intended
                     to inform investment or litigation decisions.
                     
                     This analysis and code is listed under an [MIT licence](). If you notice any mistakes, feel free to contact me (github, email, etc.)""")

write_intro()
write_methods()
write_conclusion()
write_disclaimer()
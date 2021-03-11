#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re

import pandas as pd


def get_date_etf_list_from_data(directory='data'):
    """
    Returns list of dates and etfs based on files in the given directory

    Parameters
    ----------
    directory : str, optional
        Directory where CSV files are stored. The default is 'data'.

    Returns
    -------
    dates : list of str
        Strings of dates found in files. Format YYYY-MM-DD.
    etfs : list of str
        Strings of ETF ticker symbols.

    """
    files = os.listdir(directory)
    files = [f.split('.csv')[0] for f in files if '.csv' in f]
    dates = set()
    etfs = set()
    ba_data_name = re.compile('[0-9]{4}\-[0-9]{2}\-[0-9]{2}_[A-Z]{2,6}')
    for f in files:
        if ba_data_name.match(f):
            date, etf = f.split('_')
            dates.add(date)
            etfs.add(etf)
    return dates, etfs

def create_and_save_quoated_spread_data(directory='data', sample_frequency=60, ignore_errors=1):
    """
    Convert quoted spreads from various CSV files of various days' and ETFs' data to one data frame.

    Parameters
    ----------
    directory : str, optional
        Folder containing data to be read. The default is 'data'.
    sample_frequency : int, optional
        Number of seconds of each data lump. The default is 60.
    ignore_errors : int, optional
        Level of ignoring errors in file reading:
            0 = raise exceptions
            1 = catch and print unavailable files
            2 = catch and pass

    Returns
    -------
    quoted_spread : pd.DataFrame
        If an exeption occurs, returns data frame of quoted spread data. If no
        exception, returns None.

    """
    dates, etfs = get_date_etf_list_from_data(directory)
    mi = pd.MultiIndex.from_product([dates, etfs], names=['dates','etf'])
    quoted_spread = pd.DataFrame(columns=mi)
    for index, date in enumerate(dates):
        for etf in etfs:
            try:
                df = pd.read_csv(os.path.join(directory, '{}_{}.csv'.format(date, etf)), index_col=0)
            except FileNotFoundError as e:
                if ignore_errors == 0:
                    raise e
                elif ignore_errors == 1:
                    print("Failed to find file for {} on {}".format(etf, date))
                elif ignore_errors == 2:
                    pass
                else:
                    raise AttributeError("ignore_errors must be 0, 1, 2. Given {}".format(ignore_errors))
            quoted_spread[(date, etf)] = df['relative spread']
        if index%10 == 0:
            print('finished {}/{} dates'.format(index, len(dates)))
    try:
        basetime =  pd.to_datetime('2021-01-01') + pd.Timedelta(hours=9, minutes=30)
        timedeltas = pd.TimedeltaIndex([pd.Timedelta(seconds=x) for x in quoted_spread.index])
        quoted_spread.index = basetime + timedeltas
        if sample_frequency is not None:
            resample_str = '{}s'.format(sample_frequency)
            quoted_spread = quoted_spread.resample(resample_str).mean()
            quoted_spread.index = quoted_spread.index + pd.Timedelta(seconds = sample_frequency / 2)
        quoted_spread.to_pickle(os.path.join(directory, 'quoted_spread.pkl'))
        quoted_spread.to_csv(os.path.join(directory, 'quoted_spread.csv.zip'))
    except:
        return quoted_spread
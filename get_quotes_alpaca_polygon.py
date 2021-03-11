import os
from requests.exceptions import HTTPError

import pandas as pd
import numpy as np

from polygon import RESTClient
import alpaca_trade_api as ati

data_columns = ['bid','ask']

def get_data_for_symbol(symbol, client, date, stop_time=None, start_time=None, limit=200):
    """
    Fetches full volume quote data from polygon.io for a symbol and a chosen date.

    Parameters
    ----------
    symbol : str
        STOCK/ETF name to get data of
    client : RESTClient
        polygon.io api client for fetching data
    date : str
        Date string in format to be read by pandas.Timestamp ('YYYY-MM-DD').
    stop_time : int, optional
        Time to stop data collection in ns after UNIX epoch. The default is to collect until 4 pm.
    start_time : int, optional
        Time to stare data collection in ns after UNIX epoch. The default is to collect at 9:30 am.
    limit : int, optional
        Maximum number of times to request data. The default is 200.

    Returns
    -------
    bool
        Whether the data collection was successful.
    pd.DataFrame
        retrieved data with the index being seconds after 9:30am.

    """
    if start_time is None:
        dt = pd.Timestamp(date, tz='US/Eastern') + pd.Timedelta(hours=9, minutes=30)
        start_time = int(dt.tz_convert('UTC').asm8)
    if stop_time is None:
        dt = pd.Timestamp(date, tz='US/Eastern') + pd.Timedelta(hours=16, minutes=0)
        stop_time = int(dt.tz_convert('UTC').asm8)
    result=[]
    counter=0
    while (start_time < stop_time) and (counter < limit):
        counter += 1
        try:
            response = client.historic_n___bbo_quotes_v2(symbol, date, limit=50000, timestamp=start_time)
        except HTTPError:
            print('HTTP error occured for {} on {} at {}'.format(symbol, date, start_time))
            return 0, pd.DataFrame()
        if not response.success:
            print('Response marked as failure for {} on {} at {}'.format(symbol, date, start_time))
            return 0, pd.DataFrame()
        if not response.results:
            print('Response was empty for {} on {} at {}'.format(symbol, date, start_time))
            return 0, pd.DataFrame()
        result += [{'time':r['t'], 'bid':r['p'], 'ask':r['P']} for r in response.results]
        start_time = response.results[-1]['t']
        if len(response.results) != 50000:
            break
    if (counter == limit) and (start_time < stop_time):
        print('limit reached at {} samples'.format(len(result)))
        success = False
    else:
        success = True
    ba_df = pd.DataFrame(result)
    ba_df = ba_df.loc[ba_df.time < stop_time, :]
    ba_df.index = (pd.DatetimeIndex(ba_df.time,tz='UTC') - pd.Timestamp(date, tz='US/Eastern').tz_convert('UTC') - pd.Timedelta(hours=9, minutes=30)) / pd.Timedelta(seconds=1)
    del ba_df['time']
    return success, ba_df

def get_time_averages(series, averaging_seconds=5, start_time = 0, end_time = 3600 * 6.5):
    """
    Averages full volume data for one day.

    Parameters
    ----------
    series : pd.Series
        A column of data from the DataFrame obtained from get_data_from_symbol.
    averaging_seconds : int, optional
        Number of seconds to average bid ask spreads to. The default is 5.
    start_time : int, optional
        What time (seconds) after start time to start averaging data. The default is 0.
    end_time : int, optional
        What time (seconds) after start time to start averaging data. The default is 3600 * 6.5.

    Returns
    -------
    pd.Series
        data of time averages with index being the midpoint between the times

    """
    time_cutoffs = np.arange(start_time, end_time + averaging_seconds, averaging_seconds)
    average_data = np.zeros(len(time_cutoffs) - 1)
    
    #initialize loop parameters
    cutoff_index = 0
    lower_bound = time_cutoffs[cutoff_index]
    higher_bound = time_cutoffs[cutoff_index + 1]
    previous_time = start_time
    previous_value = series.iloc[0]
    for time, value in zip(series.index, series.values):
        while time > higher_bound:
            # finish this section and extend to next section
            deltat = higher_bound - previous_time
            average_data[cutoff_index] += deltat * previous_value / averaging_seconds
            cutoff_index += 1
            lower_bound = higher_bound
            higher_bound = time_cutoffs[cutoff_index + 1]
            previous_time = lower_bound
        # save value to averaged_data
        deltat = time - previous_time
        average_data[cutoff_index] += deltat * previous_value / averaging_seconds
        previous_time = time
        previous_value = value
    # reached end so fill with last partial datapoint
    deltat = higher_bound - previous_time
    average_data[cutoff_index] += deltat * previous_value / averaging_seconds
    # fill in the rest of the data with the last point
    cutoff_index += 1
    while cutoff_index < len(average_data):
        average_data[cutoff_index] = previous_value
        cutoff_index += 1
    # create_pandas series to return 
    return pd.Series(index=time_cutoffs[:-1]+(averaging_seconds/2), data=average_data)

def get_volume_traded(etfs, dates, client):
    """
    Obtain average volume data for various ETFs

    Parameters
    ----------
    etfs : list of str
        List of strings of ETFs to collect volume data from.
    dates : list of str
        List of strings in YYYY-MM-DD format.
    client : TYPE
        Alpaca api client for fetching market data.

    Returns
    -------
    pd.Series
        Average volume data for various ETFs
    """
    avg_volume = []
    for etf in etfs:
        volumes = 0
        for date in dates:
            try:
                response = client.stocks_equities_daily_open_close(etf, dates)
            except HTTPError:
                continue
            volumes += response.volume
        avg_volume.append(volumes/len(dates))
    return pd.Series(index=etfs, data=avg_volume)

def get_valid_market_days(start_day, end_day):
    """
    Get a list of market days with timing 9:30-4:00

    Parameters
    ----------
    start_day : str
        First day. Format YYYY-MM-DD.
    end_day : str
        Last day. Format YYYY-MM-DD.

    Returns
    -------
    valid_days : list of str
        List of days in format YYYY-MM-DD.

    """
    valid_days = []
    with ati.REST() as api:
        days = api.get_calendar(start=start_day+'T00:00:00Z', end=end_day+'T00:00:00Z')
    for calendar in days:
        if (calendar.close.hour == 16) and (calendar.open.hour == 9) and (calendar.open.minute == 30):
           valid_days.append(str(calendar.date)[:10])
    return valid_days

if __name__ == '__main__':
    key = os.getenv('APCA_API_KEY_ID')
    dates = []
    dates += get_valid_market_days('2019-12-29', '2020-07-01')
    with RESTClient(key) as client:
        etf_df = pd.read_csv('etf.csv', index_col = 'Symbol')
        etfs = etf_df[etf_df['for_data'] == True].index

        for date in dates:
            for symbol in etfs:
                try:
                    with open('data/{}_{}.csv'.format(date, symbol)) as f:
                        print('data/{}_{}.csv already exists'.format(date, symbol))
                except FileNotFoundError:
                    success, df = get_data_for_symbol(symbol, client, date)
                    if success:
                        spread_fraction = 2*(df.ask - df.bid)/(df.ask + df.bid)
                
                        average_data = pd.DataFrame()
                        average_data['bid'] = get_time_averages(df['bid'])
                        average_data['ask'] = get_time_averages(df['ask'])
                        average_data['relative spread'] = get_time_averages(spread_fraction)
                        average_data.to_csv('data/{}_{}.csv'.format(date, symbol))
                        print('finished {}_{}'.format(date, symbol))
                    else:
                        print('error {}_{}'.format(date, symbol))
        volume = get_volume_traded(etfs, dates[-1], client)
        volume.to_csv('data/etf_info.csv')

import os
import datetime
from requests.exceptions import HTTPError

import pandas as pd
import numpy as np

from polygon import RESTClient
import alpaca_trade_api as ati

data_columns = ['bid','ask']

def ts_to_datetime(ts) -> str:
    return datetime.datetime.fromtimestamp(ts / 1000.0).strftime('%Y-%m-%d %H:%M')

def get_data_for_symbol(symbol, client, date, stop_time=None, start_time=None, limit=200):
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
        except HTTPError as e:
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
    series has index of seconds with various values
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

def get_assets_under_management(etfs, client):
    """
    Does not work for ETFs
    """
    aums = []
    for etf in etfs:
        #response = client.reference_ticker_details(etf)
        #aums.append(response.marketcap)
        response = client.reference_stock_financials(etf)
        print(response.results)
        print(response.status)
        aums.append(response.results[0].market_capitalization)
    return pd.Series(index=etfs, data=aums)

def get_volume_traded(etfs, dates, client):
    avg_volume = []
    for etf in etfs:
        volumes = 0
        for date in dates:
            try:
                response = client.stocks_equities_daily_open_close(etf, dates)
            except HTTPError as e:
                continue
            volumes += response.volume
        avg_volume.append(volumes/len(dates))
    return pd.Series(index=etfs, data=avg_volume)

def get_valid_market_days(start_day, end_day):
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
    #dates += get_valid_market_days('2020-07-01', '2021-01-01')
    with RESTClient(key) as client:
        etf_df = pd.read_csv('etf.csv', index_col = 'Symbol')
        etfs = etf_df[etf_df['for_data'] == True].index

        for date in dates:
            for symbol in etfs:
                try:
                    with open('data/{}_{}.csv'.format(date, symbol)) as f:
                        print('data/{}_{}.csv already exists'.format(date, symbol))
                except FileNotFoundError as e:
                    #dt = pd.Timestamp(date,tz='US/Eastern') + pd.Timedelta(hours=16, minutes=0)
                    #stop_time = float(dt.asm8)
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
        #aum = get_assets_under_management(etfs, client)
        volume.to_csv('data/etf_info.csv')

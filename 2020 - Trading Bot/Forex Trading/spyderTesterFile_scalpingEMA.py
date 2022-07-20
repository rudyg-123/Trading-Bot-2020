# -*- coding: utf-8 -*-
"""
Created on Mon Oct  5 20:17:10 2020

@author: RUDYG123
"""
import datetime
import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from datetime import datetime as dt
import numba as nb
from collections import defaultdict 
from tqdm.notebook import trange, tqdm

print('imported')

#%% Initialise the terminal etc
if not mt5.initialize():
    print(mt5.last_error())
    mt5.shutdown()
else:
    authorized=mt5.login(18676, password="aTOirs42", server="GoMarkets-Demo")
       
def getData(numBefore, timePeriod, signal, timeDict):
    rates = mt5.copy_rates_from_pos(signal, timeDict[timePeriod], 0, numBefore)       
    ratesDf = pd.DataFrame(rates)
#    print(mt5.last_error())        
    return ratesDf

## Get the dataframe with information of rates, RSI and bollinger bands
def getAllInfo(rates):
    times = rates['time'].values
        
    # First get the RSI, signal and Bollinger bands in a dataframe with respect to time
    algDf = pd.DataFrame()
    algDf['Date'] = times
    algDf = algDf.set_index('Date')
    
    # Add the signal values (using the close value)
    ratesDf = pd.DataFrame(rates.drop(columns = ['time', 'tick_volume', 'spread', 'real_volume']))
    ratesDf['Date'] = times
    ratesDf = ratesDf.set_index('Date')
        
    concatDf = pd.concat([algDf, boll, ratesDf], axis=1)
    concatDf.drop(columns=['index'], inplace=True)
    
    filteredDf = concatDf[concatDf.mav > 0]
    filteredDf.reset_index(inplace=True)
    
    return filteredDf

#%% TEST #1 - Scalping method
timeDict = {'5': mt5.TIMEFRAME_M5, '15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30,\
            '60': mt5.TIMEFRAME_H1}

# Get data for a number of years
numYears = 0.7

# Get the data in the correct format for M5 and H1
p1 = '5'
rates_M5 = getData(int(60/int(p1) * 24 * 365 * numYears), p1, 'AUDUSD', timeDict) 
filt_M5 = getAllInfo(rates_M5)

p2 = '60'
rates_H1 = getData(int(60/int(p2) * 24 * 365 * numYears), p2, 'AUDUSD', timeDict) 
filt_H1 = getAllInfo(rates_H1)

#%%



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
from tqdm import tqdm

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

# Give closePrices as an array
def getBollBands(closePrices, period=20, numStd=2):
    # Default values for bollinger bands = 20 for period & 2 for std
    bands = {k:[] for k in ['topBand','bottomBand', 'mav']} # Set lists as defaults

    for i in range(1, len(closePrices)+1):
        if i < period:
            currDat = closePrices[0:i]
        else:
            currDat = closePrices[i-period:i]

        std = np.std(currDat)
        mean = np.mean(currDat)

        bands['topBand'].append(mean+numStd*std)
        bands['bottomBand'].append(mean-numStd*std)
        bands['mav'].append(mean)

    # Remove the first n (period) of values as they are not accurate/just used for calculation
    for key, val in bands.items():
        tempVal = val.copy()
        tempVal[:period] = [float('nan')]*period
        bands[key] = tempVal

    bollDf = pd.DataFrame.from_dict(bands)
    return bollDf

@nb.jit(fastmath=True, nopython=True)   
def calc_rsi( array, deltas, avg_gain, avg_loss, n ):

# Use Wilder smoothing method
    up   = lambda x:  x if x > 0 else 0
    down = lambda x: -x if x < 0 else 0
    i = n+1
    for d in deltas[n+1:]:
        avg_gain = ((avg_gain * (n-1)) + up(d)) / n
        avg_loss = ((avg_loss * (n-1)) + down(d)) / n
        if avg_loss != 0:
            rs = avg_gain / avg_loss
            array[i] = 100 - (100 / (1 + rs))
        else:
            array[i] = 100
        i += 1

    return array

# Default period for the RSI indicator is 14
def getRSI(array, n = 14):   

    deltas = np.append([0],np.diff(array))

    avg_gain =  np.sum(deltas[1:n+1].clip(min=0)) / n
    avg_loss = -np.sum(deltas[1:n+1].clip(max=0)) / n

    array = np.empty(deltas.shape[0])
    array.fill(np.nan)

    array = calc_rsi( array, deltas, avg_gain, avg_loss, n )
    return array
print('initialised')


## Get the dataframe with information of rates, RSI and bollinger bands
def getAllInfo(rates):  
    boll = getBollBands(rates.close)
    rsi = getRSI(rates.close)
    
    times = rates['time'].values
        
    # First get the RSI, signal and Bollinger bands in a dataframe with respect to time
    algDf = pd.DataFrame()
    algDf['Date'] = times
    algDf = algDf.set_index('Date')
    
    # Add the RSI values
    algDf['RSI'] = list(rsi)
    
    # Add the signal values (using the close value)
    ratesDf = pd.DataFrame(rates.drop(columns = ['time', 'tick_volume', 'spread', 'real_volume']))
    ratesDf['Date'] = times
    ratesDf = ratesDf.set_index('Date')
    
    # Add the bollinger bands (can use the mav to figure out the take-profit value)
    boll.reset_index(inplace=True)
    boll['Date'] = times
    boll = boll.set_index('Date')
        
    concatDf = pd.concat([algDf, boll, ratesDf], axis=1)
    concatDf.drop(columns=['index'], inplace=True)
    
    filteredDf = concatDf[concatDf.mav > 0]
    filteredDf.reset_index(inplace=True)
    
    return filteredDf

#%% TEST #1 - Check if the RSI/Boll Band condition is met 2 bars ago (on close) and previous bar is moving in the correct direction
timeDict = {'15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30, '60': mt5.TIMEFRAME_H1}

threshUp = 75
threshDown = 25
# posPips = 100

barsAfter = [3, 5, 10, 15, 24]
resultDict = {}

for key, val in tqdm(timeDict.items()):
#    print(key)
    resultDict[key] = defaultdict(list)
    
    numYears = 1
    numBefore = int(60/int(key) * 24 * 365 * numYears) # Data for one year 
    
    rates = getData(numBefore, key, 'USDCHF', timeDict) 
    filteredDf = getAllInfo(rates)

    for index, row in filteredDf.iterrows():
        if index<2:
            continue # Skip the first two bars
        
        twoBarsAgo = filteredDf[filteredDf.index==index-2]
        prevBar = filteredDf[filteredDf.index==index-1]
        
        twoBarsDict = twoBarsAgo.to_dict(orient='list')
        prevBarDict = prevBar.to_dict(orient='list')
        
        # Check bottom threshold and Check the last bar is going up
        if (twoBarsDict['close'] < twoBarsDict['bottomBand']) and \
            (twoBarsDict['RSI'] < [threshDown]) and (prevBarDict['open'] < prevBarDict['close']):
            # print(pd.to_datetime(row.Date, unit='s'))

            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if max(nextBars.high) - 0.001 > row.close:
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)                
                
        #Check upper threshold and Check the last bar is going down
        elif (twoBarsDict['close'] > twoBarsDict['topBand']) and \
            (twoBarsDict['RSI'] > [threshUp]) and (prevBarDict['open'] > prevBarDict['close']):
            # print(pd.to_datetime(row.Date, unit='s'))

            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if min(nextBars.low) < row.close - 0.001:
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)   
            
#%%
print('timeframe', 'bars after', 'truth values', 'percentage true')
for key, val in resultDict.items():
    for i, j in val.items():
        n, c = np.unique(j, return_counts=True)
        print(key, i, n, c, c[1]/sum(c)*100)

#%% Test #2 - use just the bollinger bands to identify trends up/down

timeDict = {'15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30, '60': mt5.TIMEFRAME_H1}

barsAfter = [3, 5, 12]
resultDict = {}

for key, val in tqdm(timeDict.items()):
    print(key)

    resultDict[key] = defaultdict(list)
    
    numYears = 2
    numBefore = int(60/int(key) * 24 * 365 * numYears) # Data for one year 
    
#    if key=='5':
#        numBefore = numBefore/4
        
    print(numBefore)
    rates = getData(numBefore, key, "GBPUSD", timeDict) 
    
    print(mt5.last_error())
    filteredDf = getAllInfo(rates)
    
    ## FIRST CHECK IF THERE IS ANY CORRELATION FOR A SIMPLE BREACH OF BARS
    for index, row in filteredDf.iterrows():
        if index > len(filteredDf)-max(barsAfter)-1:
             continue
        
        # Current bar has closed outside upper band
        if row.close > row.topBand:
            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if min(nextBars.low) < (row.close - 0.001):
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)
        
        elif row.close < row.bottomBand:
            
            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if max(nextBars.high) > (row.close + 0.001):
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)
    
#%%
print('timeframe', 'bars_after', 'truth_values', 'percentage_true')
for key, val in resultDict.items():
    for i, j in val.items():
        n, c = np.unique(j, return_counts=True)
        print(key, i, n, c, c[1]/sum(c)*100)



########################################################################################
#%% Test #3 - use the bollinger bands and a close in the positive direction
        
timeDict = {'15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30, '60': mt5.TIMEFRAME_H1}
# timeDict = {'30': mt5.TIMEFRAME_M30}

barsAfter = [3, 5, 12]
resultDict = {}

for key, val in tqdm(timeDict.items()):
    print(key)

    resultDict[key] = defaultdict(list)
    
    numYears = 2
    numBefore = int(60/int(key) * 24 * 365 * numYears) # Data for one year 
    
#    if key=='5':
#        numBefore = numBefore/4
        
    print(numBefore)
    rates = getData(numBefore, key, "AUDUSD", timeDict) 
    
    print(mt5.last_error())
    filteredDf = getAllInfo(rates)
    
    ## FIRST CHECK IF THERE IS ANY CORRELATION FOR A SIMPLE BREACH OF BARS
    for index, row in filteredDf.iterrows():
        if index > len(filteredDf)-max(barsAfter)-1:
            continue
        if index<2:
            continue # Skip the first two bars
        
        # twoBarsAgo = filteredDf[filteredDf.index==index-2]
        prevBar = filteredDf[filteredDf.index==index-1]
        prevBarDict = prevBar.to_dict(orient='list')

        # Current bar has closed outside upper band
        if prevBarDict['close'] > prevBarDict['topBand'] and row.open > row.close:
            # print(pd.to_datetime(row.Date, unit='s'))

            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                # print(pd.to_datetime(nextBars.Date, unit='s'))
                
                if min(nextBars.low) < (row.close - 0.001):
                    # print('true')
                    resultDict[key][n].append(True)
                else:
                    # print('false')
                    resultDict[key][n].append(False)
                # print('\n')
                
        elif prevBarDict['close'] < prevBarDict['bottomBand'] and row.open < row.close:
            
            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if max(nextBars.high) > (row.close + 0.001):
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)
    
#%%
print('timeframe', 'bars_after', 'truth_values', 'percentage_true')
for key, val in resultDict.items():
    for i, j in val.items():
        n, c = np.unique(j, return_counts=True)
        print(key, i, n, c, c[1]/sum(c)*100)


#%% Test #4 - use the M30 timeframe and the RSI on H4 (above/below 50 to check trend)


#%% Test #5 - just use the RSI with threshold:
        
timeDict = {'15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30, '60': mt5.TIMEFRAME_H1}
#timeDict = {'30': mt5.TIMEFRAME_M30}

threshUp = 75
threshDown = 25

barsAfter = [3, 5, 12, 15, 24]
resultDict = {}

for key, val in tqdm(timeDict.items()):
#    print(key)

    resultDict[key] = defaultdict(list)
    
    numYears = 2
    numBefore = int(60/int(key) * 24 * 365 * numYears) # Data for one year 
        
    print(numBefore)
    rates = getData(numBefore, key, "AUDUSD", timeDict) 
    
#    print(mt5.last_error())
    filteredDf = getAllInfo(rates)
    
    ## FIRST CHECK IF THERE IS ANY CORRELATION FOR A SIMPLE BREACH OF BARS
    for index, row in filteredDf.iterrows():
        if index > len(filteredDf)-max(barsAfter)-1:
             continue
        
        # Current bar has closed outside upper band
        if row.RSI > threshUp:
#            print(pd.to_datetime(row.Date, unit='s'))

            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if min(nextBars.low) < (row.close - 0.0005):
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)
        
        elif row.RSI < threshDown:
            
            for n in barsAfter:
                nextBars = filteredDf.iloc[index+1:index+n+1]
                
                if max(nextBars.high) > (row.close + 0.0005):
                    resultDict[key][n].append(True)
                else:
                    resultDict[key][n].append(False)
    
#%%
print('timeframe', 'bars_after', 'truth_values', 'percentage_true')
for key, val in resultDict.items():
    print('\n')
    for i, j in val.items():
        n, c = np.unique(j, return_counts=True)
        print(key, i, n, c, c[1]/sum(c)*100)





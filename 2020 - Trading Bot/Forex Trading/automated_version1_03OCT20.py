#Name     : Rudraksh Goel
#Type     : Standard AUD Demo Account
#Server   : GoMarkets-Demo
#Login    : 62986
#Password : xo7rslrx
#Investor : we5sweua

# Import all of the modules
import time
# startTime = time.time()

import datetime
import MetaTrader5 as mt5
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf
from datetime import datetime as dt
import numba as nb
import smtplib, ssl

import tkinter as tk
from tkinter import ttk

# print('Importing and set up time = %0.4f' % (time.time() - startTime))

def getData(numBefore, timePeriod, signal):
	endDate = dt.now() # The most recent time
	timeBefore = (int(timePeriod) * numBefore)*60 # In seconds

	delta = datetime.timedelta(seconds=timeBefore)
	startDate = endDate - delta

	rates = mt5.copy_rates_range(signal, timeDict[timePeriod], startDate, endDate)
	ratesDf = pd.DataFrame(rates)
	ratesDf['time']=pd.to_datetime(ratesDf['time'], unit='s')
	# print(ratesDf)
	# exit()
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

def getMostRecent(rsi, boll, rates):
	# First get the RSI, signal and Bollinger bands in a dataframe with respect to time
	algDf = pd.DataFrame()
	algDf['Date'] = pd.to_datetime(rates['time'])
	algDf = algDf.set_index('Date')

	# Add the RSI values
	algDf['RSI'] = list(rsi)

	# Add the signal values (using the close value)
	algDf['Signal'] = rates['close']

	# Add the bollinger bands (can use the mav to figure out the take-profit value)
	boll.reset_index(inplace=True)
	boll['Date'] = pd.to_datetime(rates['time'])
	boll = boll.set_index('Date')

	algDf = pd.concat([algDf, boll], axis=1)

	# Just get the array where the most recent time stamp is
	recentTime = max(algDf.index)
	recentDf = algDf[algDf.index==recentTime]

	# display(recentDf)
	return recentDf, recentTime

def checkMakeTrade(recentDf, threshUp=70, threshDown=30) :
	# Thresholds for the RSI being a snapback
	recDict = recentDf.to_dict(orient='list')

	makeTrade = False
	# Case 1 - signal is above topBand and RSI is > upperthresh
	if (recDict['Signal'] > recDict['topBand']) and (recDict['RSI'] > threshUp):
		makeTrade = True
	elif (recDict['Signal'] < recDict['bottomBand'] and (recDict['RSI'] < threshDown)):
		makeTrade = True
	
	return makeTrade





################################################################
######## MAIN CODE OVER HERE:
################################################################

def popupmsg(msg):
	FONT = ("Verdana", 48)
	popup = tk.Tk()
	popup.wm_title("!")
	label = ttk.Label(popup, text=msg, font=FONT)
	label.pack(side="top", fill="x", pady=30, padx=30)
	B1 = ttk.Button(popup, text="Okay", command = popup.destroy)
	B1.pack()
	popup.mainloop()

def sendEmail(msg):
	context = ssl.create_default_context()
	with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
		server.login(sender_email, password)
		server.sendmail(sender_email, receiver_email, msg)

def checkAllSigs(numBefore, timePeriod, signals, verbose=False):
	maxTime = 0
	
	for currSig in signals:
# 		print(currSig.name)
		makeTrade = False
		try:
			rates = getData(numBefore, timePeriod, currSig.name)
			boll = getBollBands(rates.close)
			rsi = getRSI(rates.close)
			recVals, maxTime = getMostRecent(rsi, boll, rates)
			makeTrade = checkMakeTrade(recVals)

			if verbose: print(f'For signal {currSig.name}, make trade = {makeTrade}')
		except Exception as e:
			if verbose: print(f'FAILED FOR {currSig.name}. {e}')

		print(recVals)
		print(maxTime)
		# If there's a signal which should be traded, open a window
		if makeTrade:
			popupmsg(f'Make a trade on signal {currSig.name}')
			sendEmail(f'Subject: Make a trade on signal {currSig.name}\n\nHi there,\n\nCoding bot has found a suitable trade\n\nThanks')

	return maxTime

## Initialise the MT5 trading portal
initTime = time.time()

if not mt5.initialize():
	print(mt5.last_error())
	mt5.shutdown()
else:
	authorized=mt5.login(62986, password="xo7rslrx")
	print('\nInitialised mt5 successfully! Took %0.3f seconds...\n' % (time.time() - initTime))

# Uncomment below if you want to see your account info

# account_info=mt5.account_info()
# print(account_info)

# Set up the time period (IMPORTANT)
timeDict = {'15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30, '60': mt5.TIMEFRAME_H1}
timePeriod = '15'

# Get the data for n periods prior to the current period
numBefore = 40 # number of periods prior to the current one
signals = mt5.symbols_get(group="*USD*,*EUR*,*JPY*,*GBP*,*AUD*,!*USDOLLAR*,!*TRY*")

# Set up the credentials for sending mail
port = 465  # For SSL
smtp_server = "smtp.gmail.com"
sender_email = "rgforexbot@gmail.com"  # Enter your address
receiver_email = "rudyg.ace@gmail.com"  # Enter receiver address
password = 'bigbucks123'


### WANT TO DO THE NEXT CODE EVERY TIME PERIOD (i.e. WHENEVER THERE IS MORE DATA)

# Do the checks once to initialise then run in a loop
prevMaxTime = checkAllSigs(numBefore, timePeriod, signals, False)
newCollectTime = prevMaxTime + datetime.timedelta(seconds=int(timePeriod)*60) 

print(newCollectTime)
print(dt.now())
print(dt.now() - datetime.timedelta(hours=7))
exit()

while(True):
	if dt.now() - datetime.timedelta(hours=7) > newCollectTime: # A new piece of data has arrived # Use 7 hours as the time zone of GoMarkets is 7 hours behind
		print('Collecting new data!')
		prevMaxTime = checkAllSigs(numBefore, timePeriod, signals)
		newCollectTime = prevMaxTime + datetime.timedelta(seconds=int(timePeriod)*60)

	else:
		time.sleep(3)
		print('Waiting for new data...')
#Name     : Rudraksh Goel
#Type     : Standard AUD Demo Account
#Server   : GoMarkets-Demo
#Login    : 18676
#Password : aTOirs42
#Investor : we5sweua


# Import all of the modules
import time
import datetime
import MetaTrader5 as mt5
import numpy as np
# import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime as dt
import numba as nb
import smtplib, ssl

def getData(numBefore, timePeriod, signal, timeDict):
	rates = mt5.copy_rates_from_pos(signal, timeDict[timePeriod], 1, numBefore)
	ratesDf = pd.DataFrame(rates)
	return ratesDf

@nb.jit(fastmath=True, nopython=True)   
def calc_rsi(array, deltas, avg_gain, avg_loss, n ):

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

def cleanDf(rates, rsi):
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
		
	concatDf = pd.concat([algDf, ratesDf], axis=1)
	# concatDf.drop(columns=['index'], inplace=True)

	filteredDf = concatDf[concatDf.RSI > 0]
	filteredDf.reset_index(inplace=True)

	# Just get the recent time stamp
	recentTime = max(filteredDf.Date)

	return filteredDf, recentTime


def checkMakeTrade(recentDf, threshUp=75, threshDown=25) :
	# Thresholds for the RSI being a snapback
	recDict = recentDf.to_dict(orient='list')
	# print(recDict)

	makeTrade = False
	order_type = None
	rsi = recDict['RSI'][0]

	# Case 1 - signal is above topBand and RSI is > upperthresh
	if (rsi > threshUp):
		makeTrade = True
		order_type = 'sell'

	# Case 1 - signal is below bottomBand and RSI is < lowerThresh
	elif (rsi < threshDown):
		makeTrade = True
		order_type = 'buy'

	return makeTrade, order_type, rsi


def placeOrder(symbol_name, order_type, pipsprof=50, pipsloss=50, lot=0.1):
	order = None
	sl = None
	tp = None

	point = mt5.symbol_info(symbol_name).point
	price = mt5.symbol_info_tick(symbol_name).ask

	if order_type == 'buy':
		order = mt5.ORDER_TYPE_BUY
		sl = price - pipsloss * point # pips down
		tp = price + pipsprof * point # pips up
	elif order_type == 'sell':
		order = mt5.ORDER_TYPE_SELL
		sl = price + pipsloss * point # pips up
		tp = price - pipsprof * point # pips down
	else:
		print("Wrong order type passed into place order function")
		exit() # Exit the file

	deviation = 20
	request = {
		"action": mt5.TRADE_ACTION_DEAL,
		"symbol": symbol_name,
		"volume": lot,
		"type": order,
		"price": price,
		"sl": sl,
		# "tp": tp,
		"deviation": deviation,
		# "magic": 234000,
		"comment": f"Placing order on {symbol_name}",
		"type_time": mt5.ORDER_TIME_GTC,
		"type_filling": mt5.ORDER_FILLING_IOC#mt5.ORDER_FILLING_FOK#mt5.ORDER_FILLING_RETURN
	}
	result = mt5.order_send(request)

	if result.retcode != mt5.TRADE_RETCODE_DONE:
		print(mt5.last_error())
		return False
	else:
		return True


def followTrade():
	pass

def sendEmail(msg):
	context = ssl.create_default_context()
	with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
		server.login(sender_email, password)
		server.sendmail(sender_email, receiver_email, msg)

def checkAllSigs(numBefore, timePeriod, signals, verbose=True, sendMail=True, placeorder=True):
	maxTime = None
	recVals = None

	currTime = dt.now()
	tradeSigs = []

	for i, currSig in enumerate(signals):
		rates = getData(numBefore, timePeriod, currSig, timeDict)
		rsi = getRSI(rates.close)
		filteredDf, maxTime = cleanDf(rates, rsi)
		makeTrade, order_type, rsi = checkMakeTrade(filteredDf[filteredDf.Date == max(filteredDf.Date)])

		spr = mt5.symbol_info(currSig).spread
		if spr < 50:
			if verbose: print(f'Signal {i}:\t{currSig}\t\tSpread:{spr}' + '\tRSI = %.2f' % rsi + f'\tMake trade = {makeTrade}')
			pass
		else:
			if verbose: print(f'Signal {i}:\t{currSig}\t\tSpread:{spr}\tSKIP')
			continue

		# If there's a signal which should be traded, open a window     
		if makeTrade:
			tradeSigs.append(currSig)
			
			if placeorder:
				placeOrder(currSig, order_type, pipsprof=50, pipsloss=50, lot=0.05)
					
	if sendMail and len(tradeSigs)>0:
		sendEmail(f'Subject: Trading bot making {len(tradeSigs)} trades at {currTime.strftime("%H:%M:%S")} on {tradeSigs}')

	if verbose: print(f'\nTrading bot found {len(tradeSigs)} suggested trades at {currTime.strftime("%H:%M:%S")}\t Make trades on signals {tradeSigs}')

	return maxTime


def getTerminalTime():
	currTick = mt5.symbol_info_tick("AUDUSD")._asdict()
	currTime = currTick['time'] # Just need the most recent time on the M1 timeframe
	return currTime





##################################################################################
##################################################################################
##################################################################################
##################################################################################
### INITIALISE EVERYTHING

## Initialise the MT5 trading portal
if not mt5.initialize():
	print(mt5.last_error())
	mt5.shutdown()
else:
	authorized=mt5.login(18676, password="aTOirs42")

# Uncomment below if you want to see your account info
# account_info=mt5.account_info()
# print(account_info)

# Set up the time period (IMPORTANT)
timeDict = {'1': mt5.TIMEFRAME_M1, '15': mt5.TIMEFRAME_M15, '30': mt5.TIMEFRAME_M30, '60': mt5.TIMEFRAME_H1}
timePeriod = '15'

# Get the data for n periods prior to the current period
numBefore = 40 # number of periods prior to the current one
signals = mt5.symbols_get(group="*GBP*,!*JPY*,!*EUR*")
signalNames = [sig.name for sig in signals]

# Set up the credentials for sending mail
port = 465  # For SSL
smtp_server = "smtp.gmail.com"
sender_email = "rgforexbot@gmail.com"  # Enter your address
receiver_email = "rudyg.ace@gmail.com"  # Enter receiver address
password = 'bigbucks123'


##################################################################################
##################################################################################
##################################################################################
##################################################################################
### WANT TO DO THE NEXT CODE EVERY TIME PERIOD (i.e. WHENEVER THERE IS MORE DATA)
print('\n\n**************STARTING THE TRADING BOT NOW****************\n')
print(f'\nRunning bot for {len(signalNames)} signals: {signalNames}\n\n')

# Do the checks once to initialise (and get the max terminal time) then run in a loop
currTime = getTerminalTime()
currTimeDt = pd.to_datetime(currTime, unit='s') # Convert it to datetime format to print
print('Current time is ' + currTimeDt.strftime("%H:%M:%S"))

prevMaxTime = checkAllSigs(numBefore, timePeriod, signalNames, sendMail=False, placeorder=False)
newCollectTime = prevMaxTime + datetime.timedelta(seconds=int(timePeriod)*2*60).total_seconds()
newCollectDt = pd.to_datetime(newCollectTime, unit='s')

print('\nWaiting for new data...\t Next data at terminal time ' + newCollectDt.strftime("%H:%M:%S"))

while(True):
	currTime = getTerminalTime()
	currTimeDt = pd.to_datetime(currTime, unit='s') # Convert it to datetime format to print

	if currTime > newCollectTime: # A new piece of data has arrived
		print('\n\n**************COLLECTING NEW DATA****************')
		print('Current time is ' + currTimeDt.strftime("%H:%M:%S"))

		# Implement the algorithm to check if there is any signal breaching the limits
		prevMaxTime = checkAllSigs(numBefore, timePeriod, signalNames, sendMail=True, placeorder=True)
		newCollectTime = prevMaxTime + datetime.timedelta(seconds=int(timePeriod)*2*60).total_seconds()
		newCollectDt = pd.to_datetime(newCollectTime, unit='s')
		print('Waiting for new data...\t Next data at terminal time ' + newCollectDt.strftime("%H:%M:%S") + '\n\n')
		time.sleep(120)
	else:
		print(f'Current terminal time is ' + currTimeDt.strftime("%H:%M:%S"), end='\r')
		time.sleep(30)
		
		
		
		
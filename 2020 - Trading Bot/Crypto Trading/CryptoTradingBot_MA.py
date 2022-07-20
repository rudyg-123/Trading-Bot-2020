# Import all of the required packages
import time
import sys, getopt
import datetime
from poloniex import poloniex

def main(argv):
    period = 10 ## Run the script once every 10 seconds
    pair = "BTC_XRP" # 
    
    # Get the arguments/options from the command line
    try:
        opts, args = getopt.getopt(argv,"hp:",["period="])
    except getopt.GetoptError:
        print('Please try\t\t trading-bot.py -p <period length>')
        sys.exit(2)

    # Handle the various options from the command line of the program
    for opt, arg in opts: 
        # Command for getting the help options
        if opt == '-h': 
            print('trading-bot.py -p <period length>')
            sys.exit()
            
        # Command for getting the period option
        elif opt in ("-p", "--period"):
            if (int(arg) in [300,900,1800,7200,14400,86400]):
                period = arg
            else:
                print('Poloniex requires periods in 300,900,1800,7200,14400, or 86400 second increments')
                sys.exit(2)
                
        elif opt in ("-c", "--currency"):
            pair = arg
        
    conn = poloniex('keys go here', 'keys go here')
    


    while True:
        currVals = conn.api_query("returnTicker")
        
        lastPrice = currVals[pair]["last"]

        print()
        
        print("{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now()) + " Period:%ss %s: %s" % (period, pair, lastPrice))
        time.sleep(int(period))
        
        
if __name__ == "__main__":          
    main(sys.argv[1:])
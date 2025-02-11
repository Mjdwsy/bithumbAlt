#-*-coding:utf-8-*-
#유튜버 개만아 님 전략을 제 전략에 맞게 수정한 코드 입니다.
#허락없는 무단배포는 금지합니다.


import requests
import jwt 
import time
import pandas as pd
import numpy as np
from urllib.parse import urlencode
from datetime import datetime, timedelta
import math
import hashlib
import json
import uuid

def request_with_retry(url, headers=None, method='get', data=None, max_retries=5, base_delay=1.0):
    """
    재시도 로직이 포함된 HTTP 요청 함수
    """
    for retry in range(max_retries):
        try:
            if method.lower() == 'get':
                response = requests.get(url, headers=headers, timeout=30)
            else:
                response = requests.post(url, headers=headers, data=data, timeout=30)
            
            response.raise_for_status()
            return response

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if retry == max_retries - 1:
                raise
            delay = base_delay * (2 ** retry)  # 지수 백오프
            print(f"Request failed: {str(e)}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
            continue
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                if retry == max_retries - 1:
                    raise
                delay = base_delay * (2 ** retry)
                print(f"Rate limit exceeded. Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
                continue
            raise

# 재시도 관련 상수 정의
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 16.0

def make_request(url, headers=None, method='get', data=None):
    """
    재시도 로직이 포함된 HTTP 요청 함수
    """
    retry_count = 0
    backoff = INITIAL_BACKOFF

    while retry_count < MAX_RETRIES:
        try:
            if method.lower() == 'get':
                response = requests.get(url, headers=headers, timeout=30)
            else:
                response = requests.post(url, headers=headers, data=data, timeout=30)

            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx, 5xx)
            return response

        except requests.exceptions.Timeout:
            retry_count += 1
            if retry_count == MAX_RETRIES:
                raise
            print(f"Request timed out. Retrying ({retry_count}/{MAX_RETRIES})...")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                retry_count += 1
                if retry_count == MAX_RETRIES:
                    raise
                print(f"Rate limit exceeded. Retrying ({retry_count}/{MAX_RETRIES})...")
            else:
                raise

        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count == MAX_RETRIES:
                raise
            print(f"Request failed: {e}. Retrying ({retry_count}/{MAX_RETRIES})...")

        # 지수 백오프 적용
        sleep_time = min(backoff * (2 ** (retry_count - 1)), MAX_BACKOFF)
        time.sleep(sleep_time)

    raise requests.exceptions.RequestException("Max retries exceeded")


# 빗썸 API 키 설정
API_KEY = '빗썸 API를 복사해서 붙여넣으세요.'
SECRET_KEY = '빗썸 SECRET KEY를 복사해서 붙여넣으세요'

apiUrl = 'https://api.bithumb.com'


#RSI지표 수치를 구해준다. 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
def GetRSI(ohlcv,period,st):
    try:
        delta = ohlcv['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        _gain = gain.iloc[st]
        _loss = loss.iloc[st]
        if _loss == 0:
            return 100.0
        RS = _gain / _loss
        return float(pd.Series(100 - (100 / (1 + RS)), name="RSI").iloc[st])
    except:
        return 50  # 에러 발생시 중립값 반환

#이동평균선 수치를 구해준다 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
def GetMA(ohlcv,period,st):
    close = ohlcv["close"]
    ma = close.rolling(period).mean()
    return float(ma.iloc[st])

#볼린저 밴드를 구해준다 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
#차트와 다소 오차가 있을 수 있습니다.
def GetBB(ohlcv,period,st):
    dic_bb = dict()

    ohlcv = ohlcv[::-1]
    ohlcv = ohlcv.shift(st + 1)
    close = ohlcv["close"].iloc[::-1]

    unit = 2.0
    bb_center=np.mean(close[len(close)-period:len(close)])
    band1=unit*np.std(close[len(close)-period:len(close)])

    dic_bb['ma'] = float(bb_center)
    dic_bb['upper'] = float(bb_center + band1)
    dic_bb['lower'] = float(bb_center - band1)

    return dic_bb


#일목 균형표의 각 데이타를 리턴한다 첫번째: 분봉/일봉 정보, 두번째: 기준 날짜
def GetIC(ohlcv,st):

    high_prices = ohlcv['high']
    close_prices = ohlcv['close']
    low_prices = ohlcv['low']


    nine_period_high =  ohlcv['high'].shift(-2-st).rolling(window=9).max()
    nine_period_low = ohlcv['low'].shift(-2-st).rolling(window=9).min()
    ohlcv['conversion'] = (nine_period_high + nine_period_low) /2
    
    period26_high = high_prices.shift(-2-st).rolling(window=26).max()
    period26_low = low_prices.shift(-2-st).rolling(window=26).min()
    ohlcv['base'] = (period26_high + period26_low) / 2
    
    ohlcv['sunhang_span_a'] = ((ohlcv['conversion'] + ohlcv['base']) / 2).shift(26)
    
    
    period52_high = high_prices.shift(-2-st).rolling(window=52).max()
    period52_low = low_prices.shift(-2-st).rolling(window=52).min()
    ohlcv['sunhang_span_b'] = ((period52_high + period52_low) / 2).shift(26)
    
    
    ohlcv['huhang_span'] = close_prices.shift(-26)


    nine_period_high_real =  ohlcv['high'].rolling(window=9).max()
    nine_period_low_real = ohlcv['low'].rolling(window=9).min()
    ohlcv['conversion'] = (nine_period_high_real + nine_period_low_real) /2
    
    period26_high_real = high_prices.rolling(window=26).max()
    period26_low_real = low_prices.rolling(window=26).min()
    ohlcv['base'] = (period26_high_real + period26_low_real) / 2
    


    
    dic_ic = dict()

    dic_ic['conversion'] = ohlcv['conversion'].iloc[st]
    dic_ic['base'] = ohlcv['base'].iloc[st]
    dic_ic['huhang_span'] = ohlcv['huhang_span'].iloc[-27]
    dic_ic['sunhang_span_a'] = ohlcv['sunhang_span_a'].iloc[-1]
    dic_ic['sunhang_span_b'] = ohlcv['sunhang_span_b'].iloc[-1]


  

    return dic_ic


#MACD의 12,26,9 각 데이타를 리턴한다 첫번째: 분봉/일봉 정보, 두번째: 기준 날짜
def GetMACD(ohlcv,st):
    macd_short, macd_long, macd_signal=12,26,9

    ohlcv["MACD_short"]=ohlcv["close"].ewm(span=macd_short).mean()
    ohlcv["MACD_long"]=ohlcv["close"].ewm(span=macd_long).mean()
    ohlcv["MACD"]=ohlcv["MACD_short"] - ohlcv["MACD_long"]
    ohlcv["MACD_signal"]=ohlcv["MACD"].ewm(span=macd_signal).mean() 

    dic_macd = dict()
    
    dic_macd['macd'] = ohlcv["MACD"].iloc[st]
    dic_macd['macd_siginal'] = ohlcv["MACD_signal"].iloc[st]
    dic_macd['ocl'] = dic_macd['macd'] - dic_macd['macd_siginal']

    return dic_macd


#스토캐스틱 %K %D 값을 구해준다 첫번째: 분봉/일봉 정보, 두번째: 기간, 세번째: 기준 날짜
def GetStoch(ohlcv,period,st):
    try:
        ndays_high = ohlcv['high'].rolling(window=period, min_periods=1).max()
        ndays_low = ohlcv['low'].rolling(window=period, min_periods=1).min()
        diff = ndays_high - ndays_low
        # 0으로 나누기 방지
        fast_k = pd.Series(0, index=ohlcv.index)  # 기본값 0으로 초기화
        mask = diff != 0  # 분모가 0이 아닌 경우만 계산
        fast_k[mask] = (ohlcv['close'][mask] - ndays_low[mask]) / diff[mask] * 100
        slow_d = fast_k.rolling(window=3, min_periods=1).mean()
        return float(fast_k.iloc[st]), float(slow_d.iloc[st])
    except:
        return 50, 50  # 에러 발생시 중립값 반환


#해당되는 리스트안에 해당 코인이 있는지 여부를 리턴하는 함수.
def CheckCoinInList(CoinList,Ticker):
    InCoinOk = False
    for coinTicker in CoinList:
        if coinTicker == Ticker:
            InCoinOk = True
            break

    return InCoinOk


#period: 1d,4h,1h,30m,15m,10m,5m,3m,1m
def GetOhlcv(ticker, period='1d', get_len=200):
    
    # 시작 시간을 현재 시간으로 설정
    #start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_timestamp = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    
    MaxTryCnt = 400
    trycnt = 0
    
    data = []
    if period == '1d':
            
        remaining_data = get_len
        
        while True:
            
            trycnt += 1
            if trycnt > MaxTryCnt:
                print("정보 못가져옴 무한루프 탈출!")
                break
            
            # API에서 데이터 가져오기
            url = f"https://api.bithumb.com/v1/candles/days?market={ticker}&to={start_timestamp}&count={get_len}"
            headers = {"accept": "application/json"}
            response = request_with_retry(url, headers=headers)
            
            if response.status_code == 200:
            
                new_data = response.json()
            
                if len(new_data) > 0:
            
                    data.extend(new_data)
                    remaining_data -= len(new_data)
                    
                    # 마지막 데이터인지 확인하고 루프 종료
                    if remaining_data <= 0:
                        break
                    
                    # 다음 요청을 위한 시작 시간 업데이트
                    start_timestamp = new_data[-1]['candle_date_time_kst']
                    time.sleep(0.2)
                else:
                    break

            
    else:
        
        unit = 1
        if period == '4h':
            unit = 240
        elif period == '1h':
            unit = 60
        elif period == '30m':
            unit = 30
        elif period == '15m':
            unit = 15
        elif period == '10m':
            unit = 10
        elif period == '5m':
            unit = 5
        elif period == '3m':
            unit = 3
        else:
            unit = 1
            
        # 시작 시간을 현재 시간으로 설정
        #start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_timestamp = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
        
        remaining_data = get_len
        
        while True:
            
            trycnt += 1
            if trycnt > MaxTryCnt:
                print("정보 못가져옴 무한루프 탈출!")
                break
            
            # API에서 데이터 가져오기
            url = f"https://api.bithumb.com/v1/candles/minutes/{unit}?market={ticker}&to={start_timestamp}&count={get_len}"
            headers = {"accept": "application/json"}
            response = request_with_retry(url, headers=headers)
            
            
            if response.status_code == 200:
            
                new_data = response.json()
            
            
                if len(new_data) > 0:
            
                    data.extend(new_data)
                    remaining_data -= len(new_data)
                    
                    # 마지막 데이터인지 확인하고 루프 종료
                    if remaining_data <= 0:
                        break
                    
                    # 다음 요청을 위한 시작 시간 업데이트
                    start_timestamp = new_data[-1]['candle_date_time_kst']
                    time.sleep(0.2)
                    
                else:
                    break

      

    # 데이터를 OHLCV 형식으로 변환
    ohlcv = []
    
    remaining_data = get_len
    st_len = 0
        
    for candle in data:
        ohlcv.append([
            candle['candle_date_time_kst'],
            candle['opening_price'],
            candle['high_price'],
            candle['low_price'],
            candle['trade_price'],
            candle['candle_acc_trade_volume'],
            candle['candle_acc_trade_price']
        ])
        st_len += 1
        if get_len <= st_len:
            break

    # DataFrame으로 변환하여 반환
    df = pd.DataFrame(ohlcv, columns=['datetime', 'open', 'high', 'low', 'close', 'volume', 'value'])
    df[[ 'open', 'high', 'low', 'close', 'volume', 'value']] = df[[ 'open', 'high', 'low', 'close', 'volume', 'value']].apply(pd.to_numeric)
    #df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    df.set_index('datetime', inplace=True)
    df = df.iloc[::-1]
    
    return df

#코인 리스트 얻기
def GetTickers(market='KRW'): #BTC를 넣으면 BTC 마켓!
    url = "https://api.bithumb.com/v1/market/all?isDetails=false"

    headers = {"accept": "application/json"}

    response = request_with_retry(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: API request failed with status code {response.status_code}")
        return []
    
    data = response.json()

    # market 파라미터에 따라 티커 필터링
    filtered_tickers = [item['market'] for item in data if item['market'].startswith(f"{market}-")]

    return filtered_tickers

#유의코인 리스트 얻기
def Get_CAUTION_Tickers(market='KRW'): #BTC를 넣으면 BTC 마켓!
    url = "https://api.bithumb.com/v1/market/all?isDetails=true"

    headers = {"accept": "application/json"}

    response = request_with_retry(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: API request failed with status code {response.status_code}")
        return []

    data = response.json()

    # market 파라미터에 따라 티커 필터링
    filtered_tickers = [item['market'] for item in data if item['market'].startswith(f"{market}-") and item['market_warning'].startswith("CAUTION")]

    return filtered_tickers

#거래대금이 많은 순으로 코인 리스트를 얻는다. 첫번째 : Interval기간, 두번째 : 몇개까지 
def GetTopCoinList(interval,top):
    print("--------------GetTopCoinList Start-------------------")
    Tickers = GetTickers()
    time.sleep(0.1)
    dic_coin_money = dict()

    for ticker in Tickers:
        print("--------------------------", ticker)
        try:
            time.sleep(0.1)
            df = GetOhlcv(ticker,interval,200)
            #volume_money = (df['close'].iloc[-1] * df['volume'].iloc[-1]) + (df['close'].iloc[-2] * df['volume'].iloc[-2])
            volume_money = float(df['value'].iloc[-1]) + float(df['value'].iloc[-2]) #거래대금!
            dic_coin_money[ticker] = volume_money
            print(ticker, dic_coin_money[ticker])
           # time.sleep(0.1)

        except Exception as e:
            print("---:",e)

    dic_sorted_coin_money = sorted(dic_coin_money.items(), key = lambda x : x[1], reverse= True)

    coin_list = list()
    cnt = 0
    for coin_data in dic_sorted_coin_money:
        cnt += 1
        if cnt <= top:
            coin_list.append(coin_data[0])
        else:
            break

    print("--------------GetTopCoinList End-------------------")

    return coin_list

#현재 가격 얻어오기!
def GetCurrentPrice(ticker):
    
    url = "https://api.bithumb.com/v1/ticker?markets=" + ticker

    headers = {"accept": "application/json"}

    response = request_with_retry(url, headers=headers)

    data = response.json()

    return float(data[-1]['trade_price'])

#잔고가져오기!
def GetBalances():
    # Generate access token
    payload = {
        'access_key': API_KEY,
        'nonce': str(uuid.uuid4()),
        'timestamp': round(time.time() * 1000)
    }
    jwt_token = jwt.encode(payload, SECRET_KEY)
    authorization_token = 'Bearer {}'.format(jwt_token)
    headers = {
        'Authorization': authorization_token
    }

    try:
        # Call API
        response = request_with_retry(apiUrl + '/v1/accounts', headers=headers)
        
        if response.status_code != 200:
            print(f"API 호출 실패. 상태 코드: {response.status_code}")
            return []
            
        result = response.json()
        if not isinstance(result, list):
            print(f"API 응답 형식 오류: {result}")
            return []
            
        return result
        
    except Exception as err:
        print(f"GetBalances 에러 발생: {err}")
        return []  # 에러 발생시 빈 리스트 반환

#티커에 해당하는 코인의 수익율을 구해서 리턴하는 함수.
def GetRevenueRate(balances,Ticker):
    try:
        #잔고 데이타에서 해당 코인에 대한 정보를 찾는다.
        for value in balances:
            try:
                if value['currency'] == Ticker.split('-')[1]:
                    time.sleep(0.1)
                    nowPrice = float(GetCurrentPrice(Ticker))
                    avg_buy_price = float(value['avg_buy_price'])
                    if avg_buy_price == 0:  # 평균 매수가가 0인 경우
                        return 0.0
                    revenue_rate = (nowPrice - avg_buy_price) * 100.0 / avg_buy_price
                    return revenue_rate
            except:
                continue

        return 0.0
    except:
        return 0.0

#수익금과 수익률을 리턴해주는 함수 (수수료는 생각안함) 
def GetRevenueMoneyAndRate(balances,Ticker):
            
    revenue_data = dict()

    revenue_data['revenue_money'] = 0.0
    revenue_data['revenue_rate'] = 0.0

    for value in balances:
        try:
            realTicker = value['unit_currency'] + "-" + value['currency']
            if Ticker.lower() == realTicker.lower():
                
                nowPrice = float(GetCurrentPrice(realTicker))
                avg_buy_price = float(value['avg_buy_price'])
                total_balance = float(value['balance']) + float(value['locked'])
                
                # 0으로 나누기 방지
                if avg_buy_price == 0:
                    revenue_data['revenue_money'] = 0.0
                    revenue_data['revenue_rate'] = 0.0
                else:
                    revenue_data['revenue_money'] = float((nowPrice - avg_buy_price) * total_balance)
                    revenue_data['revenue_rate'] = float((nowPrice - avg_buy_price) * 100.0 / avg_buy_price)
                time.sleep(0.06)
                break

        except Exception as e:
            print(f"GetRevenueMoneyAndRate 에러: {e}")
            continue

    return revenue_data

#해당 코인의 보유 수량을 얻어온다!
def GetCoinAmount(balances,Ticker,type="ALL"):
    CoinAmount = 0.0
    for value in balances:
        realTicker = value['unit_currency'] + "-" + value['currency']
        
        if Ticker == "KRW":
            realTicker = value['currency']

        if Ticker.lower() == realTicker.lower():
            CoinAmount = float(value['balance']) 
            if type == "ALL":
                CoinAmount += float(value['locked'])
            break
    return CoinAmount

#티커에 해당하는 코인의 총 매수금액을 리턴하는 함수
def GetCoinNowMoney(balances,Ticker):
    CoinMoney = 0.0
    for value in balances:
        realTicker = value['unit_currency'] + "-" + value['currency']
        if Ticker.lower() == realTicker.lower():
            CoinMoney = float(value['avg_buy_price']) * (float(value['balance']) + float(value['locked']))
            break
    return CoinMoney

#티커에 해당하는 코인의 현재 평가 금액을 리턴하는 함수
def GetCoinNowRealMoney(balances,Ticker):
    CoinMoney = 0.0
    for value in balances:
        realTicker = value['unit_currency'] + "-" + value['currency']
        if Ticker.lower() == realTicker.lower():
            time.sleep(0.1)
            nowPrice = GetCurrentPrice(realTicker)
            CoinMoney = float(nowPrice) * (float(value['balance']) + float(value['locked']))
            break
    return CoinMoney

#티커에 해당하는 코인이 매수된 상태면 참을 리턴하는함수
def IsHasCoin(balances,Ticker):
    HasCoin = False
    for value in balances:
        realTicker = value['unit_currency'] + "-" + value['currency']
        if Ticker.lower() == realTicker.lower() and (float(value['balance']) + float(value['locked'])) > 0:
            HasCoin = True
    return HasCoin

#내가 매수한 (가지고 있는) 코인 개수를 리턴하는 함수
def GetHasCoinCnt(balances):
    CoinCnt = 0
    for value in balances:
        if (float(value['balance']) + float(value['locked'])) > 0 and float(value['avg_buy_price']) != 0:
            CoinCnt += 1
    return CoinCnt


#티커에 해당하는 코인의 평균 매입단가를 리턴한다.
def GetAvgBuyPrice(balances, Ticker):
    avg_buy_price = 0
    for value in balances:
        realTicker = value['unit_currency'] + "-" + value['currency']
        if Ticker.lower() == realTicker.lower():
            time.sleep(0.1)
            avg_buy_price = float(value['avg_buy_price'])
    return avg_buy_price

#총 원금을 구한다!
def GetTotalMoney(balances):
    total = 0.0
    for value in balances:
        try:
            ticker = value['unit_currency'] + "-" + value['currency']
            if ticker.upper() == "KRW-KRW": #원화일 때는 평균 매입 단가가 0이므로 구분해서 총 평가금액을 구한다.
                total += (float(value['balance']) + float(value['locked']))
            else:
                avg_buy_price = float(value['avg_buy_price'])
                if avg_buy_price != 0 and (float(value['balance']) != 0 or float(value['locked']) != 0):
                    total += (avg_buy_price * (float(value['balance']) + float(value['locked'])))
        except Exception as e:
            print("")
    return total

#총 평가금액을 구한다!
def GetTotalRealMoney(balances):
    total = 0.0
    for value in balances:

        try:
            ticker = value['unit_currency'] + "-" + value['currency']
            if ticker.upper() == "KRW-KRW": #원화일 때는 평균 매입 단가가 0이므로 구분해서 총 평가금액을 구한다.
                total += (float(value['balance']) + float(value['locked']))
            else:
            
                avg_buy_price = float(value['avg_buy_price'])
                if avg_buy_price != 0 and (float(value['balance']) != 0 or float(value['locked']) != 0): #드랍받은 코인(평균매입단가가 0이다) 제외 하고 현재가격으로 평가금액을 구한다,.
                   
                    time.sleep(0.1)
                    nowPrice = GetCurrentPrice(ticker)
                    total += (float(nowPrice) * (float(value['balance']) + float(value['locked'])))
        except Exception as e:
            print("")


    return total

#거래대금 폭발 여부 첫번째: 캔들 정보, 두번째: 이전 5개의 평균 거래량보다 몇 배 이상 큰지
#이전 캔들이 그 이전 캔들 5개의 평균 거래금액보다 몇 배이상 크면 거래량 폭발로 인지하고 True를 리턴해줍니다
#현재 캔들[-1]은 막 시작했으므로 이전 캔들[-2]을 보는게 맞다!
def IsVolumePung(ohlcv,st):

    Result = False
    try:
        avg_volume = (float(ohlcv['volume'].iloc[-3]) + float(ohlcv['volume'].iloc[-4]) + float(ohlcv['volume'].iloc[-5]) + float(ohlcv['volume'].iloc[-6]) + float(ohlcv['volume'].iloc[-7])) / 5.0
        if avg_volume * st < float(ohlcv['volume'].iloc[-2]):
            Result = True
    except Exception as e:
        print("IsVolumePung ---:", e)

    
    return Result

#시장가 매수한다. 2초뒤 잔고 데이타 리스트를 리턴한다.
def BuyCoinMarket(Ticker,Money):
    time.sleep(0.05)


    # Set API parameters
    requestBody = dict( market=Ticker, side='bid', price=Money, ord_type='price')

    # Generate access token
    query = urlencode(requestBody).encode()
    hash = hashlib.sha512()
    hash.update(query)
    query_hash = hash.hexdigest()
    payload = {
        'access_key': API_KEY,
        'nonce': str(uuid.uuid4()),
        'timestamp': round(time.time() * 1000), 
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }   
    jwt_token = jwt.encode(payload, SECRET_KEY)
    authorization_token = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization_token,
    'Content-Type': 'application/json'
    }

    try:
        # Call API
        response = request_with_retry(apiUrl + '/v1/orders', headers=headers, method='post', data=json.dumps(requestBody))
        # handle to success or fail
        print(response.status_code)
        print(response.json())
    except Exception as err:
        # handle exception
        print(err)
        
        
    time.sleep(2.0)
    #내가 가진 잔고 데이터를 다 가져온다.
    balances = GetBalances()
    return balances

#시장가 매도한다. 2초뒤 잔고 데이타 리스트를 리턴한다.
def SellCoinMarket(Ticker,Volume):
    time.sleep(0.05)

    # Set API parameters
    requestBody = dict( market=Ticker, side='ask', volume=Volume, ord_type='market')

    # Generate access token
    query = urlencode(requestBody).encode()
    hash = hashlib.sha512()
    hash.update(query)
    query_hash = hash.hexdigest()
    payload = {
        'access_key': API_KEY,
        'nonce': str(uuid.uuid4()),
        'timestamp': round(time.time() * 1000), 
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }   
    jwt_token = jwt.encode(payload, SECRET_KEY)
    authorization_token = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization_token,
    'Content-Type': 'application/json'
    }

    try:
        # Call API
        response = request_with_retry(apiUrl + '/v1/orders', headers=headers, method='post', data=json.dumps(requestBody))
        # handle to success or fail
        print(response.status_code)
        print(response.json())
    except Exception as err:
        # handle exception
        print(err)
        
        
    time.sleep(2.0)
    #내가 가진 잔고 데이터를 다 가져온다.
    balances = GetBalances()
    return balances

#넘겨받은 가격과 수량으로 지정가 매수한다.
def BuyCoinLimit(Ticker,Price,Volume):
    time.sleep(0.05)
    
    # Set API parameters
    requestBody = dict( market=Ticker, side='bid', volume=Volume, price=get_tick_size(Price), ord_type='limit')

    # Generate access token
    query = urlencode(requestBody).encode()
    hash = hashlib.sha512()
    hash.update(query)
    query_hash = hash.hexdigest()
    payload = {
        'access_key': API_KEY,
        'nonce': str(uuid.uuid4()),
        'timestamp': round(time.time() * 1000), 
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }   
    jwt_token = jwt.encode(payload, SECRET_KEY)
    authorization_token = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization_token,
    'Content-Type': 'application/json'
    }

    try:
        # Call API
        response = request_with_retry(apiUrl + '/v1/orders', headers=headers, method='post', data=json.dumps(requestBody))
        # handle to success or fail
        print(response.status_code)
        print(response.json())
    except Exception as err:
        # handle exception
        print(err)
                
#넘겨받은 가격과 수량으로 지정가 매도한다.
def SellCoinLimit(Ticker,Price,Volume):
    time.sleep(0.05)
    
    # Set API parameters
    requestBody = dict( market=Ticker, side='ask', volume=Volume, price=get_tick_size(Price), ord_type='limit')

    # Generate access token
    query = urlencode(requestBody).encode()
    hash = hashlib.sha512()
    hash.update(query)
    query_hash = hash.hexdigest()
    payload = {
        'access_key': API_KEY,
        'nonce': str(uuid.uuid4()),
        'timestamp': round(time.time() * 1000), 
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }   
    jwt_token = jwt.encode(payload, SECRET_KEY)
    authorization_token = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization_token,
    'Content-Type': 'application/json'
    }

    try:
        # Call API
        response = request_with_retry(apiUrl + '/v1/orders', headers=headers, method='post', data=json.dumps(requestBody))
        # handle to success or fail
        print(response.status_code)
        print(response.json())
    except Exception as err:
        # handle exception
        print(err)

#현재 라이브중인 미체결 주문 리스트 얻기
def GetActiveOrders(Ticker):
    
    ResultList = list()
    # Set API parameters
    param = dict( market=Ticker, limit=100, page=1, order_by='desc' )
    query = urlencode(param)

    # Generate access token
    hash = hashlib.sha512()
    hash.update(query.encode())
    query_hash = hash.hexdigest()
    payload = {
        'access_key': API_KEY,
        'nonce': str(uuid.uuid4()),
        'timestamp': round(time.time() * 1000), 
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }   
    jwt_token = jwt.encode(payload, SECRET_KEY)
    authorization_token = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization_token
    }

    try:
        # Call API
        response = request_with_retry(apiUrl + '/v1/orders?' + query, headers=headers)
        # handle to success or fail
        print(response.status_code)
        
        data = response.json()
        
        for order in data:
            if order['state'] == "wait":
                ResultList.append(order)
        
    except Exception as err:
        # handle exception
        print(err)
        
    return ResultList


#해당 코인에 걸어진 매수매도주문 모두를 취소한다.
def CancelCoinOrder(Ticker):
    
    orders_data = GetActiveOrders(Ticker)
    if len(orders_data) > 0:
        for order in orders_data:
            time.sleep(0.1)
                        
            # Set API parameters
            param = dict( uuid=order['uuid'] )

            # Generate access token
            query = urlencode(param).encode()
            hash = hashlib.sha512()
            hash.update(query)
            query_hash = hash.hexdigest()
            payload = {
                'access_key': API_KEY,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000), 
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512',
            }   
            jwt_token = jwt.encode(payload, SECRET_KEY)
            authorization_token = 'Bearer {}'.format(jwt_token)
            headers = {
            'Authorization': authorization_token
            }

            try:
                # Call API
                response = request_with_retry(apiUrl + '/v1/order', headers=headers, method='delete', data=json.dumps(param))
                # handle to success or fail
                print(response.status_code)
                print(response.json())
            except Exception as err:
                # handle exception
                print(err)
                        
#틱사이즈 보정!! 
def get_tick_size(price, method="floor"):

    if method == "floor":
        func = math.floor
    elif method == "round":
        func = round 
    else:
        func = math.ceil 

    if price >= 1000000:
        tick_size = func(price / 1000) * 1000
    elif price >= 500000:
        tick_size = func(price / 500) * 500
    elif price >= 100000:
        tick_size = func(price / 100) * 100
    elif price >= 50000:
        tick_size = func(price / 50) * 50
    elif price >= 10000:
        tick_size = func(price / 10) * 10
    elif price >= 1000:
        tick_size = func(price / 1) * 1
    elif price >= 100:
        tick_size = func(price / 1) * 1
    elif price >= 10:
        tick_size = func(price / 0.01) / 100
    elif price >= 1:
        tick_size = func(price / 0.001) / 1000
    else:
        tick_size = func(price / 0.0001) / 10000

    return tick_size

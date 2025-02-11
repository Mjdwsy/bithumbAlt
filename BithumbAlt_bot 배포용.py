# 유튜버 개만아 님의 코드에서 저의 전략을 추가하여 개선한 코드 입니다.
# 허락없는 무단 배포는 금지합니다.


# "기본 설정
# - 총 자산 50% 투자(InvestRate = 0.5)
# - 최대 30개 코인 투자(MaxCoinCnt = 30)
# - 코인당 최소 매수금액: 10,000원
# - BTC, ETH, USDT 제외

# 매수 조건
# 1) 거래대금 필터링
#    - 상위 50개 중 하위 30개 선정
#    - 일 거래대금 10억원 이상
#    - 거래대금 상위 & 등락률 상위 조건 동시 만족

# 2) 비트코인 상승장 확인
#    - 60일선 상승 또는 현재가 60일선 위
#    - 120일선 상승 또는 현재가 120일선 위
#    - 주간 등락률 양수

# 3) 개별 코인 매수 조건
#    - 현재가가 시가보다 높음
#    - 5일선, 50일선 모두 상승
#    - 현재가가 두 이평선 위

# 매도 조건
# 1) 손절 조건(-20% 이하)
#    - 수익률 -20% 이하
#    - 평가금액 5,500원 이하

# 2) 익절 조건(+50% 이상)
#    - 수익률 50% 이상 도달

# 3) 추세 반전 조건
#    - 비트코인 120일선 아래
#    - 5일선 또는 50일선 하락추세이면서 현재가보다 높을 때

# 투자금 관리
# - 코인당 투자금 = 총투자금 / 코인개수
# - 거래대금 10일평균의 1/2000으로 제한
# - 잔고 부족시 99%만 매수

# 실행 주기
# - 매일 오전 9시 정각 실행
# - 텔레그램으로 매매 현황 알림
# - 거래 기록 CSV 파일로 저장"



import time
import pytz
from datetime import datetime, timedelta
import schedule
import json
import myBithumb
import telegram_alert
import pandas as pd
import numpy as np
import pprint
import os

def save_trade_log(coin, action, price, quantity, profit=None, profit_rate=None):
    """거래 기록을 CSV 파일로 저장하는 함수
    
    Args:
        coin (str): 코인 심볼
        action (str): 매수/매도 구분
        price (float): 거래 가격
        quantity (float): 거래 수량
        profit (float, optional): 수익금
        profit_rate (float, optional): 수익률
    """
    now = datetime.now(pytz.timezone('Asia/Seoul'))
    log_dir = "trade_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, f"trade_history_{now.strftime('%Y%m')}.csv")
    
    # CSV 파일이 없으면 타이틀과 헤더와 함께 생성
    if not os.path.exists(log_file):
        with open(log_file, 'w', encoding='utf-8-sig') as f:
            # 타이틀 추가
            f.write("빗썸 알트코인 자동매매 거래 기록\n")
            f.write(f"생성일시: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 100 + "\n\n")
            
            # 컬럼 헤더 추가
            columns = ['거래일시', '코인', '거래종류', '거래가격', '거래수량', '거래금액', '수익금', '수익률']
            f.write(','.join(columns) + '\n')
    
    value = price * quantity
    log_data = {
        '거래일시': now.strftime('%Y-%m-%d %H:%M:%S'),
        '코인': coin,
        '거래종류': action,
        '거래가격': price,
        '거래수량': quantity,
        '거래금액': value,
        '수익금': profit if profit is not None else '',
        '수익률': f"{profit_rate:.2f}%" if profit_rate is not None else ''
    }
    
    df = pd.DataFrame([log_data])
    df.to_csv(log_file, mode='a', header=False, index=False, encoding='utf-8-sig')
    print(f"거래 기록 저장 완료: {action} {coin} - 가격: {price:,.0f}원, 수량: {quantity:.8f}")

def main_trading_logic():
    global day_n, DateDateTodayDict, AltInvestList, AltSellList, IsBuyGo
    
    print(f"빗썸 알트 투자 시행 - {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}")
    
    #시간 정보를 읽는다
    time_info = time.gmtime()
    
    if DateDateTodayDict.get('date', 0) != time_info.tm_mday:
        print("곧 업무를 시작 합니다!")
        time.sleep(5.0) #안전전략등 다른 봇과 돌릴 경우.
        
        #내가 가진 잔고 데이터를 다 가져온다.
        balances = myBithumb.GetBalances()
        
        print("\n=== 전체 보유자산 현황 ===")
        print("-" * 100)
        print(f"{'코인':^10}{'보유수량':^20}{'평균매수가':^15}{'현재가':^15}{'평가금액':^15}{'수익률':^10}")
        print("-" * 100)
        
        total_eval_price = 0
        for balance in balances:
            currency = balance['currency']
            coin_balance = float(balance['balance'])
            avg_price = float(balance['avg_buy_price']) if balance['avg_buy_price'] != '0' else 0
            
            if currency == 'KRW':
                print(f"{'KRW':^10}{float(coin_balance):,.2f}{'원':^5}")
                continue
                
            if coin_balance < 0.0001:  # 너무 작은 수량은 제외
                continue
                
            try:
                ticker = f"KRW-{currency}"
                if ticker in myBithumb.GetTickers():  # Tickers에 있는 경우에만 처리
                    current_price = myBithumb.GetCurrentPrice(ticker)
                    eval_price = coin_balance * current_price
                    
                    if eval_price < 1000:  # 1000원 미만 평가금액 제외
                        continue
                        
                    profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                    total_eval_price += eval_price
                    
                    print(f"{currency:^10}"
                          f"{coin_balance:^20.8f}"
                          f"{format(int(avg_price), ','):>15}"
                          f"{format(int(current_price), ','):>15}"
                          f"{format(int(eval_price), ','):>15}"
                          f"{profit_rate:>10.2f}%")
            except Exception as e:
                continue
        
        print("-" * 100)
        print(f"총 평가금액: {format(int(total_eval_price), ',')}원")
        
        # 원화 잔고
        krw_balance = float([balance['balance'] for balance in balances if balance['currency'] == 'KRW'][0])
        print(f"원화 잔고: {format(int(krw_balance), ',')}원")
        print(f"총 보유자산: {format(int(total_eval_price + krw_balance), ',')}원")
        
        # 금일 매매 현황
        print("\n=== 금일 매매 현황 ===")
        if len(AltInvestList) > 0 or len(AltSellList) > 0:
            if len(AltInvestList) > 0:
                print("매수한 코인:")
                for coin in AltInvestList:
                    print(f"- {coin}")
            if len(AltSellList) > 0:
                print("매도한 코인:")
                for coin in AltSellList:
                    print(f"- {coin}")
        else:
            print("금일 매매 없음")
        
        TotalMoney = myBithumb.GetTotalMoney(balances) #총 원금
        TotalRealMoney = myBithumb.GetTotalRealMoney(balances) #총 평가금액
        
        print("TotalMoney", TotalMoney)
        print("TotalRealMoney", TotalRealMoney)
        
        InvestTotalMoney = TotalMoney * InvestRate #총 투자원금+ 남은 원화 기준으로 투자!!!!
        print("InvestTotalMoney", InvestTotalMoney)
        
        # MaxCoinCnt가 0 이하일 경우 기본값 1로 설정하여 0으로 나누기 방지
        safe_divisor = max(1, MaxCoinCnt + 1)
        InvestCoinMoney = InvestTotalMoney / safe_divisor #코인당 투자금!
        
        Tickers = myBithumb.GetTickers()
        
        stock_df_list = []
        
        for ticker in Tickers:
            try:
                print("----->", ticker ,"<-----")
                df = myBithumb.GetOhlcv(ticker,'1d',700)
                
                df['value'] = df['close'] * df['volume']
                
                period = 14
                
                delta = df["close"].diff()
                up, down = delta.copy(), delta.copy()
                up[up < 0] = 0
                down[down > 0] = 0
                _gain = up.ewm(com=(period - 1), min_periods=period).mean()
                _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
                RS = _gain / _loss
                
                df['RSI'] = pd.Series(100 - (100 / (1 + RS)), name="RSI")
                
                df['prevRSI'] = df['RSI'].shift(1)
                df['ma5_rsi_before'] = df['RSI'].rolling(5).mean().shift(1)
                
                
                df['prevValue'] = df['value'].shift(1)
                df['prevClose'] = df['close'].shift(1)
                df['prevOpen'] = df['open'].shift(1)
                df['prevClose2'] = df['close'].shift(2)
                
                df['prevChange'] = (df['prevClose'] - df['prevClose2']) / df['prevClose2']
                
                df['value_ma'] = df['value'].rolling(window=10).mean().shift(1)
                
                
                df['prevCloseW'] = df['close'].shift(7)
                df['prevChangeW'] = (df['prevClose'] - df['prevCloseW']) / df['prevCloseW']
                
                #이렇게 3일선 부터 200일선을 자동으로 만들 수 있다!
                ma_dfs = []
                
                # 이동 평균 계산
                for ma in range(3, 201):
                    ma_df = df['close'].rolling(ma).mean().rename('ma'+str(ma)+'_before').shift(1)
                    ma_dfs.append(ma_df)
                    
                    ma_df = df['close'].rolling(ma).mean().rename('ma'+str(ma)+'_before2').shift(2)
                    ma_dfs.append(ma_df)
                # 이동 평균 데이터 프레임을 하나로 결합
                ma_df_combined = pd.concat(ma_dfs, axis=1)
                
                # 원본 데이터 프레임과 결합
                df = pd.concat([df, ma_df_combined], axis=1)
                
                df.dropna(inplace=True) #데이터 없는건 날린다!
                
                data_dict = {ticker: df}
                stock_df_list.append(data_dict)
                
                time.sleep(0.2)
                
            except Exception as e:
                print("Exception ", e)
        
        # Combine the OHLCV data into a single DataFrame
        combined_df = pd.concat([list(data_dict.values())[0].assign(ticker=ticker) for data_dict in stock_df_list for ticker in data_dict])
        
        # Sort the combined DataFrame by date
        combined_df.sort_index(inplace=True)
        
        pprint.pprint(combined_df)
        print(" len(combined_df) ", len(combined_df))
        
        combined_df.index = pd.DatetimeIndex(combined_df.index).strftime('%Y-%m-%d %H:%M:%S')
        
        #가장 최근 날짜를 구해서 가져옴 
        date = combined_df.iloc[-1].name
        
        btc_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == 'KRW-BTC')]
        
        pick_coins_top = combined_df.loc[combined_df.index == date].groupby('ticker')['prevValue'].max().nlargest(50).nsmallest((int(MaxCoinCnt))) #거래대금 상위 50개 중 하위 30개
        
        pick_coins_top_change = combined_df.loc[combined_df.index == date].groupby('ticker')['prevChange'].max().nlargest(50).nsmallest((int(MaxCoinCnt))) #등락률 상위 50개 중 하위 30개
        
        items_to_remove = list()
        
        #투자중 코인!
        for coin_ticker in AltInvestList:
            #잔고가 있는 경우.
            if myBithumb.IsHasCoin(balances,coin_ticker) == True and myBithumb.GetCoinNowRealMoney(balances,coin_ticker) >= minmunMoney: 
                print("")
                
                #수익금과 수익률을 구한다!
                revenue_data = myBithumb.GetRevenueMoneyAndRate(balances,coin_ticker)
                
                msg = coin_ticker + "현재 수익률 : 약 " + str(round(revenue_data['revenue_rate'],2)) + "% 수익금 : 약" + str(format(round(revenue_data['revenue_money']), ',')) + "원"
                print(msg)
                telegram_alert.SendMessage(msg)
                
                stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == coin_ticker)]
                
                if len(stock_data) == 1:
                    IsSell = False
                    
                    # 손절 로직 추가: 수익률이 -20% 이하이거나 평가금액이 5500원 이하일 때
                    eval_money = myBithumb.GetCoinNowRealMoney(balances, coin_ticker)
                    current_revenue_rate = float(revenue_data['revenue_rate'])  # float로 변환
                    
                    if current_revenue_rate <= -20 or eval_money <= 5500:
                        IsSell = True
                        msg = f"{coin_ticker} - 손절 조건 만족 (수익률: {round(current_revenue_rate,2)}%, 평가금액: {format(round(eval_money), ',')}원)"
                        print(msg)
                        telegram_alert.SendMessage(msg)
                    
                    # 익절 로직 추가: 수익률이 50% 이상일 때
                    elif current_revenue_rate >= 50:
                        IsSell = True
                        msg = f"{coin_ticker} - 익절 조건 만족 (수익률: {round(current_revenue_rate,2)}%)"
                        print(msg)
                        telegram_alert.SendMessage(msg)
                    
                    if btc_data['ma120_before'].values[0]  >  btc_data['prevClose'].values[0]:
                        IsSell = True
                        
                    if ((stock_data['ma'+str(long_ma1)+'_before2'].values[0]  >  stock_data['ma'+str(long_ma1)+'_before'].values[0] and stock_data['ma'+str(long_ma1)+'_before'].values[0]  >  stock_data['prevClose'].values[0]) or (stock_data['ma'+str(long_ma2)+'_before2'].values[0]  >  stock_data['ma'+str(long_ma2)+'_before'].values[0] and stock_data['ma'+str(long_ma2)+'_before'].values[0]  >  stock_data['prevClose'].values[0])) :
                        IsSell = True
                    
                    if IsSell == True:
                        AllAmt = myBithumb.GetCoinAmount(balances,coin_ticker) 
                        
                        balances = myBithumb.SellCoinMarket(coin_ticker,AllAmt)
                        
                        msg = coin_ticker + " 빗썸 알트 투자 : 조건을 불만족하여 모두 매도처리 했어요!!"
                        print(msg)
                        telegram_alert.SendMessage(msg)
                        
                        items_to_remove.append(coin_ticker)
                        
            #잔고가 없는 경우
            else:
                #투자중으로 나와 있는데 잔고가 없다? 있을 수 없지만 수동으로 매도한 경우..
                items_to_remove.append(coin_ticker)
        
        #리스트에서 제거
        for item in items_to_remove:
            AltInvestList.remove(item)
        
        #파일에 저장
        with open(invest_file_path, 'w') as outfile:
            json.dump(AltInvestList, outfile)
        
        #거래대금 11~30위 
        for ticker in pick_coins_top.index:
            if ticker in OutCoinList: #제외할 코인!
                continue
        
            CheckMsg = ticker
            
            print("---거래대금 상위 OK..." ,ticker)
            
            CheckMsg += " 거래대금 조건 만족! "
            
            IsAlReadyInvest = False
            for coin_ticker in AltInvestList:
                if ticker == coin_ticker: 
                    IsAlReadyInvest = True
                    break
            
            IsTOPInChange = False
            for ticker_t in pick_coins_top_change.index:
                if ticker_t == ticker:
                    coin_top_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker_t)]
                    if len(coin_top_data) == 1:
                        IsTOPInChange = True
                        break
            
            stock_data = combined_df[(combined_df.index == date) & (combined_df['ticker'] == ticker)]
            
            if len(stock_data) == 1 and IsAlReadyInvest == False and IsTOPInChange == True: 
                print("--- 등락률 상위 OK..." ,ticker)
                
                CheckMsg += " 등락률 상위 조건 만족! "
                IsBuyGo = False
                
                if (btc_data['ma60_before2'].values[0]  <  btc_data['ma60_before'].values[0] or btc_data['ma60_before'].values[0]  <  btc_data['prevClose'].values[0])  and (btc_data['ma120_before2'].values[0]  <  btc_data['ma120_before'].values[0] or btc_data['ma120_before'].values[0]  <  btc_data['prevClose'].values[0]) and stock_data['prevChangeW'].values[0] > 0:
                    CheckMsg += " 비트코인 조건 만족! "
                    #거래대금 10억 이상
                    if stock_data['prevValue'].values[0] > 1000000000:  
                        CheckMsg += " 거래대금 조건 만족 "
                        if stock_data['prevClose'].values[0] > stock_data['prevOpen'].values[0] and ((stock_data['ma'+str(long_ma1)+'_before2'].values[0]  <=  stock_data['ma'+str(long_ma1)+'_before'].values[0] and stock_data['ma'+str(long_ma1)+'_before'].values[0]  <=  stock_data['prevClose'].values[0]) and (stock_data['ma'+str(long_ma2)+'_before2'].values[0]  <=  stock_data['ma'+str(long_ma2)+'_before'].values[0] and stock_data['ma'+str(long_ma2)+'_before'].values[0]  <=  stock_data['prevClose'].values[0])) :
                            CheckMsg += " 추가 조건 만족! 모든 코인이 투자된 것이 아니라면 매수!! "
                            IsBuyGo = True
                            
            #조건 만족하고 아직 20개 코인이 투자된 것이 아니라면 
            if IsBuyGo == True and len(AltInvestList) < int(MaxCoinCnt):
                Rate = 1.0
                
                BuyMoney = InvestCoinMoney * Rate
                
                #투자금 제한!
                if BuyMoney > stock_data['value_ma'].values[0] / 2000:
                    BuyMoney = stock_data['value_ma'].values[0] / 2000
                
                if BuyMoney < minmunMoney:
                    BuyMoney = minmunMoney
                
                #원화 잔고를 가져온다
                won = myBithumb.GetCoinAmount(balances,"KRW")
                print("# Remain Won :", won)
                time.sleep(0.04)
                
                #
                if BuyMoney > won:
                    BuyMoney = won * 0.99 #슬리피지 및 수수료 고려
                
                balances = myBithumb.BuyCoinMarket(ticker,BuyMoney)
                
                msg = ticker + " 빗썸 알트 투자 : 조건 만족 하여 매수!!"
                print(msg)
                telegram_alert.SendMessage(msg)
                
                AltInvestList.append(ticker)
                
                #파일에 저장
                with open(invest_file_path, 'w') as outfile:
                    json.dump(AltInvestList, outfile)
        
        print(CheckMsg)
        telegram_alert.SendMessage(CheckMsg)

        # 수익률 조건에 따른 코인 매도 (-20% 이상 또는 +50% 이상)
        print("\n=== 수익률 조건 만족 시 코인 매도 ===")
        for ticker in myBithumb.GetTickers():
            try:
                if myBithumb.IsHasCoin(balances, ticker):
                    revenue_data = myBithumb.GetRevenueMoneyAndRate(balances, ticker)
                    revenue_money = float(revenue_data['revenue_money'])
                    revenue_rate = float(revenue_data['revenue_rate'])
                    
                    # 수익률이 -20% 이하이거나 +50% 이상일 때 전량 매도
                    if revenue_rate <= -20.0 or revenue_rate >= 50.0:
                        coin_amount = myBithumb.GetCoinAmount(balances, ticker)
                        current_price = myBithumb.GetCurrentPrice(ticker)
                        
                        print(f"\n코인: {ticker}")
                        print(f"현재 수익률: {revenue_rate:.2f}%")
                        print(f"현재 수익금: {format(int(revenue_money), ',')}원")
                        print(f"매도할 수량: {coin_amount:.8f}")
                        print(f"매도 예상 금액: {format(int(float(coin_amount) * float(current_price)), ',')}원")
                        
                        # 시장가 매도 실행
                        balances = myBithumb.SellCoinMarket(ticker, coin_amount)
                        
                        sell_reason = "손절" if revenue_rate <= -20.0 else "수익 실현"
                        msg = f"빗썸 알트 봇 - {ticker} 코인 {sell_reason}! 수익률 {revenue_rate:.2f}% (수익금: {format(int(revenue_money), ',')}원)"
                        print(msg)
                        telegram_alert.SendMessage(msg)
                        
                        # 매도 리스트에 추가
                        if ticker not in AltSellList:
                            AltSellList.append(ticker)
                    
            except Exception as e:
                print(f"매도 중 에러 발생: {e}")
                continue
        
        print("\n=== 투자 정보 요약 ===")
        print(f"총 투자 가능 금액: {format(int(TotalMoney), ',')}원")
        print(f"실제 투자 금액: {format(int(InvestTotalMoney), ',')}원")
        print(f"투자 비중: {InvestRate * 100}%")
        print(f"최대 투자 코인 수: {MaxCoinCnt}개")
        
        # 현재 보유 코인 정보 출력
        print("\n=== 보유 코인 상세 정보 ===")
        total_value = 0
        total_invested = 0  # 총 투자금액
        coin_count = 0
        for ticker in Tickers:
            # 제외할 코인은 건너뛰기
            if ticker.split('-')[1] in ['KRW', 'BTC', 'ETH', 'USDT', 'PCHT', 'BCD', 'SGB']:
                continue
                
            if myBithumb.IsHasCoin(balances, ticker):
                amount = myBithumb.GetCoinAmount(balances, ticker)
                # 보유 수량이 0.0001 미만인 경우 제외
                if float(amount) < 0.0001:
                    continue
                    
                coin_count += 1
                avg_price = myBithumb.GetAvgBuyPrice(balances, ticker)
                current_price = myBithumb.GetCurrentPrice(ticker)
                
                # 투자금액 계산
                invested = float(amount) * float(avg_price)
                total_invested += invested
                
                value = float(amount) * float(current_price)
                
                # 평가금액이 1000원 미만인 경우 제외
                if value < 1000:
                    coin_count -= 1
                    continue
                    
                profit_rate = ((float(current_price) - float(avg_price)) / float(avg_price)) * 100 if float(avg_price) > 0 else 0
                total_value += value
                
                print(f"\n코인: {ticker}")
                print(f"보유수량: {amount:.8f}")
                print(f"평균매수가: {format(int(float(avg_price)), ',')}원")
                print(f"현재가: {format(int(float(current_price)), ',')}원")
                print(f"투자금액: {format(int(invested), ',')}원")
                print(f"평가금액: {format(int(value), ',')}원")
                print(f"수익률: {profit_rate:.2f}%")
        
        if coin_count == 0:
            print("현재 보유중인 코인이 없습니다.")
        
        # 전체 포트폴리오 가치
        print("\n=== 포트폴리오 전체 요약 ===")
        print(f"총 투자금액: {format(int(total_invested), ',')}원")
        print(f"총 평가금액: {format(int(total_value), ',')}원")
        total_profit_rate = ((total_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0
        print(f"전체 수익률: {total_profit_rate:.2f}%")
        print(f"보유 코인 수: {coin_count}개")

        msg = " 빗썸 알트 투자 : 오늘 업무 끝!!"
        print(msg)
        telegram_alert.SendMessage(msg)

        #체크 날짜가 다르다면 맨 처음이거나 날이 바뀐것이다!!
        DateDateTodayDict['date'] = time_info.tm_mday
        with open(today_file_path, 'w') as outfile:
            json.dump(DateDateTodayDict, outfile)
    else:
        print("빗썸 알트 투자 : 오늘은 실행이 완료되어 업무가 끝났어요!")

# 전역 변수 초기화
day_n = 0  # 장이 변경되었을때 0으로 리셋된다. 매수 시도 횟수
DateDateTodayDict = dict()
AltInvestList = []
AltSellList = []
IsBuyGo = True  # 매수 가능 여부를 나타내는 플래그

# 설정값
InvestRate = 0.5  # 투자 비중
MaxCoinCnt = 30  # 투자 코인 개수
long_ma1 = 5
long_ma2 = 50
minmunMoney = 10000
OutCoinList = ['KRW-USDT','KRW-BTC','KRW-ETH']

# 파일 경로
today_file_path = "BithumbAltInvestToday.json"
invest_file_path = "BithumbAltInvestList.json"
sell_file_path = "BithumbAltSellList.json"

# 파일 로드
try:
    with open(today_file_path, 'r') as json_file:
        DateDateTodayDict = json.load(json_file)
        day_n = DateDateTodayDict.get('date', 0)
except Exception as e:
    print("날짜 파일 없음")

try:
    with open(invest_file_path, 'r') as json_file:
        AltInvestList = json.load(json_file)
except Exception as e:
    print("매수 리스트 파일 없음")

try:
    with open(sell_file_path, 'r') as json_file:
        AltSellList = json.load(json_file)
except Exception as e:
    print("매도 리스트 파일 없음")

def run_scheduler():
    # 한국 시간대 설정
    korea_tz = pytz.timezone('Asia/Seoul')
    
    # 현재 시간을 한국 시간으로 변환하여 출력
    now = datetime.now(korea_tz)
    print(f"현재 한국 시간: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # 매일 오전 9시에 실행하도록 스케줄 설정
    schedule.every().day.at("09:00").do(main_trading_logic)
    
    print("스케줄러가 시작되었습니다. 매일 한국 시간 오전 9시에 실행됩니다.")
    
    while True:
        try:
            # 현재 시간을 한국 시간으로 변환
            now = datetime.now(korea_tz)
            
            # 스케줄러 실행
            pending_jobs = schedule.get_jobs()
            for job in pending_jobs:
                print(f"다음 실행 예정: {job.next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            schedule.run_pending()
            
            # 매 10분마다 현재 시간 출력
            if now.minute % 10 == 0 and now.second == 0:
                print(f"현재 한국 시간: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            time.sleep(1)
            
        except Exception as e:
            error_msg = f"스케줄러 실행 중 에러 발생: {str(e)}"
            print(error_msg)
            telegram_alert.SendMessage(error_msg)
            time.sleep(60)  # 에러 발생시 1분 대기

if __name__ == "__main__":
    try:
        print("빗썸 알트코인 자동매매가 시작되었습니다.")
        run_scheduler()
    except KeyboardInterrupt:
        print("프로그램을 종료합니다.")
    except Exception as e:
        error_msg = f"빗썸 알트코인 봇 에러 발생: {str(e)}"
        print(error_msg)
        telegram_alert.SendMessage(error_msg)

import pandas as pd
import pandas_ta as ta
df = pd.DataFrame({'close': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20, 21, 22]})
bb = ta.bbands(df['close'], length=20, std=2.0)
print(bb.columns)

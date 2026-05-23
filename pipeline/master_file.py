
#---------------------------------------------------------------------------------
# ELT turdaki pipelini dasturlashga harakat qilaman
#---------------------------------------------------------------------------------
import pandas as pd
from cleaner import drop_dublicate, price_cleaner

def extract():
    df = pd.read_csv('data/Praperad/olx_apartments.csv')
    return df




def main():
    df = extract()
    df_cleaned=drop_dublicate(df)
    df_cleaned = price_cleaner(df_cleaned)



if __name__ == "__main__":
    main()
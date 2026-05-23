
#---------------------------------------------------------------------------------
# ELT turdaki pipelini dasturlashga harakat qilaman
#---------------------------------------------------------------------------------
import pandas as pd
from cleaner import price_cleaner

df = pd.read_csv('data/Praperad/olx_apartments.csv')




def main():
    price_cleaner(df)
    


if __name__ == "__main__":
    main()
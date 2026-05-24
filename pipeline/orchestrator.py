#---------------------------------------------------------------------------------
# ETL turdaki pipelini dasturlashga harakat qilaman
#---------------------------------------------------------------------------------

import pandas as pd
from transformation import drop_duplicate, price_cleaner, housing_type_cleaner, validate_rooms

def extract():
    df = pd.read_csv('data/Praperad/olx_apartments.csv')
    return df




def main():
    df = extract()

    df_cleaned=drop_duplicate(df)

    df_cleaned = price_cleaner(df_cleaned)

    df_cleaned = housing_type_cleaner(df_cleaned)

    df_cleaned = validate_rooms(df_cleaned)


if __name__ == "__main__":
    main()
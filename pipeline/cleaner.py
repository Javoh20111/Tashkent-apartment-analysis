import pandas as pd
import numpy as np

def drop_dublicate(df_cleaned):
    before = len(df_cleaned)

    df_cleaned = df_cleaned.drop_duplicates()
    df_cleaned = df_cleaned.drop_duplicates(subset=['listing_id'])

    after = len(df_cleaned)

    return df_cleaned


def price_cleaner(df_cleaned):
    # Birinchi bo'lib narxi yo'q qatorlarni olib tashlaymiz
    before1 = len(df_cleaned['price'])
    df_cleaned.dropna(subset=['price'], inplace=True)

    # Endi bir xil valyutaga o'tqazib olamiz
    exchange_rate = 12700
    df_cleaned['price_usd'] = df_cleaned['price']
    df_cleaned.loc[df_cleaned['currency']=="UZS", 'price_usd'] = (
        df_cleaned.loc[df_cleaned['currency']=="UZS", 'price_usd'] / exchange_rate
    ).round(1)
    return df_cleaned

def housing_type_cleaner(df_cleaned):
    valid_housing_type = {
    'new building': 'new building',
    'resale': 'resale',
    'Новостройка': 'new building',
    'новостройка': 'new building',
    'Новостройка.': 'new building',
    'Вторичка,кирпичный дом.': 'new building'
    }

    def validate_housing_type(text):
        if pd.isna(text):
            return np.nan

        if text in valid_housing_type:
            return valid_housing_type[text]
        else:
            return np.nan

        return text

    df_cleaned['housing_type'] = df_cleaned['housing_type'].apply(validate_housing_type)
    return df_cleaned
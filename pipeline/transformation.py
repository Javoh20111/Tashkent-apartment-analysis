import pandas as pd
import numpy as np


def drop_columns(df_cleaned):
    df_cleaned = df_cleaned.drop(columns=["living_area_m2" ,"kitchen_area_m2"])
    return df_cleaned

def drop_duplicate(df_cleaned):
    before = len(df_cleaned)

    df_cleaned = df_cleaned.drop_duplicates()
    df_cleaned = df_cleaned.drop_duplicates(subset=['listing_id'])

    after = len(df_cleaned)
    print(40*"*")
    print("Drop duplicate jarayoni")
    print(40*"-")
    print(f"Jami elonlar soni: {before}")
    print(f"Duplicate soni: {before - after}")
    print(f"Duplicatelarsiz: {after}")

    return df_cleaned


def price_cleaner(df_cleaned):
    # Birinchi bo'lib narxi yo'q qatorlarni olib tashlaymiz
    before = len(df_cleaned)
    df_cleaned = df_cleaned.dropna(subset=['price'])
    after = len(df_cleaned)

    # Endi bir xil valyutaga o'tqazib olamiz
    exchange_rate = 12700
    df_cleaned['price_usd'] = df_cleaned['price']
    df_cleaned.loc[df_cleaned['currency']=="UZS", 'price_usd'] = (
        df_cleaned.loc[df_cleaned['currency']=="UZS", 'price_usd'] / exchange_rate
    ).round(1)

    print(40*"*")
    print("Price validation jarayoni")
    print(40*"-")
    print(f"Price columndagi bosh maydonlar soni: {before - after}")
    print("price_usd column yaratildi!")

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
    print(40*"*")
    print("housing_type validation jarayoni")
    print(40*"-")
    print("Jarayon pajarildi:")
    print(df_cleaned['housing_type'].value_counts()) 

    return df_cleaned

def validate_rooms(df_cleaned):
    print(4*"\n")
    print(40*'*')
    print("rooms validation jarayoni")
    print(40*"-")

    print(f"Oldin: \n {df_cleaned['rooms'].value_counts().head(9)}")

    df_cleaned_1 = df_cleaned[df_cleaned['rooms'] < 7].copy()

    print(f"Keyin: \n {df_cleaned_1['rooms'].value_counts()}")

    return df_cleaned_1
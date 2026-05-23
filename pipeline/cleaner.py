import pandas as pd

""" 
before1 = len(df_cleaned['price'])
df_cleaned.dropna(subset=['price'], inplace=True)
print(f"Qatorlar soni(Dublikat bilan): {before1}")
print(f"Olib tashlangan qator soni: {before1 - len(df_cleaned['price'])}")
print(f"Noyoblik soni: {len(df_cleaned['price'])}")
 """


def drop_dublicate(df_cleaned):
    
def price_cleaner(df_cleaned):
    # Birinchi bo'lib narxi yo'q qatorlarni olib tashlaymiz
    before1 = len(df_cleaned['price'])
    df_cleaned.dropna(subset=['price'], inplace=True)
    print(f"Qatorlar soni(Dublikat bilan): {before1}")
    print(f"Olib tashlangan qator soni: {before1 - len(df_cleaned['price'])}")
    print(f"Noyoblik soni: {len(df_cleaned['price'])}")

    # Endi bir xil valyutaga o'tqazib olamiz
    exchange_rate = 12700
    df_cleaned['price_usd'] = df_cleaned['price']
    df_cleaned.loc[df_cleaned['currency']=="UZS", 'price_usd'] = (
        df_cleaned.loc[df_cleaned['currency']=="UZS", 'price_usd'] / exchange_rate
    ).round(1)
    return df_cleaned
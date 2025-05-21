import numpy as np
import pandas as pd
from scipy.signal import find_peaks

def format_decimal_cols(df):
    """Format decimal columns to 2 decimal places"""
    df = df.copy()
    numeric_cols = df.select_dtypes(include=['float64', 'float32']).columns
    for col in numeric_cols:
        df.loc[:, col] = df[col].round(2)
    return df

def list_posisi_puncak(df, min_height):
    peaks, _ = find_peaks(df["High"].to_numpy())
    df_puncak = pd.DataFrame({
        'datetime': df.iloc[peaks]['datetime'],
        'High': df.iloc[peaks]['High']
    })
    return format_decimal_cols(df_puncak[df_puncak['High'] > min_height])

def hitung_koefisien(heights, h0):
    def fungsi_restitusi(h1, h2):
        if h1 < h2:
            return np.sqrt(h1 / h2) if h1 > 0 else 0
        return 1 if h1 == h2 else 0
    
    koefisien = [(i, fungsi_restitusi(h, h0 if i == 0 else heights[i-1])) 
                 for i, h in enumerate(heights)]
    
    df_koef = pd.DataFrame(koefisien, columns=['No', 'Koefisien Restitusi'])
    return format_decimal_cols(df_koef[~df_koef['Koefisien Restitusi'].isin([0.0, 1.0])])

def hitung_statistik(data):
    data_clean = [x for x in data if x is not None]
    data_clean = [x for x in data_clean if x != 1.0 or x != 0.0]
    if len(data_clean) == 0:
        data_clean = [1.0,1.0]
    rata_rata = np.mean(data_clean)
    median = np.median(data_clean)
    try:
        modus = pd.Series(data_clean).mode()[0]
    except IndexError:
        modus = None
    standar_deviasi = np.std(data_clean)
    ketidakpastian = standar_deviasi / np.sqrt(len(data_clean))
    ketelitian = (1 - standar_deviasi / rata_rata) * 100
    
    df_statistik = pd.DataFrame({
        'Statistik': ['Rata-rata', 'Median', 'Modus', 'Standar Deviasi', 'Ketidakpastian', 'Ketelitian'],
        'Nilai': [rata_rata, median, modus, standar_deviasi, ketidakpastian, ketelitian]
    })
    return format_decimal_cols(df_statistik)

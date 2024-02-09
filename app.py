import asyncio
import io

import supabase

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from data import get_data, reset_data
from datetime import datetime

import plotly.express as px 
 
from shiny import reactive, render, ui
from shiny.express import input, render, ui
from shinywidgets import render_widget

SUPABASE_URL = "https://oqfqrlhqmuapbdpemcfg.supabase.co"
SUPABASE_SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xZnFybGhxbXVhcGJkcGVtY2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDcxNTcwNzMsImV4cCI6MjAyMjczMzA3M30.h92qn052dRqsUvTp9DJdFmTwVIVmLXbRgKhRqhf-rz8"
SUPABASE_ID = "oqfqrlhqmuapbdpemcfg"

client = supabase.create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

df = pd.DataFrame()
id = 0


all_times = reactive.Value([])
timer = reactive.Value([datetime.now().timestamp()])
start_times = pd.Timestamp('NaT')
stop_times = pd.Timestamp('NaT')

list_puncak = []
list_koefisien = []

#----------------------------------------------------------------------------------------------------
ui.page_opts(title="Hitung Koefisien Restitusi Dari Tumbukan")

with ui.sidebar(open="closed"):
    with ui.accordion():
        with ui.accordion_panel("Input data"):
            with ui.card():
                ui.input_slider("Init_h","Input tinggi sensor (cm):", 0, 50, 31)
                ui.input_slider("range_data", "Filter Range Data (cm)", min=0, max=50, value=[0, 31])  
                ui.input_slider("min", "Filter minimal puncak (cm)", 0, 30, 10)
                
        with ui.accordion_panel("Tombol"):    
            with ui.card(fill=True):
                ui.input_action_button("start","Mulai")
                ui.input_action_button("stop","Berhenti")

        with ui.accordion_panel("Pewaktu"):    
            with ui.card():
                @reactive.Effect
                @reactive.event(input.start)
                def _():
                    global start_times, client,df
                    
                    df = reset_data(client)
                    
                    start_times = datetime.now()
                    y = all_times().copy()
                    y.append(datetime.now().timestamp())
                    all_times.set(y)
                
                @reactive.calc
                def cur_time():
                    global start_times
                    reactive.invalidate_later(1)
                    return datetime.now().strftime('%H:%M:%S')

                @render.ui
                def clock():
                    return f"Waktu Realtime : {cur_time()}"
                
                @render.text
                @reactive.event(input.start)
                def start_text():
                    global start_times, df
                    t = start_times.strftime('%H:%M:%S')
                    return f"Mulai : {t}"
                
                @reactive.effect
                @reactive.event(input.start)
                def show_notification():
                    type_txt = "notification"
                    ui.notification_show(
                        "Pengambilan Data dimulai!",
                        type="notification",
                        duration=2,
                    )
                    
                @reactive.Effect
                @reactive.event(input.stop)
                def _():
                    global stop_times
                    stop_times = datetime.now()

                    y = all_times().copy()
                    y.append(datetime.now().timestamp())
                    all_times.set(y)

                @render.text
                @reactive.event(input.stop)
                def stop_text():
                    global stop_times,df
                    t = stop_times.strftime('%H:%M:%S')
                    return f"Berhenti : {t}"

                @reactive.effect
                @reactive.event(input.stop)
                def show_notification():
                    type_txt = "notification"
                    ui.notification_show(
                        "Pengambilan Data Selesai!",
                        type="message",
                        duration=2,
                    )

                @render.text
                @reactive.event(input.stop)
                def txt():
                    x = all_times().copy()
                    z = [round(j - i, 2) for i, j in zip(x[:-1], x[1:])]
                    return f"Selisih : {z[-1]} s"

        # with ui.accordion_panel("Download Panel"):    
        #     with ui.card(fill=True):
        #         ui.input_checkbox_group(  
        #             "checkbox_group",  
        #             "Pilih Ekstensi",  
        #             {  
        #                 "csv": "CSV",  
        #                 "txt": "TXT",  
        #                 "xlsx": "Excel",  
        #             },  
        #         )
        
        #         with ui.card(fill=True):
        #             ui.card_header("Download")
        #             ui.input_action_button("download","Download Data")

        #             @render.download(filename="Data_Plot.csv",media_type="csv")
        #             @reactive.event(input.download)
        #             def download_data():
        #                 global df
        #                 def convert_df_to_files(df, file_extensions):
        #                     if not isinstance(df, pd.DataFrame):
        #                         raise ValueError("Input harus berupa objek DataFrame.")
                            
        #                     ext_map = {'csv': 'data.csv', 'txt': 'data.txt', 'xlsx': 'data.xlsx'}
                            
        #                     for ext in file_extensions:
        #                         ext = ext.lower()
        #                         if ext in ext_map:
        #                             df.to_csv(ext_map[ext], sep='\t' if ext == 'txt' else ',', index=False)
        #                         else:
        #                             print(f"Ekstensi {ext} tidak didukung. Lewati.")
                    
        #                 convert_df_to_files(df, input.checkbox_group())            
                        
        #                 df = get_data(client)
        #                 init_h = float(input.Init_h())
        #                 min_filter = float(input.min())
        #                 df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )            
        #                 df_puncak = list_posisi_puncak(df,min_filter)
        #                 data_puncak = df_puncak['High'].tolist()
        #                 list_koefisien = hitung_koefisien(data_puncak,init_h)
        #                 list_koefisien = list_koefisien['Koefisien Restitusi'].tolist()
        #                 hasil_analisis = hitung_statistik(list_koefisien)
        #                 yield hasil_analisis


#----------------------------------------------------------------------------------------------------
with ui.layout_columns(fill=True):
    h_card = 400
    with ui.card(height=h_card,fill=True):
        ui.card_header("Plot Tumbukan", style="color:white; background:#2A2A2A !important;")

        @render_widget
        @reactive.event(input.stop)          
        def initial_plot():
            global start_times ,stop_times, df, client
            
            df = get_data(client)
            
            init_h = input.Init_h()
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )
            
            lineplot = px.line(
                data_frame=df,
                x="datetime",
                y="High"
            ).update_layout(
                title={"text": "Plot Ketinggian Objek", "x": 0.5},
                yaxis_title="High (cm)",
                xaxis_title="Time (hh:mm:ss)",
                autosize=True
            )
            return lineplot  

    with ui.card(height=h_card,fill=True):
        ui.card_header("Data Tumbukan", style="color:white; background:#2A2A2A !important;")
        
        @render.text
        @reactive.event(input.stop)
        def table_data():
            global df
            df = get_data(client)
            return f"Jumlah Data : {len(df)}"
        
        @render.data_frame
        @reactive.event(input.stop)   
        def tables_df():
            global start_times, stop_times, df,client
            df = get_data(client)
            init_h = input.Init_h()
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )
            return render.DataGrid(df)  

#----------------------------------------------------------------------------------------------------
def list_posisi_puncak(df, min):
    peaks, _ = find_peaks(df["High"].to_numpy())
    df_puncak = df.iloc[peaks][['datetime', 'High']]
    df_puncak = df_puncak[df_puncak['High'] > min]
    return df_puncak

def hitung_koefisien(list_ketinggian,h0):
    def fungsi_restitusi(h1, h2):
        if h1 < h2:
            try:
                koefisien = np.sqrt(h1 / h2)
                return koefisien
            except Exception as e:
                print(e)
                return 0
        elif h1 == h2:
            return 1
        else:
            return 0
        
    list_koefisien = []
    num = []
    for i, h in enumerate(list_ketinggian):
        if i == 0:
            h1 = fungsi_restitusi(h, h0)
        else:
            h1 = fungsi_restitusi(h, list_ketinggian[i - 1])
        num.append(i)
        list_koefisien.append(h1)
    print(len(num),"\t",len(list_koefisien))
    dataframe_koefisien = pd.DataFrame({'No': num, 'Koefisien Restitusi': list_koefisien})
    dataframe_koefisien = dataframe_koefisien[(dataframe_koefisien['Koefisien Restitusi'] != 1.0) & (dataframe_koefisien['Koefisien Restitusi'] != 0.0)]
    return dataframe_koefisien

def hitung_statistik(data):
    data_clean = [x for x in data if x is not None]
    data_clean = [x for x in data_clean if x != 1.0 or x != 0.0 ]
    if len(data_clean) == 0:
        #raise ValueError("Data tidak valid atau tidak mengandung nilai numerik.")
        data_clean = [1.0,1.0]
    rata_rata = np.mean(data_clean)
    median = np.median(data_clean)
    modus = pd.Series(data_clean).mode()
    standar_deviasi = np.std(data_clean)
    ketidakpastian = standar_deviasi / np.sqrt(len(data_clean))
    ketelitian = (1 - standar_deviasi / rata_rata) * 100
    
    # Membuat DataFrame untuk menyimpan statistik
    df_statistik = pd.DataFrame({
        'Statistik': ['Rata-rata', 'Median', 'Modus', 'Standar Deviasi', 'Ketidakpastian', 'Ketelitian'],
        'Nilai': [rata_rata, median, modus, standar_deviasi, ketidakpastian, ketelitian]
    })
    print(df_statistik)
    
    return df_statistik

#----------------------------------------------------------------------------------------------------
with ui.layout_columns(fill=True):
    h_card = 400
    with ui.card(id="#Calc",height=h_card,fill=True):
        ui.card_header("Plot Puncak Tumbukan", style="color:white; background:#2A2A2A !important;")
        
        @render_widget
        @reactive.event(input.stop)
        def plot_puncak_tumbukan():
            global df
            df = get_data(client)
            init_h = input.Init_h()
            min_filter = float(input.min())
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )            
            df_puncak = list_posisi_puncak(df,min_filter)
            
            fig = px.line(df, x='datetime', y='High', title='Plot Ketinggian')
            fig.add_scatter(x=df_puncak['datetime'], y=df_puncak['High'], mode='markers', name='Puncak')
            return fig.update_layout(
                title={"text": "Plot Puncak Ketinggian Objek", "x": 0.5},
                yaxis_title="High (cm)",
                xaxis_title="Time (hh:mm:ss)",
                autosize=True
            )         

    
    with ui.card(id='#Calc',height=h_card,fill=True):
        ui.card_header("Data Puncak Tumbukan", style="color:white; background:#2A2A2A !important;")

        @render.text
        @reactive.event(input.stop)
        def puncak_tumbukan_():
            global df
            df = get_data(client)
            init_h = input.Init_h()
            min_filter = float(input.min())

            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )            
            df_puncak = list_posisi_puncak(df, min_filter)
            return f"Jumlah Puncak : {len(df_puncak)}"  

        @render.data_frame
        @reactive.event(input.stop)
        def data_puncak_tumbukan():
            global df
            df = get_data(client)
            init_h = input.Init_h()            
            min_filter = float(input.min())

            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )
            list_puncak = list_posisi_puncak(df,min_filter)
            return list_puncak
    
    
with ui.layout_columns(fill=True):
    with ui.card(id="#Calc",height=300,fill=True):
        ui.card_header("Koefisien Restitusi", style="color:white; background:#2A2A2A !important;")

        @render.data_frame
        @reactive.event(input.stop)
        def koefisien():
            df = get_data(client)
            init_h = float(input.Init_h())
            min_filter = float(input.min())
            
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )            
            df_puncak = list_posisi_puncak(df,min_filter)
            data_puncak = df_puncak['High'].tolist()
            
            list_koefisien = hitung_koefisien(data_puncak,init_h)
            return list_koefisien
        
    with ui.card(id="#Calc",height=300,fill=True):
        ui.card_header("Analisis Statistik", style="color:white; background:#2A2A2A !important;")            

        @render.data_frame
        @reactive.event(input.stop)
        def analisis_data():
            df = get_data(client)
            init_h = float(input.Init_h())
            min_filter = float(input.min())
            
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x) )            
            df_puncak = list_posisi_puncak(df,min_filter)
            data_puncak = df_puncak['High'].tolist()
            
            list_koefisien = hitung_koefisien(data_puncak,init_h)
            list_koefisien = list_koefisien['Koefisien Restitusi'].tolist()
            hasil_analisis = hitung_statistik(list_koefisien)
            print(hasil_analisis)
            print(type(hasil_analisis))
            return hasil_analisis
            
  
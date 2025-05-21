import asyncio
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px 
from shiny import reactive, render, ui
from shiny.express import input, render, ui
from shinywidgets import render_widget
from data import DataManager
from analysis import format_decimal_cols, list_posisi_puncak, hitung_koefisien, hitung_statistik
import zipfile
import os
import plotly.io as pio
import shutil

# Initialize globals
data_manager = DataManager()
df = pd.DataFrame()
id = 0
all_times = reactive.Value([])
timer = reactive.Value([datetime.now().timestamp()])
start_times = pd.Timestamp('NaT')
stop_times = pd.Timestamp('NaT')

# Add plot placeholders
plot_ketinggian = reactive.Value(None)
plot_puncak = reactive.Value(None)

# Helper functions
def save_plot_to_png(fig, filename):
    """Helper function to save plotly figure as PNG with proper settings"""
    pio.write_image(fig, filename, format='png', engine='kaleido', 
                    width=1200, height=800, scale=2)

def create_base_plot():
    """Create empty plot template"""
    fig = px.line()
    fig.update_layout(
        showlegend=True,
        title={
            "x": 0.5,
            "xanchor": "center"
        },
        yaxis_title="Ketinggian (cm)",
        xaxis_title="Waktu (hh:mm:ss)",
        autosize=True,
        height=400  # Set default height
    )
    return fig

# Initialize empty plots pada startup
@reactive.Effect
def init_plots():
    if plot_ketinggian() is None:
        plot_ketinggian.set(create_base_plot())
    if plot_puncak() is None:
        plot_puncak.set(create_base_plot())

# Reset plots saat start
@reactive.effect
@reactive.event(input.start)
def reset_plots():
    plot_ketinggian.set(create_base_plot())
    plot_puncak.set(create_base_plot())

# UI Definition
ui.page_opts(title="Hitung Koefisien Restitusi Dari Tumbukan")

with ui.sidebar(open="always"):
    ui.input_text("sample_name", "Nama Sampel:", placeholder="Nama Sampel")
    ui.input_action_button("start","Mulai")
    ui.input_action_button("stop","Berhenti")
    ui.input_action_button("reset","Reset")
    ui.input_action_button("download","Download Data")

    @reactive.effect
    @reactive.event(input.reset)
    def reset_all():
        global df, start_times, stop_times, all_times
        # Reset data di database
        df, _ = data_manager.reset_data()
        # Reset waktu
        start_times = pd.Timestamp('NaT')
        stop_times = pd.Timestamp('NaT')
        all_times.set([])
        # Tampilkan notifikasi
        ui.notification_show(
            "Data telah direset!",
            type="warning",
            duration=2,
        )

    @reactive.effect
    @reactive.event(input.download)
    async def download_data():
        if len(df) == 0:
            ui.notification_show("Tidak ada data untuk diunduh!", type="error", duration=2)
            return
        
        try:
            # Get sample name and timestamp
            sample_name = input.sample_name() or ""  # Default if empty
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create directory with sample name
            temp_dir = os.path.join(os.getcwd(), f"temp_{sample_name}_{timestamp}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Get existing figures
            fig_raw = plot_ketinggian()
            fig_peaks = plot_puncak()
            
            # Save plots with sample name
            plot_path1 = os.path.join(temp_dir, f"{sample_name}_plot_mentah.png")
            plot_path2 = os.path.join(temp_dir, f"{sample_name}_plot_puncak.png")
            
            save_plot_to_png(fig_raw, plot_path1)
            save_plot_to_png(fig_peaks, plot_path2)
            
            # Excel file with sample name
            excel_path = os.path.join(temp_dir, f"{sample_name}_hasil_analisis.xlsx")
            
            # Save DataFrames to Excel
            df_raw = df.copy()
            init_h = float(input.Init_h())
            min_filter = float(input.min())
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df_raw.loc[:, 'High'] = df_raw["High"].apply(lambda x: init_h - float(x))
                format_decimal_cols(df_raw).to_excel(writer, sheet_name='Data Mentah', index=False)
                
                df_puncak = list_posisi_puncak(df_raw, min_filter)
                df_puncak.to_excel(writer, sheet_name='Data Puncak', index=False)
                
                data_puncak = df_puncak['High'].tolist()
                df_koef = hitung_koefisien(data_puncak, init_h)
                df_koef.to_excel(writer, sheet_name='Koefisien Restitusi', index=False)
                
                list_koefisien = df_koef['Koefisien Restitusi'].tolist()
                df_stat = hitung_statistik(list_koefisien)
                df_stat.to_excel(writer, sheet_name='Statistik', index=False)

            # Create ZIP file with sample name
            zip_filename = f"{sample_name}_hasil_analisis_{timestamp}.zip"
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                # Add files with proper paths
                zipf.write(plot_path1, os.path.basename(plot_path1))
                zipf.write(plot_path2, os.path.basename(plot_path2))
                zipf.write(excel_path, os.path.basename(excel_path))
            
            # Clean up temp directory after zip is created
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            ui.notification_show(
                f"Data {sample_name} berhasil diunduh ke {zip_filename}!",
                type="message",
                duration=3,
            )
        except Exception as e:
            ui.notification_show(
                f"Gagal mengunduh data: {str(e)}",
                type="error",
                duration=3,
            )
            # Clean up on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

            
    ui.input_slider("Init_h","Input tinggi sensor (cm):", min=15, max=150, value=35)
    ui.input_slider("range_data", "Filter Range Data (cm)", min=0, max=50, value=[0, 31])  
    ui.input_slider("min", "Filter minimal puncak (cm)", min=0, max=35, value=15)


    @reactive.Effect
    @reactive.event(input.start)
    def _():
        global start_times, df
        df = data_manager.reset_data()
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
        global start_times
        t = start_times.strftime('%H:%M:%S')
        return f"Mulai : {t}"
    
    @reactive.effect
    @reactive.event(input.start)
    def show_notification():
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
        global stop_times
        t = stop_times.strftime('%H:%M:%S')
        return f"Berhenti : {t}"

    @reactive.effect
    @reactive.event(input.stop)
    def show_notification():
        ui.notification_show(
            "Pengambilan Data Selesai!",
            type="message",
            duration=3,
        )

    @render.text
    @reactive.event(input.stop)
    def txt():
        x = all_times().copy()
        z = [round(j - i, 2) for i, j in zip(x[:-1], x[1:])]
        return f"Selisih : {z[-1]} s"

# Main layout
with ui.layout_columns(fill=True):
    h_card = 400
    with ui.card(height=h_card,fill=True):
        ui.card_header("Plot Tumbukan", style="color:white; background:#2A2A2A !important;")

        @render_widget
        @reactive.event(input.stop)          
        def initial_plot():
            global df
            df = data_manager.get_data()
            if len(df) == 0:
                return plot_ketinggian()
                
            df = df.copy()
            init_h = input.Init_h()
            df.loc[:, 'High'] = df["High"].apply(lambda x: float(init_h) - float(x))
            
            # Get current plot or create new one
            fig = plot_ketinggian() or create_base_plot()
            
            # Clear all traces
            fig.data = []
            
            # Add new trace
            fig.add_scatter(
                x=df["datetime"],
                y=df["High"],
                name="Ketinggian",
                mode='lines'
            )
            
            # Update layout
            fig.update_layout(
                title={
                    "text": "Plot Ketinggian Objek vs Waktu",
                    "x": 0.5,
                    "xanchor": "center"
                },
                legend_title_text="Data"
            )
            
            # Store updated plot
            plot_ketinggian.set(fig)
            return fig  

    with ui.card(height=h_card,fill=True):
        ui.card_header("Data Tumbukan", style="color:white; background:#2A2A2A !important;")
        
        @render.text
        @reactive.event(input.stop)
        def table_data():
            global df
            df = data_manager.get_data()
            return f"Jumlah Data : {len(df)}"
        
        @render.data_frame
        @reactive.event(input.stop)   
        def tables_df():
            global df
            df = data_manager.get_data()
            df = df.copy()  # Create explicit copy
            init_h = input.Init_h()
            df.loc[:, 'High'] = df["High"].apply(lambda x: float(init_h) - float(x))
            return render.DataGrid(format_decimal_cols(df))  

with ui.layout_columns(fill=True):
    h_card = 400
    with ui.card(id="calc_card",height=h_card,fill=True):
        ui.card_header("Plot Puncak Tumbukan", style="color:white; background:#2A2A2A !important;")
        
        @render_widget
        @reactive.event(input.stop)
        def plot_puncak_tumbukan():
            global df
            df = data_manager.get_data()
            init_h = input.Init_h()
            min_filter = float(input.min())
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x))            
            df_puncak = list_posisi_puncak(df, min_filter)
            
            # Update placeholder plot
            fig = plot_puncak() or create_base_plot()
            fig.data = []  # Clear existing traces
            
            # Add new data
            fig.add_scatter(
                x=df["datetime"],
                y=df["High"],
                name="Data Ketinggian",
                mode='lines'
            )
            fig.add_scatter(
                x=df_puncak['datetime'], 
                y=df_puncak['High'], 
                mode='markers', 
                name='Titik Puncak',
                marker=dict(size=10, symbol='circle')
            )
            
            # Update layout
            fig.update_layout(
                title={"text": "Plot Ketinggian dengan Puncak Tumbukan"},
                legend_title_text="Keterangan"
            )
            
            plot_puncak.set(fig)
            return fig         

    with ui.card(id='calc_data',height=h_card,fill=True):
        ui.card_header("Data Puncak Tumbukan", style="color:white; background:#2A2A2A !important;")

        @render.text
        @reactive.event(input.stop)
        def puncak_tumbukan_():
            global df
            df = data_manager.get_data()
            init_h = input.Init_h()
            min_filter = float(input.min())
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x))            
            df_puncak = list_posisi_puncak(df, min_filter)
            return f"Jumlah Puncak : {len(df_puncak)}"  

        @render.data_frame
        @reactive.event(input.stop)
        def data_puncak_tumbukan():
            global df
            df = data_manager.get_data()
            init_h = input.Init_h()            
            min_filter = float(input.min())
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x))
            list_puncak = list_posisi_puncak(df, min_filter)
            return list_puncak
    
with ui.layout_columns(fill=True):
    with ui.card(id="calc_koef",height=300,fill=True):
        ui.card_header("Koefisien Restitusi", style="color:white; background:#2A2A2A !important;")

        @render.data_frame
        @reactive.event(input.stop)
        def koefisien():
            df = data_manager.get_data()
            init_h = float(input.Init_h())
            min_filter = float(input.min())
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x))            
            df_puncak = list_posisi_puncak(df, min_filter)
            data_puncak = df_puncak['High'].tolist()
            list_koefisien = hitung_koefisien(data_puncak, init_h)
            return list_koefisien
        
    with ui.card(id="calc_stat",height=300,fill=True):
        ui.card_header("Analisis Statistik", style="color:white; background:#2A2A2A !important;")            

        @render.data_frame
        @reactive.event(input.stop)
        def analisis_data():
            df = data_manager.get_data()
            init_h = float(input.Init_h())
            min_filter = float(input.min())
            df['High'] = df["High"].apply(lambda x: float(init_h) - float(x))            
            df_puncak = list_posisi_puncak(df, min_filter)
            data_puncak = df_puncak['High'].tolist()
            list_koefisien = hitung_koefisien(data_puncak, init_h)
            list_koefisien = list_koefisien['Koefisien Restitusi'].tolist()
            hasil_analisis = hitung_statistik(list_koefisien)
            return hasil_analisis


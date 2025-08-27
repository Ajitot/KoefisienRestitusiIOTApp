import pandas as pd
import re
import matplotlib.pyplot as plt
import os

# Data directory
data_dir = 'Data_Baru'

# Output directory
output_dir = 'output_tex'

# Jenis Bola
list_bola = [
    "Bola Bekel","Bola Tenis Meja", "Bola Tenis Lapang", 
        "Bola Plastik", "Bola Sepak Karet"
]

# mendapatkan seluruh file dari direktori data
data_files = [f for f in os.listdir(data_dir) if f.endswith('.xlsx')]
analisis_files = [f for f in os.listdir(data_dir) if f.endswith('.txt')]
image_files = [f for f in os.listdir(data_dir) if f.endswith('.png') or f.endswith('.jpg')]

def extract_ringkasan_statistik(filename, jenis_bola, percobaan):
    """
    Ekstrak jumlah pantulan valid, koefisien rata-rata, dan standar deviasi
    dari bagian 'RINGKASAN STATISTIK' file analisis bola.
    Return: DataFrame dengan kolom ['Jumlah Pantulan', 'Koefisien Rata-rata', 'Standar Deviasi']
    """
    with open(filename, encoding='utf-8') as f:
        text = f.read()

    pantulan = re.search(r'Pasangan Pantulan Valid\s*:\s*(\d+)', text)

    tinggi_awal = 35  # cm
    tinggi_list = []
    # Ambil semua ketinggian pada bagian PERHITUNGAN KOEFISIEN
    # Format: Tinggi: 33.00 cm → 25.00 cm
    tinggi_matches = re.findall(r'Tinggi:\s*([\d.]+)\s*cm\s*→\s*([\d.]+)\s*cm', text)
    for awal, akhir in tinggi_matches:
        tinggi_list.append(float(awal))
        tinggi_list.append(float(akhir))

    # Hilangkan duplikat dan urutkan sesuai urutan kemunculan
    # (Jika ingin urutan unik, gunakan dict.fromkeys)
    tinggi_list = list(dict.fromkeys(tinggi_list))
    tinggi_list.append(tinggi_awal)
    tinggi_list.sort(reverse=True)

    # Hitung Jumlah Pantulan
    jumlah_pantulan = len(tinggi_list) - 1  # Jumlah transisi dari tinggi awal ke tinggi akhir

    # Hitung koefisien rata-rata (e) untuk setiap tinggi
    koefisien = []
    for i in range(len(tinggi_list) - 1):
        if tinggi_list[i] > tinggi_list[i + 1]:
            e = (tinggi_list[i + 1] / tinggi_list[i]) ** 0.5
            koefisien.append(e)
    # Hitung rata-rata koefisien
    if koefisien:
        rata_rata_koefisien = sum(koefisien) / len(koefisien)
    else:
        rata_rata_koefisien = None

    # Hitung standar deviasi dari koefisien restitusi
    if koefisien:
        stddev = (sum((x - rata_rata_koefisien) ** 2 for x in koefisien) / len(koefisien)) ** 0.5
    else:
        stddev = None

    data = {
        'Jumlah Pantulan': [int(jumlah_pantulan) if jumlah_pantulan else None],
        'Koefisien Rata-rata': [float(rata_rata_koefisien) if rata_rata_koefisien else None],
        'Standar Deviasi': [float(stddev) if stddev else None]
    }
    dataframe = pd.DataFrame(data)
    dataframe['Ketelitian (%)'] = (1 - dataframe['Standar Deviasi'] / dataframe['Koefisien Rata-rata']) * 100
    dataframe['Jenis Bola'] = jenis_bola
    dataframe['Percobaan'] = percobaan
    return dataframe

# Gabungkan semua DataFrame hasil ekstraksi ke satu DataFrame
all_stats = []

for analisis in analisis_files:
    # format file 
    # Analisis_{jenis_bola}_{percobaan}.txt
    # Contoh:
    # Analisis_Bola_Tenis_Lapang_17.txt
    # Mengambil jenis bola dan percobaan dari nama file
    jenis_bola = analisis.split('_')[2]  # Ambil semua bagian kecuali 'Analisis' dan '.txt'
    # jika jenis_bola menghasilkan teks tenis, maka yang diambil adalah indeks selanjutnya dari split
    if jenis_bola == 'Tenis':
        jenis_bola = analisis.split('_')[3]

    percobaan = analisis.split('_')[-1].replace('.txt', '')
    print(f"Memproses {analisis} untuk Jenis Bola: {jenis_bola}, Percobaan: {percobaan}")

    # print(f"Jenis Bola {jenis_bola}, Percobaan {percobaan}")

    df = extract_ringkasan_statistik(os.path.join(data_dir, analisis), jenis_bola, percobaan)
    # print(df)
    all_stats.append(df)

# Gabungkan semua DataFrame menjadi satu
combined_df = pd.concat(all_stats, ignore_index=True)
# Simpan DataFrame gabungan ke file Excel
output_file = os.path.join(output_dir, 'ringkasan_statistik.xlsx')
combined_df.to_excel(output_file, index=False)

# Mendapatkan Jenis Bola Unik
jenis_bola_unik = combined_df['Jenis Bola'].unique()
print(jenis_bola_unik)

# Memisahkan dataframe untuk setiap jenis bola
dataframes_per_bola = {}
for bola in jenis_bola_unik:
    dataframes_per_bola[bola] = combined_df[combined_df['Jenis Bola'] == bola]
    # Mengurutkan berdasarkan percobaan dari terkecil (1) ke terbesar (20)
    dataframes_per_bola[bola]['Percobaan'] = dataframes_per_bola[bola]['Percobaan'].astype(int)
    dataframes_per_bola[bola] = dataframes_per_bola[bola].sort_values(by='Percobaan')
    # Susun ulang kolom dengan percobaan di awal
    dataframes_per_bola[bola] = dataframes_per_bola[bola][['Percobaan', 'Jenis Bola', 'Jumlah Pantulan', 'Koefisien Rata-rata', 'Standar Deviasi', 'Ketelitian (%)']]

    # Export ke file Excel
    output_file_bola = os.path.join(output_dir, f'ringkasan_statistik_{bola}.xlsx')
    dataframes_per_bola[bola].to_excel(output_file_bola, index=False)
    print(f"Data untuk {bola} disimpan di {output_file_bola}")

    # Export ke file LaTeX
    output_file_latex_bola = os.path.join(output_dir, f'ringkasan_statistik_{bola}.tex')
    dataframes_per_bola[bola].to_latex(
        output_file_latex_bola,
        caption=f'ringkasan_statistik_{bola}',
        label=f'tab:ringkasan_{bola}',
        longtable=True,
        index=False,
        escape=True
    )
    print(f"Data untuk {bola} disimpan di {output_file_latex_bola}")

    # Membuat grafik antara kolom "Percobaan" dengan "Ketelitian (%)"
    # plt.figure(figsize=(10, 6))
    # plt.plot(dataframes_per_bola[bola]['Percobaan'], dataframes_per_bola[bola]['Ketelitian (%)'], marker='o', linestyle='-', color='b')
    # plt.title(f'Grafik Ketelitian (%) untuk {bola}')
    # plt.xlabel('Percobaan')
    # plt.ylabel('Ketelitian (%)')
    # plt.xticks(dataframes_per_bola[bola]['Percobaan'])
    # plt.grid()
    # # Simpan grafik sebagai file PNG
    # image_filename = f'Grafik_ketelitian_{bola}.png'
    # plt.savefig(os.path.join(output_dir, image_filename))
    # plt.close()

# # Menyimpan setiap DataFrame ke file Excel terpisah
# for bola, df in dataframes_per_bola.items():
#     output_file_bola = os.path.join(output_dir, f'ringkasan_statistik_{bola}.xlsx')
#     df.to_excel(output_file_bola, index=False)
#     output_file_latex_bola = os.path.join(output_dir, f'ringkasan_statistik_{bola}.tex')
#     df.to_latex(
#         output_file_bola,
#         caption=f'ringkasan_statistik_{bola}',
#         label=f'tab:ringkasan_{bola}',
#         escape=True
#     )
#     print(f"Data untuk {bola} disimpan di {output_file_bola}")


# for data in data_files:
#     # Ambil nama file tanpa ekstensi
#     nama_file = os.path.splitext(data)[0]
#     # Ambil jenis bola dari nama file
#     jenis_bola = nama_file.split('_')[1]  # Ambil bagian kedua setelah 'Data'
    
#     # Cek apakah jenis bola ada dalam list_bola
#     # export ke latex
#     df = pd.read_excel(os.path.join(data_dir, data))
#     output_latex_file = os.path.join(output_dir, f'{nama_file}.tex')
#     df.to_latex(
#         output_latex_file, index=False, 
#         caption=f'Data Ketinggian{jenis_bola}', 
#         label=f'tab:data_ketinggian_{jenis_bola}',
#         escape=True
#     )
#     print(f"Data untuk {jenis_bola} disimpan di {output_latex_file}")
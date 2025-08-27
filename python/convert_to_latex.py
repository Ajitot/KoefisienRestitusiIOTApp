import pandas as pd
import os

output_dir = 'output_tex'

# Only include actual Excel files (not LaTeX .tex files)
filenames = [
    'ringkasan_statistik_Bekel.xlsx',
    'ringkasan_statistik_Lapang.xlsx',
    'ringkasan_statistik_Plastik.xlsx',
    'ringkasan_statistik_Meja.xlsx',
    'ringkasan_statistik_Sepak.xlsx'
]

for filename in filenames:
    file_path = os.path.join(output_dir, filename)
    # Skip if file does not exist or is not a valid Excel file
    if not os.path.isfile(file_path) or not filename.lower().endswith('.xlsx'):
        print(f"Skipping non-Excel file: {file_path}")
        continue
    try:
        # Explicitly specify engine to avoid ambiguity
        df = pd.read_excel(file_path, engine='openpyxl')
    except Exception as e:
        print(f"Failed to read {file_path} as Excel: {e}")
        continue
    output_file = os.path.join(output_dir, filename.replace('.xlsx', '.tex'))
    df.to_latex(
        output_file,
        caption=f'Ringkasan Statistik {filename.split("_")[2].capitalize()}',
        label=f'tab:ringkasan_{filename.split("_")[2]}',
        escape=True
    )
    print(f"File LaTeX untuk {filename} telah dibuat: {output_file}")
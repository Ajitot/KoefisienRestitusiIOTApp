# Koefisien Restitusi IOT App

Aplikasi untuk menghitung koefisien restitusi menggunakan sensor ultrasonic dan IoT.


## Diagram

![](images\circuit_diagram.png)

| Ultrasonic Sensor | ESP8266 |
|-------------------|---------|
| VCC               | VIN     |
| Trig              | (D14) |
| Echo              | (D27) |
| GND               | GND     |

## Cara Penggunaan

1. Clone repository ini
```bash
git clone https://github.com/Ajitot/KoefisienRestitusiIOTApp.git
cd KoefisienRestitusiIOTApp
```

2. Setup Python Environment
```bash
# Buat virtual environment
python -m venv venv

# Aktivasi environment
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependensi
```bash
pip install -r requirements.txt
```

4. Setup environment
- Buat file `.env` di root folder
- Copy file `.env.example` ke `.env` jika ada
- Isi kredensial Supabase:
```bash
# Buat file .env
touch .env  # Linux/Mac
# atau
type nul > .env  # Windows

# Isi kredensial berikut
SUPABASE_URL=your_url
SUPABASE_SECRET_KEY=your_key
SUPABASE_ID=your_id
TIMEZONE=Asia/Jakarta
TABLE_NAME=maintable
```

5. Jalankan aplikasi
```bash
# Pastikan virtual environment aktif
shiny run --reload --launch-browser app.py
```

6. Untuk menonaktifkan environment
```bash
deactivate
```

## Supabase Setup

Buat tabel dengan struktur berikut di Supabase:

| Name       | Description        | Data Type                  | Format    |
|------------|--------------------|----------------------------|-----------|
| id         | Primary key        | bigint                     | int8      |
| created_at | Waktu dibuat       | time without time zone     | time      |
| datetime   | Waktu pengukuran   | timestamp without time zone| timestamp |
| High       | Tinggi pantulan    | real                       | float4    |

### Sintaks SQL untuk membuat Tabel

```sql
CREATE TABLE maintable (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    created_at time without time zone DEFAULT CURRENT_TIME,
    datetime timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    High real NOT NULL
);
```


## Hardware Setup

### Pinout Diagram

![Pinout Diagram](images/Pinout.png)

## Link Penting

### Aplikasi
- [Website Koefisien Restitusi IOT](https://koefisien-restitusi-iot.shinyapps.io/koefisien-restitusi-app1/)

### Development
- [Shinyapps Hosting](https://www.shinyapps.io/)
- [Supabase Dashboard](https://supabase.com/dashboard/project/)

## Preview

![Preview Aplikasi](https://github.com/Ajitot/KoefisienRestitusiIOTApp/assets/105025628/c1e33e2d-33b1-455a-ac37-2abdeead9a54)

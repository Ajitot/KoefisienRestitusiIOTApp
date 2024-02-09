import supabase
import pandas as pd
from datetime import datetime
import pytz

SUPABASE_URL = "https://oqfqrlhqmuapbdpemcfg.supabase.co"
SUPABASE_SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xZnFybGhxbXVhcGJkcGVtY2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDcxNTcwNzMsImV4cCI6MjAyMjczMzA3M30.h92qn052dRqsUvTp9DJdFmTwVIVmLXbRgKhRqhf-rz8"
SUPABASE_ID = "oqfqrlhqmuapbdpemcfg"

client = supabase.create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

def convert_to_local_time(utc_time_str):
    utc_time = datetime.strptime(utc_time_str, '%Y-%m-%dT%H:%M:%S.%f')
    utc_zone = pytz.timezone('UTC')
    local_time = utc_time.replace(tzinfo=utc_zone).astimezone(pytz.timezone('Asia/Jakarta'))
    return local_time

def get_data(client):
    response = client.table('maintable').select("*").execute()
    df = pd.DataFrame(response.data)
    print(list(df.columns))
    try:
        df = df.drop(columns=['created_at'])
    except Exception as e:
        print(e)
    df['datetime'] = df['datetime'].apply(convert_to_local_time)
    df['datetime'] = pd.to_datetime(df['datetime']).dt.time
    df['datetime'] = df['datetime'].apply(lambda x: x.strftime('%H:%M:%S'))
    df = df[['id','datetime', 'High']]
    df = df.sort_values(['id', 'datetime'], ascending=[True, True])
    return df

def reset_data(client):
    try:
        all_data = client.table('maintable').select("*").execute()
        id = pd.DataFrame(all_data.data)['id'].tail(1).values
        response = client.table('maintable').delete().lt('id', id[-1]).execute()
        dataframe = pd.DataFrame()
        return dataframe, id[-1]
    except Exception as e:
        print(e)
        dataframe = pd.DataFrame()
        return dataframe, id[-1]

# df = reset_data(client)

# print("reset_data".center(100,"="))
# print(df)
# print("df.describe".center(100,"="))
# print(df.info)

# df = get_data(client)

# print("get_data".center(100,"="))
# print(df)
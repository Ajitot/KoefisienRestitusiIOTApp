import pandas as pd
from datetime import datetime
import pytz
import supabase
from config import SUPABASE_CONFIG, TIMEZONE, TABLE_NAME

class DataManager:
    def __init__(self):
        self.client = supabase.create_client(
            SUPABASE_CONFIG["url"], 
            SUPABASE_CONFIG["secret_key"]
        )

    def _convert_to_local_time(self, utc_time_str):
        try:
            utc_time = datetime.strptime(utc_time_str, '%Y-%m-%dT%H:%M:%S.%f')
            utc_zone = pytz.timezone('UTC')
            local_time = utc_time.replace(tzinfo=utc_zone).astimezone(pytz.timezone(TIMEZONE))
            return local_time
        except Exception as e:
            print(f"Time conversion error: {e}")
            return None

    def get_data(self):
        try:
            response = self.client.table(TABLE_NAME).select("*").execute()
            df = pd.DataFrame(response.data)
            
            if 'created_at' in df.columns:
                df = df.drop(columns=['created_at'])
                
            df['datetime'] = df['datetime'].apply(self._convert_to_local_time)
            df['datetime'] = pd.to_datetime(df['datetime']).dt.time
            df['datetime'] = df['datetime'].apply(lambda x: x.strftime('%H:%M:%S'))
            
            return df[['id','datetime', 'High']].sort_values(['id', 'datetime'])
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()

    def get_last_id(self):
        """Get the last ID from database"""
        try:
            response = self.client.table(TABLE_NAME).select("id").order('id', desc=True).limit(1).execute()
            if response.data:
                return response.data[0]['id']
            return 0
        except Exception as e:
            print(f"Error getting last ID: {e}")
            return 0

    def get_data_range(self, start_id, end_id):
        """Get data between start_id and end_id"""
        try:
            response = self.client.table(TABLE_NAME)\
                .select("*")\
                .gte('id', start_id)\
                .lte('id', end_id)\
                .execute()
            
            df = pd.DataFrame(response.data)
            if len(df) == 0:
                return pd.DataFrame()
            
            if 'created_at' in df.columns:
                df = df.drop(columns=['created_at'])
                
            df['datetime'] = df['datetime'].apply(self._convert_to_local_time)
            df['datetime'] = pd.to_datetime(df['datetime']).dt.time
            df['datetime'] = df['datetime'].apply(lambda x: x.strftime('%H:%M:%S'))
            
            return df[['id','datetime', 'High']].sort_values(['id', 'datetime'])
            
        except Exception as e:
            print(f"Error fetching data range: {e}")
            return pd.DataFrame()

    def reset_data(self):
        try:
            all_data = self.client.table(TABLE_NAME).select("*").execute()
            last_id = pd.DataFrame(all_data.data)['id'].tail(1).values[0]
            self.client.table(TABLE_NAME).delete().lt('id', last_id).execute()
            return pd.DataFrame(), last_id
        except Exception as e:
            print(f"Error resetting data: {e}")
            return pd.DataFrame(), 0
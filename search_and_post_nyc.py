import pandas as pd
import json
from datetime import datetime, timezone,timedelta
from atproto import Client
from ebird.api import get_nearby_notable,get_taxonomy,get_species_observations,get_notable_observations
from dotenv import load_dotenv
import os
import requests

from PIL import Image
from io import BytesIO
import time

POSTED_BIRDS_FILE = "posted_birds.json"

def load_posted_birds():
    try:
        with open(POSTED_BIRDS_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_posted_birds(posted_birds):
    with open(POSTED_BIRDS_FILE, "w") as file:
        json.dump(posted_birds, file)

def clean_posted_birds(posted_birds, days=3):
    cutoff_date = datetime.now() - timedelta(days=days)
    return {bird: date for bird, date in posted_birds.items() if datetime.strptime(date, "%Y-%m-%d") > cutoff_date}


load_dotenv()

bird_key = os.getenv("bird_key")
nuthatch_key = os.getenv("nuthatch")
bsky_username = os.getenv("bsky_username")
bsky_password = os.getenv("bsky_password")

client = Client()
client.login(bsky_username, bsky_password)

url = 'https://nuthatch.lastelm.software/v2/birds'
headers = {
    'accept': 'application/json',
    'API-Key': nuthatch_key
}

lat = 40.01 
long = -74.00
dist=50

def find_local_notables(lat, lon, dist,bird_key):
    notables = get_nearby_notable(bird_key,lat, lon, dist,back=1)
    notables_df = pd.DataFrame(notables)
    notables_df = notables_df.drop_duplicates(subset=['comName'])
    return notables_df

def make_list(df,num=3):
    short_df = df.sample(num)
    b_list = short_df['comName'].tolist()
    return b_list,short_df

def get_bird_info(df,url,headers):
    name = df['comName'].unique()[0]
    locname = df['locName'].unique()[0]
    cl_key = df['subId'].unique()[0]
    params = {
    'page': 1,
    'pageSize': 1,
    'name': name,
    'operator': 'AND'
    }   
    response = requests.get(url, headers=headers, params=params)

    response.json()
    data = response.json()
    entity = data['entities'][0]
    sci_name = entity['sciName']
    images = entity['images']  
    if images:
        image_1 = images[0]
    else:
        image_1 = "No image available"
    status = entity['status']
    family = entity['family']
    order = entity['order']
    region = entity['region'][0] 

    return sci_name, name, image_1, status, region,locname,family,order,cl_key

def write_nyc_text(df,url,headers):
    sci_name,name,image,concern,region,locname,family,order,cl_id = get_bird_info(df,url,headers)
    text = f"Notable bird near NYC! The {name}, also known as the {sci_name}. It was spotted at {locname}. An image of the {name} is below, if available. Here is a link to the eBird checklist https://ebird.org/checklist/{cl_id}"
    return text,image,name

def post(df, url, headers, max_width=800, max_height=600):
    text, image_url, name = write_nyc_text(df, url, headers)
    
    if image_url and image_url != "No image available":  
        try:
            response = requests.get(image_url)
            response.raise_for_status()  
            image = Image.open(BytesIO(response.content))
            image.thumbnail((max_width, max_height)) 
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='JPEG') 
            img_byte_arr = img_byte_arr.getvalue()
            
            client.send_image(text=text, image=img_byte_arr, image_alt=name)
        except Exception as e:
            print(f"Failed to process the image: {e}")
            client.send_post(text=text)
    else:
        client.send_post(text=text)
    
    print("Post made")


def post_list(short_df, url, headers, b_list):
    posted_birds = load_posted_birds()
    posted_birds = clean_posted_birds(posted_birds)  

    for bird in b_list:
        if bird in posted_birds:
            print(f"Skipping {bird}: already posted recently.")
            continue

        try:
            df = short_df[short_df['comName'] == bird]
            post(df, url, headers)
            posted_birds[bird] = datetime.now().strftime("%Y-%m-%d")  
            save_posted_birds(posted_birds)
            time.sleep(5)
        except Exception as e:
            print(f"Failed to post {bird}: {e}")


def main():
    print("Starting main process...")
    try:
        df = find_local_notables(lat, long, dist, bird_key)
        print("Found local notables")
        b_list, short_df = make_list(df)
        print(f"Made list of birds: {b_list}")
        post_list(short_df, url, headers, b_list)
        print("Completed posting")
    except Exception as e:
        print(f"Error in main process: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Script terminated due to an unexpected error: {e}")
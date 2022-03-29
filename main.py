from pydub import AudioSegment
from shazam_helper.communication import recognize_song_from_signature
from shazam_helper.algorithm import SignatureGenerator
import requests
import os
from yt_dlp import YoutubeDL
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
import time
import re

RADIO_URL = "http://.../;stream.mp3" # ONLINE RADIO URL
USER_AGENT = 'VLC/3.0.4 LibVLC/3.0.4'
LOOP_TIME = 60
M3U8_MODE = False # Some radio stations broadcasting on m3u8 format, just try this: True

def record_radio():
    print("Radio record...")
    if os.path.exists("audio.mp3"):
        os.remove("audio.mp3")
    if os.path.exists("audio.temp"):
        os.remove("audio.temp")

    headers = {'User-Agent': USER_AGENT}
    url = RADIO_URL
    if M3U8_MODE is True:
        main = "/".join(RADIO_URL.split("/")[0:-1]) + "/"
        r = requests.get(url, headers=headers)
        parts = re.findall('\n#EXTINF:([0-9.]*),\n(.*)', r.text)
        if len(parts) > 0:
            total = 0
            with open('audio.temp', 'wb') as f:
                try:
                    for part in parts:
                        duration = float(part[0])
                        name = part[1]
                        r2 = requests.get(main + name, headers=headers, stream=True)
                        for block in r2.iter_content(1024):
                            f.write(block)
                            total += len(block)
                            if total > 1024 * 256:
                                break
                except:
                    pass

        
    else:
        r = requests.get(url, headers=headers, stream=True)
        
        total = 0
        with open('audio.temp', 'wb') as f:
            try:
                for block in r.iter_content(1024):
                    f.write(block)
                    total += len(block)
                    if total > 1024 * 256:
                        break
            except:
                pass


    if os.path.exists("audio.temp") and total > 0:
        os.system("ffmpeg -y -nostats -loglevel 0 -i audio.temp -f mp3 -vn -sn -dn -ignore_unknown audio.mp3")
        if os.path.exists("audio.mp3"):
            detect_and_download() 

def detect_and_download():
    print('Create signature from the audio record...')
    audio = AudioSegment.from_file("audio.mp3", "mp3")
    audio = audio.set_sample_width(2)
    audio = audio.set_frame_rate(16000)
    audio = audio.set_channels(1)
        
    signature_generator = SignatureGenerator()
    signature_generator.feed_input(audio.get_array_of_samples())
        
    signature_generator.MAX_TIME_SECONDS = 12
    if audio.duration_seconds > 12 * 3:
        signature_generator.samples_processed += 16000 * (int(audio.duration_seconds / 2) - 6)
        
    results = '{"error": "Not found"}'
    sarki = None
    print('Push to Shazam...')
    while True:
        signature = signature_generator.get_next_signature()
        if not signature:
            sarki = results
            break
        results = recognize_song_from_signature(signature)
        if results['matches']:
            sarki = results
            break
    
    if not 'track' in sarki:
        return print('Shazam found no results!')
    filename = f'musics/{sarki["track"]["title"]} - {sarki["track"]["subtitle"]}.mp3'
    
    if os.path.exists(filename):
        print(f'Song found: {sarki["track"]["title"]} - {sarki["track"]["subtitle"]}. Already downloaded!')
        return

    print(f'Song found: {sarki["track"]["title"]} - {sarki["track"]["subtitle"]}. Downloading...')

    for section in sarki['track']['sections']:
        if section['type'] == 'VIDEO':
            if 'youtubeurl' in section:
                Youtube = requests.get(section['youtubeurl']).json()
                url = f'{Youtube["actions"][0]["uri"]}'
                opts = {
                    'format': 'bestaudio',
                    'prefer_ffmpeg': True,
                    'geo_bypass': True,
                    'nocheckcertificate': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '256',
                    }],
                    'outtmpl': filename,
                    'quiet': True,
                    'logtostderr': False
                }
                try:
                    with YoutubeDL(opts) as rip:
                        rip_data = rip.extract_info(url)
                        print("Download finished!")

                        track = sarki["track"]

                        if "title" in track:
                            audio = EasyID3(filename)
                            audio['title'] = track["title"]
                            audio['artist'] = track["subtitle"] if "subtitle" in track else ""
                            if "sections" in track and len(track['sections']) > 0 and "metadata" in track['sections'][0]:
                                audio['album'] = track['sections'][0]['metadata'][0]['text']
                                audio['date'] = track['sections'][0]['metadata'][2]['text']
                            audio['genre'] = track["genres"]["primary"]
                            audio.save()

                        if "images" in sarki["track"] and "coverart" in sarki["track"]["images"]:
                            r = requests.get(sarki["track"]["images"]["coverart"])
                            audio = ID3(filename)
                            audio.add(APIC(3, 'image/jpeg', 3, 'Front cover', r.content))
                            audio.save(v2_version=3)
                except Exception as e:
                    print(f"{str(type(e)): {str(e)}}")
                
                return

while True:
    record_radio()
    time.sleep(LOOP_TIME)
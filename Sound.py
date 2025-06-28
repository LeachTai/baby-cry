import serial
import time
import requests
import wave
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import PushMessageRequest, TextMessage

# === LINE 設定 ===
LINE_CHANNEL_ACCESS_TOKEN = '你的_channel_access_token'
LINE_USER_ID = '你的_user_id'

# === 串口設定 ===
SERIAL_PORT = 'COM3'  # 根據你的 Arduino 調整
BAUD_RATE = 115200
OUTPUT_FILE = 'baby.wav'

# === 錄音儲存 ===
def write_wav(audio_bytes, filename, sample_rate=16000):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)

def save_audio(timeout=5):
    print("開始錄音...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    audio = b''
    start_time = time.time()

    while True:
        if ser.in_waiting:
            audio += ser.read(ser.in_waiting)
            start_time = time.time()  # reset timer when data received
        if time.time() - start_time > timeout:
            break
    ser.close()

    write_wav(audio, OUTPUT_FILE)
    print(f"音檔儲存完成，長度約 {len(audio)/32000:.2f} 秒")

# === 上傳檔案到 transfer.sh ===
def upload_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            filename = filepath.split('/')[-1]
            response = requests.put(f"https://transfer.sh/{filename}", data=f)

        if response.status_code == 200:
            url = response.text.strip()
            print("上傳成功：", url)
            return url
        else:
            print("上傳失敗，狀態碼：", response.status_code)
            print("內容：", response.text)
            return None
    except Exception as e:
        print("上傳時錯誤：", str(e))
        return None

# === 發送 LINE Bot 訊息 ===
def send_line_message(message_text):
    try:
        config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        with ApiClient(config) as api_client:
            line_bot_api = MessagingApi(api_client)
            message = TextMessage(text=message_text)
            request = PushMessageRequest(to=LINE_USER_ID, messages=[message])
            line_bot_api.push_message(request)
            print("LINE 訊息發送成功！")
    except Exception as e:
        print("發送失敗:", str(e).encode('utf-8', errors='ignore').decode())

# === 主流程 ===
if __name__ == '__main__':
    save_audio()
    file_url = upload_file(OUTPUT_FILE)
    if file_url:
        send_line_message(f"偵測到聲音！\n錄音連結：{file_url}")
    else:
        send_line_message("錄音上傳失敗。")

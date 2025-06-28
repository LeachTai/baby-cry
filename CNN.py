import serial
import time
import requests
import wave
import os # Import os for path manipulation

# Import libraries for spectrogram conversion
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf # Used for reading and writing audio files, especially for formats like MP3

from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import PushMessageRequest, TextMessage

# === 全局設定與常數 ===
# 請替換為您的 LINE Channel Access Token 和 User ID
LINE_CHANNEL_ACCESS_TOKEN = 'p6sj7qQEZqNIGjg6kyDLvAP/DkznyQYwXqCQZTREuu9M8zC8pLlbj88Y++fIfyKI4zSnfP/nRr5/Nk43R0c15gi5pvAmnJRy8/LtCdvP4iMGGkyPSyxqzwztXPAN3ROKEsCsk5weWXgVOCme/jhTxQdB04t89/1O/w1cDnyilFU='
LINE_USER_ID = '你的_user_id' # 請將此替換為您想要接收訊息的 LINE 用戶 ID

# 串口設定：根據您的 Arduino 設定調整
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200

# 音訊採樣率：確保與 Arduino 輸出音訊的採樣率一致
# 一般 Arduino 錄音常見 8000, 16000, 32000 Hz
SAMPLE_RATE = 16000

# 輸出檔案名
OUTPUT_AUDIO_FILE = 'baby.wav' # 錄製的音訊檔案名
OUTPUT_SPECTROGRAM_FILE = 'baby_spectrogram.png' # 梅爾頻譜圖檔案名

# 錄音超時時間 (秒)：如果此時間內沒有收到新的串口資料，則停止錄音
AUDIO_RECORDING_TIMEOUT = 5 

# === 錄音儲存 ===
def write_wav(audio_bytes, filename, sample_rate_val):
    """
    將位元組形式的音訊資料寫入 WAV 檔案。
    Args:
        audio_bytes (bytes): 錄製到的音訊位元組數據。
        filename (str): 要保存的 WAV 檔案路徑。
        sample_rate_val (int): 音訊的採樣率。
    """
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1) # 單聲道
            wf.setsampwidth(2) # 16-bit 樣本寬度 (每個樣本佔 2 個位元組)
            wf.setframerate(sample_rate_val) # 採樣率
            wf.writeframes(audio_bytes)
        print(f"音檔 '{filename}' 儲存完成。")
    except Exception as e:
        print(f"寫入 WAV 檔案時發生錯誤: {e}")

def record_audio_from_serial():
    """
    從指定的串口錄製音訊，並保存為 WAV 檔案。
    Returns:
        bool: 如果成功錄製並保存音訊，返回 True；否則返回 False。
    """
    print("開始從串口錄音...")
    ser = None
    try:
        # 打開串口連接
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) # timeout for read operations
        audio_data = b''
        last_data_received_time = time.time() # 記錄最後收到資料的時間

        while True:
            if ser.in_waiting: # 如果串口緩衝區有資料
                audio_data += ser.read(ser.in_waiting) # 讀取所有可用資料
                last_data_received_time = time.time() # 更新最後收到資料的時間
            
            # 如果在指定超時時間內沒有收到新資料，則停止錄音
            if time.time() - last_data_received_time > AUDIO_RECORDING_TIMEOUT:
                print(f"達到錄音超時 ({AUDIO_RECORDING_TIMEOUT} 秒無資料)，停止錄音。")
                break
        
        if len(audio_data) > 0:
            # 計算錄音時長 (位元組數 / (採樣率 * 樣本寬度))
            duration_seconds = len(audio_data) / (SAMPLE_RATE * 2) 
            write_wav(audio_data, OUTPUT_AUDIO_FILE, SAMPLE_RATE)
            print(f"音檔儲存完成，長度約 {duration_seconds:.2f} 秒")
            return True # 指示成功
        else:
            print("沒有從串口收到任何音訊資料。")
            return False # 指示沒有收到音訊
    except serial.SerialException as e:
        print(f"串口連接錯誤：{e}。請檢查串口名稱 ({SERIAL_PORT}) 是否正確連接及設置。")
        return False
    except Exception as e:
        print(f"錄音過程中發生錯誤：{e}")
        return False
    finally:
        # 無論如何，確保串口被關閉
        if ser and ser.is_open:
            ser.close()
            print("串口已關閉。")

# === 音檔轉換為梅爾頻譜圖 ===
def convert_audio_to_spectrogram_image(audio_file_path, output_image_path):
    """
    將音檔轉換為梅爾頻譜圖並保存為圖片。
    Args:
        audio_file_path (str): 輸入音檔的路徑。
        output_image_path (str): 輸出圖片的路徑。
    Returns:
        bool: 如果成功轉換，返回 True；否則返回 False。
    """
    # 檢查輸入音檔是否存在
    if not os.path.exists(audio_file_path):
        print(f"錯誤：找不到音檔 '{audio_file_path}'，無法生成頻譜圖。")
        return False

    try:
        # 載入音檔，確保使用全局定義的採樣率
        y, loaded_sr = librosa.load(audio_file_path, sr=SAMPLE_RATE)

        # 計算梅爾頻譜圖參數 (可以根據需求調整這些參數)
        n_fft_val = 2048
        hop_length_val = 512
        n_mels_val = 128

        # 計算梅爾頻譜圖，並轉換為分貝 (dB) 刻度
        S_dB = librosa.feature.melspectrogram(y=y, sr=loaded_sr, n_fft=n_fft_val, hop_length=hop_length_val, n_mels=n_mels_val)
        S_dB = librosa.power_to_db(S_dB, ref=np.max) 

        # 繪製頻譜圖
        plt.figure(figsize=(10, 4)) # 設定圖片大小
        librosa.display.specshow(S_dB, sr=loaded_sr, x_axis='time', y_axis='mel', cmap='viridis')
        plt.colorbar(format='%+2.0f dB') # 添加顏色條
        plt.title(f'音檔 {os.path.basename(audio_file_path)} 的梅爾頻譜圖') # 設定圖表標題
        plt.tight_layout() # 自動調整佈局

        # 移除軸標籤和刻度，讓圖片更純粹，適合嵌入或作為機器學習輸入
        plt.axis('off')

        # 保存圖片，確保沒有多餘的空白邊框
        plt.savefig(output_image_path, bbox_inches='tight', pad_inches=0)
        plt.close() # 關閉圖形，釋放記憶體

        print(f"成功將音檔 '{audio_file_path}' 轉換為圖片 '{output_image_path}'")
        return True
    except Exception as e:
        print(f"轉換為梅爾頻譜圖時發生錯誤：{e}")
        return False

# === 上傳檔案到 transfer.sh ===
def upload_file(filepath):
    """
    上傳檔案到 transfer.sh 並返回公開連結。
    Args:
        filepath (str): 要上傳的檔案路徑。
    Returns:
        str: 上傳成功的檔案公開連結；如果失敗，返回 None。
    """
    try:
        # 檢查檔案是否存在
        if not os.path.exists(filepath):
            print(f"上傳失敗：檔案 '{filepath}' 不存在。")
            return None

        with open(filepath, 'rb') as f:
            filename = os.path.basename(filepath) # 獲取檔案名
            # 使用 HTTP PUT 請求上傳檔案
            response = requests.put(f"https://transfer.sh/{filename}", data=f)

        if response.status_code == 200:
            url = response.text.strip() # 從回應中獲取連結
            print(f"檔案 '{filename}' 上傳成功：{url}")
            return url
        else:
            print(f"檔案 '{filename}' 上傳失敗，狀態碼：{response.status_code}")
            print("內容：", response.text)
            return None
    except Exception as e:
        print(f"上傳時錯誤：{e}")
        return None

# === 發送 LINE Bot 訊息 ===
def send_line_message(message_text):
    """
    使用 LINE Messaging API 發送文字訊息。
    Args:
        message_text (str): 要發送的文字訊息內容。
    """
    try:
        # 配置 LINE Messaging API 客戶端
        config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        with ApiClient(config) as api_client:
            line_bot_api = MessagingApi(api_client)
            message = TextMessage(text=message_text)
            request = PushMessageRequest(to=LINE_USER_ID, messages=[message])
            # 發送訊息
            line_bot_api.push_message(request)
            print("LINE 訊息發送成功！")
    except Exception as e:
        # 處理發送失敗的錯誤
        print(f"發送 LINE 訊息失敗: {str(e).encode('utf-8', errors='ignore').decode()}")
        print("請檢查您的 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID 是否正確，或網路連接是否正常。")

# === 主流程 ===
if __name__ == '__main__':
    # 程式啟動時檢查 LINE Bot 的 Token 和 User ID 是否已設定
    if LINE_CHANNEL_ACCESS_TOKEN == '你的_channel_access_token' or \
       LINE_USER_ID == '你的_user_id':
        print("\n錯誤：請先在程式碼中設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID。")
        print("程式已終止。")
        exit()

    # 1. 錄製音訊
    print("\n--- 啟動音訊監測 ---")
    audio_recorded_success = record_audio_from_serial()

    if audio_recorded_success:
        print("\n--- 音訊處理中 ---")
        # 2. 將錄製的音訊轉換為梅爾頻譜圖
        spectrogram_created_success = convert_audio_to_spectrogram_image(OUTPUT_AUDIO_FILE, OUTPUT_SPECTROGRAM_FILE)
        
        # 3. 上傳音訊檔案到 transfer.sh
        audio_file_url = upload_file(OUTPUT_AUDIO_FILE)

        # 組合要發送的 LINE 訊息
        line_message_content = "偵測到聲音！\n"
        if audio_file_url:
            line_message_content += f"錄音連結：{audio_file_url}\n"
        else:
            line_message_content += "錄音上傳失敗，無法提供連結。\n"
        
        if spectrogram_created_success:
            line_message_content += f"梅爾頻譜圖已生成：'{OUTPUT_SPECTROGRAM_FILE}' (已保存在本地)"
            # 注意：LINE TextMessage 無法直接發送圖片，若要發送圖片需使用 ImageMessage
            # 如果需要發送圖片，您可能需要將頻譜圖也上傳到一個公開連結，然後發送 ImageMessage
            # 但這超出了 TextMessage 的範圍，需要 LINE Bot 進階功能。
        else:
            line_message_content += "梅爾頻譜圖生成失敗。"

        # 4. 發送 LINE 訊息
        print("\n--- 發送 LINE 通知 ---")
        send_line_message(line_message_content)

        # 5. 清理本地生成的檔案 (可選，但推薦)
        print("\n--- 清理本地檔案 ---")
        if os.path.exists(OUTPUT_AUDIO_FILE):
            os.remove(OUTPUT_AUDIO_FILE)
            print(f"已刪除本地音檔：'{OUTPUT_AUDIO_FILE}'")
        if os.path.exists(OUTPUT_SPECTROGRAM_FILE):
            os.remove(OUTPUT_SPECTROGRAM_FILE)
            print(f"已刪除本地梅爾頻譜圖：'{OUTPUT_SPECTROGRAM_FILE}'")
        
        print("\n--- 處理完成 ---")

    else:
        # 如果錄音失敗，也發送 LINE 訊息通知
        send_line_message("未偵測到聲音或錄音過程中發生錯誤。")
        print("\n--- 處理結束：未錄到音訊 ---")

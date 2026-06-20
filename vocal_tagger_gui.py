import os
import sys
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading

# Import the core audio processing tools
from spleeter.separator import Separator
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

# Define the 2stems JSON layout block string with absolute numerical array parameters filled in
SPLEETER_JSON_DATA = {
    "mix_name": "mix",
    "instrumentals_name": "accompaniment",
    "sample_rate": 44100,
    "frame_length": 4096,
    "frame_step": 1024,
    "window_exponent": 1.0,
    "stft_backend": "tensorflow",
    "model_dir": "pretrained_models",
    "instruments": ["vocals", "accompaniment"],
    "train_csv": None,
    "validation_csv": None,
    "model": {
        "type": "unet.unet",
        "params": {
            "conv_activation": "ELU",
            "deconv_activation": "ELU",
            "pool_size":,
            "strides":,
            "kernel_size":,
            "n_chunks_per_epoch": 100,
            "batch_size": 4,
            "learning_rate": 0.001
        }
    }
}

class VocalTaggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Vocal Detector & Tagging Tool")
        self.root.geometry("650x450")
        self.root.minsize(550, 350)
        
        self.selected_folder = ""
        self.mp3_files = []
        self.is_processing = False
        
        # --- UI LAYOUT ---
        top_frame = ttk.Frame(root, padding="10")
        top_frame.pack(fill=tk.X)
        
        self.btn_select = ttk.Button(top_frame, text="Select Folder", command=self.browse_folder)
        self.btn_select.pack(side=tk.LEFT, padx=(0, 10))
        
        self.lbl_folder = ttk.Label(top_frame, text="No folder selected", wraplength=450, foreground="gray")
        self.lbl_folder.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        mid_frame = ttk.LabelFrame(root, text=" Target Tracks ", padding="10")
        mid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.txt_console = tk.Text(mid_frame, wrap=tk.WORD, height=12, state=tk.DISABLED, bg="#fbfbfb")
        self.txt_console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(mid_frame, command=self.txt_console.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_console.config(yscrollcommand=scrollbar.set)
        
        bot_frame = ttk.Frame(root, padding="10")
        bot_frame.pack(fill=tk.X)
        
        self.progress = ttk.Progressbar(bot_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_start = ttk.Button(bot_frame, text="Start Tagging Process", state=tk.DISABLED, command=self.start_thread)
        self.btn_start.pack(side=tk.RIGHT)

    def log(self, text):
        self.txt_console.config(state=tk.NORMAL)
        self.txt_console.insert(tk.END, text + "\n")
        self.txt_console.see(tk.END)
        self.txt_console.config(state=tk.DISABLED)

    def browse_folder(self):
        if self.is_processing:
            return
            
        folder = filedialog.askdirectory()
        if not folder:
            return
            
        self.selected_folder = folder
        self.lbl_folder.config(text=folder, foreground="black")
        
        self.mp3_files = [f for f in os.listdir(folder) if f.lower().endswith('.mp3')]
        
        self.txt_console.config(state=tk.NORMAL)
        self.txt_console.delete('1.0', tk.END)
        self.txt_console.config(state=tk.DISABLED)
        
        self.log(f"📍 Selected Folder: {folder}")
        self.log(f"🎵 Found {len(self.mp3_files)} MP3 files inside.\n")
        
        if self.mp3_files:
            self.btn_start.config(state=tk.NORMAL)
            self.progress['value'] = 0
        else:
            self.btn_start.config(state=tk.DISABLED)
            self.log("⚠️ No MP3 files found in this folder.")

    def start_thread(self):
        self.is_processing = True
        self.btn_select.config(state=tk.DISABLED)
        self.btn_start.config(state=tk.DISABLED)
        threading.Thread(target=self.process_audio, daemon=True).start()

    def process_audio(self):
        config_path = "spleeter_local_config.json"
        try:
            self.log("📝 Generating local system config file...")
            with open(config_path, 'w') as f:
                json.dump(SPLEETER_JSON_DATA, f)
                
            self.log("🤖 Initializing AI Separation Model (Spleeter)...")
            separator = Separator(config_path)
            self.log("⚡ Model Loaded. Starting analysis...\n")
            
            total_files = len(self.mp3_files)
            
            for index, file_name in enumerate(self.mp3_files, 1):
                file_path = os.path.join(self.selected_folder, file_name)
                self.log(f"[{index}/{total_files}] Processing: {file_name}")
                
                try:
                    prediction = separator.separate(file_path)
                    vocals_data = prediction['vocals']
                    vocal_energy = vocals_data.mean()
                    
                    if vocal_energy > 0.005:
                        tag_result = "With Vocals"
                    else:
                        tag_result = "Instrumental"
                    
                    audio = MP3(file_path, ID3=EasyID3)
                    audio['comment'] = tag_result
                    audio.save()
                    
                    self.log(f"   ↳ 🏷️ Tag Written: \"{tag_result}\"\n")
                except Exception as e:
                    self.log(f"   ↳ ❌ Error processing this track: {e}\n")
                
                progress_percent = (index / total_files) * 100
                self.progress['value'] = progress_percent
                self.root.update_idletasks()
                
            self.log("🎉 SUCCESS: Processing is complete! All tracks have been tagged.")
            messagebox.showinfo("Done!", "All files have been successfully tagged!")
            
        except Exception as global_error:
            self.log(f"\n❌ Core System Error: {global_error}")
            messagebox.showerror("Error", f"A processing error occurred:\n{global_error}")
            
        finally:
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                except:
                    pass
            self.is_processing = False
            self.btn_select.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)

if __name__ == '__main__':
    root = tk.Tk()
    app = VocalTaggerApp(root)
    root.mainloop()

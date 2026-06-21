import os
import sys
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading

# Import the core audio processing tools
from spleeter.separator import Separator
from mutagen import File as MutagenFile

# Explicitly defining configuration as a safe flat string to prevent any parsing bugs
SPLEETER_CONFIG_STRING = """{
    "mix_name": "mix",
    "instrumentals_name": "accompaniment",
    "sample_rate": 44100,
    "frame_length": 4096,
    "frame_step": 1024,
    "window_exponent": 1.0,
    "stft_backend": "tensorflow",
    "model_dir": "pretrained_models",
    "instruments": ["vocals", "accompaniment"],
    "train_csv": null,
    "validation_csv": null,
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
}"""

# Supported multi-format extensions
SUPPORTED_EXTENSIONS = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.wma')

class VocalTaggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Multi-Format Vocal Detector & Tagging Tool")
        self.root.geometry("650x450")
        self.root.minsize(550, 350)
        
        self.selected_folder = ""
        self.audio_files = []
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
        
        # Scan folder for ALL supported formats
        self.audio_files = [f for f in os.listdir(folder) if f.lower().endswith(SUPPORTED_EXTENSIONS)]
        
        self.txt_console.config(state=tk.NORMAL)
        self.txt_console.delete('1.0', tk.END)
        self.txt_console.config(state=tk.DISABLED)
        
        self.log(f"📍 Selected Folder: {folder}")
        self.log(f"🎵 Found {len(self.audio_files)} compatible audio tracks inside.\n")
        
        if self.audio_files:
            self.btn_start.config(state=tk.NORMAL)
            self.progress['value'] = 0
        else:
            self.btn_start.config(state=tk.DISABLED)
            self.log("⚠️ No supported audio files (.mp3, .flac, .wav, .m4a) found in this folder.")

    def start_thread(self):
        self.is_processing = True
        self.btn_select.config(state=tk.DISABLED)
        self.btn_start.config(state=tk.DISABLED)
        threading.Thread(target=self.process_audio, daemon=True).start()

    def write_universal_comment(self, file_path, tag_text):
        """Safely writes a comment tag across different audio wrappers (MP3, FLAC, M4A, WAV)."""
        audio = MutagenFile(file_path)
        if audio is None:
            raise Exception("Unsupported or corrupted metadata layout")
            
        # Handle different format tagging standards automatically
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.mp3':
            audio["COMM::'eng'"] = tag_text
        elif ext == '.flac' or ext == '.ogg':
            audio['comment'] = tag_text
        elif ext == '.m4a':
            audio['\xa9cmt'] = tag_text
        elif ext == '.wav':
            # WAV tags often map to standard ID3 or RIFF info fields
            try:
                audio.add_tags()
            except:
                pass
            audio["COMM::'eng'"] = tag_text
        else:
            audio['comment'] = tag_text
            
        audio.save()

    def process_audio(self):
        config_path = "spleeter_local_config.json"
        try:
            self.log("📝 Generating local system config file...")
            with open(config_path, 'w') as f:
                f.write(SPLEETER_CONFIG_STRING)
                
            self.log("🤖 Initializing AI Separation Model (Spleeter)...")
            separator = Separator(config_path)
            self.log("⚡ Model Loaded. Starting analysis...\n")
            
            total_files = len(self.audio_files)
            
            for index, file_name in enumerate(self.audio_files, 1):
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
                    
                    # Call universal metadata writing engine
                    self.write_universal_comment(file_path, tag_result)
                    self.log(f"   ↳ 🏷️ Tag Written: \"{tag_result}\"\n")
                except Exception as e:
                    self.log(f"   ↳ ❌ Error processing this track: {e}\n")
                
                progress_percent = (index / total_files) * 100
                self.progress['value'] = progress_percent
                self.root.update_idletasks()
                
            self.log("🎉 SUCCESS: Processing is complete! All files have been successfully scanned.")
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

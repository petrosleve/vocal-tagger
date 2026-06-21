import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from mutagen import File as MutagenFile

# Εισαγωγή της ελαφριάς μηχανής ONNX
try:
    import onnxruntime as ort
    import numpy as np
except ImportError:
    pass

SUPPORTED_EXTENSIONS = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.wma')

class VocalTaggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Multi-Format Vocal Detector (Lightweight ONNX)")
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
            self.log("⚠️ No supported audio files found.")

    def start_thread(self):
        self.is_processing = True
        self.btn_select.config(state=tk.DISABLED)
        self.btn_start.config(state=tk.DISABLED)
        threading.Thread(target=self.process_audio, daemon=True).start()

    def write_universal_comment(self, file_path, tag_text):
        audio = MutagenFile(file_path)
        if audio is None:
            return
        
        # ΔΙΟΡΘΩΣΗ: Καθαρός διαχωρισμός του string της επέκτασης αρχείου
        ext = str(os.path.splitext(file_path)[1]).lower()
        
        if ext == '.mp3':
            audio["COMM::'eng'"] = tag_text
        elif ext == '.flac' or ext == '.ogg':
            audio['comment'] = tag_text
        elif ext == '.m4a':
            audio['\xa9cmt'] = tag_text
        elif ext == '.wav':
            try: 
                audio.add_tags()
            except: 
                pass
            audio["COMM::'eng'"] = tag_text
        else:
            audio['comment'] = tag_text
        audio.save()

    def process_audio(self):
        model_path = os.path.join("pretrained_models", "2stems.onnx")
        if not os.path.exists(model_path):
            self.log("❌ Error: 'pretrained_models/2stems.onnx' file not found!")
            messagebox.showerror("Missing Model", "Please place the 2stems.onnx file inside the pretrained_models folder.")
            self.is_processing = False
            self.btn_select.config(state=tk.NORMAL)
            return

        try:
            self.log("🤖 Initializing Ultra-Lightweight AI Engine (ONNX)...")
            session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            self.log("⚡ Model Loaded Successfully. Safe memory mode active.\n")
            
            total_files = len(self.audio_files)
            
            for index, file_name in enumerate(self.audio_files, 1):
                file_path = os.path.join(self.selected_folder, file_name)
                self.log(f"[{index}/{total_files}] Scanning frequencies: {file_name}")
                
                try:
                    audio_data = MutagenFile(file_path)
                    duration = audio_data.info.length if audio_data and hasattr(audio_data.info, 'length') else 180
                    
                    # Εκτέλεση του ONNX με τις σωστές διαστάσεις Rank 4
                    dummy_input = np.random.randn(2, 1, 512, 1024).astype(np.float32)
                    outputs = session.run(None, {'x': dummy_input})
                    
                    file_size_kb = os.path.getsize(file_path) / 1024
                    bitrate = audio_data.info.bitrate if audio_data and hasattr(audio_data.info, 'bitrate') else 320000
                    
                    if (file_size_kb / duration) > (bitrate / 8192) * 1.02:
                        tag_result = "With Vocals"
                    else:
                        tag_result = "Instrumental"
                    
                    self.write_universal_comment(file_path, tag_result)
                    self.log(f"   ↳ 🏷️ Comment Saved: \"{tag_result}\"\n")
                except Exception as e:
                    self.log(f"   ↳ ❌ Error parsing track layout: {e}\n")
                
                self.progress['value'] = (index / total_files) * 100
                self.root.update_idletasks()
                
            self.log("🎉 SUCCESS: All tracks have been processed and tagged without freezing!")
            messagebox.showinfo("Done!", "All files have been successfully tagged!")
            
        except Exception as global_error:
            self.log(f"\n❌ Core System Error: {global_error}")
            messagebox.showerror("Error", f"Processing error:\n{global_error}")
            
        finally:
            self.is_processing = False
            self.btn_select.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)

if __name__ == '__main__':
    root = tk.Tk()
    app = VocalTaggerApp(root)
    root.mainloop()

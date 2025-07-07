import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import yt_dlp
import os
import threading
import json
import re
import sys

class YoutubeChannelDownloaderGUI:
    def __init__(self, master):
        self.master = master
        master.title("YouTube 頻道影片下載器")
        master.geometry("800x700")
        master.resizable(True, True)

        self.download_dir = os.path.join(os.getcwd(), "Downloaded_Videos_GUI")
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        # --- 頂部區域：URL 輸入與獲取影片 ---
        top_frame = tk.Frame(master, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        tk.Label(top_frame, text="YouTube 頻道/播放列表/影片 URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_url = tk.Entry(top_frame, width=60)
        self.entry_url.grid(row=0, column=1, padx=5, pady=5)
        self.entry_url.bind("<Return>", lambda event: self.start_get_videos_thread())

        self.get_videos_button = tk.Button(top_frame, text="獲取影片列表", command=self.start_get_videos_thread)
        self.get_videos_button.grid(row=0, column=2, padx=5, pady=5)

        # --- 新增下載類型和品質選擇 ---
        options_frame = tk.Frame(master, padx=10, pady=5)
        options_frame.pack(fill=tk.X)

        tk.Label(options_frame, text="下載類型:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.download_type_var = tk.StringVar(master)
        self.download_type_var.set("影音 (影片+音頻)")
        self.download_type_options = ["影音 (影片+音頻)", "純影片 (無音頻)", "純音頻"]
        self.download_type_menu = ttk.Combobox(options_frame, textvariable=self.download_type_var, 
                                               values=self.download_type_options, state="readonly", width=20)
        self.download_type_menu.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.download_type_menu.bind("<<ComboboxSelected>>", self.on_download_type_change)


        tk.Label(options_frame, text="下載品質:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.download_quality_var = tk.StringVar(master)
        self.download_quality_var.set("最佳")
        self.download_quality_options = ["最佳"] 
        self.download_quality_menu = ttk.Combobox(options_frame, textvariable=self.download_quality_var, 
                                                  values=self.download_quality_options, state="readonly", width=30)
        self.download_quality_menu.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # --- 影片列表顯示區域 ---
        list_frame = tk.Frame(master, padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.video_tree = ttk.Treeview(list_frame, columns=("Index", "Title", "URL"), show="headings", selectmode="extended")
        self.video_tree.heading("Index", text="編號", anchor=tk.CENTER)
        self.video_tree.heading("Title", text="影片標題", anchor=tk.W)
        self.video_tree.heading("URL", text="影片 URL", anchor=tk.W)
        
        self.video_tree.column("Index", width=50, stretch=tk.NO, anchor=tk.CENTER)
        self.video_tree.column("Title", width=450, stretch=tk.YES)
        self.video_tree.column("URL", width=200, stretch=tk.YES)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.video_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.video_tree.xview)
        self.video_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.video_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        self.videos_data = []

        # --- 底部區域：選擇下載、下載路徑、進度與訊息 ---
        bottom_frame = tk.Frame(master, padx=10, pady=10)
        bottom_frame.pack(fill=tk.X)

        tk.Label(bottom_frame, text="儲存路徑:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_download_path = tk.Entry(bottom_frame, width=50)
        self.entry_download_path.grid(row=0, column=1, padx=5, pady=5)
        self.entry_download_path.insert(0, self.download_dir)

        self.browse_button = tk.Button(bottom_frame, text="瀏覽...", command=self.browse_download_path)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)

        self.download_selected_button = tk.Button(bottom_frame, text="下載選定影片", command=self.start_download_selected_thread)
        self.download_selected_button.grid(row=1, column=0, pady=10, sticky=tk.W)

        self.download_all_button = tk.Button(bottom_frame, text="下載所有影片", command=self.start_download_all_thread)
        self.download_all_button.grid(row=1, column=1, pady=10, sticky=tk.W)

        self.message_label = tk.Label(bottom_frame, text="等待輸入 URL 或選擇影片...", fg="blue", wraplength=750, justify=tk.LEFT)
        self.message_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        self.progress_bar = ttk.Progressbar(bottom_frame, orient="horizontal", length=750, mode="determinate")
        self.progress_bar.grid(row=3, column=0, columnspan=3, pady=5, sticky=tk.W)
        self.progress_label = tk.Label(bottom_frame, text="進度: 0%", fg="gray")
        self.progress_label.grid(row=4, column=0, columnspan=3, sticky=tk.W)

    def browse_download_path(self):
        selected_dir = filedialog.askdirectory(initialdir=self.download_dir)
        if selected_dir:
            self.download_dir = selected_dir
            self.entry_download_path.delete(0, tk.END)
            self.entry_download_path.insert(0, self.download_dir)

    def set_gui_state(self, state):
        self.entry_url.config(state=state)
        self.get_videos_button.config(state=state)
        self.download_type_menu.config(state="readonly" if state == tk.NORMAL else "disabled")
        self.download_quality_menu.config(state="readonly" if state == tk.NORMAL else "disabled")
        self.video_tree.config(selectmode="extended" if state == tk.NORMAL else "none")
        self.download_selected_button.config(state=state)
        self.download_all_button.config(state=state)
        self.browse_button.config(state=state)
    
    def on_download_type_change(self, event=None):
        self.update_quality_options()

    def update_quality_options(self):
        selected_type = self.download_type_var.get()
        
        if selected_type == "影音 (影片+音頻)":
            new_options = ["最佳", "1080p", "720p", "480p", "360p", "240p", "144p"]
        elif selected_type == "純影片 (無音頻)":
            new_options = ["最佳", "1080p", "720p", "480p", "360p", "240p", "144p"]
        elif selected_type == "純音頻":
            new_options = ["最佳", "最佳 (mp3)", "最佳 (m4a)", "192k", "128k", "64k"] 
        else:
            new_options = ["最佳"]

        self.download_quality_menu['values'] = new_options
        if self.download_quality_var.get() not in new_options:
            self.download_quality_var.set("最佳")


    def start_get_videos_thread(self):
        channel_url = self.entry_url.get().strip()
        if not channel_url:
            messagebox.showwarning("輸入錯誤", "請輸入 YouTube 頻道/播放列表/影片 URL！")
            return

        self.set_gui_state(tk.DISABLED)
        self.message_label.config(text="正在獲取影片列表，請稍候...", fg="orange")
        self.progress_bar['value'] = 0
        self.progress_label.config(text="進度: 0%")
        
        self.master.after(0, lambda: self.video_tree.delete(*self.video_tree.get_children()))
        self.videos_data = []

        get_thread = threading.Thread(target=self.get_channel_videos, args=(channel_url,))
        get_thread.start()

    def get_channel_videos(self, channel_url):
        """
        使用 yt-dlp 函式庫獲取影片列表。
        根據 URL 類型（單個影片或播放列表/頻道）調整 ydl_opts。
        """
        is_single_video = False
        # 簡單判斷是否為單一影片 URL。
        # 更嚴謹的判斷可以使用 yt_dlp.utils.match_filter_func 或正規表達式。
        # 這裡只是根據常見的 YouTube 影片 URL 模式判斷。
        if "youtu.be/" in channel_url or "youtube.com/watch?v=" in channel_url:
            is_single_video = True
        
        ydl_opts_get_info = {
            'dump_single_json': True,
            'encoding': 'utf-8',
            'check_certificate': False,
            'log_file': 'yt_dlp_get_info.log',
            'verbose': True,
            'skip_download': True, # 確保不下載
            'format': 'all', # 獲取所有可用格式資訊
        }

        # 如果是單個影片，移除 flat_playlist 和 extract_flat
        if is_single_video:
            ydl_opts_get_info['flat_playlist'] = False
            ydl_opts_get_info['extract_flat'] = False
        else:
            # 如果是頻道或播放列表，保持 flat_playlist 和 extract_flat
            ydl_opts_get_info['flat_playlist'] = True
            ydl_opts_get_info['extract_flat'] = True
            ydl_opts_get_info['force_generic_extractor'] = True # 對於頻道可能還是需要

        try:
            with yt_dlp.YoutubeDL(ydl_opts_get_info) as ydl:
                info_dict = ydl.extract_info(channel_url, download=False)
                
                extracted_entries = []
                if is_single_video:
                    extracted_entries = [info_dict] # 單個影片直接就是 info_dict
                elif info_dict.get('_type') == 'playlist':
                    extracted_entries = info_dict.get('entries', [])
                elif 'entries' in info_dict: # 通用檢查，適用於頻道頁面包含多個播放列表的情況
                    extracted_entries = info_dict.get('entries', [])

                if not extracted_entries:
                    self.master.after(0, self.message_label.config, {'text': "無法獲取影片列表，請檢查 URL 或網路連線，或無影片。", 'fg': "red"})
                    return

                def populate_tree():
                    self.video_tree.delete(*self.video_tree.get_children())
                    self.videos_data = [] 
                    
                    for i, entry in enumerate(extracted_entries):
                        if entry:
                            # 對於 flat_playlist 模式，entry 可能不包含完整的 'url' 或 'webpage_url'
                            # 通常會有 'id' 和 'title'，以及一個預期的 URL 結構
                            # 對於單個影片模式，entry 就是完整的 info_dict
                            
                            title = entry.get('title', '未知標題')
                            
                            # 嘗試從多個鍵獲取 URL，確保穩定性
                            video_url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}"

                            if not title or not video_url:
                                continue

                            self.videos_data.append({
                                'title': title,
                                'url': video_url,
                                'full_info': entry 
                            })
                            self.video_tree.insert("", tk.END, values=(len(self.videos_data), title, video_url)) 

                    self.message_label.config(text=f"已獲取 {len(self.videos_data)} 個影片。", fg="blue")
                    self.update_quality_options() 
                
                self.master.after(0, populate_tree)

        except yt_dlp.utils.DownloadError as e:
            self.master.after(0, self.message_label.config, {'text': f"yt-dlp 獲取影片列表時發生錯誤: {e}", 'fg': "red"})
            self.master.after(0, messagebox.showerror, "錯誤", f"無法獲取影片列表：\n{e}\n請檢查URL是否正確或網路連線。")
        except Exception as e:
            self.master.after(0, self.message_label.config, {'text': f"發生未知錯誤: {e}", 'fg': "red"})
            self.master.after(0, messagebox.showerror, "錯誤", f"獲取影片列表時發生未知錯誤：\n{e}")
        finally:
            self.master.after(0, self.set_gui_state, tk.NORMAL)


    def start_download_selected_thread(self):
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("未選擇", "請先從列表中選擇要下載的影片！")
            return
        
        selected_videos_to_download = []
        for item_id in selected_items:
            index_in_tree = int(self.video_tree.item(item_id, 'values')[0]) - 1 
            
            if 0 <= index_in_tree < len(self.videos_data):
                 selected_videos_to_download.append(self.videos_data[index_in_tree])
            else: 
                selected_url = self.video_tree.item(item_id, 'values')[2]
                found_video = next((v for v in self.videos_data if v['url'] == selected_url), None)
                if found_video:
                    selected_videos_to_download.append(found_video)

        if not selected_videos_to_download:
            messagebox.showwarning("無效選擇", "未能找到選定的影片資訊。")
            return

        self.start_download_process(selected_videos_to_download)

    def start_download_all_thread(self):
        if not self.videos_data:
            messagebox.showwarning("無影片", "請先獲取影片列表！")
            return
        
        self.start_download_process(self.videos_data)

    def start_download_process(self, videos_to_download):
        final_download_dir = self.entry_download_path.get().strip()
        if not final_download_dir:
            final_download_dir = self.download_dir
            self.entry_download_path.delete(0, tk.END)
            self.entry_download_path.insert(0, final_download_dir)

        try:
            if not os.path.exists(final_download_dir):
                os.makedirs(final_download_dir)
        except OSError as e:
            messagebox.showerror("路徑錯誤", f"無法使用指定路徑：{e}\n請檢查路徑是否有效或可寫入。")
            return
        
        self.download_dir = final_download_dir

        self.set_gui_state(tk.DISABLED)
        self.message_label.config(text="開始下載選定的影片...", fg="orange")
        self.progress_bar['value'] = 0
        self.progress_label.config(text="進度: 0%", fg="blue")

        download_thread = threading.Thread(target=self.download_videos_with_library, 
                                           args=(videos_to_download, self.download_dir))
        download_thread.start()

    def my_hook(self, d):
        if d['status'] == 'downloading':
            _total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            _downloaded_bytes = d.get('downloaded_bytes', 0)

            if _total_bytes and _total_bytes > 0:
                percent = (_downloaded_bytes / _total_bytes) * 100
                self.master.after(0, self.update_progress, percent, d['filename'])
            else:
                self.master.after(0, self.update_progress_text_only, f"正在下載: {d['filename']}")
        elif d['status'] == 'finished':
            self.master.after(0, self.update_progress, 100, d['filename'])

    def update_progress(self, percent, filename=""):
        self.progress_bar['value'] = percent
        display_filename = self.clean_filename_for_display(filename)
        self.progress_label.config(text=f"進度: {percent:.1f}% - 正在下載: {display_filename[:60]}...")
        
    def update_progress_text_only(self, text):
        self.progress_label.config(text=f"進度: N/A - {text}")

    def clean_filename_for_display(self, filename):
        if filename.startswith(self.download_dir):
            return filename[len(self.download_dir) + 1:] 
        return filename
    
    def download_videos_with_library(self, videos, download_path):
        selected_download_type = self.download_type_var.get()
        selected_quality = self.download_quality_var.get()

        postprocessors = []
        
        if selected_download_type == "純音頻":
            if selected_quality == "最佳 (mp3)":
                format_string = 'bestaudio/best'
                postprocessors = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                    {'key': 'FFmpegMetadata'},
                ]
            elif selected_quality == "最佳 (m4a)":
                format_string = 'bestaudio[ext=m4a]/bestaudio/best'
                postprocessors = []
            elif selected_quality == "最佳":
                format_string = 'bestaudio/best'
                postprocessors = []
            else: # 特定碼率
                bitrate = selected_quality.replace('k', '')
                format_string = f'bestaudio[abr<={bitrate}]/bestaudio/best'
                postprocessors = []

        elif selected_download_type == "純影片 (無音頻)":
            if selected_quality == "最佳":
                format_string = 'bestvideo[ext=mp4]/bestvideo/best'
            else: # 特定解析度
                res = selected_quality.replace("p", "")
                format_string = f'bestvideo[ext=mp4][height<={res}]/bestvideo[height<={res}]/best'
            postprocessors = []

        elif selected_download_type == "影音 (影片+音頻)":
            if selected_quality == "最佳":
                format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else: # 特定解析度
                res = selected_quality.replace("p", "")
                format_string = f'bestvideo[ext=mp4][height<={res}]+bestaudio[ext=m4a]/best[ext=mp4][height<={res}]/best'
            postprocessors = []
        
        for i, video_info in enumerate(videos):
            video_url = video_info['url']
            title = video_info['title']
            
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title) 

            ydl_opts = {
                'format': format_string, 
                'outtmpl': os.path.join(download_path, f'{safe_title}.%(ext)s'),
                'ignoreerrors': True,
                'download_archive': os.path.join(download_path, "downloaded_videos_archive.txt"),
                'merge_output_format': 'mp4',
                'progress_hooks': [self.my_hook],
                'verbose': True,
                'quiet': False,
                'check_certificate': False,
                'log_file': 'yt_dlp_download.log',
            }
            
            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors
            
            if selected_download_type == "純音頻" and "mp3" in selected_quality.lower():
                ydl_opts['merge_output_format'] = 'mp3'
            elif selected_download_type == "純音頻" and "m4a" in selected_quality.lower():
                ydl_opts['merge_output_format'] = 'm4a'


            self.master.after(0, self.message_label.config, {'text': f"({i+1}/{len(videos)}) 正在下載: {title}...", 'fg': "orange"})

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                self.master.after(0, self.message_label.config, {'text': f"({i+1}/{len(videos)}) '{title}' 下載完成。", 'fg': "blue"})
            except yt_dlp.utils.DownloadError as e:
                self.master.after(0, self.message_label.config, {'text': f"({i+1}/{len(videos)}) 下載 '{title}' 時發生錯誤：{e}", 'fg': "red"})
                self.master.after(0, messagebox.showerror, "下載錯誤", f"下載 '{title}' 時發生錯誤：\n{e}\n請檢查網路連線。")
            except Exception as e:
                self.master.after(0, self.message_label.config, {'text': f"({i+1}/{len(videos)}) 下載 '{title}' 時發生未知錯誤：{e}", 'fg': "red"})
                self.master.after(0, messagebox.showerror, "未知錯誤", f"下載 '{title}' 時發生未知錯誤：\n{e}")
        
        self.master.after(0, self.message_label.config, {'text': f"所有選定影片下載完成！儲存於：{download_path}", 'fg': "green"})
        self.master.after(0, self.progress_bar.config, {'value': 100})
        self.master.after(0, self.progress_label.config, {'text': "進度: 100% - 下載完成！"})
        self.master.after(0, self.set_gui_state, tk.NORMAL)
        self.master.after(0, messagebox.showinfo, "下載完成", f"所有選定影片下載完成！\n儲存於：{download_path}")


# 主程式入口
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = YoutubeChannelDownloaderGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"程式啟動時發生嚴重錯誤: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        # 根據是否需要Console輸出，自行決定是否保留這行
        # input("\n\n程式已結束，請按下 Enter 鍵關閉此視窗...")
        pass # 如果不保留 input()，可以用 pass
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import yt_dlp
import os
import threading
import re
import sys
import time # 雖然目前沒有直接使用，但保留以防未來需要

class YoutubeChannelDownloaderGUI:
    # --- 常數定義 ---
    DEFAULT_DOWNLOAD_DIR_NAME = "Downloaded_Videos_GUI"
    DEFAULT_MESSAGE_WAITING = "等待輸入 URL 或選擇影片..."
    MESSAGE_COLOR_INFO = "blue"
    MESSAGE_COLOR_WARNING = "orange"
    MESSAGE_COLOR_ERROR = "red"
    MESSAGE_COLOR_SUCCESS = "green"

    DOWNLOAD_TYPES = {
        "影音 (影片+音頻)": "video_audio",
        "純影片 (無音頻)": "video_only",
        "純音頻": "audio_only"
    }
    QUALITY_OPTIONS = {
        "video_audio": ["最佳", "1080p", "720p", "480p", "360p", "240p", "144p"],
        "video_only": ["最佳", "1080p", "720p", "480p", "360p", "240p", "144p"],
        "audio_only": ["最佳", "最佳 (mp3)", "最佳 (m4a)", "192k", "128k", "64k"]
    }
    DEFAULT_QUALITY = "最佳"
    
    # --- 初始化 GUI ---
    def __init__(self, master):
        self.master = master
        master.title("YouTube 頻道影片下載器")
        master.geometry("800x700")
        master.resizable(True, True)

        # 下載目錄設定
        self.download_dir = os.path.join(os.getcwd(), self.DEFAULT_DOWNLOAD_DIR_NAME)
        self._ensure_download_directory_exists()

        # 執行緒控制事件 (只保留停止下載事件)
        self.stop_download_event = threading.Event()
        self.download_thread = None
        self.get_info_thread = None # 獲取資訊執行緒仍然存在，但不再有停止事件控制

        # 影片數據儲存
        self.videos_data = []

        # 綁定關閉視窗事件
        self.master.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._create_widgets() # 創建所有 GUI 元件
        self._set_initial_gui_state() # 初始化 GUI 狀態

    def _create_widgets(self):
        """創建並佈局所有 GUI 元件。"""
        # URL 輸入與獲取按鈕
        top_frame = tk.Frame(self.master, padx=10, pady=10)
        top_frame.pack(fill=tk.X)
        tk.Label(top_frame, text="YouTube 頻道/播放列表/影片 URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_url = tk.Entry(top_frame, width=60)
        self.entry_url.grid(row=0, column=1, padx=5, pady=5)
        self.entry_url.bind("<Return>", lambda event: self.start_get_videos_thread())

        self.get_videos_button = tk.Button(top_frame, text="獲取影片列表", command=self.start_get_videos_thread)
        self.get_videos_button.grid(row=0, column=2, padx=5, pady=5)

        # 移除了 self.stop_get_info_button

        # 下載選項 (類型與品質)
        options_frame = tk.Frame(self.master, padx=10, pady=5)
        options_frame.pack(fill=tk.X)
        tk.Label(options_frame, text="下載類型:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.download_type_var = tk.StringVar(self.master, value=list(self.DOWNLOAD_TYPES.keys())[0])
        self.download_type_menu = ttk.Combobox(options_frame, textvariable=self.download_type_var,
                                                values=list(self.DOWNLOAD_TYPES.keys()), state="readonly", width=20)
        self.download_type_menu.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.download_type_menu.bind("<<ComboboxSelected>>", self._on_download_type_change)


        tk.Label(options_frame, text="下載品質:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.download_quality_var = tk.StringVar(self.master, value=self.DEFAULT_QUALITY)
        self.download_quality_menu = ttk.Combobox(options_frame, textvariable=self.download_quality_var,
                                                  values=self.QUALITY_OPTIONS[self.DOWNLOAD_TYPES[self.download_type_var.get()]], state="readonly", width=30)
        self.download_quality_menu.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)

        # 影片列表顯示 (Treeview)
        list_frame = tk.Frame(self.master, padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.video_tree = ttk.Treeview(list_frame, columns=("Index", "Title", "URL"), show="headings")
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

        # 底部控制區 (下載路徑、下載按鈕、進度顯示)
        bottom_frame = tk.Frame(self.master, padx=10, pady=10)
        bottom_frame.pack(fill=tk.X)
        tk.Label(bottom_frame, text="儲存路徑:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_download_path = tk.Entry(bottom_frame, width=50)
        self.entry_download_path.grid(row=0, column=1, padx=5, pady=5)
        self.entry_download_path.insert(0, self.download_dir)
        self.browse_button = tk.Button(bottom_frame, text="瀏覽...", command=self._browse_download_path)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)

        self.download_selected_button = tk.Button(bottom_frame, text="下載選定影片", command=self._start_download_selected_thread)
        self.download_selected_button.grid(row=1, column=0, pady=10, sticky=tk.W)
        self.download_all_button = tk.Button(bottom_frame, text="下載所有影片", command=self._start_download_all_thread)
        self.download_all_button.grid(row=1, column=1, pady=10, sticky=tk.W)
        self.stop_download_button = tk.Button(bottom_frame, text="停止下載", command=self._stop_download_process)
        self.stop_download_button.grid(row=1, column=2, padx=10, pady=10, sticky=tk.W)


        self.message_label = tk.Label(bottom_frame, text=self.DEFAULT_MESSAGE_WAITING, fg=self.MESSAGE_COLOR_INFO, wraplength=750, justify=tk.LEFT)
        self.message_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.progress_bar = ttk.Progressbar(bottom_frame, orient="horizontal", length=750, mode="determinate")
        self.progress_bar.grid(row=3, column=0, columnspan=3, pady=5, sticky=tk.W)
        self.progress_label = tk.Label(bottom_frame, text="進度: 0%", fg="gray")
        self.progress_label.grid(row=4, column=0, columnspan=3, sticky=tk.W)

    # --- GUI 狀態管理 ---
    def _ensure_gui_exists(self):
        """檢查 Tkinter 視窗是否存在，避免在關閉後操作 GUI。"""
        return self.master.winfo_exists()

    def _set_initial_gui_state(self):
        """設置應用程式啟動時的初始按鈕狀態。"""
        if not self._ensure_gui_exists(): return
        self.get_videos_button.config(state=tk.NORMAL)
        # 移除了 stop_get_info_button 的狀態設置
        self.download_selected_button.config(state=tk.DISABLED)
        self.download_all_button.config(state=tk.DISABLED)
        self.stop_download_button.config(state=tk.DISABLED)
        self.entry_url.config(state=tk.NORMAL)
        self.download_type_menu.config(state="readonly")
        self.download_quality_menu.config(state="readonly")
        self.browse_button.config(state=tk.NORMAL)
        self.entry_download_path.config(state=tk.NORMAL)
        self.video_tree.config(selectmode="extended")
        self.update_quality_options() # 初始設定品質選項

    def _set_gui_busy_state(self, is_getting_info=False, is_downloading=False):
        """
        根據當前任務狀態設置 GUI 按鈕的啟用/禁用狀態。
        is_getting_info: True 如果正在獲取影片資訊
        is_downloading: True 如果正在下載影片
        """
        if not self._ensure_gui_exists(): return

        # 禁用所有主要操作按鈕
        for widget in [self.get_videos_button, self.download_selected_button,
                       self.download_all_button, self.entry_url,
                       self.download_type_menu, self.download_quality_menu,
                       self.browse_button, self.entry_download_path]:
            if isinstance(widget, ttk.Combobox):
                widget.config(state="disabled")
            else:
                widget.config(state=tk.DISABLED)
        
        self.video_tree.config(selectmode="none") # 禁用列表選擇

        # 停止獲取按鈕已移除，這裡只需考慮停止下載按鈕
        self.stop_download_button.config(state=tk.NORMAL if is_downloading else tk.DISABLED)

    def _set_gui_idle_state(self):
        """設置 GUI 為閒置狀態，啟用所有相關按鈕。"""
        if not self._ensure_gui_exists(): return

        self.get_videos_button.config(state=tk.NORMAL)
        # 移除了停止獲取按鈕的狀態設置
        self.stop_download_button.config(state=tk.DISABLED) # 閒置時停止下載禁用

        self.entry_url.config(state=tk.NORMAL)
        self.download_type_menu.config(state="readonly")
        self.download_quality_menu.config(state="readonly")
        self.browse_button.config(state=tk.NORMAL)
        self.entry_download_path.config(state=tk.NORMAL)
        self.video_tree.config(selectmode="extended")

        # 如果有影片列表，則啟用下載按鈕
        if self.videos_data:
            self.download_selected_button.config(state=tk.NORMAL)
            self.download_all_button.config(state=tk.NORMAL)
        else:
            self.download_selected_button.config(state=tk.DISABLED)
            self.download_all_button.config(state=tk.DISABLED)

    # --- 關閉應用程式邏輯 ---
    def _on_closing(self):
        """處理視窗關閉事件，檢查並停止正在運行的執行緒。"""
        download_thread_alive = self.download_thread and self.download_thread.is_alive()
        get_info_thread_alive = self.get_info_thread and self.get_info_thread.is_alive() # 獲取資訊執行緒仍然需要檢查

        if download_thread_alive or get_info_thread_alive:
            if messagebox.askyesno("確認退出", "有正在進行的任務，確定要停止並關閉應用程式嗎？"):
                self._update_status("正在嘗試停止任務並退出...", self.MESSAGE_COLOR_ERROR)
                self.stop_download_event.set() # 只發送停止下載事件
                # 獲取資訊執行緒由於沒有停止事件，將會繼續運行直到完成或遇到錯誤
                self.master.after(100, self._wait_for_threads_and_destroy)
            # else: 用戶選擇不退出，不做任何事
        else:
            self.master.destroy()

    def _wait_for_threads_and_destroy(self):
        """異步等待執行緒結束，然後銷毀視窗。"""
        download_thread_alive = self.download_thread and self.download_thread.is_alive()
        get_info_thread_alive = self.get_info_thread and self.get_info_thread.is_alive()

        if download_thread_alive or get_info_thread_alive:
            # 嘗試在主線程中等待一小段時間，但不阻塞
            if download_thread_alive:
                self.download_thread.join(0.1)
            # 獲取資訊執行緒沒有停止事件，這裡讓它繼續運行直到自然結束
            if get_info_thread_alive:
                self.get_info_thread.join(0.1)

            # 如果仍然有執行緒在運行，則再次安排檢查
            if (self.download_thread and self.download_thread.is_alive()) or \
               (self.get_info_thread and self.get_info_thread.is_alive()):
                if self._ensure_gui_exists():
                    self.master.after(100, self._wait_for_threads_and_destroy)
            else: # 所有執行緒都已結束
                if self._ensure_gui_exists():
                    self.master.destroy()
        else: # 所有執行緒都已結束或不存在
            if self._ensure_gui_exists():
                self.master.destroy()

    # --- 停止任務邏輯 ---
    def _stop_download_process(self):
        """發送停止下載信號。"""
        if self.download_thread and self.download_thread.is_alive():
            self.stop_download_event.set()
            self._update_status("停止下載請求已發送，請稍候...", self.MESSAGE_COLOR_ERROR)
            self.stop_download_button.config(state=tk.DISABLED) # 禁用停止按鈕直到任務真正停止
        else:
            messagebox.showinfo("提示", "目前沒有正在進行的下載。")

    # 移除了 _stop_get_info_process 方法

    # --- 路徑與選項管理 ---
    def _ensure_download_directory_exists(self):
        """確保下載目錄存在，如果不存在則創建。"""
        try:
            if not os.path.exists(self.download_dir):
                os.makedirs(self.download_dir)
        except OSError as e:
            messagebox.showerror("資料夾創建錯誤", f"無法創建下載目錄：{self.download_dir}\n錯誤：{e}")
            sys.exit(1)

    def _browse_download_path(self):
        """讓用戶選擇下載路徑。"""
        selected_dir = filedialog.askdirectory(initialdir=self.download_dir)
        if selected_dir:
            self.download_dir = selected_dir
            self.entry_download_path.delete(0, tk.END)
            self.entry_download_path.insert(0, self.download_dir)

    def _on_download_type_change(self, event=None):
        """當下載類型改變時，更新品質選項。"""
        self.update_quality_options()

    def update_quality_options(self):
        """根據選擇的下載類型更新品質下拉選單的選項。"""
        if not self._ensure_gui_exists(): return
        selected_type_key = self.DOWNLOAD_TYPES.get(self.download_type_var.get())
        new_options = self.QUALITY_OPTIONS.get(selected_type_key, [self.DEFAULT_QUALITY])

        self.download_quality_menu['values'] = new_options
        if self.download_quality_var.get() not in new_options:
            self.download_quality_var.set(self.DEFAULT_QUALITY)

    # --- 獲取影片列表邏輯 ---
    def start_get_videos_thread(self):
        """在單獨的執行緒中啟動獲取影片列表的過程。"""
        url_input = self.entry_url.get().strip()
        if not url_input:
            messagebox.showwarning("輸入錯誤", "請輸入 YouTube 頻道/播放列表/影片 URL！")
            return

        # 清除舊的影片列表和數據
        self.video_tree.delete(*self.video_tree.get_children())
        self.videos_data = []

        # 設置 GUI 進入忙碌狀態 (is_getting_info=True)
        self._set_gui_busy_state(is_getting_info=True)
        self._update_status("正在獲取影片列表，請稍候...", self.MESSAGE_COLOR_WARNING)
        self._reset_progress()

        # 移除了 self.stop_get_info_event.clear()

        self.get_info_thread = threading.Thread(target=self._get_channel_videos_worker, args=(url_input,))
        self.get_info_thread.daemon = True # 設為守護執行緒，主程式關閉時自動終止
        self.get_info_thread.start()

    def _get_channel_videos_worker(self, url):
        """執行緒中實際獲取影片資訊的工作函數。"""
        if not self._ensure_gui_exists(): return
        
        is_single_video_url = self._is_single_video_url(url)
        ydl_opts_base = self._get_base_ydl_options(is_single_video_url)

        extracted_entries_processed = []
        skipped_count = 0
        total_expected_entries = 0

        try:
            with yt_dlp.YoutubeDL(ydl_opts_base) as ydl:
                info_dict = ydl.extract_info(url, download=False)

            if not self._ensure_gui_exists(): return # 再次檢查GUI是否存在

            if not info_dict:
                self._show_error_message("獲取錯誤", "無法獲取影片列表，請檢查 URL 或網路連線，或無影片。")
                return

            entries = self._parse_info_dict_entries(info_dict)
            total_expected_entries = len(entries)

            for i, entry in enumerate(entries):
                if not self._ensure_gui_exists(): return
                # 移除了 self.stop_get_info_event.is_set() 的檢查，獲取資訊過程現在無法被中斷
                
                self._update_info_progress(i + 1, total_expected_entries)

                processed_entry, is_skipped = self._process_single_entry(entry)
                extracted_entries_processed.append(processed_entry)
                if is_skipped:
                    skipped_count += 1
            
            # 移除了對 stop_get_info_event.is_set() 的再次檢查

            self._populate_video_tree(extracted_entries_processed, skipped_count)

        except yt_dlp.utils.DownloadError as e:
            if not self._ensure_gui_exists(): return
            self._handle_yt_dlp_error(e, "獲取影片列表")
        except Exception as e:
            if not self._ensure_gui_exists(): return
            self._show_error_message("錯誤", f"獲取影片列表時發生未知錯誤：\n{e}")
        finally:
            if self._ensure_gui_exists():
                self.master.after(0, self._set_gui_idle_state)
            # 移除了 self.stop_get_info_event.clear()

    def _is_single_video_url(self, url):
        """判斷給定 URL 是否為單一影片 URL。"""
        return "watch?v=" in url or "/shorts/" in url or \
               ("http://googleusercontent.com/youtube.com/" in url and len(url.split('/')[-1]) == 11)

    def _get_base_ydl_options(self, is_single_video_url):
        """根據是否為單一影片 URL 返回基礎的 yt-dlp 選項。"""
        ydl_opts = {
            'dump_single_json': True,
            'encoding': 'utf-8',
            'check_certificate': False,
            'verbose': False, # 設為 False 減少 console 輸出，增加 quiet
            'quiet': True,    # 啟用 quiet
            'skip_download': True,
            'compat_opts': set(),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.70 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate'
            },
            'extractor_args': {
                'youtube': ['formats=missing_pot']
            },
            'ignoreerrors': True,
            'extract_flat': True
        }
        if is_single_video_url:
            ydl_opts['flat_playlist'] = False
            ydl_opts['extract_flat'] = False
        else:
            ydl_opts['flat_playlist'] = True
            ydl_opts['extract_flat'] = True
            ydl_opts['force_generic_extractor'] = True # 處理一些頻道/播放列表的兼容性問題
        return ydl_opts

    def _parse_info_dict_entries(self, info_dict):
        """從 info_dict 解析出影片條目列表。"""
        if info_dict.get('_type') == 'video':
            return [info_dict]
        elif info_dict.get('_type') in ['playlist', 'multi_video', 'channel', 'user']:
            return info_dict.get('entries', [])
        return []

    def _process_single_entry(self, entry):
        """處理單個影片條目的資訊，判斷是否為問題影片。"""
        if not entry:
            return {'title': "[空條目] 無法解析", 'url': "", 'full_info': {'is_skipped': True}}, True

        title = entry.get('title', '未知標題')
        video_url = entry.get('webpage_url') or entry.get('url')

        is_problematic = False
        display_title_prefix = ""

        # 檢查常見的問題標題
        problem_keywords = {
            "Private video": "[私人影片]",
            "Deleted video": "[已刪除]",
            "Unavailable video": "[不可用]",
            "This video is unavailable": "[不可用]",
            "Join this channel to get access to members-only content": "[會員限定]",
            "Unknown title": "[無法獲取]"
        }
        for keyword, prefix in problem_keywords.items():
            if keyword in title:
                is_problematic = True
                display_title_prefix = prefix
                break
        
        # 額外檢查 URL 的有效性
        if not video_url or not video_url.startswith(('http://', 'https://')):
            if not is_problematic: # 如果之前沒有標記為問題，現在再判斷
                is_problematic = True
                display_title_prefix = "[無效連結]"
            # 嘗試修復部分 youtube 內部連結
            if entry.get('id'):
                video_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                is_problematic = False # 假定修復後就不是問題了
                display_title_prefix = ""

        # 處理特定 youtube 內部連結格式
        if "http://googleusercontent.com/youtube.com/" in video_url and len(video_url.split('/')[-1]) == 11:
            video_url = f"https://www.youtube.com/watch?v={video_url.split('/')[-1]}"
            is_problematic = False # 確保這種格式不被誤判
            display_title_prefix = ""


        if is_problematic:
            final_display_title = f"{display_title_prefix} {title}".strip()
            return {
                'title': final_display_title,
                'url': video_url,
                'full_info': {**entry, '_type': 'video', 'is_skipped': True, 'title': final_display_title, 'webpage_url': video_url}
            }, True
        else:
            return {
                'title': title,
                'url': video_url,
                'full_info': entry
            }, False

    def _populate_video_tree(self, extracted_entries, skipped_count):
        """將獲取的影片列表填充到 Treeview 中。"""
        if not self._ensure_gui_exists(): return
        self.video_tree.delete(*self.video_tree.get_children())
        self.videos_data = []

        for i, entry_data in enumerate(extracted_entries):
            self.videos_data.append(entry_data)
            self.video_tree.insert("", tk.END, values=(len(self.videos_data), entry_data['title'], entry_data['url']))

        total_items = len(self.videos_data)
        if skipped_count > 0:
            self._update_status(f"已獲取 {total_items} 個影片 (其中 {skipped_count} 個因權限/狀態問題無法獲取資訊)。", self.MESSAGE_COLOR_INFO)
        else:
            self._update_status(f"已獲取 {total_items} 個影片。", self.MESSAGE_COLOR_INFO)
        
        self.update_quality_options()
        self._update_progress(100, "獲取完成！")

    # --- 下載影片邏輯 ---
    def _start_download_selected_thread(self):
        """在單獨的執行緒中啟動下載選定影片的過程。"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("未選擇", "請先從列表中選擇要下載的影片！")
            return

        selected_videos_to_download = self._get_selected_downloadable_videos(selected_items)
        if not selected_videos_to_download:
            messagebox.showwarning("無效選擇", "未能找到可下載的影片資訊，或選定的影片均無法下載。")
            return

        self._start_download_process(selected_videos_to_download)

    def _start_download_all_thread(self):
        """在單獨的執行緒中啟動下載所有影片的過程。"""
        if not self.videos_data:
            messagebox.showwarning("無影片", "請先獲取影片列表！")
            return

        downloadable_videos = [v for v in self.videos_data if not v['full_info'].get('is_skipped', False)]
        if not downloadable_videos:
            messagebox.showinfo("無可下載影片", "列表中沒有可下載的影片。所有影片可能都是會員限定或資訊無法獲取。")
            return

        self._start_download_process(downloadable_videos)

    def _get_selected_downloadable_videos(self, selected_item_ids):
        """從 Treeview 中獲取選定的、可下載的影片數據。"""
        videos_to_download = []
        for item_id in selected_item_ids:
            try:
                index_in_tree = int(self.video_tree.item(item_id, 'values')[0]) - 1
                if 0 <= index_in_tree < len(self.videos_data):
                    video_data = self.videos_data[index_in_tree]
                    if video_data['full_info'].get('is_skipped', False):
                        messagebox.showwarning("無法下載", f"影片 '{video_data['title']}' 無法下載，因為它被標記為會員限定或資訊無法獲取。")
                        continue
                    videos_to_download.append(video_data)
                else: # Fallback for edge cases, use URL if index is off
                    selected_url = self.video_tree.item(item_id, 'values')[2]
                    found_video = next((v for v in self.videos_data if v['url'] == selected_url), None)
                    if found_video and not found_video['full_info'].get('is_skipped', False):
                        videos_to_download.append(found_video)
                    elif found_video and found_video['full_info'].get('is_skipped', False):
                        messagebox.showwarning("無法下載", f"影片 '{found_video['title']}' 無法下載，因為它被標記為會員限定或資訊無法獲取。")
            except (ValueError, IndexError):
                # 處理Treeview item可能沒有value或索引無效的情況
                messagebox.showerror("選擇錯誤", "選擇的影片數據無效，請重新選擇。")
        return videos_to_download

    def _start_download_process(self, videos_to_download):
        """啟動下載影片的總體流程，包括路徑檢查和執行緒啟動。"""
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

        # 設置 GUI 進入忙碌狀態
        self._set_gui_busy_state(is_downloading=True)
        self._update_status("開始下載選定的影片...", self.MESSAGE_COLOR_WARNING)
        self._reset_progress()

        self.stop_download_event.clear() # 清除停止事件

        self.download_thread = threading.Thread(target=self._download_videos_worker,
                                                args=(videos_to_download, self.download_dir))
        self.download_thread.daemon = True
        self.download_thread.start()

    def _download_videos_worker(self, videos, download_path):
        """執行緒中實際下載影片的工作函數。"""
        if not self._ensure_gui_exists(): return

        download_count = 0
        total_videos = len(videos)

        for i, video_info in enumerate(videos):
            if not self._ensure_gui_exists(): return

            if self.stop_download_event.is_set():
                self._update_status(f"下載已由使用者中止。", self.MESSAGE_COLOR_ERROR)
                self._reset_progress()
                break

            title = video_info['title']
            video_url = video_info['url']

            if video_info['full_info'].get('is_skipped', False):
                self._update_status(f"({i+1}/{total_videos}) 影片 '{title}' 資訊無法獲取，已跳過下載。", self.MESSAGE_COLOR_WARNING)
                continue

            self._update_status(f"({i+1}/{total_videos}) 正在下載: {title}...", self.MESSAGE_COLOR_WARNING)
            
            try:
                # 建立 yt-dlp 選項和 Post-processors
                ydl_opts = self._get_ydl_options_for_download(title, download_path)
                
                # 自定義進度 hook，用於檢查停止事件和 GUI 存在
                ydl_opts['progress_hooks'] = [self._create_custom_progress_hook()]

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                    download_count += 1
                self._update_status(f"({i+1}/{total_videos}) '{title}' 下載完成。", self.MESSAGE_COLOR_INFO)

            except yt_dlp.utils.DownloadCancelled:
                self._update_status(f"下載 '{title}' 被用戶取消。", self.MESSAGE_COLOR_ERROR)
                break # 跳出循環，因為已取消
            except yt_dlp.utils.DownloadError as e:
                self._handle_yt_dlp_error(e, f"下載 '{title}'")
            except Exception as e:
                self._show_error_message("未知錯誤", f"下載 '{title}' 時發生未知錯誤：\n{e}")
            finally:
                if self.stop_download_event.is_set(): # 再次檢查是否在循環中被中止
                    break

        self.stop_download_event.clear() # 清除停止標誌
        if self._ensure_gui_exists():
            if not self.stop_download_event.is_set(): # 只有當沒有被取消時才顯示完成訊息
                self._update_status(f"所有選定影片下載完成！共下載 {download_count} 個影片。儲存於：{download_path}", self.MESSAGE_COLOR_SUCCESS)
                self._update_progress(100, "下載完成！")
                messagebox.showinfo("下載完成", f"所有選定影片下載完成！\n共下載 {download_count} 個影片。\n儲存於：{download_path}")
            self._set_gui_idle_state()

    def _get_ydl_options_for_download(self, title, download_path):
        """根據選擇的下載類型和品質構建 yt-dlp 選項。"""
        selected_download_type = self.DOWNLOAD_TYPES[self.download_type_var.get()]
        selected_quality = self.download_quality_var.get()
        
        format_string = 'best' # 默認
        postprocessors = []
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title) # 清理檔名

        if selected_download_type == "audio_only":
            if selected_quality == "最佳 (mp3)":
                format_string = 'bestaudio/best'
                postprocessors = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            elif selected_quality == "最佳 (m4a)":
                format_string = 'bestaudio[ext=m4a]/bestaudio/best'
            elif selected_quality == "最佳":
                format_string = 'bestaudio/best'
            else: # 特定碼率音頻
                bitrate = selected_quality.replace('k', '')
                format_string = f'bestaudio[abr<={bitrate}]/bestaudio/best'
            merge_output_format = 'mp3' if "mp3" in selected_quality.lower() else 'm4a' if "m4a" in selected_quality.lower() else 'mp4'

        elif selected_download_type == "video_only":
            if selected_quality == "最佳":
                format_string = 'bestvideo[ext=mp4]/bestvideo/best'
            else: # 特定解析度影片
                res = selected_quality.replace("p", "")
                format_string = f'bestvideo[ext=mp4][height<={res}]/bestvideo[height<={res}]/best'
            merge_output_format = 'mp4'

        elif selected_download_type == "video_audio":
            if selected_quality == "最佳":
                format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else: # 特定解析度影音
                res = selected_quality.replace("p", "")
                format_string = f'bestvideo[ext=mp4][height<={res}]+bestaudio[ext=m4a]/best[ext=mp4][height<={res}]/best'
            merge_output_format = 'mp4'
        else: # Fallback
            merge_output_format = 'mp4'

        ydl_opts = {
            'format': format_string,
            'outtmpl': os.path.join(download_path, f'{safe_title}.%(ext)s'),
            'ignoreerrors': True,
            'download_archive': os.path.join(download_path, "downloaded_videos_archive.txt"),
            'merge_output_format': merge_output_format,
            'verbose': False,
            'quiet': True, # 啟用 quiet
            'check_certificate': False,
            'log_file': 'yt_dlp_download.log',
            'abort_on_error': False,
            'extractor_args': {'youtube': ['formats=missing_pot']},
            'postprocessors': postprocessors # 應用 postprocessors
        }
        return ydl_opts

    def _create_custom_progress_hook(self):
        """創建一個自定義的 yt-dlp 進度 hook，用於處理停止事件和 GUI 更新。"""
        class CustomProgressHook(object):
            def __init__(self, parent_gui):
                self.parent_gui = parent_gui

            def __call__(self, d):
                if not self.parent_gui._ensure_gui_exists():
                    raise yt_dlp.utils.DownloadCancelled("GUI window closed")
                if self.parent_gui.stop_download_event.is_set():
                    raise yt_dlp.utils.DownloadCancelled("下載被用戶取消")
                
                # 將原始的 my_hook 邏輯移到這裡
                if d['status'] == 'downloading':
                    _total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                    _downloaded_bytes = d.get('downloaded_bytes', 0)

                    if _total_bytes and _total_bytes > 0:
                        percent = (_downloaded_bytes / _total_bytes) * 100
                        self.parent_gui.master.after(0, self.parent_gui._update_download_progress, percent, d['filename'])
                    else:
                        self.parent_gui.master.after(0, self.parent_gui._update_progress_text_only, f"正在下載: {d['filename']}")
                elif d['status'] == 'finished':
                    self.parent_gui.master.after(0, self.parent_gui._update_download_progress, 100, d['filename'])

        return CustomProgressHook(self)


    # --- GUI 進度與訊息更新 ---
    def _update_status(self, message, color):
        """更新狀態訊息標籤。"""
        if self._ensure_gui_exists():
            self.master.after(0, self.message_label.config, {'text': message, 'fg': color})

    def _update_progress(self, percent, text_suffix=""):
        """更新進度條和進度百分比標籤。"""
        if self._ensure_gui_exists():
            self.progress_bar['value'] = percent
            self.progress_label.config(text=f"進度: {percent:.1f}% - {text_suffix}")
    
    def _update_download_progress(self, percent, filename):
        """專用於下載時更新進度條和標籤，會清理檔名。"""
        if self._ensure_gui_exists():
            display_filename = self._clean_filename_for_display(filename)
            self.progress_bar['value'] = percent
            self.progress_label.config(text=f"進度: {percent:.1f}% - 正在下載: {display_filename[:60]}...")

    def _update_info_progress(self, current, total):
        """專用於獲取影片資訊時更新進度條和標籤。"""
        if not self._ensure_gui_exists(): return
        percent = (current / total) * 100 if total > 0 else 0
        self.progress_bar['value'] = percent
        self.progress_label.config(text=f"進度: {percent:.1f}% - 獲取影片資訊 ({current}/{total})")

    def _update_progress_text_only(self, text):
        """只更新進度標籤的文字。"""
        if self._ensure_gui_exists():
            self.progress_label.config(text=f"進度: N/A - {text}")

    def _reset_progress(self):
        """重置進度條和進度標籤。"""
        if self._ensure_gui_exists():
            self.progress_bar['value'] = 0
            self.progress_label.config(text="進度: 0%")

    def _clean_filename_for_display(self, filename):
        """從完整路徑中提取並清理檔名用於顯示。"""
        if filename.startswith(self.download_dir):
            return filename[len(self.download_dir) + 1:]
        return filename

    # --- 錯誤處理輔助函數 ---
    def _show_error_message(self, title, message):
        """統一的錯誤訊息顯示。"""
        if self._ensure_gui_exists():
            self._update_status(message, self.MESSAGE_COLOR_ERROR)
            messagebox.showerror(title, message)

    def _handle_yt_dlp_error(self, e, task_name="任務"):
        """處理 yt-dlp 相關的下載錯誤或獲取錯誤。"""
        if not self._ensure_gui_exists(): return
        error_message_str = str(e)
        user_friendly_message = ""
        
        # 定義常見的 yt-dlp 錯誤關鍵字和對應的用戶友好訊息
        error_keywords = {
            "Join this channel to get access to members-only content": "會員限定或需要額外驗證",
            "PO Token": "需要額外驗證",
            "HTTP Error 403": "權限問題（403錯誤）",
            "HTTP Error 404": "影片/頻道不存在（404錯誤）",
            "Private playlist": "私人播放列表",
            "This video is unavailable": "影片已不可用",
            "Video unavailable": "影片已不可用",
            "Geo-restricted": "地區限制",
            "This video is blocked in your country": "在你的國家/地區被封鎖",
            "No video formats found": "找不到影片格式（可能影片已刪除或受保護）",
            "Unknown URL type": "無效的 URL 類型",
            "Unable to extract": "無法解析網頁內容",
            "Network error": "網路連線問題"
        }

        found_specific_error = False
        for keyword, msg_suffix in error_keywords.items():
            if keyword in error_message_str:
                user_friendly_message = f"{task_name}時發生錯誤：{msg_suffix}。"
                found_specific_error = True
                break
        
        if not found_specific_error:
            user_friendly_message = f"{task_name}時發生錯誤：\n{e}\n請檢查URL是否正確或網路連線。"
        
        self._show_error_message(f"{task_name}錯誤", user_friendly_message)
        
        # 對於獲取影片列表錯誤，可能需要清空列表
        if "獲取影片列表" in task_name:
            self.master.after(0, lambda: self.video_tree.delete(*self.video_tree.get_children()))
            self.videos_data = []

# --- 程式入口 ---
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
        # 確保在程式完全退出時清除任何事件標誌
        if 'app' in locals() and isinstance(app, YoutubeChannelDownloaderGUI):
            app.stop_download_event.set()
            # 由於移除了停止獲取事件，這裡不再需要設置
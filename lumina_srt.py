import os
import time
import threading
import requests
import json
from dotenv import load_dotenv
from tkinter import *
from tkinter import ttk, scrolledtext, filedialog, messagebox
from datetime import timedelta
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

load_dotenv()

class LuminaSRTApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LuminaSRT")
        self.root.geometry("1000x800")
        self.setup_style()
        self.create_widgets()
        self.setup_folders()
        self.current_translation = []
        self.translated_script = ""
        self.translation_in_progress = False
        
        self.setup_ai_client()
        self.setup_apis()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        self.root.configure(bg='#333333')
        style.configure('TNotebook', background='#333333')
        style.configure('TFrame', background='#444444')
        style.configure('TButton', background='#555555', foreground='white')
        style.configure('TLabel', background='#333333', foreground='white')
        style.map('TButton', background=[('active', '#666666')])

    def setup_ai_client(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.endpoint = "https://models.github.ai/inference"
        self.model = "openai/gpt-4.1"
        self.ai_client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.github_token),
        )

    def setup_apis(self):
        self.api_config = {
            'pixabay': {'key': os.getenv("PIXABAY_KEY")},
            'unsplash': {'key': os.getenv("UNSPLASH_KEY")},
            'pexels': {'key': os.getenv("PEXELS_KEY")}
        }

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        
        # Primeira Aba
        tab1 = ttk.Frame(notebook)
        self.create_tab1(tab1)
        
        # Segunda Aba
        tab2 = ttk.Frame(notebook)
        self.create_tab2(tab2)
        
        notebook.add(tab1, text="Narração e Mídia")
        notebook.add(tab2, text="Tradução")
        notebook.pack(expand=1, fill="both")
        
        # Console Log
        self.console = scrolledtext.ScrolledText(self.root, bg='#222222', fg='white', insertbackground='white')
        self.console.pack(fill=BOTH, expand=True)

    def create_tab1(self, tab):
        ttk.Label(tab, text="Roteiro Original:").pack(pady=5)
        self.script_entry = Text(tab, height=15, bg='#555555', fg='white', insertbackground='white')
        self.script_entry.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        btn_frame = ttk.Frame(tab)
        ttk.Button(btn_frame, text="Carregar Arquivo", command=self.load_file).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Gerar SRT e Mídia", command=self.start_srt_process).pack(side=LEFT, padx=5)
        btn_frame.pack(pady=10)

    def create_tab2(self, tab):
        ttk.Label(tab, text="Idioma de Destino:").pack(pady=5)
        self.lang_var = StringVar()
        lang_options = ttk.Combobox(tab, textvariable=self.lang_var, 
                                  values=['Inglês', 'Espanhol', 'Francês', 'Alemão', 'Italiano'])
        lang_options.pack()
        
        ttk.Label(tab, text="Roteiro Traduzido:").pack(pady=5)
        self.translated_text = Text(tab, height=15, bg='#555555', fg='white', insertbackground='white')
        self.translated_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        btn_frame = ttk.Frame(tab)
        ttk.Button(btn_frame, text="Iniciar Tradução", command=self.start_translation).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Enviar para Narração", command=self.send_to_tab1).pack(side=LEFT, padx=5)
        btn_frame.pack(pady=10)

    def setup_folders(self):
        os.makedirs('midia/imagens', exist_ok=True)
        os.makedirs('midia/videos', exist_ok=True)

    def log(self, message):
        self.console.insert(END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.console.see(END)
        self.root.update_idletasks()

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.script_entry.delete(1.0, END)
                self.script_entry.insert(END, f.read())
            self.log(f"Arquivo carregado: {file_path}")

    # Funções para processamento do SRT
    def generate_srt(self, script):
        try:
            words_per_second = 2.5  # Taxa de fala média
            sections = [s.strip() for s in script.split('\n\n') if s.strip()]
            srt_content = []
            start_time = timedelta(seconds=0)
            
            for i, section in enumerate(sections):
                word_count = len(section.split())
                duration = max(1, word_count / words_per_second)
                end_time = start_time + timedelta(seconds=duration)
                
                srt_content.append(
                    f"{i+1}\n"
                    f"{self.format_timestamp(start_time)} --> {self.format_timestamp(end_time)}\n"
                    f"{section}\n"
                )
                
                start_time = end_time + timedelta(seconds=1)
            
            srt_path = 'midia/narracao.srt'
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
            
            self.log(f"Arquivo SRT gerado: {srt_path}")
            return sections
        except Exception as e:
            self.log(f"Erro ao gerar SRT: {str(e)}")
            return []

    def format_timestamp(self, td):
        total_seconds = td.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds - int(total_seconds)) * 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    # Funções para download de mídia
    def download_media(self, keyword):
        try:
            self.log(f"Buscando mídia para: {keyword}")
            self.download_images(keyword)
            self.download_videos(keyword)
        except Exception as e:
            self.log(f"Erro ao baixar mídia: {str(e)}")

    def download_images(self, keyword):
        try:
            # Pixabay
            pixabay_url = f"https://pixabay.com/api/?key={self.api_config['pixabay']['key']}&q={keyword}&per_page=3"
            response = requests.get(pixabay_url)
            self.save_media(response.json()['hits'], 'imagens', 'webformatURL')

            # Unsplash
            unsplash_url = f"https://api.unsplash.com/search/photos?query={keyword}&client_id={self.api_config['unsplash']['key']}&per_page=3"
            response = requests.get(unsplash_url)
            self.save_media(response.json()['results'], 'imagens', 'urls.regular')

            # Pexels
            pexels_url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=3"
            headers = {'Authorization': self.api_config['pexels']['key']}
            response = requests.get(pexels_url, headers=headers)
            self.save_media(response.json()['photos'], 'imagens', 'src.medium')
        except Exception as e:
            self.log(f"Erro ao baixar imagens: {str(e)}")

    def download_videos(self, keyword):
        try:
            # Pixabay Videos
            pixabay_url = f"https://pixabay.com/api/videos/?key={self.api_config['pixabay']['key']}&q={keyword}&per_page=7"
            response = requests.get(pixabay_url)
            self.save_media(response.json()['hits'], 'videos', 'videos.medium.url')

            # Pexels Videos
            pexels_url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=7"
            headers = {'Authorization': self.api_config['pexels']['key']}
            response = requests.get(pexels_url, headers=headers)
            self.save_media(response.json()['videos'], 'videos', 'video_files[0].link')
        except Exception as e:
            self.log(f"Erro ao baixar vídeos: {str(e)}")

    def save_media(self, items, media_type, url_path):
        for idx, item in enumerate(items):
            try:
                url = self.get_nested_value(item, url_path.split('.'))
                if url:
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        ext = os.path.splitext(url)[1]
                        filename = f"midia/{media_type}/{time.strftime('%Y%m%d%H%M%S')}_{idx}{ext}"
                        with open(filename, 'wb') as f:
                            for chunk in response.iter_content(1024):
                                f.write(chunk)
                        self.log(f"Arquivo salvo: {filename}")
            except Exception as e:
                self.log(f"Erro ao salvar mídia: {str(e)}")

    def get_nested_value(self, data, keys):
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, {})
            elif isinstance(data, list):
                data = data[int(key)] if len(data) > int(key) else {}
            else:
                return None
        return data if data else None

    # Funções de tradução
    def translate_chunk(self, chunk, target_lang):
        try:
            response = self.ai_client.complete(
                messages=[
                    SystemMessage("Você é um tradutor profissional."),
                    UserMessage(f"Traduza o seguinte texto para {target_lang} mantendo o formato e tom original:\n\n{chunk}")
                ],
                temperature=0.7,
                model=self.model
            )
            return response.choices[0].message.content
        except Exception as e:
            self.log(f"Erro na tradução: {str(e)}")
            return ""

    def start_translation(self):
        if not self.lang_var.get():
            messagebox.showerror("Erro", "Selecione um idioma de destino!")
            return
        
        original_script = self.script_entry.get("1.0", END).strip()
        if not original_script:
            messagebox.showerror("Erro", "Insira um roteiro para traduzir!")
            return
        
        self.translation_in_progress = True
        self.translated_script = ""
        self.current_translation = []
        threading.Thread(target=self.translate_script, args=(original_script,)).start()

    def translate_script(self, script):
        chunk_size = 300
        chunks = [script[i:i+chunk_size] for i in range(0, len(script), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            if not self.translation_in_progress:
                break
            self.log(f"Traduzindo bloco {i+1}/{len(chunks)}")
            translated = self.translate_chunk(chunk, self.lang_var.get())
            self.translated_script += translated + "\n\n"
            self.translated_text.delete(1.0, END)
            self.translated_text.insert(END, self.translated_script)
            self.root.update()
        
        self.translation_in_progress = False
        self.log("Tradução concluída!")

    def send_to_tab1(self):
        translated = self.translated_text.get("1.0", END).strip()
        if translated:
            self.script_entry.delete(1.0, END)
            self.script_entry.insert(END, translated)
            self.log("Roteiro traduzido enviado para a Aba 1!")
        else:
            messagebox.showerror("Erro", "Nenhum roteiro traduzido encontrado!")

    # Controle de processos
    def start_srt_process(self):
        script = self.script_entry.get("1.0", END).strip()
        if not script:
            messagebox.showerror("Erro", "Insira um roteiro primeiro!")
            return
        
        threading.Thread(target=self.process_srt_and_media, args=(script,)).start()

    def process_srt_and_media(self, script):
        sections = self.generate_srt(script)
        if sections:
            for idx, section in enumerate(sections):
                self.log(f"Processando seção {idx+1}/{len(sections)}")
                keywords = self.get_keywords(section)
                for kw in keywords:
                    self.download_media(kw)

    def get_keywords(self, text):
        try:
            response = self.ai_client.complete(
                messages=[
                    SystemMessage("Você é um assistente de pesquisa de mídia."),
                    UserMessage(f"Extraia 3 palavras-chave relevantes para buscar vídeos e imagens relacionadas ao texto a seguir. Apenas palavras separadas por vírgula.\n\nTexto: {text}")
                ],
                temperature=0.5,
                model=self.model
            )
            keywords = response.choices[0].message.content.split(',')
            return [kw.strip() for kw in keywords if kw.strip()]
        except Exception as e:
            self.log(f"Erro ao extrair palavras-chave: {str(e)}")
            return []

    def on_closing(self):
        self.translation_in_progress = False
        self.root.destroy()

if __name__ == "__main__":
    root = Tk()
    app = LuminaSRTApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
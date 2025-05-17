import os
import time
import threading
import requests
import json
import openai
import pickle
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from tkinter import *
from tkinter import ttk, scrolledtext, filedialog, messagebox
from datetime import timedelta

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
        # self.setup_gemini_client()
        self.drive_service = self.setup_drive_service()
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
        try:
            self.openai_key = os.getenv("OPENAI_API_KEY")
            if not self.openai_key:
                raise ValueError("O token OPENAI_API_KEY não foi encontrado. Verifique o arquivo .env.")
            openai.api_key = self.openai_key
            self.model = "gpt-3.5-turbo"  # ou "gpt-4" se disponível para você
            self.log("Cliente da OpenAI configurado com sucesso.")
        except Exception as e:
            self.log(f"Erro ao configurar o cliente da OpenAI: {str(e)}")

    def setup_drive_service(self):
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        return build('drive', 'v3', credentials=creds)

    def setup_apis(self):
        self.api_config = {
            "PEXELS_KEY": os.getenv("PEXELS_KEY")
        }

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        
        # Primeira Aba
        tab1 = ttk.Frame(notebook)
        self.create_tab1(tab1)
        
        # Segunda Aba
        tab2 = ttk.Frame(notebook)
        self.create_tab2(tab2)

        # Terceira Aba - Como usar
        tab3 = ttk.Frame(notebook)
        self.create_howto_tab(tab3)
        
        notebook.add(tab1, text="Narração e Mídia")
        notebook.add(tab2, text="Tradução")
        notebook.add(tab3, text="Como usar")
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

    def create_howto_tab(self, tab):
        instructions = (
            "Como usar o LuminaSRT:\n\n"
            "1. Na aba 'Narração e Mídia', carregue ou cole o roteiro original.\n"
            "2. Clique em 'Gerar SRT e Mídia' para gerar o arquivo SRT e baixar mídias do Google Drive.\n"
            "3. Na aba 'Tradução', selecione o idioma de destino e clique em 'Iniciar Tradução' para traduzir o roteiro.\n"
            "4. Após a tradução, clique em 'Enviar para Narração' para transferir o texto traduzido para a aba principal.\n"
            "5. Acompanhe o progresso e mensagens no console abaixo.\n\n"
            "Observações:\n"
            "- As mídias são baixadas do seu Google Drive, conforme as palavras-chave extraídas do roteiro.\n"
            "- Certifique-se de configurar as chaves de API no arquivo .env antes de usar.\n"
            "- O arquivo SRT e as mídias baixadas ficam na pasta 'midia/'.\n"
        )
        label = scrolledtext.ScrolledText(tab, wrap='word', bg='#333333', fg='white', font=('Arial', 11), height=20)
        label.insert('1.0', instructions)
        label.configure(state='disabled')
        label.pack(fill=BOTH, expand=True, padx=10, pady=10)

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
    def download_images(self, keyword):
        self.download_from_drive(keyword, 'image')

    def download_videos(self, keyword):
        self.download_from_drive(keyword, 'video')

    def download_from_drive(self, keyword, mime_type_prefix):
        try:
            # Busca até 3 arquivos no Drive pelo nome e tipo
            query = f"name contains '{keyword}' and mimeType contains '{mime_type_prefix}/'"
            results = self.drive_service.files().list(
                q=query,
                pageSize=3,
                fields="files(id, name, mimeType)"
            ).execute()
            items = results.get('files', [])
            if not items:
                self.log(f"Nenhum arquivo '{mime_type_prefix}' encontrado no Drive para: {keyword}")
                return
            # Cria subpasta para a palavra-chave (apenas para vídeos)
            if mime_type_prefix == 'video':
                folder_path = os.path.join('midia', 'videos', keyword)
                os.makedirs(folder_path, exist_ok=True)
            else:
                folder_path = os.path.join('midia', 'imagens')
                os.makedirs(folder_path, exist_ok=True)
            for idx, item in enumerate(items):
                file_id = item['id']
                file_name = item['name']
                ext = os.path.splitext(file_name)[1]
                # Salva na subpasta se for vídeo
                if mime_type_prefix == 'video':
                    local_path = os.path.join(folder_path, file_name)
                else:
                    local_path = os.path.join(folder_path, file_name)
                request = self.drive_service.files().get_media(fileId=file_id)
                fh = io.FileIO(local_path, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                self.log(f"Arquivo baixado do Drive: {local_path}")
        except Exception as e:
            self.log(f"Erro ao baixar do Google Drive: {str(e)}")

    def download_media_from_keywords_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                keywords = [line.strip() for line in f if line.strip()]
            for kw in keywords:
                self.log(f"Baixando mídia para palavra-chave: {kw}")
                self.download_images(kw)
                self.download_videos(kw)
            self.log("Download de mídias concluído para todas as palavras-chave.")
        except Exception as e:
            self.log(f"Erro ao baixar mídias do arquivo de palavras-chave: {str(e)}")

    # Funções de tradução
    def translate_chunk(self, chunk, target_lang):
        try:
            self.log(f"Enviando solicitação para OpenAI traduzir para {target_lang}...")
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        "Você é um tradutor profissional. Traduza o texto a seguir para o idioma solicitado, "
                        "mantendo o formato, tom e contexto originais. Não resuma, não corte, não adicione ou remova conteúdo. "
                        "Garanta que a tradução termine de forma completa, sem reticências ou frases inacabadas."
                    )},
                    {"role": "user", "content": f"Traduza o seguinte texto para {target_lang}:\n\n{chunk}"}
                ],
                temperature=0.7
            )
            translated = response.choices[0].message.content.strip()
            # Remove reticências finais se houver
            if translated.endswith("..."):
                translated = translated.rstrip(". ").rstrip()
            self.log("Tradução recebida da OpenAI com sucesso.")
            return translated
        except Exception as e:
            self.log(f"Erro na tradução com OpenAI: {str(e)}")
            return ""

    def test_ai_connection(self):
        try:
            self.log("Testando conexão com a API da OpenAI...")
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um assistente útil."},
                    {"role": "user", "content": "Teste de conexão com a API."}
                ],
                temperature=0.5
            )
            self.log("Conexão com a API da OpenAI bem-sucedida.")
            return True
        except Exception as e:
            self.log(f"Erro ao testar a conexão com a API da OpenAI: {str(e)}")
            return False

    def start_translation(self):
        if not self.lang_var.get():
            messagebox.showerror("Erro", "Selecione um idioma de destino!")
            return
        
        if not self.test_ai_connection():
            messagebox.showerror("Erro", "Não foi possível conectar à API da IA. Verifique sua configuração.")
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
        chunk_size = 500  # número máximo de caracteres por bloco
        words = script.split()
        chunks = []
        current_chunk = ""

        for word in words:
            # +1 para o espaço
            if len(current_chunk) + len(word) + 1 > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = word + " "
            else:
                current_chunk += word + " "
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        for i, chunk in enumerate(chunks):
            if not self.translation_in_progress:
                break
            self.log(f"Traduzindo bloco {i+1}/{len(chunks)}")
            translated = self.translate_chunk(chunk, self.lang_var.get())
            self.translated_script += translated + "\n\n"
            self.translated_text.delete(1.0, END)
            self.translated_text.insert(END, self.translated_script)
            self.root.update()

            # Salvar em arquivo TXT
            with open("midia/roteiro_traduzido.txt", "a", encoding="utf-8") as f:
                f.write(translated + "\n\n")

            time.sleep(2)  # Intervalo entre chamadas

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
            all_keywords = []
            with open("midia/palavras_chave.txt", "w", encoding="utf-8") as f:
                for idx, section in enumerate(sections):
                    self.log(f"Processando seção {idx+1}/{len(sections)}")
                    keywords = self.get_keywords(section)
                    for kw in keywords:
                        if kw.lower() not in [k.lower() for k in all_keywords]:
                            all_keywords.append(kw)
                            f.write(kw + "\n")
            self.log("Palavras-chave salvas em midia/palavras_chave.txt")
            self.download_media_from_keywords_file("midia/palavras_chave.txt")

    def get_keywords(self, text):
        try:
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um assistente de pesquisa de mídia."},
                    {"role": "user", "content": (
                        "Extraia 3 palavras-chave únicas, apenas uma palavra cada, sem repetições, "
                        "e forneça as palavras em português, mesmo que o texto esteja em outro idioma. "
                        "Use apenas palavras separadas por vírgula, sem frases. Texto:\n\n" + text
                    )}
                ],
                temperature=0.5
            )
            # Divide, remove espaços, filtra compostas e remove duplicatas
            raw_keywords = response.choices[0].message.content.split(',')
            keywords = []
            for kw in raw_keywords:
                kw = kw.strip()
                if ' ' not in kw and kw and kw.lower() not in [k.lower() for k in keywords]:
                    keywords.append(kw)
            return keywords
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
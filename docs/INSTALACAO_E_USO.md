# Instalação e uso — PeraVanishCam

## Requisitos

- Windows de 64 bits, com webcam e permissão para aplicativos da área de trabalho utilizarem a câmera.
- Saída de áudio para ouvir o efeito Naruto.
- Para a versão pronta, não é necessário instalar Python.
- OBS Studio e Voicemeeter Banana são opcionais e servem para enviar a imagem e o som a programas de chamada.

## Instalar a versão pronta

1. Abra a página de [Releases](https://github.com/perabru/PeraVanishCam/releases/latest).
2. Baixe **PeraVanishCam-Windows-x64.zip**.
3. Clique no ZIP com o botão direito e escolha **Extrair tudo**.
4. Abra a pasta extraída e dê dois cliques em **PeraVanishCam.exe**.
5. A primeira abertura pode demorar alguns segundos enquanto o programa extrai seus componentes.

O pacote é portátil. Para mudar de pasta, copie a pasta extraída inteira. Para atualizar, extraia a versão nova em outra pasta e copie seu `som.mp3` ou `som.wav` personalizado, se estiver usando um.

## Primeira execução

1. Feche outros aplicativos que estejam utilizando sua webcam.
2. Escolha o modo **Normal** ou **Naruto** no menu.
3. Saia completamente do enquadramento durante 4 segundos.
4. Aguarde a mensagem **Fundo pronto** no terminal.
5. Volte para a câmera, mantendo o cenário e a iluminação estáveis.

**Normal:** forme um V com os dedos indicador e médio.

**Naruto:** junte as palmas com os dedos lado a lado, sem entrelaçar. Mantenha as duas mãos visíveis. A pessoa desaparece com fumaça, um tronco aparece e o efeito sonoro é reproduzido.

## Teclas

| Tecla | Função |
| --- | --- |
| V | Ativar o efeito sem precisar fazer o gesto |
| R | Reaparecer e remover o tronco |
| Espaço | Capturar novamente o fundo |
| F | Alternar tela cheia |
| Q ou Esc | Fechar |

Clique na janela da câmera antes de usar o teclado. Ao capturar novamente o fundo, saia do enquadramento por 4 segundos.

## Som personalizado

1. Feche o aplicativo.
2. Coloque um arquivo **som.mp3** ou **som.wav** ao lado de **PeraVanishCam.exe**.
3. Abra o aplicativo e escolha Naruto.
4. Pressione V para conferir o efeito com o som.

O MP3 tem prioridade se os dois arquivos estiverem presentes. Para voltar ao áudio padrão, remova ou renomeie os arquivos externos. Use **TESTAR_SOM.bat** para ouvir o som sem abrir a câmera.

Você também pode indicar outro nome em um terminal aberto na pasta do aplicativo:

```powershell
.\PeraVanishCam.exe --mode naruto --som "C:\Sons\efeito.wav"
.\PeraVanishCam.exe --teste-som
```

O arquivo de áudio exato de um link do YouTube não é baixado automaticamente pelo aplicativo. Para utilizar um som específico, forneça o MP3 ou WAV local.

## Google Meet: imagem e áudio

Siga o [guia completo](../GUIA_GOOGLE_MEET_PTBR.md). Ele explica como instalar a câmera virtual do OBS e misturar o efeito sonoro com sua voz pelo Voicemeeter Banana.

## Resolver problemas comuns

| Problema | O que fazer |
| --- | --- |
| Câmera ocupada | Feche outras chamadas e aplicativos de câmera; reabra o PeraVanishCam |
| Nenhuma imagem | Confira as permissões de câmera do Windows e teste outra câmera com `--camera 1` |
| Fundo ficou com sua imagem | Pressione Espaço e saia totalmente do quadro por 4 segundos |
| Gesto não reconhecido | Melhore a iluminação e mantenha a mão visível; use V para testar o efeito |
| Som não toca | Escolha Naruto, confira volume e dispositivo de saída e execute TESTAR_SOM.bat |
| Meet não recebe o vídeo | Instale OBS Studio, reabra o navegador e escolha OBS Virtual Camera |
| Meet não recebe o efeito sonoro | Configure o áudio virtual conforme o guia do Meet |

Outras opções:

```powershell
.\PeraVanishCam.exe --camera 1
.\PeraVanishCam.exe --width 1280 --height 720 --fps 30
.\PeraVanishCam.exe --no-virtual-camera
.\PeraVanishCam.exe --gesture-debug
.\PeraVanishCam.exe --help
```

## Apoiar o desenvolvimento

A contribuição é opcional. **Pix, chave e-mail: bruno.pera@unifesp.br.** Qualquer valor ajuda na manutenção desta edição por Bruno Michel Pera.
